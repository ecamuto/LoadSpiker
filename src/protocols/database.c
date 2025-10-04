#include "database.h"
#include "../common.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>

// Connection pool for database connections
#define MAX_DB_CONNECTIONS 100
static db_connection_t db_connections[MAX_DB_CONNECTIONS];
static int db_connection_count = 0;


db_type_t database_parse_type(const char* db_type_str) {
    if (!db_type_str) return DB_TYPE_UNKNOWN;
    
    if (strcmp(db_type_str, "mysql") == 0) return DB_TYPE_MYSQL;
    if (strcmp(db_type_str, "postgresql") == 0) return DB_TYPE_POSTGRESQL;
    if (strcmp(db_type_str, "postgres") == 0) return DB_TYPE_POSTGRESQL;
    if (strcmp(db_type_str, "mongodb") == 0) return DB_TYPE_MONGODB;
    if (strcmp(db_type_str, "mongo") == 0) return DB_TYPE_MONGODB;
    
    return DB_TYPE_UNKNOWN;
}

const char* database_type_to_string(db_type_t type) {
    switch (type) {
        case DB_TYPE_MYSQL: return "mysql";
        case DB_TYPE_POSTGRESQL: return "postgresql";
        case DB_TYPE_MONGODB: return "mongodb";
        default: return "unknown";
    }
}

int database_parse_connection_string(const char* connection_string, char* host, int* port, char* database, char* username, char* password) {
    if (!connection_string || !host || !port || !database || !username || !password) {
        return -1;
    }
    
    // Initialize output parameters
    *host = '\0';
    *port = 0;
    *database = '\0';
    *username = '\0';
    *password = '\0';
    
    // Parse different connection string formats
    // MySQL: mysql://username:password@host:port/database
    // PostgreSQL: postgresql://username:password@host:port/database
    // MongoDB: mongodb://username:password@host:port/database
    
    const char* protocol_end = strstr(connection_string, "://");
    if (!protocol_end) {
        return -1;
    }
    
    const char* url_part = protocol_end + 3;
    
    // Extract username and password
    const char* at_sign = strchr(url_part, '@');
    if (at_sign) {
        const char* colon = strchr(url_part, ':');
        if (colon && colon < at_sign) {
            // Extract username
            size_t username_len = colon - url_part;
            strncpy(username, url_part, username_len);
            username[username_len] = '\0';
            
            // Extract password
            size_t password_len = at_sign - colon - 1;
            strncpy(password, colon + 1, password_len);
            password[password_len] = '\0';
            
            url_part = at_sign + 1;
        }
    }
    
    // Extract host and port
    const char* slash = strchr(url_part, '/');
    const char* colon = strchr(url_part, ':');
    
    if (colon && (!slash || colon < slash)) {
        // Host with port
        size_t host_len = colon - url_part;
        strncpy(host, url_part, host_len);
        host[host_len] = '\0';
        
        // Extract port
        *port = atoi(colon + 1);
    } else {
        // Host without port
        size_t host_len = slash ? (slash - url_part) : strlen(url_part);
        strncpy(host, url_part, host_len);
        host[host_len] = '\0';
        
        // Set default ports
        if (strstr(connection_string, "mysql://")) {
            *port = 3306;
        } else if (strstr(connection_string, "postgresql://")) {
            *port = 5432;
        } else if (strstr(connection_string, "mongodb://")) {
            *port = 27017;
        }
    }
    
    // Extract database name
    if (slash) {
        strcpy(database, slash + 1);
    }
    
    return 0;
}

static db_connection_t* find_connection(const char* connection_string) {
    for (int i = 0; i < db_connection_count; i++) {
        if (strcmp(db_connections[i].connection_string, connection_string) == 0) {
            return &db_connections[i];
        }
    }
    return NULL;
}

static db_connection_t* create_connection(const char* connection_string, db_type_t type) {
    if (db_connection_count >= MAX_DB_CONNECTIONS) {
        return NULL;
    }
    
    db_connection_t* conn = &db_connections[db_connection_count++];
    memset(conn, 0, sizeof(db_connection_t));
    
    strncpy(conn->connection_string, connection_string, sizeof(conn->connection_string) - 1);
    conn->type = type;
    conn->is_connected = false;
    conn->connection_handle = NULL;
    
    return conn;
}

int database_connect(const char* connection_string, const char* db_type_str, response_t* response) {
    if (!connection_string || !db_type_str || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_DATABASE;
    uint64_t start_time = get_time_us();
    
    db_type_t db_type = database_parse_type(db_type_str);
    if (db_type == DB_TYPE_UNKNOWN) {
        response->success = false;
        response->status_code = 400;
        snprintf(response->error_message, sizeof(response->error_message), 
                "Unsupported database type: %s", db_type_str);
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Check if connection already exists
    db_connection_t* conn = find_connection(connection_string);
    if (conn && conn->is_connected) {
        response->success = true;
        response->status_code = 200;
        strcpy(response->body, "Connection already established");
        response->response_time_us = get_time_us() - start_time;
        return 0;
    }
    
    // Create new connection if needed
    if (!conn) {
        conn = create_connection(connection_string, db_type);
        if (!conn) {
            response->success = false;
            response->status_code = 500;
            strcpy(response->error_message, "Too many database connections");
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
    }
    
    // Parse connection parameters
    char host[256], database[256], username[256], password[256];
    int port;
    
    if (database_parse_connection_string(connection_string, host, &port, database, username, password) != 0) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "Invalid connection string format");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Simulate database connection (in a real implementation, this would use actual database drivers)
    // For now, we'll simulate a successful connection
    conn->is_connected = true;
    conn->connection_handle = (void*)1; // Placeholder
    
    // Populate response
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), 
            "Connected to %s database at %s:%d/%s", 
            database_type_to_string(db_type), host, port, database);
    
    // Set database-specific response data
    database_response_data_t* db_data = (database_response_data_t*)response->protocol_data.protocol_data;
    db_data->rows_affected = 0;
    db_data->rows_returned = 0;
    strcpy(db_data->result_set, "Connection established");
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int database_execute_query(const char* connection_string, const char* query, response_t* response) {
    if (!connection_string || !query || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_DATABASE;
    uint64_t start_time = get_time_us();
    
    // Find existing connection
    db_connection_t* conn = find_connection(connection_string);
    if (!conn || !conn->is_connected) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active database connection");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Simulate query execution based on query type
    // In a real implementation, this would use actual database drivers
    
    bool is_select = (strncasecmp(query, "SELECT", 6) == 0);
    bool is_insert = (strncasecmp(query, "INSERT", 6) == 0);
    bool is_update = (strncasecmp(query, "UPDATE", 6) == 0);
    bool is_delete = (strncasecmp(query, "DELETE", 6) == 0);
    
    // Simulate query execution time (100-500ms)
    usleep((100 + (rand() % 400)) * 1000);
    
    response->success = true;
    response->status_code = 200;
    
    // Set database-specific response data
    database_response_data_t* db_data = (database_response_data_t*)response->protocol_data.protocol_data;
    
    if (is_select) {
        // Simulate SELECT result
        db_data->rows_returned = 3;
        db_data->rows_affected = 0;
        strcpy(db_data->result_set, "id,name,email\n1,John,john@example.com\n2,Jane,jane@example.com\n3,Bob,bob@example.com");
        snprintf(response->body, sizeof(response->body), "Query executed successfully. %d rows returned.", db_data->rows_returned);
    } else if (is_insert) {
        // Simulate INSERT result
        db_data->rows_affected = 1;
        db_data->rows_returned = 0;
        strcpy(db_data->result_set, "");
        snprintf(response->body, sizeof(response->body), "Query executed successfully. %d row(s) inserted.", db_data->rows_affected);
    } else if (is_update) {
        // Simulate UPDATE result
        db_data->rows_affected = 2;
        db_data->rows_returned = 0;
        strcpy(db_data->result_set, "");
        snprintf(response->body, sizeof(response->body), "Query executed successfully. %d row(s) updated.", db_data->rows_affected);
    } else if (is_delete) {
        // Simulate DELETE result
        db_data->rows_affected = 1;
        db_data->rows_returned = 0;
        strcpy(db_data->result_set, "");
        snprintf(response->body, sizeof(response->body), "Query executed successfully. %d row(s) deleted.", db_data->rows_affected);
    } else {
        // Generic query
        db_data->rows_affected = 0;
        db_data->rows_returned = 0;
        strcpy(db_data->result_set, "");
        strcpy(response->body, "Query executed successfully.");
    }
    
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}

int database_disconnect(const char* connection_string, response_t* response) {
    if (!connection_string || !response) {
        return -1;
    }
    
    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_DATABASE;
    uint64_t start_time = get_time_us();
    
    // Find existing connection
    db_connection_t* conn = find_connection(connection_string);
    if (!conn || !conn->is_connected) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active database connection to disconnect");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }
    
    // Disconnect
    conn->is_connected = false;
    conn->connection_handle = NULL;
    
    response->success = true;
    response->status_code = 200;
    strcpy(response->body, "Database connection closed successfully");
    response->response_time_us = get_time_us() - start_time;
    
    return 0;
}
