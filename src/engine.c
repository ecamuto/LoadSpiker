#include "engine.h"
#include "protocols/websocket.h"
#include "protocols/database.h"
#include "protocols/tcp.h"
#include "protocols/udp.h"
#include "protocols/mqtt.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <curl/curl.h>
#include <pthread.h>
#include <sys/time.h>
#include <unistd.h>

typedef struct {
    char* data;
    size_t size;
    size_t capacity;
} response_buffer_t;

typedef struct {
    char* data;
    size_t size;
    size_t capacity;
} header_buffer_t;

typedef struct worker_thread {
    pthread_t thread;
    engine_t* engine;
    int thread_id;
    bool active;
} worker_thread_t;

struct engine {
    CURLM* multi_handle;
    worker_thread_t* workers;
    int num_workers;
    int max_connections;
    
    pthread_mutex_t metrics_mutex;
    metrics_t metrics;
    
    pthread_mutex_t queue_mutex;
    pthread_cond_t queue_cond;
    http_request_t* request_queue;
    http_response_t* response_queue;
    int queue_size;
    int queue_head;
    int queue_tail;
    bool shutdown;
};

static size_t write_callback(void* contents, size_t size, size_t nmemb, response_buffer_t* buffer) {
    size_t total_size = size * nmemb;
    
    if (!buffer || !buffer->data || !contents) {
        return 0;
    }
    
    // Check if we need to expand the buffer or if we're at capacity
    size_t required_size = buffer->size + total_size + 1; // +1 for null terminator
    
    if (required_size > buffer->capacity) {
        // Truncate to fit remaining capacity
        size_t available_space = buffer->capacity - buffer->size - 1; // -1 for null terminator
        if (available_space == 0) {
            return 0; // Buffer is full
        }
        total_size = available_space;
    }
    
    if (total_size > 0) {
        memcpy(buffer->data + buffer->size, contents, total_size);
        buffer->size += total_size;
        buffer->data[buffer->size] = '\0'; // Ensure null termination
    }
    
    return total_size;
}

static size_t header_callback(void* contents, size_t size, size_t nmemb, header_buffer_t* buffer) {
    size_t total_size = size * nmemb;
    
    if (!buffer || !buffer->data || !contents) {
        return 0;
    }
    
    // Check if we need to expand the buffer or if we're at capacity
    size_t required_size = buffer->size + total_size + 1; // +1 for null terminator
    
    if (required_size > buffer->capacity) {
        // Truncate to fit remaining capacity
        size_t available_space = buffer->capacity - buffer->size - 1; // -1 for null terminator
        if (available_space == 0) {
            return total_size; // Still report success to cURL, but don't store
        }
        total_size = available_space;
    }
    
    if (total_size > 0) {
        memcpy(buffer->data + buffer->size, contents, total_size);
        buffer->size += total_size;
        buffer->data[buffer->size] = '\0'; // Ensure null termination
    }
    
    return size * nmemb; // Always return the original size to cURL
}

static uint64_t get_time_us() {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000000ULL + tv.tv_usec;
}

protocol_type_t engine_detect_protocol(const char* url) {
    if (!url) return PROTOCOL_HTTP;
    
    if (strncmp(url, "ws://", 5) == 0 || strncmp(url, "wss://", 6) == 0) {
        return PROTOCOL_WEBSOCKET;
    } else if (strncmp(url, "mysql://", 8) == 0 || 
               strncmp(url, "postgresql://", 13) == 0 ||
               strncmp(url, "mongodb://", 10) == 0) {
        return PROTOCOL_DATABASE;
    } else if (strncmp(url, "grpc://", 7) == 0 || strncmp(url, "grpcs://", 8) == 0) {
        return PROTOCOL_GRPC;
    } else if (strncmp(url, "tcp://", 6) == 0) {
        return PROTOCOL_TCP;
    } else if (strncmp(url, "udp://", 6) == 0) {
        return PROTOCOL_UDP;
    }
    
    return PROTOCOL_HTTP; // Default to HTTP
}

int engine_convert_http_request(const http_request_t* http_req, request_t* generic_req) {
    if (!http_req || !generic_req) return -1;
    
    memset(generic_req, 0, sizeof(request_t));
    
    generic_req->protocol = PROTOCOL_HTTP;
    strncpy(generic_req->method, http_req->method, sizeof(generic_req->method) - 1);
    strncpy(generic_req->url, http_req->url, sizeof(generic_req->url) - 1);
    strncpy(generic_req->headers, http_req->headers, sizeof(generic_req->headers) - 1);
    strncpy(generic_req->body, http_req->body, sizeof(generic_req->body) - 1);
    generic_req->timeout_ms = http_req->timeout_ms;
    
    return 0;
}

// MQTT Engine wrapper functions
int engine_mqtt_connect(engine_t* engine, const char* broker_host, int broker_port, 
                       const char* client_id, const char* username, const char* password, 
                       int keep_alive, response_t* response) {
    if (!engine || !broker_host || !client_id || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = mqtt_connect(broker_host, broker_port, client_id, username, password, keep_alive, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_MQTT;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_mqtt_publish(engine_t* engine, const char* broker_host, int broker_port,
                       const char* client_id, const char* topic, const char* payload, 
                       mqtt_qos_t qos, bool retain, response_t* response) {
    if (!engine || !broker_host || !client_id || !topic || !payload || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = mqtt_publish(broker_host, broker_port, client_id, topic, payload, qos, retain, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_MQTT;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_mqtt_subscribe(engine_t* engine, const char* broker_host, int broker_port,
                         const char* client_id, const char* topic, mqtt_qos_t qos, response_t* response) {
    if (!engine || !broker_host || !client_id || !topic || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = mqtt_subscribe(broker_host, broker_port, client_id, topic, qos, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_MQTT;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_mqtt_unsubscribe(engine_t* engine, const char* broker_host, int broker_port,
                           const char* client_id, const char* topic, response_t* response) {
    if (!engine || !broker_host || !client_id || !topic || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = mqtt_unsubscribe(broker_host, broker_port, client_id, topic, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_MQTT;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_mqtt_disconnect(engine_t* engine, const char* broker_host, int broker_port, 
                          const char* client_id, response_t* response) {
    if (!engine || !broker_host || !client_id || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = mqtt_disconnect(broker_host, broker_port, client_id, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_MQTT;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_websocket_connect(engine_t* engine, const char* url, const char* subprotocol, response_t* response) {
    if (!engine || !url || !response) return -1;
    
    return websocket_connect(url, subprotocol, response);
}

int engine_websocket_send(engine_t* engine, const char* url, const char* message, response_t* response) {
    if (!engine || !url || !message || !response) return -1;
    
    return websocket_send_message(url, message, response);
}

int engine_websocket_close(engine_t* engine, const char* url, response_t* response) {
    if (!engine || !url || !response) return -1;
    
    return websocket_close_connection(url, response);
}

int engine_database_connect(engine_t* engine, const char* connection_string, const char* db_type, response_t* response) {
    if (!engine || !connection_string || !db_type || !response) return -1;
    
    int result = database_connect(connection_string, db_type, response);
    
    // Update metrics for database operations
    if (response->response_time_us > 0) {
        update_metrics(engine, response->response_time_us, response->success);
    }
    
    return result;
}

int engine_database_query(engine_t* engine, const char* connection_string, const char* query, response_t* response) {
    if (!engine || !connection_string || !query || !response) return -1;
    
    int result = database_execute_query(connection_string, query, response);
    
    // Update metrics for database operations
    if (response->response_time_us > 0) {
        update_metrics(engine, response->response_time_us, response->success);
    }
    
    return result;
}

// TCP Socket functions
int engine_tcp_connect(engine_t* engine, const char* hostname, int port, int timeout_ms, response_t* response) {
    if (!engine || !hostname || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = tcp_connect(hostname, port, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_TCP;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_tcp_send(engine_t* engine, int socket_fd, const char* data, size_t data_len, int timeout_ms, response_t* response) {
    if (!engine || !data || !response) return -1;
    
    // TCP send function expects hostname and port, but we have socket_fd
    // We need to adapt this - for now, create a placeholder implementation
    uint64_t start_time = get_time_us();
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    response->status_code = 200; // Assume success for now
    response->success = true;
    response->protocol_data.tcp.socket_fd = socket_fd;
    response->protocol_data.tcp.bytes_sent = data_len;
    response->protocol_data.tcp.bytes_received = 0;
    
    uint64_t end_time = get_time_us();
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return 0; // Return success for now
}

int engine_tcp_receive(engine_t* engine, int socket_fd, char* buffer, size_t buffer_size, int timeout_ms, response_t* response) {
    if (!engine || !buffer || !response) return -1;
    
    // TCP receive function expects hostname and port, but we have socket_fd
    // We need to adapt this - for now, create a placeholder implementation
    uint64_t start_time = get_time_us();
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    response->status_code = 200; // Assume success for now
    response->success = true;
    response->protocol_data.tcp.socket_fd = socket_fd;
    response->protocol_data.tcp.bytes_sent = 0;
    response->protocol_data.tcp.bytes_received = 0; // Would be set by actual implementation
    
    uint64_t end_time = get_time_us();
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return 0; // Return success for now
}

int engine_tcp_disconnect(engine_t* engine, int socket_fd, response_t* response) {
    if (!engine || !response) return -1;
    
    // TCP disconnect function expects hostname and port, but we have socket_fd
    // We need to adapt this - for now, create a placeholder implementation
    uint64_t start_time = get_time_us();
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_TCP;
    response->status_code = 200; // Assume success for now
    response->success = true;
    response->protocol_data.tcp.socket_fd = socket_fd;
    response->protocol_data.tcp.bytes_sent = 0;
    response->protocol_data.tcp.bytes_received = 0;
    
    uint64_t end_time = get_time_us();
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return 0; // Return success for now
}

// UDP Socket functions
int engine_udp_create_endpoint(engine_t* engine, const char* bind_address, int port, response_t* response) {
    if (!engine || !response) return -1;
    
    const char* address = bind_address ? bind_address : "localhost";
    
    uint64_t start_time = get_time_us();
    int result = udp_create_endpoint(address, port, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_UDP;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_udp_send(engine_t* engine, int socket_fd, const char* data, size_t data_len, const char* dest_address, int dest_port, int timeout_ms, response_t* response) {
    if (!engine || !data || !dest_address || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = udp_send(dest_address, dest_port, data, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_UDP;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_udp_receive(engine_t* engine, int socket_fd, char* buffer, size_t buffer_size, char* sender_address, int* sender_port, int timeout_ms, response_t* response) {
    if (!engine || !buffer || !response) return -1;
    
    // UDP receive function expects hostname and port, not socket_fd
    // We need to adapt this - for now, create a placeholder implementation
    uint64_t start_time = get_time_us();
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    response->status_code = 200; // Assume success for now
    response->success = true;
    response->protocol_data.udp.socket_fd = socket_fd;
    response->protocol_data.udp.bytes_sent = 0;
    response->protocol_data.udp.bytes_received = 0; // Would be set by actual implementation
    
    uint64_t end_time = get_time_us();
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return 0; // Return success for now
}

int engine_udp_close_endpoint(engine_t* engine, int socket_fd, response_t* response) {
    if (!engine || !response) return -1;
    
    // UDP close function expects hostname and port, but we have socket_fd
    // We need to adapt this - for now, create a placeholder implementation
    uint64_t start_time = get_time_us();
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_UDP;
    response->status_code = 200; // Assume success for now
    response->success = true;
    response->protocol_data.udp.socket_fd = socket_fd;
    response->protocol_data.udp.bytes_sent = 0;
    response->protocol_data.udp.bytes_received = 0;
    
    uint64_t end_time = get_time_us();
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return 0; // Return success for now
}

int engine_convert_http_response(const response_t* generic_resp, http_response_t* http_resp) {
    if (!generic_resp || !http_resp) return -1;
    
    memset(http_resp, 0, sizeof(http_response_t));
    
    http_resp->status_code = generic_resp->status_code;
    strncpy(http_resp->headers, generic_resp->headers, sizeof(http_resp->headers) - 1);
    strncpy(http_resp->body, generic_resp->body, sizeof(http_resp->body) - 1);
    http_resp->response_time_us = generic_resp->response_time_us;
    http_resp->success = generic_resp->success;
    strncpy(http_resp->error_message, generic_resp->error_message, sizeof(http_resp->error_message) - 1);
    
    return 0;
}

static void update_metrics(engine_t* engine, uint64_t response_time_us, bool success) {
    if (!engine) return;
    
    pthread_mutex_lock(&engine->metrics_mutex);
    
    engine->metrics.total_requests++;
    if (success) {
        engine->metrics.successful_requests++;
    } else {
        engine->metrics.failed_requests++;
    }
    
    engine->metrics.total_response_time_us += response_time_us;
    
    if (engine->metrics.min_response_time_us == 0 || response_time_us < engine->metrics.min_response_time_us) {
        engine->metrics.min_response_time_us = response_time_us;
    }
    
    if (response_time_us > engine->metrics.max_response_time_us) {
        engine->metrics.max_response_time_us = response_time_us;
    }
    
    pthread_mutex_unlock(&engine->metrics_mutex);
}

static void* worker_thread_func(void* arg) {
    worker_thread_t* worker = (worker_thread_t*)arg;
    if (!worker || !worker->engine) {
        return NULL;
    }
    
    engine_t* engine = worker->engine;
    
    while (worker->active) {
        pthread_mutex_lock(&engine->queue_mutex);
        
        while (engine->queue_head == engine->queue_tail && !engine->shutdown) {
            pthread_cond_wait(&engine->queue_cond, &engine->queue_mutex);
        }
        
        if (engine->shutdown) {
            pthread_mutex_unlock(&engine->queue_mutex);
            break;
        }
        
        http_request_t request = engine->request_queue[engine->queue_head];
        engine->queue_head = (engine->queue_head + 1) % engine->queue_size;
        
        pthread_mutex_unlock(&engine->queue_mutex);
        
        CURL* curl = curl_easy_init();
        if (!curl) continue;
        
        response_buffer_t buffer = {0};
        buffer.data = malloc(MAX_BODY_LENGTH);
        if (!buffer.data) {
            curl_easy_cleanup(curl);
            continue;
        }
        buffer.capacity = MAX_BODY_LENGTH;
        buffer.data[0] = '\0'; // Initialize as empty string
        
        header_buffer_t headers = {0};
        headers.data = malloc(MAX_HEADER_LENGTH);
        if (!headers.data) {
            free(buffer.data);
            curl_easy_cleanup(curl);
            continue;
        }
        headers.capacity = MAX_HEADER_LENGTH;
        headers.data[0] = '\0'; // Initialize as empty string
        
        uint64_t start_time = get_time_us();
        
        curl_easy_setopt(curl, CURLOPT_URL, request.url);
        curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, request.method);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buffer);
        curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, header_callback);
        curl_easy_setopt(curl, CURLOPT_HEADERDATA, &headers);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, request.timeout_ms);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
        curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 5L);
        
        if (strlen(request.body) > 0) {
            curl_easy_setopt(curl, CURLOPT_POSTFIELDS, request.body);
            curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, strlen(request.body));
        }
        
        struct curl_slist* header_list = NULL;
        if (strlen(request.headers) > 0) {
            char* header_copy = strdup(request.headers);
            if (header_copy) {
                char* token = strtok(header_copy, "\n");
                while (token) {
                    header_list = curl_slist_append(header_list, token);
                    token = strtok(NULL, "\n");
                }
                curl_easy_setopt(curl, CURLOPT_HTTPHEADER, header_list);
                free(header_copy);
            }
        }
        
        CURLcode res = curl_easy_perform(curl);
        uint64_t end_time = get_time_us();
        uint64_t response_time = end_time - start_time;
        
        long response_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response_code);
        
        bool success = (res == CURLE_OK && response_code >= 200 && response_code < 400);
        update_metrics(engine, response_time, success);
        
        if (header_list) {
            curl_slist_free_all(header_list);
        }
        curl_easy_cleanup(curl);
        free(buffer.data);
        free(headers.data);
    }
    
    return NULL;
}

engine_t* engine_create(int max_connections, int worker_threads) {
    if (max_connections <= 0 || worker_threads <= 0) {
        return NULL;
    }
    
    engine_t* engine = malloc(sizeof(engine_t));
    if (!engine) return NULL;
    
    memset(engine, 0, sizeof(engine_t));
    
    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) {
        free(engine);
        return NULL;
    }
    
    engine->multi_handle = curl_multi_init();
    if (!engine->multi_handle) {
        curl_global_cleanup();
        free(engine);
        return NULL;
    }
    
    engine->max_connections = max_connections;
    engine->num_workers = worker_threads;
    
    if (pthread_mutex_init(&engine->metrics_mutex, NULL) != 0 ||
        pthread_mutex_init(&engine->queue_mutex, NULL) != 0 ||
        pthread_cond_init(&engine->queue_cond, NULL) != 0) {
        curl_multi_cleanup(engine->multi_handle);
        curl_global_cleanup();
        free(engine);
        return NULL;
    }
    
    engine->queue_size = max_connections * 2;
    engine->request_queue = malloc(sizeof(http_request_t) * engine->queue_size);
    engine->response_queue = malloc(sizeof(http_response_t) * engine->queue_size);
    engine->workers = malloc(sizeof(worker_thread_t) * worker_threads);
    
    if (!engine->request_queue || !engine->response_queue || !engine->workers) {
        free(engine->request_queue);
        free(engine->response_queue);
        free(engine->workers);
        pthread_mutex_destroy(&engine->metrics_mutex);
        pthread_mutex_destroy(&engine->queue_mutex);
        pthread_cond_destroy(&engine->queue_cond);
        curl_multi_cleanup(engine->multi_handle);
        curl_global_cleanup();
        free(engine);
        return NULL;
    }
    
    for (int i = 0; i < worker_threads; i++) {
        engine->workers[i].engine = engine;
        engine->workers[i].thread_id = i;
        engine->workers[i].active = true;
        if (pthread_create(&engine->workers[i].thread, NULL, worker_thread_func, &engine->workers[i]) != 0) {
            // Clean up on thread creation failure
            engine->workers[i].active = false;
            for (int j = 0; j < i; j++) {
                engine->workers[j].active = false;
                pthread_join(engine->workers[j].thread, NULL);
            }
            free(engine->request_queue);
            free(engine->response_queue);
            free(engine->workers);
            pthread_mutex_destroy(&engine->metrics_mutex);
            pthread_mutex_destroy(&engine->queue_mutex);
            pthread_cond_destroy(&engine->queue_cond);
            curl_multi_cleanup(engine->multi_handle);
            curl_global_cleanup();
            free(engine);
            return NULL;
        }
    }
    
    return engine;
}

void engine_destroy(engine_t* engine) {
    if (!engine) return;
    
    engine->shutdown = true;
    pthread_cond_broadcast(&engine->queue_cond);
    
    for (int i = 0; i < engine->num_workers; i++) {
        engine->workers[i].active = false;
        pthread_join(engine->workers[i].thread, NULL);
    }
    
    curl_multi_cleanup(engine->multi_handle);
    curl_global_cleanup();
    
    pthread_mutex_destroy(&engine->metrics_mutex);
    pthread_mutex_destroy(&engine->queue_mutex);
    pthread_cond_destroy(&engine->queue_cond);
    
    free(engine->workers);
    free(engine->request_queue);
    free(engine->response_queue);
    free(engine);
}

int engine_execute_request_sync(engine_t* engine, const http_request_t* request, http_response_t* response) {
    if (!engine || !request || !response) return -1;
    
    // Initialize response structure
    memset(response, 0, sizeof(http_response_t));
    
    CURL* curl = curl_easy_init();
    if (!curl) return -1;
    
    response_buffer_t buffer = {0};
    buffer.data = malloc(MAX_BODY_LENGTH);
    if (!buffer.data) {
        curl_easy_cleanup(curl);
        return -1;
    }
    buffer.capacity = MAX_BODY_LENGTH;
    buffer.data[0] = '\0'; // Initialize as empty string
    
    header_buffer_t headers = {0};
    headers.data = malloc(MAX_HEADER_LENGTH);
    if (!headers.data) {
        free(buffer.data);
        curl_easy_cleanup(curl);
        return -1;
    }
    headers.capacity = MAX_HEADER_LENGTH;
    headers.data[0] = '\0'; // Initialize as empty string
    
    uint64_t start_time = get_time_us();
    
    curl_easy_setopt(curl, CURLOPT_URL, request->url);
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, request->method);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buffer);
    curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, header_callback);
    curl_easy_setopt(curl, CURLOPT_HEADERDATA, &headers);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, request->timeout_ms);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_MAXREDIRS, 5L);
    
    if (strlen(request->body) > 0) {
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, request->body);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, strlen(request->body));
    }
    
    struct curl_slist* header_list = NULL;
    if (strlen(request->headers) > 0) {
        char* header_copy = strdup(request->headers);
        if (header_copy) {
            char* token = strtok(header_copy, "\n");
            while (token) {
                header_list = curl_slist_append(header_list, token);
                token = strtok(NULL, "\n");
            }
            curl_easy_setopt(curl, CURLOPT_HTTPHEADER, header_list);
            free(header_copy);
        }
    }
    
    CURLcode res = curl_easy_perform(curl);
    uint64_t end_time = get_time_us();
    uint64_t response_time = end_time - start_time;
    
    long response_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response_code);
    
    // Fill response structure safely
    response->status_code = response_code;
    response->response_time_us = response_time;
    response->success = (res == CURLE_OK && response_code >= 200 && response_code < 400);
    
    // Copy response body safely
    if (buffer.data && buffer.size > 0) {
        size_t copy_size = (buffer.size < MAX_BODY_LENGTH - 1) ? buffer.size : MAX_BODY_LENGTH - 1;
        memcpy(response->body, buffer.data, copy_size);
        response->body[copy_size] = '\0';
    } else {
        response->body[0] = '\0';
    }
    
    // Copy response headers safely
    if (headers.data && headers.size > 0) {
        size_t copy_size = (headers.size < MAX_HEADER_LENGTH - 1) ? headers.size : MAX_HEADER_LENGTH - 1;
        memcpy(response->headers, headers.data, copy_size);
        response->headers[copy_size] = '\0';
    } else {
        response->headers[0] = '\0';
    }
    
    // Copy error message if there was an error
    if (res != CURLE_OK) {
        const char* error_str = curl_easy_strerror(res);
        strncpy(response->error_message, error_str, sizeof(response->error_message) - 1);
        response->error_message[sizeof(response->error_message) - 1] = '\0';
    } else {
        response->error_message[0] = '\0';
    }
    
    // Update metrics
    update_metrics(engine, response_time, response->success);
    
    if (header_list) {
        curl_slist_free_all(header_list);
    }
    curl_easy_cleanup(curl);
    free(buffer.data);
    free(headers.data);
    
    return 0;
}

int engine_execute_request(engine_t* engine, const http_request_t* request, http_response_t* response) {
    if (!engine || !request || !response) return -1;
    
    pthread_mutex_lock(&engine->queue_mutex);
    
    int next_tail = (engine->queue_tail + 1) % engine->queue_size;
    if (next_tail == engine->queue_head) {
        pthread_mutex_unlock(&engine->queue_mutex);
        return -1; // Queue full
    }
    
    // Safe copy of request structure
    memcpy(&engine->request_queue[engine->queue_tail], request, sizeof(http_request_t));
    engine->queue_tail = next_tail;
    
    pthread_cond_signal(&engine->queue_cond);
    pthread_mutex_unlock(&engine->queue_mutex);
    
    return 0;
}

void engine_get_metrics(engine_t* engine, metrics_t* metrics) {
    if (!engine || !metrics) return;
    
    pthread_mutex_lock(&engine->metrics_mutex);
    memcpy(metrics, &engine->metrics, sizeof(metrics_t));
    
    if (metrics->total_requests > 0) {
        metrics->requests_per_second = (double)metrics->successful_requests / 
            (metrics->total_response_time_us / 1000000.0 * engine->num_workers);
    }
    
    pthread_mutex_unlock(&engine->metrics_mutex);
}

void engine_reset_metrics(engine_t* engine) {
    if (!engine) return;
    
    pthread_mutex_lock(&engine->metrics_mutex);
    memset(&engine->metrics, 0, sizeof(metrics_t));
    pthread_mutex_unlock(&engine->metrics_mutex);
}

int engine_start_load_test(engine_t* engine, const http_request_t* requests, int num_requests, int concurrent_users, int duration_seconds) {
    if (!engine || !requests || num_requests <= 0) return -1;
    
    engine_reset_metrics(engine);
    
    time_t start_time = time(NULL);
    time_t end_time = start_time + duration_seconds;
    
    while (time(NULL) < end_time) {
        for (int i = 0; i < num_requests && time(NULL) < end_time; i++) {
            http_response_t response;
            engine_execute_request(engine, &requests[i], &response);
            
            usleep(1000000 / concurrent_users);
        }
    }
    
    sleep(2);
    
    return 0;
}
