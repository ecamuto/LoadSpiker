#ifndef MQTT_H
#define MQTT_H

#include "../engine.h"
#include <stdint.h>
#include <stdbool.h>

#define MAX_MQTT_TOPIC_LENGTH 256
#define MAX_MQTT_MESSAGE_LENGTH 8192
#define MAX_MQTT_CLIENT_ID_LENGTH 128
#define MAX_MQTT_USERNAME_LENGTH 256
#define MAX_MQTT_PASSWORD_LENGTH 256

// MQTT Quality of Service levels
typedef enum {
    MQTT_QOS_0 = 0,  // At most once delivery
    MQTT_QOS_1 = 1,  // At least once delivery
    MQTT_QOS_2 = 2   // Exactly once delivery
} mqtt_qos_t;

// MQTT connection structure
typedef struct {
    char client_id[MAX_MQTT_CLIENT_ID_LENGTH];
    char host[256];
    int port;
    char username[MAX_MQTT_USERNAME_LENGTH];
    char password[MAX_MQTT_PASSWORD_LENGTH];
    bool is_connected;
    int socket_fd;
    uint16_t packet_id;
    int keep_alive_seconds;
    char last_error[256];
} mqtt_connection_t;

// MQTT-specific response data
typedef struct {
    bool message_published;
    bool message_received;
    int messages_published_count;
    int messages_received_count;
    char topic[MAX_MQTT_TOPIC_LENGTH];
    char last_message[MAX_MQTT_MESSAGE_LENGTH];
    mqtt_qos_t qos_level;
    bool retained;
    uint64_t publish_time_us;
} mqtt_data_t;

// MQTT request data
typedef struct {
    char client_id[MAX_MQTT_CLIENT_ID_LENGTH];
    char topic[MAX_MQTT_TOPIC_LENGTH];
    char message[MAX_MQTT_MESSAGE_LENGTH];
    char username[MAX_MQTT_USERNAME_LENGTH];
    char password[MAX_MQTT_PASSWORD_LENGTH];
    mqtt_qos_t qos;
    bool retain;
    int keep_alive_seconds;
} mqtt_request_data_t;

// Function declarations
int mqtt_connect(const char* host, int port, const char* client_id, 
                const char* username, const char* password, 
                int keep_alive_seconds, response_t* response);

int mqtt_publish(const char* host, int port, const char* client_id,
                const char* topic, const char* message, 
                mqtt_qos_t qos, bool retain, response_t* response);

int mqtt_subscribe(const char* host, int port, const char* client_id,
                  const char* topic, mqtt_qos_t qos, response_t* response);

int mqtt_unsubscribe(const char* host, int port, const char* client_id,
                    const char* topic, response_t* response);

int mqtt_disconnect(const char* host, int port, const char* client_id, response_t* response);

// Helper functions
int mqtt_parse_url(const char* url, char* host, int* port, char* client_id);
mqtt_connection_t* mqtt_find_connection(const char* host, int port, const char* client_id);
mqtt_connection_t* mqtt_create_connection(const char* host, int port, const char* client_id);
uint64_t get_time_us(void);

#endif // MQTT_H
