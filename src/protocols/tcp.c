#include "tcp.h"
#include "../common.h"
#include "pool_common.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>

// Connection pool for TCP connections. Slots are keyed by (host, port, conn_id)
// so each virtual user gets its own socket. Slots are appended, never moved, so
// a tcp_connection_t* obtained under the lock stays valid for the process
// lifetime — which lets us release the pool mutex before doing blocking I/O.
#define MAX_TCP_CONNECTIONS 1024
static tcp_connection_t tcp_connections[MAX_TCP_CONNECTIONS];
static int tcp_connection_count = 0;
static pthread_mutex_t tcp_pool_mutex = PTHREAD_MUTEX_INITIALIZER;
static int tcp_pool_warned = 0;

static const char* effective_conn_id(const char* conn_id) {
    return (conn_id && conn_id[0]) ? conn_id : "default";
}

/* Probe whether a pooled stream socket is still usable. The pools are
   process-global statics, so when the OS recycles an ephemeral port a later
   connect can match a stale slot whose fd points at a now-closed socket and
   wrongly report "already established". A non-blocking MSG_PEEK distinguishes
   the three cases without consuming data:
     >0  -> data buffered, clearly alive
      0  -> peer performed an orderly shutdown (dead)
     <0  -> EAGAIN/EWOULDBLOCK means alive-but-idle; anything else is dead. */
static bool tcp_fd_is_alive(int fd) {
    if (fd < 0) return false;
    char probe;
    ssize_t n = recv(fd, &probe, 1, MSG_PEEK | MSG_DONTWAIT);
    if (n > 0) return true;
    if (n == 0) return false;
    return (errno == EAGAIN || errno == EWOULDBLOCK);
}

int tcp_parse_url(const char* url, char* host, int* port) {
    if (!url || !host || !port) {
        return -1;
    }

    *host = '\0';
    *port = 0;

    const char* protocol_end = strstr(url, "://");
    if (!protocol_end) {
        return -1;
    }

    const char* url_part = protocol_end + 3;

    const char* colon = strchr(url_part, ':');
    if (colon) {
        size_t host_len = colon - url_part;
        if (host_len >= 256) host_len = 255;
        strncpy(host, url_part, host_len);
        host[host_len] = '\0';
        *port = atoi(colon + 1);
    } else {
        strncpy(host, url_part, 255);
        host[255] = '\0';
        *port = 80;
    }

    return 0;
}

/* Find a pool slot for (host, port, conn_id). Caller MUST hold tcp_pool_mutex. */
static tcp_connection_t* tcp_find_locked(const char* host, int port, const char* conn_id) {
    for (int i = 0; i < tcp_connection_count; i++) {
        if (POOL_SLOT_MATCHES(tcp_connections[i], host, port, conn_id, conn_id)) {
            return &tcp_connections[i];
        }
    }
    return NULL;
}

/* Find or reserve a slot. Caller MUST hold tcp_pool_mutex. Returns NULL if the
   pool is full. A reserved slot starts disconnected with socket_fd = -1. */
static tcp_connection_t* tcp_find_or_reserve_locked(const char* host, int port, const char* conn_id) {
    tcp_connection_t* conn = tcp_find_locked(host, port, conn_id);
    if (conn) return conn;

    if (pool_reserve_full(tcp_connection_count, MAX_TCP_CONNECTIONS,
                          &tcp_pool_warned, "TCP", "MAX_TCP_CONNECTIONS")) {
        return NULL;
    }

    conn = &tcp_connections[tcp_connection_count++];
    memset(conn, 0, sizeof(tcp_connection_t));
    strncpy(conn->host, host, sizeof(conn->host) - 1);
    strncpy(conn->conn_id, conn_id, sizeof(conn->conn_id) - 1);
    conn->port = port;
    conn->socket_fd = -1;
    conn->is_connected = false;
    return conn;
}

int tcp_connect(const char* host, int port, const char* conn_id, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();

    /* --- Critical section 1: find/reserve the slot --- */
    pthread_mutex_lock(&tcp_pool_mutex);
    tcp_connection_t* conn = tcp_find_or_reserve_locked(host, port, conn_id);
    if (!conn) {
        pthread_mutex_unlock(&tcp_pool_mutex);
        response->success = false;
        response->status_code = 500;
        strcpy(response->error_message, "Too many TCP connections");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    if (conn->is_connected) {
        if (tcp_fd_is_alive(conn->socket_fd)) {
            pthread_mutex_unlock(&tcp_pool_mutex);
            response->success = true;
            response->status_code = 200;
            snprintf(response->body, sizeof(response->body),
                    "TCP connection already established to %s:%d", host, port);
            response->response_time_us = get_time_us() - start_time;
            return 0;
        }
        /* Stale slot: drop the dead fd and fall through to reconnect. The slot
           stays reserved (conn pointer remains valid) and is republished with a
           fresh socket in critical section 2 below. */
        if (conn->socket_fd >= 0) close(conn->socket_fd);
        conn->socket_fd = -1;
        conn->is_connected = false;
    }
    pthread_mutex_unlock(&tcp_pool_mutex);

    /* --- Blocking work happens WITHOUT the pool mutex held --- */
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to create socket: %s", strerror(errno));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    char port_str[16];
    snprintf(port_str, sizeof(port_str), "%d", port);
    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    int gai_err = getaddrinfo(host, port_str, &hints, &res);
    if (gai_err != 0) {
        close(fd);
        snprintf(response->error_message, sizeof(response->error_message),
                "DNS resolution failed for %s: %s", host, gai_strerror(gai_err));
        response->success = false; response->status_code = 404;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    int flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags | O_NONBLOCK);

    int connect_result = connect(fd, res->ai_addr, res->ai_addrlen);
    if (connect_result < 0 && errno != EINPROGRESS) {
        freeaddrinfo(res);
        close(fd);
        snprintf(response->error_message, sizeof(response->error_message),
                "Connection failed: %s", strerror(errno));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    fd_set write_fds;
    struct timeval timeout = {5, 0}; // 5 second timeout
    FD_ZERO(&write_fds);
    FD_SET(fd, &write_fds);
    int select_result = select(fd + 1, NULL, &write_fds, NULL, &timeout);
    if (select_result <= 0) {
        freeaddrinfo(res);
        close(fd);
        strcpy(response->error_message, "Connection timeout");
        response->success = false; response->status_code = 408;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    int socket_error;
    socklen_t len = sizeof(socket_error);
    if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &socket_error, &len) < 0 || socket_error != 0) {
        freeaddrinfo(res);
        close(fd);
        snprintf(response->error_message, sizeof(response->error_message),
                "Connection failed: %s", strerror(socket_error));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    fcntl(fd, F_SETFL, flags); // back to blocking
    freeaddrinfo(res);

    /* --- Critical section 2: publish the live socket into the slot --- */
    pthread_mutex_lock(&tcp_pool_mutex);
    conn->socket_fd = fd;
    conn->is_connected = true;
    pthread_mutex_unlock(&tcp_pool_mutex);

    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body),
            "TCP connection established to %s:%d", host, port);
    response->protocol_data.tcp.bytes_sent = 0;
    response->protocol_data.tcp.bytes_received = 0;
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

int tcp_send(const char* host, int port, const char* conn_id, const char* data, size_t data_len, response_t* response) {
    if (!host || port <= 0 || !data || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();

    pthread_mutex_lock(&tcp_pool_mutex);
    tcp_connection_t* conn = tcp_find_locked(host, port, conn_id);
    int fd = (conn && conn->is_connected) ? conn->socket_fd : -1;
    pthread_mutex_unlock(&tcp_pool_mutex);

    if (fd < 0) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active TCP connection");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    /* Blocking send loop runs without the pool mutex. data_len is carried from
       the caller so binary payloads with embedded NULs are sent in full. */
    size_t total_sent = 0;
    while (total_sent < data_len) {
        ssize_t bytes_sent = send(fd, data + total_sent, data_len - total_sent, 0);
        if (bytes_sent < 0) {
            pthread_mutex_lock(&tcp_pool_mutex);
            if (conn->socket_fd == fd) conn->is_connected = false;
            pthread_mutex_unlock(&tcp_pool_mutex);
            snprintf(response->error_message, sizeof(response->error_message),
                    "Send failed after %zu bytes: %s", total_sent, strerror(errno));
            response->success = false; response->status_code = 500;
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        total_sent += (size_t)bytes_sent;
    }

    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body),
            "Sent %zu bytes to %s:%d", total_sent, host, port);
    response->protocol_data.tcp.bytes_sent = total_sent;
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

int tcp_receive(const char* host, int port, const char* conn_id, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();

    pthread_mutex_lock(&tcp_pool_mutex);
    tcp_connection_t* conn = tcp_find_locked(host, port, conn_id);
    int fd = (conn && conn->is_connected) ? conn->socket_fd : -1;
    pthread_mutex_unlock(&tcp_pool_mutex);

    if (fd < 0) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active TCP connection");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    int flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags | O_NONBLOCK);

    fd_set read_fds;
    struct timeval timeout = {5, 0}; // 5 second timeout per CONTEXT.md
    FD_ZERO(&read_fds);
    FD_SET(fd, &read_fds);
    int select_result = select(fd + 1, &read_fds, NULL, NULL, &timeout);

    if (select_result <= 0) {
        fcntl(fd, F_SETFL, flags);
        response->success = true;
        response->status_code = 204;
        strcpy(response->body, "No data available");
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }

    char buffer[MAX_BODY_LENGTH];
    ssize_t bytes_received = recv(fd, buffer, sizeof(buffer) - 1, 0);
    fcntl(fd, F_SETFL, flags);

    if (bytes_received < 0) {
        snprintf(response->error_message, sizeof(response->error_message),
                "Receive failed: %s", strerror(errno));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    if (bytes_received == 0) {
        // Peer closed — tear down the slot's socket under the lock.
        pthread_mutex_lock(&tcp_pool_mutex);
        if (conn->socket_fd == fd) {
            close(fd);
            conn->socket_fd = -1;
            conn->is_connected = false;
        }
        pthread_mutex_unlock(&tcp_pool_mutex);
        response->success = false;
        response->status_code = 410;
        strcpy(response->error_message, "Connection closed by peer");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    /* Store the actual payload in body so callers can read it back. */
    size_t copy_len = (size_t)bytes_received;
    if (copy_len >= sizeof(response->body)) copy_len = sizeof(response->body) - 1;
    memcpy(response->body, buffer, copy_len);
    response->body[copy_len] = '\0';

    response->success = true;
    response->status_code = 200;
    response->protocol_data.tcp.bytes_received = bytes_received;
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

int tcp_disconnect(const char* host, int port, const char* conn_id, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();

    pthread_mutex_lock(&tcp_pool_mutex);
    tcp_connection_t* conn = tcp_find_locked(host, port, conn_id);
    int fd = -1;
    if (conn && conn->is_connected) {
        fd = conn->socket_fd;
        conn->socket_fd = -1;
        conn->is_connected = false;
    }
    pthread_mutex_unlock(&tcp_pool_mutex);

    if (fd < 0) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active TCP connection to disconnect");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    // The fd is already detached from the slot; close it without the lock.
    if (shutdown(fd, SHUT_RDWR) < 0) {
        /* already closed / not connected — ignore */
    }
    if (close(fd) < 0) {
        static int disconnect_warn = 0;
        if (!disconnect_warn) {
            fprintf(stderr, "[LoadSpiker] TCP close() failed: %s\n", strerror(errno));
            disconnect_warn = 1;
        }
    }

    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body),
            "TCP connection to %s:%d closed successfully", host, port);
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

void tcp_cleanup_all(void) {
    pthread_mutex_lock(&tcp_pool_mutex);
    for (int i = 0; i < tcp_connection_count; i++) {
        if (tcp_connections[i].socket_fd >= 0) {
            close(tcp_connections[i].socket_fd);
            tcp_connections[i].socket_fd = -1;
        }
        tcp_connections[i].is_connected = false;
    }
    tcp_connection_count = 0;
    pthread_mutex_unlock(&tcp_pool_mutex);
}
