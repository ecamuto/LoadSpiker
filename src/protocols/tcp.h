#ifndef TCP_H
#define TCP_H

#include "../engine.h"
#include <stdint.h>
#include <stdbool.h>

#define MAX_CONN_ID_LENGTH 64

// TCP connection structure
typedef struct {
    char host[256];
    int port;
    char conn_id[MAX_CONN_ID_LENGTH]; // per-virtual-user key; "" / "default" for single-user
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

// Function declarations.
// conn_id identifies the logical owner (one virtual user) so concurrent users
// targeting the same host:port get isolated sockets. Pass "default" (or "") for
// single-user / direct use.
int tcp_connect(const char* host, int port, const char* conn_id, response_t* response);
int tcp_send(const char* host, int port, const char* conn_id, const char* data, response_t* response);
int tcp_receive(const char* host, int port, const char* conn_id, response_t* response);
int tcp_disconnect(const char* host, int port, const char* conn_id, response_t* response);

// Helper functions
int tcp_parse_url(const char* url, char* host, int* port);

// Cleanup function - closes all TCP connections
void tcp_cleanup_all(void);

#endif // TCP_H
