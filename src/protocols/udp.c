#include "udp.h"
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

// Endpoint pool, keyed by (host, port, conn_id). Slots are appended, never
// moved, so a udp_endpoint_t* obtained under the lock stays valid — letting us
// release the pool mutex before blocking I/O.
#define MAX_UDP_ENDPOINTS 1024
static udp_endpoint_t udp_endpoints[MAX_UDP_ENDPOINTS];
static int udp_endpoint_count = 0;
static pthread_mutex_t udp_pool_mutex = PTHREAD_MUTEX_INITIALIZER;
static int udp_pool_warned = 0;

static const char* effective_conn_id(const char* conn_id) {
    return (conn_id && conn_id[0]) ? conn_id : "default";
}

int udp_parse_url(const char* url, char* host, int* port) {
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
        *port = 53;
    }

    return 0;
}

/* Find a slot for (host, port, conn_id). Caller MUST hold udp_pool_mutex. */
static udp_endpoint_t* udp_find_locked(const char* host, int port, const char* conn_id) {
    for (int i = 0; i < udp_endpoint_count; i++) {
        if (POOL_SLOT_MATCHES(udp_endpoints[i], host, port, conn_id, conn_id)) {
            return &udp_endpoints[i];
        }
    }
    return NULL;
}

/* Find or reserve a slot. Caller MUST hold udp_pool_mutex. NULL if pool full. */
static udp_endpoint_t* udp_find_or_reserve_locked(const char* host, int port, const char* conn_id) {
    udp_endpoint_t* ep = udp_find_locked(host, port, conn_id);
    if (ep) return ep;

    if (pool_reserve_full(udp_endpoint_count, MAX_UDP_ENDPOINTS,
                          &udp_pool_warned, "UDP", "MAX_UDP_ENDPOINTS")) {
        return NULL;
    }

    ep = &udp_endpoints[udp_endpoint_count++];
    memset(ep, 0, sizeof(udp_endpoint_t));
    strncpy(ep->host, host, sizeof(ep->host) - 1);
    strncpy(ep->conn_id, conn_id, sizeof(ep->conn_id) - 1);
    ep->port = port;
    ep->socket_fd = -1;
    ep->is_bound = false;
    return ep;
}

int udp_create_endpoint(const char* host, int port, const char* conn_id, response_t* response) {
    /* port 0 is valid for a local endpoint (OS picks an ephemeral port). */
    if (!host || port < 0 || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();

    pthread_mutex_lock(&udp_pool_mutex);
    udp_endpoint_t* ep = udp_find_or_reserve_locked(host, port, conn_id);
    if (!ep) {
        pthread_mutex_unlock(&udp_pool_mutex);
        response->success = false; response->status_code = 500;
        strcpy(response->error_message, "Too many UDP endpoints");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    if (ep->is_bound) {
        pthread_mutex_unlock(&udp_pool_mutex);
        response->success = true; response->status_code = 200;
        snprintf(response->body, sizeof(response->body),
                "UDP endpoint already created for %s:%d", host, port);
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }
    pthread_mutex_unlock(&udp_pool_mutex);

    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) {
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to create UDP socket: %s", strerror(errno));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    int opt = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        close(fd);
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to set socket options: %s", strerror(errno));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    pthread_mutex_lock(&udp_pool_mutex);
    ep->socket_fd = fd;
    ep->is_bound = true;
    pthread_mutex_unlock(&udp_pool_mutex);

    response->success = true; response->status_code = 200;
    snprintf(response->body, sizeof(response->body),
            "UDP endpoint created for %s:%d", host, port);
    response->protocol_data.udp.bytes_sent = 0;
    response->protocol_data.udp.bytes_received = 0;
    strncpy(response->protocol_data.udp.sender_address, host,
            sizeof(response->protocol_data.udp.sender_address) - 1);
    response->protocol_data.udp.sender_port = port;
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

int udp_send(const char* host, int port, const char* conn_id, const char* data, size_t data_len, response_t* response) {
    if (!host || port <= 0 || !data || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();

    /* Find or reserve + lazily create the socket, all under the lock except the
       blocking sendto below. */
    pthread_mutex_lock(&udp_pool_mutex);
    udp_endpoint_t* ep = udp_find_or_reserve_locked(host, port, conn_id);
    if (!ep) {
        pthread_mutex_unlock(&udp_pool_mutex);
        response->success = false; response->status_code = 500;
        strcpy(response->error_message, "Too many UDP endpoints");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    if (!ep->is_bound || ep->socket_fd < 0) {
        int fd = socket(AF_INET, SOCK_DGRAM, 0);
        if (fd < 0) {
            pthread_mutex_unlock(&udp_pool_mutex);
            response->success = false; response->status_code = 400;
            strcpy(response->error_message, "Failed to create UDP endpoint");
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        ep->socket_fd = fd;
        ep->is_bound = true;
    }
    int fd = ep->socket_fd;
    pthread_mutex_unlock(&udp_pool_mutex);

    char port_str[16];
    snprintf(port_str, sizeof(port_str), "%d", port);
    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_DGRAM;
    int gai_err = getaddrinfo(host, port_str, &hints, &res);
    if (gai_err != 0) {
        snprintf(response->error_message, sizeof(response->error_message),
                "DNS resolution failed for %s: %s", host, gai_strerror(gai_err));
        response->success = false; response->status_code = 404;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    ssize_t bytes_sent = sendto(fd, data, data_len, 0, res->ai_addr, res->ai_addrlen);
    freeaddrinfo(res);

    if (bytes_sent < 0) {
        snprintf(response->error_message, sizeof(response->error_message),
                "UDP send failed: %s", strerror(errno));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    response->success = true; response->status_code = 200;
    snprintf(response->body, sizeof(response->body),
            "Sent %zd bytes to %s:%d via UDP", bytes_sent, host, port);
    response->protocol_data.udp.bytes_sent = bytes_sent;
    strncpy(response->protocol_data.udp.sender_address, host,
            sizeof(response->protocol_data.udp.sender_address) - 1);
    response->protocol_data.udp.sender_port = port;
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

int udp_receive(const char* host, int port, const char* conn_id, response_t* response) {
    /* port 0 is valid: receive on the OS-assigned ephemeral port. */
    if (!host || port < 0 || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();

    pthread_mutex_lock(&udp_pool_mutex);
    udp_endpoint_t* ep = udp_find_locked(host, port, conn_id);
    int fd = (ep && ep->is_bound) ? ep->socket_fd : -1;
    bool needs_bind = (fd >= 0) && !ep->local_bound;
    pthread_mutex_unlock(&udp_pool_mutex);

    if (fd < 0) {
        response->success = false; response->status_code = 400;
        strcpy(response->error_message, "No UDP endpoint available");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    // Bind to the local port for receiving — only once per endpoint. Repeated
    // binds on the same socket are rejected by the OS anyway; track it so we
    // don't issue a failing bind() on every receive.
    if (needs_bind) {
        struct sockaddr_in local_addr;
        memset(&local_addr, 0, sizeof(local_addr));
        local_addr.sin_family = AF_INET;
        local_addr.sin_addr.s_addr = INADDR_ANY;
        local_addr.sin_port = htons(port);
        if (bind(fd, (struct sockaddr*)&local_addr, sizeof(local_addr)) == 0) {
            pthread_mutex_lock(&udp_pool_mutex);
            if (ep->socket_fd == fd) ep->local_bound = true;
            pthread_mutex_unlock(&udp_pool_mutex);
        }
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
        response->success = true; response->status_code = 204;
        strcpy(response->body, "No UDP data available");
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }

    char buffer[MAX_BODY_LENGTH];
    struct sockaddr_in sender_addr;
    socklen_t sender_len = sizeof(sender_addr);
    ssize_t bytes_received = recvfrom(fd, buffer, sizeof(buffer) - 1, 0,
                                     (struct sockaddr*)&sender_addr, &sender_len);
    fcntl(fd, F_SETFL, flags);

    if (bytes_received < 0) {
        snprintf(response->error_message, sizeof(response->error_message),
                "UDP receive failed: %s", strerror(errno));
        response->success = false; response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    char sender_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &sender_addr.sin_addr, sender_ip, INET_ADDRSTRLEN);
    int sender_port = ntohs(sender_addr.sin_port);

    /* Store the actual datagram payload in body for the caller. */
    size_t copy_len = (size_t)bytes_received;
    if (copy_len >= sizeof(response->body)) copy_len = sizeof(response->body) - 1;
    memcpy(response->body, buffer, copy_len);
    response->body[copy_len] = '\0';

    response->success = true; response->status_code = 200;
    response->protocol_data.udp.bytes_received = bytes_received;
    strncpy(response->protocol_data.udp.sender_address, sender_ip,
            sizeof(response->protocol_data.udp.sender_address) - 1);
    response->protocol_data.udp.sender_port = sender_port;
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

int udp_close_endpoint(const char* host, int port, const char* conn_id, response_t* response) {
    if (!host || port < 0 || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();

    pthread_mutex_lock(&udp_pool_mutex);
    udp_endpoint_t* ep = udp_find_locked(host, port, conn_id);
    int fd = -1;
    if (ep && ep->is_bound) {
        fd = ep->socket_fd;
        ep->socket_fd = -1;
        ep->is_bound = false;
        ep->local_bound = false;
    }
    pthread_mutex_unlock(&udp_pool_mutex);

    if (fd < 0) {
        response->success = false; response->status_code = 400;
        strcpy(response->error_message, "No UDP endpoint to close");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    close(fd);

    response->success = true; response->status_code = 200;
    snprintf(response->body, sizeof(response->body),
            "UDP endpoint for %s:%d closed successfully", host, port);
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

void udp_cleanup_all(void) {
    pthread_mutex_lock(&udp_pool_mutex);
    for (int i = 0; i < udp_endpoint_count; i++) {
        if (udp_endpoints[i].socket_fd >= 0) {
            close(udp_endpoints[i].socket_fd);
            udp_endpoints[i].socket_fd = -1;
        }
        udp_endpoints[i].is_bound = false;
    }
    udp_endpoint_count = 0;
    pthread_mutex_unlock(&udp_pool_mutex);
}
