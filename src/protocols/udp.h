#ifndef UDP_H
#define UDP_H

#include "../engine.h"
#include <stdint.h>
#include <stdbool.h>

#define MAX_CONN_ID_LENGTH 64

// UDP connection structure (UDP is connectionless, but we track endpoints)
typedef struct {
    char host[256];
    int port;
    char conn_id[MAX_CONN_ID_LENGTH]; // per-virtual-user key; "" / "default" for single-user
    int socket_fd;
    bool is_bound;       // socket created (and tracked in the pool)
    bool local_bound;    // bind() to the local port already done (for receive)
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

// Function declarations.
// conn_id identifies the logical owner (one virtual user) so concurrent users
// get isolated endpoints. Pass "default" (or "") for single-user / direct use.
int udp_create_endpoint(const char* host, int port, const char* conn_id, response_t* response);
// data_len lets binary payloads with embedded NULs through (no strlen()).
int udp_send(const char* host, int port, const char* conn_id, const char* data, size_t data_len, response_t* response);
int udp_receive(const char* host, int port, const char* conn_id, response_t* response);
int udp_close_endpoint(const char* host, int port, const char* conn_id, response_t* response);

// Helper functions
int udp_parse_url(const char* url, char* host, int* port);

// Cleanup function - closes all UDP endpoints
void udp_cleanup_all(void);

#endif // UDP_H
