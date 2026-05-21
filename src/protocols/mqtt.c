#include "mqtt.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <errno.h>
#include <time.h>
#include <pthread.h>
#include <stdint.h>

/* Per-thread RNG seed — initialized lazily on first use */
static __thread unsigned int thread_rng_seed = 0;

/* Inline helper to lazily initialize seed from pthread_self() */
static inline unsigned int get_thread_seed(void) {
    if (thread_rng_seed == 0) {
        thread_rng_seed = (unsigned int)(uintptr_t)pthread_self();
        if (thread_rng_seed == 0) thread_rng_seed = 1; /* avoid all-zero seed */
    }
    return thread_rng_seed;
}

// Connection pool for MQTT connections
#define MAX_MQTT_CONNECTIONS 50
static mqtt_connection_t mqtt_connections[MAX_MQTT_CONNECTIONS];
static int mqtt_connection_count = 0;
static pthread_mutex_t mqtt_pool_mutex = PTHREAD_MUTEX_INITIALIZER;
static int mqtt_pool_warned = 0;

// MQTT packet types
#define MQTT_CONNECT     0x10
#define MQTT_CONNACK     0x20
#define MQTT_PUBLISH     0x30
#define MQTT_PUBACK      0x40
#define MQTT_SUBSCRIBE   0x82
#define MQTT_SUBACK      0x90
#define MQTT_UNSUBSCRIBE 0xA2
#define MQTT_UNSUBACK    0xB0
#define MQTT_DISCONNECT  0xE0


int mqtt_parse_url(const char* url, char* host, int* port, char* client_id) {
    if (!url || !host || !port || !client_id) {
        return -1;
    }

    /* Ensure per-thread seed is initialized before any rand_r use */
    get_thread_seed();

    // Parse mqtt://host:port/client_id format
    const char* protocol_end = strstr(url, "://");
    if (!protocol_end) {
        strncpy(host, url, 255);
        host[255] = '\0';
        *port = 1883; // Default MQTT port
        snprintf(client_id, MAX_MQTT_CLIENT_ID_LENGTH, "loadspiker_%u", rand_r(&thread_rng_seed));
        return 0;
    }

    const char* host_start = protocol_end + 3;
    const char* port_start = strchr(host_start, ':');
    const char* client_start = strchr(host_start, '/');

    if (port_start && (!client_start || port_start < client_start)) {
        // Host with port
        size_t host_len = port_start - host_start;
        strncpy(host, host_start, host_len);
        host[host_len] = '\0';

        if (client_start) {
            *port = atoi(port_start + 1);
            strncpy(client_id, client_start + 1, MAX_MQTT_CLIENT_ID_LENGTH - 1);
        } else {
            *port = atoi(port_start + 1);
            snprintf(client_id, MAX_MQTT_CLIENT_ID_LENGTH, "loadspiker_%u", rand_r(&thread_rng_seed));
        }
    } else if (client_start) {
        // Host with client ID but no port
        size_t host_len = client_start - host_start;
        strncpy(host, host_start, host_len);
        host[host_len] = '\0';
        *port = 1883;
        strncpy(client_id, client_start + 1, MAX_MQTT_CLIENT_ID_LENGTH - 1);
    } else {
        // Just host
        strncpy(host, host_start, 255);
        host[255] = '\0';
        *port = 1883;
        snprintf(client_id, MAX_MQTT_CLIENT_ID_LENGTH, "loadspiker_%u", rand_r(&thread_rng_seed));
    }

    client_id[MAX_MQTT_CLIENT_ID_LENGTH - 1] = '\0';
    return 0;
}

mqtt_connection_t* mqtt_find_connection(const char* host, int port, const char* client_id) {
    pthread_mutex_lock(&mqtt_pool_mutex);
    mqtt_connection_t* result = NULL;
    for (int i = 0; i < mqtt_connection_count; i++) {
        if (strcmp(mqtt_connections[i].host, host) == 0 &&
            mqtt_connections[i].port == port &&
            strcmp(mqtt_connections[i].client_id, client_id) == 0) {
            result = &mqtt_connections[i];
            break;
        }
    }
    pthread_mutex_unlock(&mqtt_pool_mutex);
    return result;
}

mqtt_connection_t* mqtt_create_connection(const char* host, int port, const char* client_id) {
    pthread_mutex_lock(&mqtt_pool_mutex);
    if (mqtt_connection_count >= MAX_MQTT_CONNECTIONS) {
        if (!mqtt_pool_warned) {
            fprintf(stderr, "[LoadSpiker] MQTT pool full — increase MAX_MQTT_CONNECTIONS\n");
            mqtt_pool_warned = 1;
        }
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return NULL;
    }

    mqtt_connection_t* conn = &mqtt_connections[mqtt_connection_count++];
    memset(conn, 0, sizeof(mqtt_connection_t));

    strncpy(conn->host, host, sizeof(conn->host) - 1);
    conn->port = port;
    strncpy(conn->client_id, client_id, sizeof(conn->client_id) - 1);
    conn->is_connected = false;
    conn->socket_fd = -1;
    conn->packet_id = 1;
    conn->keep_alive_seconds = 60;

    pthread_mutex_unlock(&mqtt_pool_mutex);
    return conn;
}

static int mqtt_create_connect_packet(char* buffer, const char* client_id,
                                     const char* username, const char* password,
                                     int keep_alive) {
    int pos = 0;

    // Fixed header
    buffer[pos++] = MQTT_CONNECT;

    // Variable header length calculation
    int var_header_len = 10; // Protocol name + version + flags + keep alive
    int payload_len = 2 + strlen(client_id);

    bool has_username = username && strlen(username) > 0;
    bool has_password = password && strlen(password) > 0;

    if (has_username) {
        payload_len += 2 + strlen(username);
    }
    if (has_password) {
        payload_len += 2 + strlen(password);
    }

    int remaining_length = var_header_len + payload_len;

    // Encode remaining length
    do {
        char encoded_byte = remaining_length % 128;
        remaining_length = remaining_length / 128;
        if (remaining_length > 0) {
            encoded_byte = encoded_byte | 128;
        }
        buffer[pos++] = encoded_byte;
    } while (remaining_length > 0);

    // Variable header - Protocol Name
    buffer[pos++] = 0x00; buffer[pos++] = 0x04; // Length
    buffer[pos++] = 'M'; buffer[pos++] = 'Q'; buffer[pos++] = 'T'; buffer[pos++] = 'T';

    // Protocol Level
    buffer[pos++] = 0x04; // MQTT 3.1.1

    // Connect Flags
    char flags = 0x02; // Clean Session
    if (has_username) flags |= 0x80;
    if (has_password) flags |= 0x40;
    buffer[pos++] = flags;

    // Keep Alive
    buffer[pos++] = (keep_alive >> 8) & 0xFF;
    buffer[pos++] = keep_alive & 0xFF;

    // Payload - Client ID
    int client_id_len = strlen(client_id);
    buffer[pos++] = (client_id_len >> 8) & 0xFF;
    buffer[pos++] = client_id_len & 0xFF;
    memcpy(&buffer[pos], client_id, client_id_len);
    pos += client_id_len;

    // Username
    if (has_username) {
        int username_len = strlen(username);
        buffer[pos++] = (username_len >> 8) & 0xFF;
        buffer[pos++] = username_len & 0xFF;
        memcpy(&buffer[pos], username, username_len);
        pos += username_len;
    }

    // Password
    if (has_password) {
        int password_len = strlen(password);
        buffer[pos++] = (password_len >> 8) & 0xFF;
        buffer[pos++] = password_len & 0xFF;
        memcpy(&buffer[pos], password, password_len);
        pos += password_len;
    }

    return pos;
}

static int mqtt_create_publish_packet(char* buffer, const char* topic,
                                     const char* message, mqtt_qos_t qos,
                                     bool retain, uint16_t packet_id) {
    int pos = 0;

    // Fixed header
    char fixed_header = MQTT_PUBLISH;
    if (retain) fixed_header |= 0x01;
    fixed_header |= (qos << 1);
    buffer[pos++] = fixed_header;

    // Calculate remaining length
    int topic_len = strlen(topic);
    int message_len = strlen(message);
    int remaining_length = 2 + topic_len + message_len;
    if (qos > 0) remaining_length += 2; // Packet ID for QoS > 0

    // Encode remaining length
    do {
        char encoded_byte = remaining_length % 128;
        remaining_length = remaining_length / 128;
        if (remaining_length > 0) {
            encoded_byte = encoded_byte | 128;
        }
        buffer[pos++] = encoded_byte;
    } while (remaining_length > 0);

    // Variable header - Topic Name
    buffer[pos++] = (topic_len >> 8) & 0xFF;
    buffer[pos++] = topic_len & 0xFF;
    memcpy(&buffer[pos], topic, topic_len);
    pos += topic_len;

    // Packet ID (for QoS > 0)
    if (qos > 0) {
        buffer[pos++] = (packet_id >> 8) & 0xFF;
        buffer[pos++] = packet_id & 0xFF;
    }

    // Payload - Message
    memcpy(&buffer[pos], message, message_len);
    pos += message_len;

    return pos;
}

int mqtt_connect(const char* host, int port, const char* client_id,
                const char* username, const char* password,
                int keep_alive_seconds, response_t* response) {
    if (!host || !client_id || !response) {
        return -1;
    }

    pthread_mutex_lock(&mqtt_pool_mutex);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_MQTT;
    uint64_t start_time = get_time_us();

    // Check if connection already exists (inline find — mutex already held)
    bool new_entry = false;
    mqtt_connection_t* conn = NULL;
    for (int i = 0; i < mqtt_connection_count; i++) {
        if (strcmp(mqtt_connections[i].host, host) == 0 &&
            mqtt_connections[i].port == port &&
            strcmp(mqtt_connections[i].client_id, client_id) == 0) {
            conn = &mqtt_connections[i];
            break;
        }
    }
    if (conn && conn->is_connected) {
        response->status_code = 200;
        response->success = true;
        snprintf(response->body, sizeof(response->body),
                "MQTT connection already established to %s:%d with client ID %s",
                host, port, client_id);
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return 0;
    }

    if (!conn) {
        if (mqtt_connection_count >= MAX_MQTT_CONNECTIONS) {
            if (!mqtt_pool_warned) {
                fprintf(stderr, "[LoadSpiker] MQTT pool full — increase MAX_MQTT_CONNECTIONS\n");
                mqtt_pool_warned = 1;
            }
            response->status_code = 500;
            response->success = false;
            strcpy(response->error_message, "Too many MQTT connections");
            response->response_time_us = get_time_us() - start_time;
            pthread_mutex_unlock(&mqtt_pool_mutex);
            return -1;
        }
        conn = &mqtt_connections[mqtt_connection_count++];
        memset(conn, 0, sizeof(mqtt_connection_t));
        strncpy(conn->host, host, sizeof(conn->host) - 1);
        conn->port = port;
        strncpy(conn->client_id, client_id, sizeof(conn->client_id) - 1);
        conn->is_connected = false;
        conn->socket_fd = -1;
        conn->packet_id = 1;
        conn->keep_alive_seconds = 60;
        new_entry = true;
    }

    // Create socket
    conn->socket_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (conn->socket_fd < 0) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to create socket: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Resolve hostname (thread-safe getaddrinfo)
    char port_str[8];
    snprintf(port_str, sizeof(port_str), "%d", port);
    struct addrinfo hints, *res;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    int gai_err = getaddrinfo(host, port_str, &hints, &res);
    if (gai_err != 0) {
        close(conn->socket_fd);
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "DNS resolution failed for %s: %s", host, gai_strerror(gai_err));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Connect to server
    if (connect(conn->socket_fd, res->ai_addr, res->ai_addrlen) < 0) {
        freeaddrinfo(res);
        close(conn->socket_fd);
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to connect to MQTT broker: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    freeaddrinfo(res);

    // Send CONNECT packet
    char connect_packet[1024];
    int packet_len = mqtt_create_connect_packet(connect_packet, client_id,
                                               username, password, keep_alive_seconds);

    if (send(conn->socket_fd, connect_packet, packet_len, 0) < 0) {
        close(conn->socket_fd);
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to send CONNECT packet: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    /* Read CONNACK — MQTT 3.1.1 §3.2: fixed 4 bytes: 0x20 0x02 <ack_flags> <return_code> */
    char connack[4];
    ssize_t connack_len = recv(conn->socket_fd, connack, sizeof(connack), 0);
    if (connack_len < 0) {
        close(conn->socket_fd);
        conn->socket_fd = -1;
        /* Remove pool entry only if it was newly allocated for this call */
        if (new_entry) {
            mqtt_connection_count--;
            memset(&mqtt_connections[mqtt_connection_count], 0, sizeof(mqtt_connection_t));
        }
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to receive CONNACK: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }
    if (connack_len < 4 ||
        (unsigned char)connack[0] != 0x20 ||
        (unsigned char)connack[1] != 0x02 ||
        (unsigned char)connack[2] != 0x00 ||
        (unsigned char)connack[3] != 0x00) {
        close(conn->socket_fd);
        conn->socket_fd = -1;
        /* Remove pool entry — bad CONNACK means connection was rejected; leave no half-open slot */
        if (new_entry) {
            mqtt_connection_count--;
            memset(&mqtt_connections[mqtt_connection_count], 0, sizeof(mqtt_connection_t));
        }
        response->status_code = 500;
        response->success = false;
        if (connack_len >= 4 && (unsigned char)connack[0] == 0x20 && (unsigned char)connack[1] == 0x02) {
            /* Packet structure OK but broker rejected — include return code in message */
            snprintf(response->error_message, sizeof(response->error_message),
                    "MQTT broker rejected connection: CONNACK return code 0x%02X",
                    (unsigned char)connack[3]);
        } else {
            snprintf(response->error_message, sizeof(response->error_message),
                    "Invalid CONNACK packet (got 0x%02X 0x%02X, len=%zd)",
                    connack_len > 0 ? (unsigned char)connack[0] : 0,
                    connack_len > 1 ? (unsigned char)connack[1] : 0,
                    connack_len);
        }
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Mark connection as established
    conn->is_connected = true;
    conn->keep_alive_seconds = keep_alive_seconds;
    if (username) strncpy(conn->username, username, sizeof(conn->username) - 1);
    // Security: Do NOT store password after connection is established
    // The password was already used in the CONNECT packet above
    // Storing it in memory would be a security risk (memory dumps, core dumps, debugging)
    memset(conn->password, 0, sizeof(conn->password));

    response->status_code = 200;
    response->success = true;
    snprintf(response->body, sizeof(response->body),
            "MQTT connection established to %s:%d with client ID %s",
            host, port, client_id);
    response->response_time_us = get_time_us() - start_time;

    // Set MQTT-specific response data
    mqtt_response_data_t* mqtt_data = &response->protocol_data.mqtt;
    mqtt_data->message_published = false;
    mqtt_data->message_received = false;
    mqtt_data->messages_published_count = 0;
    mqtt_data->messages_received_count = 0;
    strncpy(mqtt_data->topic, "", sizeof(mqtt_data->topic) - 1);
    mqtt_data->qos_level = MQTT_QOS_0;
    mqtt_data->retained = false;

    pthread_mutex_unlock(&mqtt_pool_mutex);
    return 0;
}

int mqtt_publish(const char* host, int port, const char* client_id,
                const char* topic, const char* message,
                mqtt_qos_t qos, bool retain, response_t* response) {
    if (!host || !client_id || !topic || !message || !response) {
        return -1;
    }

    pthread_mutex_lock(&mqtt_pool_mutex);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_MQTT;
    uint64_t start_time = get_time_us();

    // Find existing connection
    mqtt_connection_t* conn = NULL;
    for (int i = 0; i < mqtt_connection_count; i++) {
        if (strcmp(mqtt_connections[i].host, host) == 0 &&
            mqtt_connections[i].port == port &&
            strcmp(mqtt_connections[i].client_id, client_id) == 0) {
            conn = &mqtt_connections[i];
            break;
        }
    }
    if (!conn || !conn->is_connected) {
        response->status_code = 400;
        response->success = false;
        strcpy(response->error_message, "No active MQTT connection");
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Create PUBLISH packet
    char publish_packet[MAX_MQTT_MESSAGE_LENGTH + 512];
    int packet_len = mqtt_create_publish_packet(publish_packet, topic, message,
                                               qos, retain, conn->packet_id++);

    // Send PUBLISH packet
    if (send(conn->socket_fd, publish_packet, packet_len, 0) < 0) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to send PUBLISH packet: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    response->status_code = 200;
    response->success = true;
    snprintf(response->body, sizeof(response->body),
            "Published message to topic '%s' (QoS %d, retain=%s)",
            topic, qos, retain ? "true" : "false");
    response->response_time_us = get_time_us() - start_time;

    // Set MQTT-specific response data
    mqtt_response_data_t* mqtt_data = &response->protocol_data.mqtt;
    mqtt_data->message_published = true;
    mqtt_data->messages_published_count++;
    strncpy(mqtt_data->topic, topic, sizeof(mqtt_data->topic) - 1);
    strncpy(mqtt_data->last_message, message, sizeof(mqtt_data->last_message) - 1);
    mqtt_data->qos_level = qos;
    mqtt_data->retained = retain;
    mqtt_data->publish_time_us = get_time_us() - start_time;

    pthread_mutex_unlock(&mqtt_pool_mutex);
    return 0;
}

static int mqtt_create_subscribe_packet(char* buffer, const char* topic,
                                       mqtt_qos_t qos, uint16_t packet_id) {
    int pos = 0;
    int topic_len = strlen(topic);

    // Fixed header - SUBSCRIBE with reserved bits
    buffer[pos++] = MQTT_SUBSCRIBE;  // 0x82

    // Calculate remaining length: packet_id(2) + topic_len_field(2) + topic + qos(1)
    int remaining_length = 2 + 2 + topic_len + 1;

    /* Encode remaining length — multi-byte for topics >= 128 bytes (MQTT §1.5.5) */
    int rl = remaining_length;
    do {
        char encoded_byte = rl % 128;
        rl = rl / 128;
        if (rl > 0) {
            encoded_byte = encoded_byte | 128;
        }
        buffer[pos++] = encoded_byte;
    } while (rl > 0);

    // Variable header - Packet ID
    buffer[pos++] = (packet_id >> 8) & 0xFF;
    buffer[pos++] = packet_id & 0xFF;

    // Payload - Topic Filter
    buffer[pos++] = (topic_len >> 8) & 0xFF;
    buffer[pos++] = topic_len & 0xFF;
    memcpy(&buffer[pos], topic, topic_len);
    pos += topic_len;

    // Requested QoS
    buffer[pos++] = (char)qos;

    return pos;
}

int mqtt_subscribe(const char* host, int port, const char* client_id,
                  const char* topic, mqtt_qos_t qos, response_t* response) {
    if (!host || !client_id || !topic || !response) {
        return -1;
    }

    pthread_mutex_lock(&mqtt_pool_mutex);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_MQTT;
    uint64_t start_time = get_time_us();

    // Find existing connection
    mqtt_connection_t* conn = NULL;
    for (int i = 0; i < mqtt_connection_count; i++) {
        if (strcmp(mqtt_connections[i].host, host) == 0 &&
            mqtt_connections[i].port == port &&
            strcmp(mqtt_connections[i].client_id, client_id) == 0) {
            conn = &mqtt_connections[i];
            break;
        }
    }
    if (!conn || !conn->is_connected) {
        response->status_code = 400;
        response->success = false;
        strcpy(response->error_message, "No active MQTT connection");
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Create SUBSCRIBE packet
    char subscribe_packet[512];
    uint16_t packet_id = conn->packet_id++;
    int packet_len = mqtt_create_subscribe_packet(subscribe_packet, topic, qos, packet_id);

    // Send SUBSCRIBE packet
    if (send(conn->socket_fd, subscribe_packet, packet_len, 0) < 0) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to send SUBSCRIBE packet: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Read SUBACK response
    char suback[5];
    int recv_len = recv(conn->socket_fd, suback, sizeof(suback), 0);
    if (recv_len < 0) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to receive SUBACK: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Verify SUBACK packet type
    if ((suback[0] & 0xF0) != MQTT_SUBACK) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Invalid SUBACK response (got 0x%02X)", (unsigned char)suback[0]);
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    response->status_code = 200;
    response->success = true;
    snprintf(response->body, sizeof(response->body),
            "Subscribed to topic '%s' with QoS %d", topic, qos);
    response->response_time_us = get_time_us() - start_time;

    // Set MQTT-specific response data
    mqtt_response_data_t* mqtt_data = &response->protocol_data.mqtt;
    strncpy(mqtt_data->topic, topic, sizeof(mqtt_data->topic) - 1);
    mqtt_data->qos_level = qos;

    pthread_mutex_unlock(&mqtt_pool_mutex);
    return 0;
}

static int mqtt_create_unsubscribe_packet(char* buffer, const char* topic, uint16_t packet_id) {
    int pos = 0;
    int topic_len = strlen(topic);

    // Fixed header - UNSUBSCRIBE with reserved bits
    buffer[pos++] = MQTT_UNSUBSCRIBE;  // 0xA2

    // Calculate remaining length: packet_id(2) + topic_len_field(2) + topic
    int remaining_length = 2 + 2 + topic_len;

    /* Encode remaining length — multi-byte for topics >= 128 bytes (MQTT §1.5.5) */
    int rl = remaining_length;
    do {
        char encoded_byte = rl % 128;
        rl = rl / 128;
        if (rl > 0) {
            encoded_byte = encoded_byte | 128;
        }
        buffer[pos++] = encoded_byte;
    } while (rl > 0);

    // Variable header - Packet ID
    buffer[pos++] = (packet_id >> 8) & 0xFF;
    buffer[pos++] = packet_id & 0xFF;

    // Payload - Topic Filter
    buffer[pos++] = (topic_len >> 8) & 0xFF;
    buffer[pos++] = topic_len & 0xFF;
    memcpy(&buffer[pos], topic, topic_len);
    pos += topic_len;

    return pos;
}

int mqtt_unsubscribe(const char* host, int port, const char* client_id,
                    const char* topic, response_t* response) {
    if (!host || !client_id || !topic || !response) {
        return -1;
    }

    pthread_mutex_lock(&mqtt_pool_mutex);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_MQTT;
    uint64_t start_time = get_time_us();

    // Find existing connection
    mqtt_connection_t* conn = NULL;
    for (int i = 0; i < mqtt_connection_count; i++) {
        if (strcmp(mqtt_connections[i].host, host) == 0 &&
            mqtt_connections[i].port == port &&
            strcmp(mqtt_connections[i].client_id, client_id) == 0) {
            conn = &mqtt_connections[i];
            break;
        }
    }
    if (!conn || !conn->is_connected) {
        response->status_code = 400;
        response->success = false;
        strcpy(response->error_message, "No active MQTT connection");
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Create UNSUBSCRIBE packet
    char unsubscribe_packet[512];
    uint16_t packet_id = conn->packet_id++;
    int packet_len = mqtt_create_unsubscribe_packet(unsubscribe_packet, topic, packet_id);

    // Send UNSUBSCRIBE packet
    if (send(conn->socket_fd, unsubscribe_packet, packet_len, 0) < 0) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to send UNSUBSCRIBE packet: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Read UNSUBACK response
    char unsuback[4];
    int recv_len = recv(conn->socket_fd, unsuback, sizeof(unsuback), 0);
    if (recv_len < 0) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Failed to receive UNSUBACK: %s", strerror(errno));
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Verify UNSUBACK packet type
    if ((unsuback[0] & 0xF0) != MQTT_UNSUBACK) {
        response->status_code = 500;
        response->success = false;
        snprintf(response->error_message, sizeof(response->error_message),
                "Invalid UNSUBACK response (got 0x%02X)", (unsigned char)unsuback[0]);
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    response->status_code = 200;
    response->success = true;
    snprintf(response->body, sizeof(response->body),
            "Unsubscribed from topic '%s'", topic);
    response->response_time_us = get_time_us() - start_time;

    pthread_mutex_unlock(&mqtt_pool_mutex);
    return 0;
}

int mqtt_disconnect(const char* host, int port, const char* client_id, response_t* response) {
    if (!host || !client_id || !response) {
        return -1;
    }

    pthread_mutex_lock(&mqtt_pool_mutex);

    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_MQTT;
    uint64_t start_time = get_time_us();

    // Find existing connection
    mqtt_connection_t* conn = NULL;
    for (int i = 0; i < mqtt_connection_count; i++) {
        if (strcmp(mqtt_connections[i].host, host) == 0 &&
            mqtt_connections[i].port == port &&
            strcmp(mqtt_connections[i].client_id, client_id) == 0) {
            conn = &mqtt_connections[i];
            break;
        }
    }
    if (!conn || !conn->is_connected) {
        response->status_code = 400;
        response->success = false;
        strcpy(response->error_message, "No active MQTT connection to disconnect");
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&mqtt_pool_mutex);
        return -1;
    }

    // Send DISCONNECT packet
    char disconnect_packet[2] = {MQTT_DISCONNECT, 0x00};
    send(conn->socket_fd, disconnect_packet, 2, 0);

    // Close socket and mark as disconnected
    close(conn->socket_fd);
    conn->is_connected = false;
    conn->socket_fd = -1;

    response->status_code = 200;
    response->success = true;
    snprintf(response->body, sizeof(response->body),
            "MQTT connection to %s:%d closed successfully", host, port);
    response->response_time_us = get_time_us() - start_time;

    pthread_mutex_unlock(&mqtt_pool_mutex);
    return 0;
}

void mqtt_cleanup_all(void) {
    pthread_mutex_lock(&mqtt_pool_mutex);
    for (int i = 0; i < mqtt_connection_count; i++) {
        if (mqtt_connections[i].socket_fd >= 0) {
            // Try to send DISCONNECT packet before closing
            char disconnect_packet[2] = {MQTT_DISCONNECT, 0x00};
            send(mqtt_connections[i].socket_fd, disconnect_packet, 2, MSG_NOSIGNAL);
            close(mqtt_connections[i].socket_fd);
            mqtt_connections[i].socket_fd = -1;
        }
        mqtt_connections[i].is_connected = false;
    }
    mqtt_connection_count = 0;
    pthread_mutex_unlock(&mqtt_pool_mutex);
}
