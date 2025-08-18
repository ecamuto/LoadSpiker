#ifndef TCP_H
#define TCP_H

#include "../engine.h"
#include <stdint.h>
#include <stdbool.h>

// TCP connection structure
typedef struct {
    char host[256];
    int port;
    int socket_fd;
    bool is_connected;
    char last_error[256];
} tcp_connection_t;

// TCP-specific response data
typedef struct {
    int bytes_sent;
    int bytes_received;
    char received_data[MAX_BODY_LENGTH];
    bool connection_established;
    int connection_time_us;
} tcp_data_t;

// Function declarations
int tcp_connect(const char* host, int port, response_t* response);
int tcp_send(const char* host, int port, const char* data, response_t* response);
int tcp_receive(const char* host, int port, response_t* response);
int tcp_disconnect(const char* host, int port, response_t* response);

// Helper functions
int tcp_parse_url(const char* url, char* host, int* port);
tcp_connection_t* tcp_find_connection(const char* host, int port);
tcp_connection_t* tcp_create_connection(const char* host, int port);

#endif // TCP_H
