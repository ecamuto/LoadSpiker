#include "websocket.h"
#include "../engine.h"
#include "../common.h"   /* shared monotonic get_time_us() */
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <pthread.h>
#include <unistd.h>

#ifdef HAVE_CURL_WEBSOCKETS
#include <curl/curl.h>
#endif

/* WebSocket connection context.
 *
 * When built against a libcurl with the WebSocket API (HAVE_CURL_WEBSOCKETS),
 * connect/send/close drive real RFC 6455 frames via curl_ws_send/curl_ws_recv.
 * Otherwise the calls fall back to the original simulated behaviour so the
 * extension still builds where libcurl lacks WebSocket support.
 *
 * One context (and one CURL handle) per URL — a CURL easy handle is not safe
 * for concurrent use, so concurrent virtual users targeting the *same* ws URL
 * share state (same limitation as the other protocol pools). */
typedef struct {
    char url[MAX_URL_LENGTH];
    char subprotocol[256];
    bool connected;
    uint64_t messages_sent;
    uint64_t messages_received;
    uint64_t bytes_sent;
    uint64_t bytes_received;
#ifdef HAVE_CURL_WEBSOCKETS
    CURL* curl;
#endif
} websocket_context_t;

// Simple connection management
#define MAX_WS_CONNECTIONS 1000
static websocket_context_t* ws_connections[MAX_WS_CONNECTIONS] = {0};
static pthread_mutex_t ws_connections_mutex = PTHREAD_MUTEX_INITIALIZER;

// Find or create WebSocket connection context
static websocket_context_t* get_websocket_connection(const char* url) {
    pthread_mutex_lock(&ws_connections_mutex);

    // Look for existing connection
    for (int i = 0; i < MAX_WS_CONNECTIONS; i++) {
        if (ws_connections[i] && strcmp(ws_connections[i]->url, url) == 0) {
            pthread_mutex_unlock(&ws_connections_mutex);
            return ws_connections[i];
        }
    }

    // Create new connection
    for (int i = 0; i < MAX_WS_CONNECTIONS; i++) {
        if (!ws_connections[i]) {
            ws_connections[i] = malloc(sizeof(websocket_context_t));
            if (!ws_connections[i]) {
                pthread_mutex_unlock(&ws_connections_mutex);
                return NULL;
            }
            memset(ws_connections[i], 0, sizeof(websocket_context_t));
            strncpy(ws_connections[i]->url, url, sizeof(ws_connections[i]->url) - 1);
            pthread_mutex_unlock(&ws_connections_mutex);
            return ws_connections[i];
        }
    }

    pthread_mutex_unlock(&ws_connections_mutex);
    return NULL; // No available slots
}

int websocket_connect(const char* url, const char* subprotocol, response_t* response) {
    if (!url || !response) return -1;

    websocket_context_t* ctx = get_websocket_connection(url);
    if (!ctx) {
        strncpy(response->error_message, "Too many WebSocket connections", sizeof(response->error_message) - 1);
        return -1;
    }

    if (ctx->connected) {
        response->success = true;
        response->status_code = 101; // Switching Protocols
        return 0; // Already connected
    }

    uint64_t start_time = get_time_us();

    if (subprotocol && strlen(subprotocol) > 0) {
        strncpy(ctx->subprotocol, subprotocol, sizeof(ctx->subprotocol) - 1);
    }

    response->protocol = PROTOCOL_WEBSOCKET;

#ifdef HAVE_CURL_WEBSOCKETS
    CURL* curl = curl_easy_init();
    if (!curl) {
        strncpy(response->error_message, "Failed to initialize libcurl for WebSocket",
                sizeof(response->error_message) - 1);
        response->success = false;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_CONNECT_ONLY, 2L); // perform the WS handshake only
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);     // don't hang forever
    if (getenv("LOADSPIKER_WS_DEBUG")) {
        curl_easy_setopt(curl, CURLOPT_VERBOSE, 1L);
    }

    struct curl_slist* headers = NULL;
    if (ctx->subprotocol[0]) {
        char hdr[320];
        snprintf(hdr, sizeof(hdr), "Sec-WebSocket-Protocol: %s", ctx->subprotocol);
        headers = curl_slist_append(NULL, hdr);
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    }

    CURLcode res = curl_easy_perform(curl);
    if (headers) curl_slist_free_all(headers);

    if (res != CURLE_OK) {
        snprintf(response->error_message, sizeof(response->error_message),
                "WebSocket handshake failed: %s", curl_easy_strerror(res));
        curl_easy_cleanup(curl);
        response->success = false;
        response->status_code = 0;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    ctx->curl = curl;
    ctx->connected = true;

    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    response->status_code = http_code ? (int)http_code : 101;
    strncpy(response->body, "WebSocket connection established",
            sizeof(response->body) - 1);
#else
    // Simulated handshake (libcurl built without WebSocket support)
    usleep(10000); // 10ms to simulate network
    ctx->connected = true;
    response->status_code = 101; // Switching Protocols
    strncpy(response->body, "WebSocket connection established (simulated)", sizeof(response->body) - 1);
    strncpy(response->headers, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade", sizeof(response->headers) - 1);
#endif

    response->response_time_us = get_time_us() - start_time;
    response->success = true;

    // Set WebSocket-specific response data
    strncpy(response->protocol_data.websocket.subprotocol, ctx->subprotocol,
            sizeof(response->protocol_data.websocket.subprotocol) - 1);

    return 0;
}

int websocket_send_message(const char* url, const char* message, response_t* response) {
    if (!url || !message || !response) return -1;

    websocket_context_t* ctx = get_websocket_connection(url);
    if (!ctx || !ctx->connected) {
        strncpy(response->error_message, "WebSocket not connected", sizeof(response->error_message) - 1);
        return -1;
    }

    uint64_t start_time = get_time_us();
    size_t message_len = strlen(message);
    response->protocol = PROTOCOL_WEBSOCKET;

#ifdef HAVE_CURL_WEBSOCKETS
    size_t sent = 0;
    CURLcode res = curl_ws_send(ctx->curl, message, message_len, &sent, 0, CURLWS_TEXT);
    if (res != CURLE_OK) {
        snprintf(response->error_message, sizeof(response->error_message),
                "WebSocket send failed: %s", curl_easy_strerror(res));
        response->success = false;
        response->status_code = 500;
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    ctx->messages_sent++;
    ctx->bytes_sent += sent;
    snprintf(response->body, sizeof(response->body), "Message sent: %zu bytes", sent);
#else
    // Simulated send
    usleep(1000); // 1ms to simulate network
    ctx->messages_sent++;
    ctx->bytes_sent += message_len;
    snprintf(response->body, sizeof(response->body), "Message sent: %zu bytes (simulated)", message_len);
#endif

    response->success = true;
    response->status_code = 200;
    response->response_time_us = get_time_us() - start_time;
    response->protocol_data.websocket.messages_sent = (int)ctx->messages_sent;
    response->protocol_data.websocket.bytes_sent = ctx->bytes_sent;

    return 0;
}

int websocket_close_connection(const char* url, response_t* response) {
    if (!url || !response) return -1;

    websocket_context_t* ctx = get_websocket_connection(url);
    if (!ctx || !ctx->connected) {
        response->success = true; // Already closed
        response->status_code = 200;
        response->protocol = PROTOCOL_WEBSOCKET;
        strcpy(response->body, "WebSocket connection already closed");
        return 0;
    }

    uint64_t start_time = get_time_us();
    response->protocol = PROTOCOL_WEBSOCKET;

#ifdef HAVE_CURL_WEBSOCKETS
    if (ctx->curl) {
        size_t sent = 0;
        // Best-effort CLOSE frame, then tear down the handle
        curl_ws_send(ctx->curl, "", 0, &sent, 0, CURLWS_CLOSE);
        curl_easy_cleanup(ctx->curl);
        ctx->curl = NULL;
    }
    strcpy(response->body, "WebSocket connection closed");
#else
    usleep(5000); // 5ms to simulate network
    strcpy(response->body, "WebSocket connection closed (simulated)");
#endif

    ctx->connected = false;

    response->success = true;
    response->status_code = 200;
    response->response_time_us = get_time_us() - start_time;

    // Clean up connection context
    pthread_mutex_lock(&ws_connections_mutex);
    for (int i = 0; i < MAX_WS_CONNECTIONS; i++) {
        if (ws_connections[i] == ctx) {
            free(ws_connections[i]);
            ws_connections[i] = NULL;
            break;
        }
    }
    pthread_mutex_unlock(&ws_connections_mutex);

    return 0;
}

void websocket_cleanup_all(void) {
    pthread_mutex_lock(&ws_connections_mutex);
    for (int i = 0; i < MAX_WS_CONNECTIONS; i++) {
        if (ws_connections[i]) {
#ifdef HAVE_CURL_WEBSOCKETS
            if (ws_connections[i]->curl) {
                curl_easy_cleanup(ws_connections[i]->curl);
                ws_connections[i]->curl = NULL;
            }
#endif
            free(ws_connections[i]);
            ws_connections[i] = NULL;
        }
    }
    pthread_mutex_unlock(&ws_connections_mutex);
}
