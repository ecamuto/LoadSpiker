#ifndef COMMON_H
#define COMMON_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>

/*
 * ============================================================================
 * LoadSpiker Common Definitions
 * ============================================================================
 * 
 * This file contains shared constants, macros, and utility functions used
 * across all protocol implementations in the LoadSpiker load testing tool.
 */

/* ---------------------------------------------------------------------------
 * Timeout and Delay Constants
 * ---------------------------------------------------------------------------
 * These values define default timeouts for various operations. They can be
 * overridden at runtime through function parameters where applicable.
 */

/** Default timeout for establishing connections (seconds) */
#define DEFAULT_CONNECT_TIMEOUT_SEC 5

/** Default timeout for read operations (seconds) */
#define DEFAULT_READ_TIMEOUT_SEC 30

/** Default timeout for write operations (seconds) */
#define DEFAULT_WRITE_TIMEOUT_SEC 30

/** Default timeout for HTTP requests (milliseconds) */
#define DEFAULT_HTTP_TIMEOUT_MS 30000

/** Simulated network delay for stub implementations (microseconds) */
#define SIMULATED_NETWORK_DELAY_US 10000

/** Simulated connection delay for stub implementations (microseconds) */
#define SIMULATED_CONNECT_DELAY_US 10000

/** Simulated close delay for stub implementations (microseconds) */
#define SIMULATED_CLOSE_DELAY_US 5000

/** Simulated send delay for stub implementations (microseconds) */
#define SIMULATED_SEND_DELAY_US 1000

/* ---------------------------------------------------------------------------
 * HTTP Status Code Ranges
 * ---------------------------------------------------------------------------
 * Constants for categorizing HTTP response status codes.
 */

/** Minimum value for successful HTTP status codes (2xx, 3xx) */
#define HTTP_STATUS_OK_MIN 200

/** Maximum value for successful HTTP status codes (2xx, 3xx) */
#define HTTP_STATUS_OK_MAX 399

/** HTTP status code for successful response */
#define HTTP_STATUS_OK 200

/** HTTP status code for created resource */
#define HTTP_STATUS_CREATED 201

/** HTTP status code for no content */
#define HTTP_STATUS_NO_CONTENT 204

/** HTTP status code for bad request */
#define HTTP_STATUS_BAD_REQUEST 400

/** HTTP status code for not found */
#define HTTP_STATUS_NOT_FOUND 404

/** HTTP status code for request timeout */
#define HTTP_STATUS_REQUEST_TIMEOUT 408

/** HTTP status code for gone (resource no longer available) */
#define HTTP_STATUS_GONE 410

/** HTTP status code for internal server error */
#define HTTP_STATUS_INTERNAL_ERROR 500

/* ---------------------------------------------------------------------------
 * Connection Pool Limits
 * ---------------------------------------------------------------------------
 * Maximum number of simultaneous connections for each protocol.
 */

/** Maximum concurrent TCP connections */
#define MAX_TCP_CONNECTIONS_DEFAULT 100

/** Maximum concurrent UDP endpoints */
#define MAX_UDP_ENDPOINTS_DEFAULT 100

/** Maximum concurrent MQTT connections */
#define MAX_MQTT_CONNECTIONS_DEFAULT 50

/** Maximum concurrent WebSocket connections */
#define MAX_WS_CONNECTIONS_DEFAULT 1000

/** Maximum concurrent database connections */
#define MAX_DB_CONNECTIONS_DEFAULT 100

/* ---------------------------------------------------------------------------
 * Buffer Size Constants
 * ---------------------------------------------------------------------------
 * Standard buffer sizes used throughout the codebase.
 */

/** Maximum length for hostnames */
#define MAX_HOSTNAME_LENGTH 256

/** Maximum length for topic names (MQTT) */
#define MAX_TOPIC_LENGTH 256

/** Maximum length for client identifiers */
#define MAX_CLIENT_ID_LENGTH 128

/** Maximum length for error messages */
#define MAX_ERROR_MESSAGE_LENGTH 256

/* ---------------------------------------------------------------------------
 * MQTT Protocol Constants
 * ---------------------------------------------------------------------------
 */

/** Default MQTT broker port */
#define MQTT_DEFAULT_PORT 1883

/** Default MQTT keep-alive interval (seconds) */
#define MQTT_DEFAULT_KEEP_ALIVE_SEC 60

/* ---------------------------------------------------------------------------
 * Database Protocol Constants
 * ---------------------------------------------------------------------------
 */

/** Default MySQL port */
#define MYSQL_DEFAULT_PORT 3306

/** Default PostgreSQL port */
#define POSTGRESQL_DEFAULT_PORT 5432

/** Default MongoDB port */
#define MONGODB_DEFAULT_PORT 27017

/* ---------------------------------------------------------------------------
 * Timing Utility Functions
 * ---------------------------------------------------------------------------
 */

/**
 * @brief Get current time in microseconds
 * 
 * Returns the current monotonic time in microseconds. This function is used
 * for measuring operation durations and response times.
 * 
 * @return Current time in microseconds since an unspecified starting point
 * 
 * @note Uses CLOCK_MONOTONIC to ensure consistent measurements even if
 *       system time is adjusted during execution.
 */
static inline uint64_t get_time_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}

/* ---------------------------------------------------------------------------
 * Response Initialization Macros
 * ---------------------------------------------------------------------------
 * Helper macros to reduce code duplication in protocol implementations.
 */

/**
 * @brief Initialize a response structure
 * 
 * Zeros out the response structure and sets the protocol type.
 * This macro should be called at the beginning of every protocol function.
 * 
 * @param resp      Pointer to response_t structure
 * @param proto     Protocol type (e.g., PROTOCOL_TCP, PROTOCOL_MQTT)
 * 
 * @note Requires response_t and protocol type enum to be defined.
 */
#define INIT_RESPONSE(resp, proto) do { \
    memset((resp), 0, sizeof(*(resp))); \
    (resp)->protocol = (proto); \
} while(0)

/**
 * @brief Set response as success
 * 
 * Sets common fields for a successful response.
 * 
 * @param resp          Pointer to response_t structure
 * @param status        HTTP-style status code (e.g., 200)
 * @param start         Start timestamp from get_time_us()
 */
#define SET_SUCCESS_RESPONSE(resp, status, start) do { \
    (resp)->success = true; \
    (resp)->status_code = (status); \
    (resp)->response_time_us = get_time_us() - (start); \
} while(0)

/**
 * @brief Set response as failure
 * 
 * Sets common fields for a failed response with an error message.
 * 
 * @param resp          Pointer to response_t structure
 * @param status        HTTP-style status code (e.g., 500)
 * @param start         Start timestamp from get_time_us()
 * @param err_msg       Error message string
 */
#define SET_ERROR_RESPONSE(resp, status, start, err_msg) do { \
    (resp)->success = false; \
    (resp)->status_code = (status); \
    (resp)->response_time_us = get_time_us() - (start); \
    strncpy((resp)->error_message, (err_msg), sizeof((resp)->error_message) - 1); \
    (resp)->error_message[sizeof((resp)->error_message) - 1] = '\0'; \
} while(0)

/**
 * @brief Check if HTTP status code indicates success
 * 
 * @param code      HTTP status code to check
 * @return true if status code is in success range (200-399)
 */
#define HTTP_STATUS_IS_SUCCESS(code) \
    ((code) >= HTTP_STATUS_OK_MIN && (code) <= HTTP_STATUS_OK_MAX)

#endif /* COMMON_H */
