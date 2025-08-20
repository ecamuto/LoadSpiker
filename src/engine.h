#ifndef ENGINE_H
#define ENGINE_H

#include <stdint.h>
#include <stdbool.h>
#include <time.h>

#define MAX_URL_LENGTH 2048
#define MAX_HEADER_LENGTH 8192
#define MAX_BODY_LENGTH 65536
#define MAX_CONNECTIONS 10000
#define MAX_PROTOCOL_DATA 32768

// Protocol types for Phase 1
typedef enum {
    PROTOCOL_HTTP = 0,
    PROTOCOL_WEBSOCKET = 1,
    PROTOCOL_DATABASE = 2,
    PROTOCOL_GRPC = 3,
    PROTOCOL_TCP = 4,
    PROTOCOL_UDP = 5,
    PROTOCOL_MQTT = 6,
    PROTOCOL_AMQP = 7,
    PROTOCOL_KAFKA = 8
} protocol_type_t;

// WebSocket specific request data
typedef struct {
    char subprotocol[256];
    char origin[256];
    int ping_interval_ms;
    bool auto_ping;
} websocket_request_data_t;

// Database specific request data
typedef struct {
    char connection_string[1024];
    char query[4096];
    char database_type[32]; // mysql, postgresql, mongodb
} database_request_data_t;

// Generic request structure supporting multiple protocols
typedef struct {
    protocol_type_t protocol;
    char method[16];  // HTTP method, WS action, DB operation, etc.
    char url[MAX_URL_LENGTH];
    char headers[MAX_HEADER_LENGTH];
    char body[MAX_BODY_LENGTH];
    int timeout_ms;
    
    // Protocol-specific data
    union {
        websocket_request_data_t websocket;
        database_request_data_t database;
        char protocol_data[MAX_PROTOCOL_DATA];
    } protocol_data;
} request_t;

// Legacy HTTP request structure (for backward compatibility)
typedef struct {
    char method[8];
    char url[MAX_URL_LENGTH];
    char headers[MAX_HEADER_LENGTH];
    char body[MAX_BODY_LENGTH];
    int timeout_ms;
} http_request_t;

// WebSocket specific response data
typedef struct {
    char subprotocol[256];
    int messages_sent;
    int messages_received;
    uint64_t bytes_sent;
    uint64_t bytes_received;
} websocket_response_data_t;

// Database specific response data
typedef struct {
    int rows_affected;
    int rows_returned;
    char result_set[MAX_BODY_LENGTH];
} database_response_data_t;

// TCP specific response data
typedef struct {
    int socket_fd;
    size_t bytes_sent;
    size_t bytes_received;
} tcp_response_data_t;

// UDP specific response data
typedef struct {
    int socket_fd;
    size_t bytes_sent;
    size_t bytes_received;
    char sender_address[256];
    int sender_port;
} udp_response_data_t;

// MQTT specific response data
typedef struct {
    bool message_published;
    bool message_received;
    int messages_published_count;
    int messages_received_count;
    char topic[256];
    char last_message[8192];
    int qos_level;
    bool retained;
    uint64_t publish_time_us;
} mqtt_response_data_t;

// Generic response structure supporting multiple protocols
typedef struct {
    protocol_type_t protocol;
    int status_code;
    char headers[MAX_HEADER_LENGTH];
    char body[MAX_BODY_LENGTH];
    uint64_t response_time_us;
    bool success;
    char error_message[256];
    
    // Protocol-specific data
    union {
        websocket_response_data_t websocket;
        database_response_data_t database;
        tcp_response_data_t tcp;
        udp_response_data_t udp;
        mqtt_response_data_t mqtt;
        char protocol_data[MAX_PROTOCOL_DATA];
    } protocol_data;
} response_t;

// Legacy HTTP response structure (for backward compatibility)
typedef struct {
    int status_code;
    char headers[MAX_HEADER_LENGTH];
    char body[MAX_BODY_LENGTH];
    uint64_t response_time_us;
    bool success;
    char error_message[256];
} http_response_t;

typedef struct {
    uint64_t total_requests;
    uint64_t successful_requests;
    uint64_t failed_requests;
    uint64_t total_response_time_us;
    uint64_t min_response_time_us;
    uint64_t max_response_time_us;
    double requests_per_second;
} metrics_t;

typedef struct engine engine_t;

// Core engine functions
engine_t* engine_create(int max_connections, int worker_threads);
void engine_destroy(engine_t* engine);

// New protocol-aware functions
int engine_execute_request_generic(engine_t* engine, const request_t* request, response_t* response);
int engine_execute_request_generic_sync(engine_t* engine, const request_t* request, response_t* response);
int engine_start_load_test_generic(engine_t* engine, const request_t* requests, int num_requests, int concurrent_users, int duration_seconds);

// Legacy HTTP functions (for backward compatibility)
int engine_execute_request(engine_t* engine, const http_request_t* request, http_response_t* response);
int engine_execute_request_sync(engine_t* engine, const http_request_t* request, http_response_t* response);
int engine_start_load_test(engine_t* engine, const http_request_t* requests, int num_requests, int concurrent_users, int duration_seconds);

// WebSocket specific functions
int engine_websocket_connect(engine_t* engine, const char* url, const char* subprotocol, response_t* response);
int engine_websocket_send(engine_t* engine, const char* url, const char* message, response_t* response);
int engine_websocket_close(engine_t* engine, const char* url, response_t* response);

// Database specific functions (stubs for now)
int engine_database_connect(engine_t* engine, const char* connection_string, const char* db_type, response_t* response);
int engine_database_query(engine_t* engine, const char* connection_string, const char* query, response_t* response);

// TCP Socket functions
int engine_tcp_connect(engine_t* engine, const char* hostname, int port, int timeout_ms, response_t* response);
int engine_tcp_send(engine_t* engine, int socket_fd, const char* data, size_t data_len, int timeout_ms, response_t* response);
int engine_tcp_receive(engine_t* engine, int socket_fd, char* buffer, size_t buffer_size, int timeout_ms, response_t* response);
int engine_tcp_disconnect(engine_t* engine, int socket_fd, response_t* response);

// UDP Socket functions
int engine_udp_create_endpoint(engine_t* engine, const char* bind_address, int port, response_t* response);
int engine_udp_send(engine_t* engine, int socket_fd, const char* data, size_t data_len, const char* dest_address, int dest_port, int timeout_ms, response_t* response);
int engine_udp_receive(engine_t* engine, int socket_fd, char* buffer, size_t buffer_size, char* sender_address, int* sender_port, int timeout_ms, response_t* response);
int engine_udp_close_endpoint(engine_t* engine, int socket_fd, response_t* response);

// MQTT Message Queue functions
int engine_mqtt_connect(engine_t* engine, const char* host, int port, const char* client_id, 
                       const char* username, const char* password, int keep_alive_seconds, response_t* response);
int engine_mqtt_publish(engine_t* engine, const char* host, int port, const char* client_id,
                       const char* topic, const char* message, int qos, bool retain, response_t* response);
int engine_mqtt_subscribe(engine_t* engine, const char* host, int port, const char* client_id,
                         const char* topic, int qos, response_t* response);
int engine_mqtt_unsubscribe(engine_t* engine, const char* host, int port, const char* client_id,
                           const char* topic, response_t* response);
int engine_mqtt_disconnect(engine_t* engine, const char* host, int port, const char* client_id, response_t* response);

// Metrics and utilities
void engine_get_metrics(engine_t* engine, metrics_t* metrics);
void engine_reset_metrics(engine_t* engine);

// Helper functions for protocol detection and conversion
protocol_type_t engine_detect_protocol(const char* url);
int engine_convert_http_request(const http_request_t* http_req, request_t* generic_req);
int engine_convert_http_response(const response_t* generic_resp, http_response_t* http_resp);

#endif
