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
#include <sys/select.h>
#include <stdatomic.h>
#include <unistd.h>

typedef struct {
    char* data;
    size_t size;
    size_t capacity;
} response_buffer_t;

#define BODY_BUFFER_INITIAL   (16 * 1024)
#define HEADER_BUFFER_INITIAL (4 * 1024)

typedef struct worker_thread {
    pthread_t thread;
    engine_t* engine;
    int thread_id;
    _Atomic bool active;
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
    int queue_size;
    int queue_head;
    int queue_tail;
    _Atomic bool shutdown;
    _Atomic int stop_flag;    /* cooperative cancel signal; set to 1 to stop load-test workers */
    bool load_test_active;    /* true while a load test is running; blocks pool workers from dequeuing */
    struct timeval test_start_time;  /* wall-clock time when load test started */
};

/* Append to a growable, always-NUL-terminated buffer. Doubles capacity as
   needed, hard-capped at HTTP_RESPONSE_BUFFER_MAX. Returns 0 on success,
   -1 on OOM or cap exceeded (buffer contents stay valid). */
static int buffer_append(response_buffer_t* buffer, size_t initial_capacity,
                         const char* contents, size_t total_size) {
    size_t required_size = buffer->size + total_size + 1; // +1 for null terminator
    if (required_size < total_size || required_size > HTTP_RESPONSE_BUFFER_MAX) {
        return -1; // overflow or over the safety cap
    }

    if (required_size > buffer->capacity) {
        size_t new_capacity = buffer->capacity ? buffer->capacity : initial_capacity;
        while (new_capacity < required_size) {
            new_capacity *= 2;
        }
        if (new_capacity > HTTP_RESPONSE_BUFFER_MAX) {
            new_capacity = HTTP_RESPONSE_BUFFER_MAX;
        }
        char* new_data = realloc(buffer->data, new_capacity);
        if (!new_data) {
            return -1;
        }
        buffer->data = new_data;
        buffer->capacity = new_capacity;
    }

    if (total_size > 0) {
        memcpy(buffer->data + buffer->size, contents, total_size);
        buffer->size += total_size;
    }
    buffer->data[buffer->size] = '\0';
    return 0;
}

static size_t write_callback(char* contents, size_t size, size_t nmemb, void* userdata) {
    response_buffer_t* buffer = (response_buffer_t*)userdata;
    size_t total_size = size * nmemb;

    if (!buffer || !contents) {
        return 0;
    }
    if (buffer_append(buffer, BODY_BUFFER_INITIAL, contents, total_size) != 0) {
        return 0; // abort the transfer (curl reports a write error)
    }
    return total_size;
}

static size_t header_callback(char* contents, size_t size, size_t nmemb, void* userdata) {
    response_buffer_t* buffer = (response_buffer_t*)userdata;
    size_t total_size = size * nmemb;

    if (!buffer || !contents) {
        return 0;
    }
    /* Header storage failure (OOM/cap) drops the header block but does not
       abort the transfer: always report success to cURL. */
    (void)buffer_append(buffer, HEADER_BUFFER_INITIAL, contents, total_size);
    return total_size;
}

void http_response_free(http_response_t* response) {
    if (!response) return;
    free(response->headers);
    free(response->body);
    response->headers = NULL;
    response->body = NULL;
    response->body_len = 0;
}

// Removed static get_time_us as it conflicts with mqtt.h declaration

// Forward declaration for update_metrics
static void update_metrics(engine_t* engine, uint64_t response_time_us, bool success);

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
    /* snprintf (not strncpy) so the copy always null-terminates and gcc's
       -Wstringop-truncation doesn't fire on these same-sized field copies. */
    snprintf(generic_req->method, sizeof(generic_req->method), "%s", http_req->method);
    snprintf(generic_req->url, sizeof(generic_req->url), "%s", http_req->url);
    snprintf(generic_req->headers, sizeof(generic_req->headers), "%s", http_req->headers);
    snprintf(generic_req->body, sizeof(generic_req->body), "%s", http_req->body);
    generic_req->timeout_ms = http_req->timeout_ms;
    
    return 0;
}

// MQTT Engine wrapper functions
int engine_mqtt_connect(engine_t* engine, const char* broker_host, int broker_port,
                       const char* client_id, const char* username, const char* password,
                       int keep_alive, response_t* response) {
    return engine_mqtt_connect_tls(engine, broker_host, broker_port, client_id,
                                   username, password, keep_alive, false, true, response);
}

int engine_mqtt_connect_tls(engine_t* engine, const char* broker_host, int broker_port,
                            const char* client_id, const char* username, const char* password,
                            int keep_alive, bool use_tls, bool tls_verify, response_t* response) {
    if (!engine || !broker_host || !client_id || !response) return -1;

    uint64_t start_time = get_time_us();
    int result = mqtt_connect_tls(broker_host, broker_port, client_id, username, password,
                                  keep_alive, use_tls, tls_verify, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_MQTT;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_mqtt_publish(engine_t* engine, const char* host, int port, const char* client_id,
                       const char* topic, const char* message, int qos, bool retain, response_t* response) {
    if (!engine || !host || !client_id || !topic || !message || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = mqtt_publish(host, port, client_id, topic, message, (mqtt_qos_t)qos, retain, response);
    uint64_t end_time = get_time_us();
    
    // Set protocol and timing information
    response->protocol = PROTOCOL_MQTT;
    response->response_time_us = end_time - start_time;
    
    // Update metrics
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_mqtt_subscribe(engine_t* engine, const char* host, int port, const char* client_id,
                         const char* topic, int qos, response_t* response) {
    if (!engine || !host || !client_id || !topic || !response) return -1;
    
    uint64_t start_time = get_time_us();
    int result = mqtt_subscribe(host, port, client_id, topic, (mqtt_qos_t)qos, response);
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

int engine_database_connect(engine_t* engine, const char* connection_string, const char* conn_id, const char* db_type, response_t* response) {
    if (!engine || !connection_string || !db_type || !response) return -1;

    int result = database_connect(connection_string, conn_id, db_type, response);
    
    // Update metrics for database operations
    update_metrics(engine, response->response_time_us, response->success);
    
    return result;
}

int engine_database_query(engine_t* engine, const char* connection_string, const char* conn_id, const char* query, response_t* response) {
    if (!engine || !connection_string || !query || !response) return -1;

    int result = database_execute_query(connection_string, conn_id, query, response);

    // Update metrics for database operations
    update_metrics(engine, response->response_time_us, response->success);

    return result;
}

int engine_database_disconnect(engine_t* engine, const char* connection_string, const char* conn_id, response_t* response) {
    if (!engine || !connection_string || !response) return -1;

    int result = database_disconnect(connection_string, conn_id, response);

    update_metrics(engine, response->response_time_us, response->success);

    return result;
}


int engine_convert_http_response(const response_t* generic_resp, http_response_t* http_resp) {
    if (!generic_resp || !http_resp) return -1;

    memset(http_resp, 0, sizeof(http_response_t));

    http_resp->status_code = generic_resp->status_code;
    /* http_response_t owns heap copies now; caller releases with
       http_response_free(). */
    http_resp->headers = strdup(generic_resp->headers);
    http_resp->body = strdup(generic_resp->body);
    if (!http_resp->headers || !http_resp->body) {
        http_response_free(http_resp);
        return -1;
    }
    http_resp->body_len = strlen(http_resp->body);
    http_resp->response_time_us = generic_resp->response_time_us;
    http_resp->success = generic_resp->success;
    snprintf(http_resp->error_message, sizeof(http_resp->error_message), "%s", generic_resp->error_message);

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

    /* Insert into histogram (O(1)) */
    size_t bucket = response_time_us / 1000;  /* 1ms buckets */
    if (bucket >= HISTOGRAM_BUCKET_COUNT) {
        bucket = HISTOGRAM_OVERFLOW_INDEX;
    }
    engine->metrics.histogram_buckets[bucket]++;

    pthread_mutex_unlock(&engine->metrics_mutex);
}

/* Perform a single HTTP request with libcurl and fill `response` completely.
   Shared by the synchronous path and both worker pools to avoid triplicating
   the curl setup/teardown. On any setup failure the response is marked
   unsuccessful with an explanatory error_message.
   The response owns its heap body/headers; callers must release them with
   http_response_free(). Buffers grow to the actual response size (see
   buffer_append), so bodies are no longer truncated at MAX_BODY_LENGTH. */
static void http_execute(const http_request_t* request, http_response_t* response) {
    memset(response, 0, sizeof(http_response_t));

    CURL* curl = curl_easy_init();
    if (!curl) {
        strncpy(response->error_message, "Failed to initialize CURL handle",
                sizeof(response->error_message) - 1);
        return;
    }

    /* Grown lazily by the callbacks; ownership moves into the response below. */
    response_buffer_t buffer = {0};
    response_buffer_t headers = {0};

    uint64_t start_time = get_time_us();

    curl_easy_setopt(curl, CURLOPT_URL, request->url);
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, request->method);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buffer);
    curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, header_callback);
    curl_easy_setopt(curl, CURLOPT_HEADERDATA, &headers);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, (long)(request->timeout_ms > 0 ? request->timeout_ms : 30000));
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
    uint64_t response_time = get_time_us() - start_time;

    long response_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response_code);

    response->status_code = response_code;
    response->response_time_us = response_time;
    response->success = (res == CURLE_OK && response_code >= 200 && response_code < 400);

    /* Transfer buffer ownership into the response (NULL when nothing arrived;
       consumers treat NULL as empty). */
    response->body = buffer.data;
    response->body_len = buffer.size;
    response->headers = headers.data;

    if (res != CURLE_OK) {
        if (res == CURLE_WRITE_ERROR) {
            snprintf(response->error_message, sizeof(response->error_message),
                     "Response exceeded %lu MiB buffer cap (or out of memory)",
                     (unsigned long)(HTTP_RESPONSE_BUFFER_MAX / (1024 * 1024)));
        } else {
            strncpy(response->error_message, curl_easy_strerror(res), sizeof(response->error_message) - 1);
            response->error_message[sizeof(response->error_message) - 1] = '\0';
        }
    }

    if (header_list) curl_slist_free_all(header_list);
    curl_easy_cleanup(curl);
}

static void* worker_thread_func(void* arg) {
    worker_thread_t* worker = (worker_thread_t*)arg;
    if (!worker || !worker->engine) {
        return NULL;
    }

    engine_t* engine = worker->engine;

    while (worker->active) {
        pthread_mutex_lock(&engine->queue_mutex);

        while ((engine->queue_head == engine->queue_tail || engine->load_test_active) && !engine->shutdown) {
            pthread_cond_wait(&engine->queue_cond, &engine->queue_mutex);
        }

        if (engine->shutdown) {
            pthread_mutex_unlock(&engine->queue_mutex);
            break;
        }

        http_request_t request = engine->request_queue[engine->queue_head];
        engine->queue_head = (engine->queue_head + 1) % engine->queue_size;

        pthread_mutex_unlock(&engine->queue_mutex);

        http_response_t response;
        http_execute(&request, &response);
        update_metrics(engine, response.response_time_us, response.success);
        http_response_free(&response);
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
    engine->workers = malloc(sizeof(worker_thread_t) * worker_threads);

    if (!engine->request_queue || !engine->workers) {
        free(engine->request_queue);
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

/* Public wrapper so callers outside this translation unit (e.g. the Python
   extension wrapping TCP/UDP/MQTT/Database calls) can fold a single operation
   into the engine metrics. */
void engine_record_metrics(engine_t* engine, uint64_t response_time_us, bool success) {
    update_metrics(engine, response_time_us, success);
}

void engine_destroy(engine_t* engine) {
    if (!engine) return;
    
    engine->shutdown = true;
    pthread_cond_broadcast(&engine->queue_cond);
    
    for (int i = 0; i < engine->num_workers; i++) {
        engine->workers[i].active = false;
        pthread_join(engine->workers[i].thread, NULL);
    }
    
    // Clean up all protocol connection pools
    tcp_cleanup_all();
    udp_cleanup_all();
    mqtt_cleanup_all();
    websocket_cleanup_all();
    database_cleanup_all();
    
    curl_multi_cleanup(engine->multi_handle);
    curl_global_cleanup();
    
    pthread_mutex_destroy(&engine->metrics_mutex);
    pthread_mutex_destroy(&engine->queue_mutex);
    pthread_cond_destroy(&engine->queue_cond);
    
    free(engine->workers);
    free(engine->request_queue);
    free(engine);
}

int engine_execute_request_sync(engine_t* engine, const http_request_t* request, http_response_t* response) {
    if (!engine || !request || !response) return -1;

    http_execute(request, response);
    update_metrics(engine, response->response_time_us, response->success);

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

    /* RPS: use wall-clock elapsed time, not cumulative response time */
    struct timeval now;
    gettimeofday(&now, NULL);
    double elapsed_sec = (now.tv_sec - engine->test_start_time.tv_sec) +
                         (now.tv_usec - engine->test_start_time.tv_usec) / 1000000.0;
    if (elapsed_sec > 0.0 && metrics->total_requests > 0) {
        metrics->requests_per_second = (double)metrics->total_requests / elapsed_sec;
    } else {
        metrics->requests_per_second = 0.0;
    }

    /* Percentile computation from histogram */
    if (metrics->total_requests > 0) {
        uint64_t p95_target = (uint64_t)(metrics->total_requests * 0.95);
        uint64_t p99_target = (uint64_t)(metrics->total_requests * 0.99);
        uint64_t cumulative = 0;
        bool p95_set = false, p99_set = false;

        for (int i = 0; i < HISTOGRAM_BUCKET_COUNT; i++) {
            cumulative += metrics->histogram_buckets[i];
            if (!p95_set && cumulative >= p95_target) {
                metrics->p95_us = (uint64_t)(i + 1) * 1000;
                p95_set = true;
            }
            if (!p99_set && cumulative >= p99_target) {
                metrics->p99_us = (uint64_t)(i + 1) * 1000;
                p99_set = true;
                break;
            }
        }
        /* If not set (all in overflow bucket), use max */
        if (!p95_set) metrics->p95_us = metrics->max_response_time_us;
        if (!p99_set) metrics->p99_us = metrics->max_response_time_us;
    } else {
        metrics->p95_us = 0;
        metrics->p99_us = 0;
    }

    pthread_mutex_unlock(&engine->metrics_mutex);
}

void engine_reset_metrics(engine_t* engine) {
    if (!engine) return;
    
    pthread_mutex_lock(&engine->metrics_mutex);
    memset(&engine->metrics, 0, sizeof(metrics_t));
    pthread_mutex_unlock(&engine->metrics_mutex);
}

/* True when a is at or after b. */
static inline int tv_reached(struct timeval a, struct timeval b) {
    return (a.tv_sec > b.tv_sec) ||
           (a.tv_sec == b.tv_sec && a.tv_usec >= b.tv_usec);
}

/* Per-worker context for a sustained, optionally ramped, load test. The struct
   lives on the launching thread's stack until it joins all workers. */
typedef struct {
    engine_t* engine;
    const http_request_t* requests;
    int num_requests;
    _Atomic int* next_index;        /* shared round-robin request selector */
    struct timeval activate_time;   /* when this worker begins (ramp stagger) */
    struct timeval end_time;        /* when the whole test ends */
    bool started;                   /* pthread_create succeeded → must join */
} load_worker_t;

static void* sustained_worker_func(void* arg) {
    load_worker_t* w = (load_worker_t*)arg;
    engine_t* engine = w->engine;

    /* Ramp: wait until this worker's activation time (cooperatively cancellable). */
    while (!atomic_load(&engine->stop_flag)) {
        struct timeval now;
        gettimeofday(&now, NULL);
        if (tv_reached(now, w->activate_time)) break;
        struct timeval tv = {0, 20000};  /* 20 ms */
        select(0, NULL, NULL, NULL, &tv);
    }

    /* Sustained load: cycle through the request set until the duration elapses.
       stop_flag=1 does not abort an in-flight perform; it only prevents the next. */
    while (!atomic_load(&engine->stop_flag)) {
        struct timeval now;
        gettimeofday(&now, NULL);
        if (tv_reached(now, w->end_time)) break;

        int idx = atomic_fetch_add(w->next_index, 1) % w->num_requests;
        http_request_t request = w->requests[idx];
        http_response_t response;
        http_execute(&request, &response);
        update_metrics(engine, response.response_time_us, response.success);
        http_response_free(&response);
    }

    return NULL;
}

int engine_start_load_test(engine_t* engine, const http_request_t* requests,
                           int num_requests, int concurrent_users,
                           int duration_seconds, int ramp_up_seconds) {
    if (!engine || !requests || num_requests <= 0 || concurrent_users <= 0) return -1;
    if (duration_seconds < 0) duration_seconds = 0;
    if (ramp_up_seconds < 0) ramp_up_seconds = 0;
    if (ramp_up_seconds > duration_seconds) ramp_up_seconds = duration_seconds;

    /* 1. Keep a stable copy of the request set; workers cycle over it for the
       whole test. queue_head/tail stay equal (empty) so the async pool path is
       unaffected, and load_test_active blocks the persistent pool workers. */
    pthread_mutex_lock(&engine->queue_mutex);

    if (num_requests > engine->queue_size) {
        http_request_t* new_queue = realloc(engine->request_queue,
                                            sizeof(http_request_t) * num_requests);
        if (!new_queue) {
            pthread_mutex_unlock(&engine->queue_mutex);
            return -1;
        }
        engine->request_queue = new_queue;
        engine->queue_size    = num_requests;
    }
    for (int i = 0; i < num_requests; i++) {
        memcpy(&engine->request_queue[i], &requests[i], sizeof(http_request_t));
    }
    engine->queue_head = 0;
    engine->queue_tail = 0;
    atomic_store(&engine->stop_flag, 0);
    engine->load_test_active = true;

    pthread_mutex_unlock(&engine->queue_mutex);

    /* 2. Wall-clock start (RPS) plus the test/ramp time bounds. */
    gettimeofday(&engine->test_start_time, NULL);
    struct timeval start = engine->test_start_time;
    struct timeval end_time = start;
    end_time.tv_sec += duration_seconds;

    int actual_workers = concurrent_users;
    load_worker_t* lw  = malloc(sizeof(load_worker_t) * actual_workers);
    pthread_t* threads = malloc(sizeof(pthread_t) * actual_workers);
    if (!lw || !threads) {
        free(lw); free(threads);
        pthread_mutex_lock(&engine->queue_mutex);
        engine->load_test_active = false;
        pthread_cond_broadcast(&engine->queue_cond);
        pthread_mutex_unlock(&engine->queue_mutex);
        return -1;
    }

    /* Shared round-robin selector; lives until the join loop below. */
    _Atomic int next_index = 0;
    long ramp_us = (long)ramp_up_seconds * 1000000L;

    /* 3. Spawn workers. Each self-gates on its activation time so load ramps up
       smoothly across ramp_up_seconds instead of arriving all at once. */
    int spawned = 0;
    for (int i = 0; i < actual_workers; i++) {
        lw[i].engine       = engine;
        lw[i].requests     = engine->request_queue;
        lw[i].num_requests = num_requests;
        lw[i].next_index   = &next_index;
        lw[i].end_time     = end_time;
        lw[i].started      = false;

        long offset_us = (actual_workers > 1) ? (ramp_us * i) / (actual_workers - 1) : 0;
        struct timeval act = start;
        act.tv_sec  += offset_us / 1000000L;
        act.tv_usec += offset_us % 1000000L;
        if (act.tv_usec >= 1000000L) { act.tv_sec += 1; act.tv_usec -= 1000000L; }
        lw[i].activate_time = act;

        if (pthread_create(&threads[i], NULL, sustained_worker_func, &lw[i]) == 0) {
            lw[i].started = true;
            spawned++;
        }
    }

    if (spawned == 0) {
        free(lw); free(threads);
        pthread_mutex_lock(&engine->queue_mutex);
        engine->load_test_active = false;
        pthread_cond_broadcast(&engine->queue_cond);
        pthread_mutex_unlock(&engine->queue_mutex);
        return -1;
    }

    /* 4. Wait out the duration (hard cap = duration + 5s grace), then stop. */
    time_t hard_stop = time(NULL) + duration_seconds + 5;
    for (;;) {
        struct timeval now;
        gettimeofday(&now, NULL);
        if (tv_reached(now, end_time) || time(NULL) >= hard_stop) {
            atomic_store(&engine->stop_flag, 1);
            break;
        }
        struct timeval tv = {0, 50000};  /* 50 ms poll */
        select(0, NULL, NULL, NULL, &tv);
    }

    /* 5. Join workers (each finishes its in-flight request then exits). */
    for (int i = 0; i < actual_workers; i++) {
        if (lw[i].started) pthread_join(threads[i], NULL);
    }

    /* 6. Unblock the persistent pool workers. */
    pthread_mutex_lock(&engine->queue_mutex);
    engine->load_test_active = false;
    pthread_cond_broadcast(&engine->queue_cond);
    pthread_mutex_unlock(&engine->queue_mutex);

    free(lw);
    free(threads);
    return 0;
}
