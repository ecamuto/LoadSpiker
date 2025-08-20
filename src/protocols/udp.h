#ifndef UDP_H
#define UDP_H

#include "../engine.h"
#include <stdint.h>
#include <stdbool.h>

// UDP connection structure (UDP is connectionless, but we track endpoints)
typedef struct {
    char host[256];
    int port;
    int socket_fd;
    bool is_bound;
    char last_error[256];
} udp_endpoint_t;

// UDP-specific response data
typedef struct {
    int bytes_sent;
    int bytes_received;
    char received_data[MAX_BODY_LENGTH];
    char remote_host[256];
    int remote_port;
    bool datagram_sent;
} udp_data_t;

// Function declarations
int udp_create_endpoint(const char* host, int port, response_t* response);
int udp_send(const char* host, int port, const char* data, response_t* response);
int udp_receive(const char* host, int port, response_t* response);
int udp_close_endpoint(const char* host, int port, response_t* response);

// Helper functions
int udp_parse_url(const char* url, char* host, int* port);
udp_endpoint_t* udp_find_endpoint(const char* host, int port);
udp_endpoint_t* udp_create_endpoint_struct(const char* host, int port);

#endif // UDP_H
