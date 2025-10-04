#include "udp.h"
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

// Endpoint pool for UDP endpoints
#define MAX_UDP_ENDPOINTS 100
static udp_endpoint_t udp_endpoints[MAX_UDP_ENDPOINTS];
static int udp_endpoint_count = 0;


int udp_parse_url(const char* url, char* host, int* port) {
    if (!url || !host || !port) {
        return -1;
    }
    
    // Initialize output parameters
    *host = '\0';
    *port = 0;
    
    // Parse udp://host:port format
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
        *port = 53; // Default UDP port (DNS)
    }
    
    return 0;
}

udp_endpoint_t* udp_find_endpoint(const char* host, int port) {
    for (int i = 0; i < udp_endpoint_count; i++) {
        if (strcmp(udp_endpoints[i].host, host) == 0 && udp_endpoints[i].port == port) {
            return &udp_endpoints[i];
        }
    }
    return NULL;
}

udp_endpoint_t* udp_create_endpoint_struct(const char* host, int port) {
    if (udp_endpoint_count >= MAX_UDP_ENDPOINTS) {
        return NULL;
    }
    
    udp_endpoint_t* endpoint = &udp_endpoints[udp_endpoint_count++];
    memset(endpoint, 0, sizeof(udp_endpoint_t));
    
    strncpy(endpoint->host, host, sizeof(endpoint->host) - 1);
    endpoint->port = port;
    endpoint->socket_fd = -1;
    endpoint->is_bound = false;
    
    return endpoint;
}

int udp_create_endpoint(const char* host, int port, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();
    
    // Check if endpoint already exists
    udp_endpoint_t* endpoint = udp_find_endpoint(host, port);
    if (endpoint && endpoint->is_bound) {
        response->success = true;
        response->status_code = 200;
        snprintf(response->body, sizeof(response->body), "UDP endpoint already created for %s:%d", host, port);
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }
    
    // Create new endpoint if needed
    if (!endpoint) {
        endpoint = udp_create_endpoint_struct(host, port);
        if (!endpoint) {
            response->success = false;
            response->status_code = 500;
            strcpy(response->error_message, "Too many UDP endpoints");
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
    }
    
    // Create UDP socket
    endpoint->socket_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (endpoint->socket_fd < 0) {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Failed to create UDP socket: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Set socket to reuse address
    int opt = 1;
    if (setsockopt(endpoint->socket_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        close(endpoint->socket_fd);
        endpoint->socket_fd = -1;
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Failed to set socket options: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // For sending, we don't need to bind to a specific local address
    // Just mark as ready for use
    endpoint->is_bound = true;
    
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "UDP endpoint created for %s:%d", host, port);
    
    // Set UDP-specific response data
    udp_data_t* udp_data = (udp_data_t*)response->protocol_data.protocol_data;
    udp_data->datagram_sent = false;
    udp_data->bytes_sent = 0;
    udp_data->bytes_received = 0;
    strncpy(udp_data->remote_host, host, sizeof(udp_data->remote_host) - 1);
    udp_data->remote_port = port;
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int udp_send(const char* host, int port, const char* data, response_t* response) {
    if (!host || port <= 0 || !data || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();
    
    // Find or create endpoint
    udp_endpoint_t* endpoint = udp_find_endpoint(host, port);
    if (!endpoint || !endpoint->is_bound) {
        // Auto-create endpoint for sending
        response_t create_response;
        if (udp_create_endpoint(host, port, &create_response) != 0) {
            response->success = false;
            response->status_code = 400;
            strcpy(response->error_message, "Failed to create UDP endpoint");
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        endpoint = udp_find_endpoint(host, port);
    }
    
    // Resolve hostname
    struct hostent* server = gethostbyname(host);
    if (!server) {
        response->success = false;
        response->status_code = 404;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Host not found: %s", host);
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Set up destination address
    struct sockaddr_in dest_addr;
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sin_family = AF_INET;
    memcpy(&dest_addr.sin_addr.s_addr, server->h_addr, server->h_length);
    dest_addr.sin_port = htons(port);
    
    // Send UDP datagram
    size_t data_len = strlen(data);
    ssize_t bytes_sent = sendto(endpoint->socket_fd, data, data_len, 0,
                               (struct sockaddr*)&dest_addr, sizeof(dest_addr));
    
    if (bytes_sent < 0) {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "UDP send failed: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "Sent %zd bytes to %s:%d via UDP", bytes_sent, host, port);
    
    // Set UDP-specific response data
    udp_data_t* udp_data = (udp_data_t*)response->protocol_data.protocol_data;
    udp_data->bytes_sent = bytes_sent;
    udp_data->datagram_sent = true;
    strncpy(udp_data->remote_host, host, sizeof(udp_data->remote_host) - 1);
    udp_data->remote_port = port;
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int udp_receive(const char* host, int port, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();
    
    // Find existing endpoint
    udp_endpoint_t* endpoint = udp_find_endpoint(host, port);
    if (!endpoint || !endpoint->is_bound) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No UDP endpoint available");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // For receiving, we need to bind to the local port
    struct sockaddr_in local_addr;
    memset(&local_addr, 0, sizeof(local_addr));
    local_addr.sin_family = AF_INET;
    local_addr.sin_addr.s_addr = INADDR_ANY;
    local_addr.sin_port = htons(port);
    
    // Try to bind if not already bound to this port
    if (bind(endpoint->socket_fd, (struct sockaddr*)&local_addr, sizeof(local_addr)) < 0) {
        // Binding failed, but socket might already be in use for sending
        // Continue with receive attempt
    }
    
    // Set socket to non-blocking for timeout control
    int flags = fcntl(endpoint->socket_fd, F_GETFL, 0);
    fcntl(endpoint->socket_fd, F_SETFL, flags | O_NONBLOCK);
    
    // Wait for data with timeout
    fd_set read_fds;
    struct timeval timeout;
    FD_ZERO(&read_fds);
    FD_SET(endpoint->socket_fd, &read_fds);
    timeout.tv_sec = 1;  // 1 second timeout
    timeout.tv_usec = 0;
    
    int select_result = select(endpoint->socket_fd + 1, &read_fds, NULL, NULL, &timeout);
    
    if (select_result <= 0) {
        fcntl(endpoint->socket_fd, F_SETFL, flags);
        response->success = true;
        response->status_code = 204;
        strcpy(response->body, "No UDP data available");
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }
    
    // Receive UDP datagram
    char buffer[MAX_BODY_LENGTH];
    struct sockaddr_in sender_addr;
    socklen_t sender_len = sizeof(sender_addr);
    
    ssize_t bytes_received = recvfrom(endpoint->socket_fd, buffer, sizeof(buffer) - 1, 0,
                                     (struct sockaddr*)&sender_addr, &sender_len);
    
    // Set socket back to blocking mode
    fcntl(endpoint->socket_fd, F_SETFL, flags);
    
    if (bytes_received < 0) {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message), 
                "UDP receive failed: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    buffer[bytes_received] = '\0';
    
    // Get sender information
    char sender_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &sender_addr.sin_addr, sender_ip, INET_ADDRSTRLEN);
    int sender_port = ntohs(sender_addr.sin_port);
    
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "Received %zd bytes from %s:%d via UDP", bytes_received, sender_ip, sender_port);
    
    // Set UDP-specific response data
    udp_data_t* udp_data = (udp_data_t*)response->protocol_data.protocol_data;
    udp_data->bytes_received = bytes_received;
    strncpy(udp_data->received_data, buffer, sizeof(udp_data->received_data) - 1);
    udp_data->received_data[sizeof(udp_data->received_data) - 1] = '\0';
    strncpy(udp_data->remote_host, sender_ip, sizeof(udp_data->remote_host) - 1);
    udp_data->remote_port = sender_port;
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int udp_close_endpoint(const char* host, int port, response_t* response) {
    if (!host || port <= 0 || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    uint64_t start_time = get_time_us();
    
    // Find existing endpoint
    udp_endpoint_t* endpoint = udp_find_endpoint(host, port);
    if (!endpoint || !endpoint->is_bound) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No UDP endpoint to close");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Close socket
    if (endpoint->socket_fd >= 0) {
        close(endpoint->socket_fd);
        endpoint->socket_fd = -1;
    }
    
    endpoint->is_bound = false;
    
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "UDP endpoint for %s:%d closed successfully", host, port);
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}
