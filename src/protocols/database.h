#ifndef DATABASE_H
#define DATABASE_H

#include "../engine.h"
#include <stdint.h>
#include <stdbool.h>

// Database types
typedef enum {
    DB_TYPE_MYSQL,
    DB_TYPE_POSTGRESQL,
    DB_TYPE_MONGODB,
    DB_TYPE_UNKNOWN
} db_type_t;

#define MAX_DB_CONN_ID_LENGTH 64

// Database connection structure
typedef struct {
    char connection_string[MAX_URL_LENGTH];
    char conn_id[MAX_DB_CONN_ID_LENGTH]; // per-virtual-user key; "default" for single-user
    db_type_t type;
    void* connection_handle;
    bool is_connected;
    char last_error[256];
} db_connection_t;

// Database-specific response data
typedef struct {
    int affected_rows;
    int num_columns;
    int num_rows;
    char column_names[MAX_BODY_LENGTH / 4];  // Store column names
    char result_set[MAX_BODY_LENGTH];        // Store query results
    bool has_result_set;
} database_data_t;

// Function declarations.
// conn_id identifies the logical owner (one virtual user) so concurrent users
// sharing a connection_string get isolated connection state. Pass "default"
// (or "") for single-user / direct use.
int database_connect(const char* connection_string, const char* conn_id, const char* db_type, response_t* response);
int database_execute_query(const char* connection_string, const char* conn_id, const char* query, response_t* response);
int database_disconnect(const char* connection_string, const char* conn_id, response_t* response);

// Helper functions
db_type_t database_parse_type(const char* db_type_str);
const char* database_type_to_string(db_type_t type);
int database_parse_connection_string(const char* connection_string, char* host, int* port, char* database, char* username, char* password);

// Cleanup function - resets all database connections
void database_cleanup_all(void);

#endif // DATABASE_H
