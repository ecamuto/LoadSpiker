#include "tcp.h"
#include "../common.h"
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

// Connection pool for TCP connections
#define MAX_TCP_CONNECTIONS 100
static tcp_connection_t tcp_connections[MAX_TCP_CONNECTIONS];
static int tcp_connection_count = 0;


int tcp_parse_url(const char* url, char* host, int* port) {
    if (!url || !host || !port) {
        return -1;
    }
    
    // Initialize output parameters
    *host = '\0';
    *port = 0;
    
    // Parse tcp://host:port format
    const char* protocol_end = strstr(url, "://");
    if (!protocol_end) {
        return -1;
    }
    
    const char* url_part = protocol_end + 3;
    
    // Extract host and port
    const char* colon = strchr(url_part, ':');
    if (colon) {
        // Host with port
        size_t host_len = colon - url_part;
        if (host_len >= 256) host_len = 255;
        strncpy(host, url_part, host_len);
        host[host_len] = '\0';
        
        // Extract port
        *port = atoi(colon + 1);
    } else {
        // Host without port (use default)
        strncpy(host, url_part, 255);
        host[255] = '\0';
        *port = 80; // Default port
    }
    
    return 0;
}

tcp_connection_t* tcp_find_connection(const char* host, int port) {
    for (int i = 0; i < tcp_connection_count; i++) {
        if (strcmp(tcp_connections[i].host, host) == 0 && tcp_connections[i].port == port) {
            return &tcp_connections[i];
        }
    }
    return NULL;
}

tcp_connection_t* tcp_create_connection(const char* host, int port) {
    if (tcp_connection_count >= MAX_TCP_CONNECTIONS) {
        return NULL;
    }
    
    tcp_connection_t* conn = &tcp_connections[tcp_connection_count++];
    memset(conn, 0, sizeof(tcp_connection_t));
    
    strncpy(conn->host, host, sizeof(conn->host) - 1);
    conn->port = port;
    conn->socket_fd = -1;
    conn->is_connected = false;
    
    return conn;
}

int tcp_connect(const char* host, int port, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();
    
    // Check if connection already exists
    tcp_connection_t* conn = tcp_find_connection(host, port);
    if (conn && conn->is_connected) {
        response->success = true;
        response->status_code = 200;
        snprintf(response->body, sizeof(response->body), "TCP connection already established to %s:%d", host, port);
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }
    
    // Create new connection if needed
    if (!conn) {
        conn = tcp_create_connection(host, port);
        if (!conn) {
            response->success = false;
            response->status_code = 500;
            strcpy(response->error_message, "Too many TCP connections");
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
    }
    
    // Create socket
    conn->socket_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (conn->socket_fd < 0) {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Failed to create socket: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Resolve hostname
    struct hostent* server = gethostbyname(host);
    if (!server) {
        close(conn->socket_fd);
        conn->socket_fd = -1;
        response->success = false;
        response->status_code = 404;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Host not found: %s", host);
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Set up server address
    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    memcpy(&server_addr.sin_addr.s_addr, server->h_addr, server->h_length);
    server_addr.sin_port = htons(port);
    
    // Set socket to non-blocking for timeout control
    int flags = fcntl(conn->socket_fd, F_GETFL, 0);
    fcntl(conn->socket_fd, F_SETFL, flags | O_NONBLOCK);
    
    // Attempt connection
    int connect_result = connect(conn->socket_fd, (struct sockaddr*)&server_addr, sizeof(server_addr));
    
    if (connect_result < 0 && errno != EINPROGRESS) {
        close(conn->socket_fd);
        conn->socket_fd = -1;
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Connection failed: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Wait for connection to complete (with timeout)
    fd_set write_fds;
    struct timeval timeout;
    FD_ZERO(&write_fds);
    FD_SET(conn->socket_fd, &write_fds);
    timeout.tv_sec = 5;  // 5 second timeout
    timeout.tv_usec = 0;
    
    int select_result = select(conn->socket_fd + 1, NULL, &write_fds, NULL, &timeout);
    
    if (select_result <= 0) {
        close(conn->socket_fd);
        conn->socket_fd = -1;
        response->success = false;
        response->status_code = 408;
        strcpy(response->error_message, "Connection timeout");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Check if connection was successful
    int socket_error;
    socklen_t len = sizeof(socket_error);
    if (getsockopt(conn->socket_fd, SOL_SOCKET, SO_ERROR, &socket_error, &len) < 0 || socket_error != 0) {
        close(conn->socket_fd);
        conn->socket_fd = -1;
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Connection failed: %s", strerror(socket_error));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Set socket back to blocking mode
    fcntl(conn->socket_fd, F_SETFL, flags);
    
    // Connection successful
    conn->is_connected = true;
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "TCP connection established to %s:%d", host, port);
    
    // Set TCP-specific response data
    tcp_data_t* tcp_data = (tcp_data_t*)response->protocol_data.protocol_data;
    tcp_data->connection_established = true;
    tcp_data->connection_time_us = get_time_us() - start_time;
    tcp_data->bytes_sent = 0;
    tcp_data->bytes_received = 0;
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int tcp_send(const char* host, int port, const char* data, response_t* response) {
    if (!host || port <= 0 || !data || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();
    
    // Find existing connection
    tcp_connection_t* conn = tcp_find_connection(host, port);
    if (!conn || !conn->is_connected) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active TCP connection");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Send data
    size_t data_len = strlen(data);
    ssize_t bytes_sent = send(conn->socket_fd, data, data_len, 0);
    
    if (bytes_sent < 0) {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Send failed: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "Sent %zd bytes to %s:%d", bytes_sent, host, port);
    
    // Set TCP-specific response data
    tcp_data_t* tcp_data = (tcp_data_t*)response->protocol_data.protocol_data;
    tcp_data->bytes_sent = bytes_sent;
    tcp_data->connection_established = true;
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int tcp_receive(const char* host, int port, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();
    
    // Find existing connection
    tcp_connection_t* conn = tcp_find_connection(host, port);
    if (!conn || !conn->is_connected) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active TCP connection");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Set socket to non-blocking for timeout control
    int flags = fcntl(conn->socket_fd, F_GETFL, 0);
    fcntl(conn->socket_fd, F_SETFL, flags | O_NONBLOCK);
    
    // Wait for data with timeout
    fd_set read_fds;
    struct timeval timeout;
    FD_ZERO(&read_fds);
    FD_SET(conn->socket_fd, &read_fds);
    timeout.tv_sec = 1;  // 1 second timeout
    timeout.tv_usec = 0;
    
    int select_result = select(conn->socket_fd + 1, &read_fds, NULL, NULL, &timeout);
    
    if (select_result <= 0) {
        fcntl(conn->socket_fd, F_SETFL, flags);
        response->success = true;
        response->status_code = 204;
        strcpy(response->body, "No data available");
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }
    
    // Receive data
    char buffer[MAX_BODY_LENGTH];
    ssize_t bytes_received = recv(conn->socket_fd, buffer, sizeof(buffer) - 1, 0);
    
    // Set socket back to blocking mode
    fcntl(conn->socket_fd, F_SETFL, flags);
    
    if (bytes_received < 0) {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Receive failed: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    if (bytes_received == 0) {
        // Connection closed by peer
        conn->is_connected = false;
        close(conn->socket_fd);
        conn->socket_fd = -1;
        response->success = false;
        response->status_code = 410;
        strcpy(response->error_message, "Connection closed by peer");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    buffer[bytes_received] = '\0';
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "Received %zd bytes from %s:%d", bytes_received, host, port);
    
    // Set TCP-specific response data
    tcp_data_t* tcp_data = (tcp_data_t*)response->protocol_data.protocol_data;
    tcp_data->bytes_received = bytes_received;
    tcp_data->connection_established = true;
    strncpy(tcp_data->received_data, buffer, sizeof(tcp_data->received_data) - 1);
    tcp_data->received_data[sizeof(tcp_data->received_data) - 1] = '\0';
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int tcp_disconnect(const char* host, int port, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    uint64_t start_time = get_time_us();
    
    // Find existing connection
    tcp_connection_t* conn = tcp_find_connection(host, port);
    if (!conn || !conn->is_connected) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active TCP connection to disconnect");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Close socket
    if (conn->socket_fd >= 0) {
        close(conn->socket_fd);
        conn->socket_fd = -1;
    }
    
    conn->is_connected = false;
    
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "TCP connection to %s:%d closed successfully", host, port);
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}
