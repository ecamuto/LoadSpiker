#include "database.h"
#include "../common.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <pthread.h>
#include <stdint.h>

#ifdef HAVE_LIBPQ
#include <libpq-fe.h>
#endif

#ifdef HAVE_MYSQL
#include <mysql.h>
#endif

#ifdef HAVE_MONGOC
#include <mongoc/mongoc.h>
/* mongoc requires a one-time process-wide init before any client is created. */
static pthread_once_t mongoc_init_once = PTHREAD_ONCE_INIT;
static void mongoc_init_once_fn(void) { mongoc_init(); }
#endif

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

// Connection pool for database connections
#define MAX_DB_CONNECTIONS 100
static db_connection_t db_connections[MAX_DB_CONNECTIONS];
static int db_connection_count = 0;
static pthread_mutex_t db_pool_mutex = PTHREAD_MUTEX_INITIALIZER;
static int db_pool_warned = 0;


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
        size_t host_len = slash ? (size_t)(slash - url_part) : strlen(url_part);
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

static const char* effective_conn_id(const char* conn_id) {
    return (conn_id && conn_id[0]) ? conn_id : "default";
}

/* Find a connection slot for (connection_string, conn_id). Each virtual user
   gets its own slot so one user's disconnect can't flip is_connected for all. */
static db_connection_t* find_connection(const char* connection_string, const char* conn_id) {
    for (int i = 0; i < db_connection_count; i++) {
        if (strcmp(db_connections[i].connection_string, connection_string) == 0 &&
            strcmp(db_connections[i].conn_id, conn_id) == 0) {
            return &db_connections[i];
        }
    }
    return NULL;
}

static db_connection_t* create_connection(const char* connection_string, const char* conn_id, db_type_t type) {
    if (db_connection_count >= MAX_DB_CONNECTIONS) {
        return NULL;
    }

    db_connection_t* conn = &db_connections[db_connection_count++];
    memset(conn, 0, sizeof(db_connection_t));

    strncpy(conn->connection_string, connection_string, sizeof(conn->connection_string) - 1);
    strncpy(conn->conn_id, conn_id, sizeof(conn->conn_id) - 1);
    conn->type = type;
    conn->is_connected = false;
    conn->connection_handle = NULL;

    return conn;
}

#ifdef HAVE_LIBPQ
/* Execute a query against a live PostgreSQL connection. Builds a CSV result_set
   (header + rows), bounded to the response buffer. start_time is the caller's
   timestamp so response_time_us covers the whole operation. */
static int database_pg_query(PGconn* pg, const char* query, response_t* response, uint64_t start_time) {
    database_response_data_t* db_data = &response->protocol_data.database;
    const size_t cap = sizeof(db_data->result_set);
    PGresult* res = PQexec(pg, query);
    ExecStatusType st = res ? PQresultStatus(res) : PGRES_FATAL_ERROR;

    if (st == PGRES_TUPLES_OK) {
        int nrows = PQntuples(res);
        int ncols = PQnfields(res);
        size_t pos = 0;
        db_data->result_set[0] = '\0';

        for (int c = 0; c < ncols && pos < cap - 1; c++) {
            int n = snprintf(db_data->result_set + pos, cap - pos,
                             "%s%s", c ? "," : "", PQfname(res, c));
            if (n < 0) break;
            pos += (size_t)n;
            if (pos >= cap) { pos = cap - 1; break; }
        }
        for (int r = 0; r < nrows && pos < cap - 1; r++) {
            int n = snprintf(db_data->result_set + pos, cap - pos, "\n");
            if (n < 0) break;
            pos += (size_t)n;
            for (int c = 0; c < ncols && pos < cap - 1; c++) {
                const char* val = PQgetisnull(res, r, c) ? "" : PQgetvalue(res, r, c);
                n = snprintf(db_data->result_set + pos, cap - pos,
                             "%s%s", c ? "," : "", val);
                if (n < 0) break;
                pos += (size_t)n;
                if (pos >= cap) { pos = cap - 1; break; }
            }
        }

        db_data->rows_returned = nrows;
        db_data->rows_affected = 0;
        response->success = true;
        response->status_code = 200;
        snprintf(response->body, sizeof(response->body),
                "Query executed successfully. %d rows returned.", nrows);
    } else if (st == PGRES_COMMAND_OK) {
        const char* aff = PQcmdTuples(res);
        db_data->rows_affected = (aff && *aff) ? atoi(aff) : 0;
        db_data->rows_returned = 0;
        db_data->result_set[0] = '\0';
        response->success = true;
        response->status_code = 200;
        snprintf(response->body, sizeof(response->body),
                "Query executed successfully. %d row(s) affected.", db_data->rows_affected);
    } else {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message),
                "PostgreSQL query failed: %s", PQerrorMessage(pg));
        if (res) PQclear(res);
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    PQclear(res);
    response->response_time_us = get_time_us() - start_time;
    return 0;
}
#endif

#ifdef HAVE_MYSQL
/* Execute a query against a live MySQL/MariaDB connection. Mirrors the
   PostgreSQL helper: SELECT-style statements build a CSV result_set, other
   statements report affected rows. start_time is the caller's timestamp. */
static int database_mysql_query(MYSQL* my, const char* query, response_t* response, uint64_t start_time) {
    database_response_data_t* db_data = &response->protocol_data.database;
    const size_t cap = sizeof(db_data->result_set);

    if (mysql_query(my, query) != 0) {
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message),
                "MySQL query failed: %s", mysql_error(my));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    MYSQL_RES* res = mysql_store_result(my);
    if (res) {
        unsigned int ncols = mysql_num_fields(res);
        MYSQL_FIELD* fields = mysql_fetch_fields(res);
        size_t pos = 0;
        db_data->result_set[0] = '\0';

        for (unsigned int c = 0; c < ncols && pos < cap - 1; c++) {
            int n = snprintf(db_data->result_set + pos, cap - pos,
                             "%s%s", c ? "," : "", fields[c].name);
            if (n < 0) break;
            pos += (size_t)n;
            if (pos >= cap) { pos = cap - 1; break; }
        }
        MYSQL_ROW row;
        while ((row = mysql_fetch_row(res)) != NULL && pos < cap - 1) {
            int n = snprintf(db_data->result_set + pos, cap - pos, "\n");
            if (n < 0) break;
            pos += (size_t)n;
            for (unsigned int c = 0; c < ncols && pos < cap - 1; c++) {
                const char* val = row[c] ? row[c] : "";
                n = snprintf(db_data->result_set + pos, cap - pos,
                             "%s%s", c ? "," : "", val);
                if (n < 0) break;
                pos += (size_t)n;
                if (pos >= cap) { pos = cap - 1; break; }
            }
        }

        db_data->rows_returned = (int)mysql_num_rows(res);
        db_data->rows_affected = 0;
        mysql_free_result(res);
        response->success = true;
        response->status_code = 200;
        snprintf(response->body, sizeof(response->body),
                "Query executed successfully. %d rows returned.", db_data->rows_returned);
    } else if (mysql_field_count(my) != 0) {
        /* Columns were expected but the result couldn't be read — a real error. */
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message),
                "MySQL result fetch failed: %s", mysql_error(my));
        response->response_time_us = get_time_us() - start_time;
        return -1;
    } else {
        /* Non-SELECT statement (INSERT/UPDATE/DELETE/DDL). */
        db_data->rows_affected = (int)mysql_affected_rows(my);
        db_data->rows_returned = 0;
        db_data->result_set[0] = '\0';
        response->success = true;
        response->status_code = 200;
        snprintf(response->body, sizeof(response->body),
                "Query executed successfully. %d row(s) affected.", db_data->rows_affected);
    }

    response->response_time_us = get_time_us() - start_time;
    return 0;
}
#endif

#ifdef HAVE_MONGOC
/* Run a command against a live MongoDB connection. MongoDB has no SQL, so the
   query string is interpreted as a JSON command document (e.g.
   '{"find": "users", "filter": {}}') executed via the C driver's command API;
   the reply BSON is serialized back into result_set as relaxed extended JSON. */
static int database_mongo_query(mongoc_client_t* client, const char* dbname,
                                const char* query, response_t* response, uint64_t start_time) {
    database_response_data_t* db_data = &response->protocol_data.database;
    bson_error_t error;
    bson_t cmd;

    if (!bson_init_from_json(&cmd, query, -1, &error)) {
        response->success = false;
        response->status_code = 400;
        /* Bound %s with a precision: bson_error_t.message is a fixed char[504],
           so without it gcc's -Wformat-truncation warns it may not fit. */
        snprintf(response->error_message, sizeof(response->error_message),
                "Invalid MongoDB command JSON: %.200s", error.message);
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    bson_t reply;
    bool ok = mongoc_client_command_simple(client,
                                           (dbname && dbname[0]) ? dbname : "admin",
                                           &cmd, NULL, &reply, &error);
    bson_destroy(&cmd);

    if (!ok) {
        bson_destroy(&reply);
        response->success = false;
        response->status_code = 500;
        snprintf(response->error_message, sizeof(response->error_message),
                "MongoDB command failed: %.200s", error.message);
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    size_t json_len = 0;
    char* json = bson_as_relaxed_extended_json(&reply, &json_len);
    if (json) {
        strncpy(db_data->result_set, json, sizeof(db_data->result_set) - 1);
        db_data->result_set[sizeof(db_data->result_set) - 1] = '\0';
        bson_free(json);
    } else {
        db_data->result_set[0] = '\0';
    }
    db_data->rows_returned = 0;
    db_data->rows_affected = 0;
    bson_destroy(&reply);

    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body), "MongoDB command executed successfully.");
    response->response_time_us = get_time_us() - start_time;
    return 0;
}
#endif

int database_connect(const char* connection_string, const char* conn_id, const char* db_type_str, response_t* response) {
    if (!connection_string || !db_type_str || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

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

    /* --- Critical section 1: find/reserve the slot --- */
    pthread_mutex_lock(&db_pool_mutex);
    db_connection_t* conn = find_connection(connection_string, conn_id);
    if (conn && conn->is_connected) {
        response->success = true;
        response->status_code = 200;
        strcpy(response->body, "Connection already established");
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&db_pool_mutex);
        return 0;
    }
    if (!conn) {
        if (db_connection_count >= MAX_DB_CONNECTIONS) {
            if (!db_pool_warned) {
                fprintf(stderr, "[LoadSpiker] DB pool full — increase MAX_DB_CONNECTIONS\n");
                db_pool_warned = 1;
            }
            response->success = false;
            response->status_code = 500;
            strcpy(response->error_message, "Too many database connections");
            response->response_time_us = get_time_us() - start_time;
            pthread_mutex_unlock(&db_pool_mutex);
            return -1;
        }
        conn = create_connection(connection_string, conn_id, db_type);
    }
    pthread_mutex_unlock(&db_pool_mutex);

    // Parse connection parameters (params only; no lock needed)
    char host[256], database[256], username[256], password[256];
    int port;
    if (database_parse_connection_string(connection_string, host, &port, database, username, password) != 0) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "Invalid connection string format");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

    void* handle = (void*)1; // sim placeholder

#ifdef HAVE_LIBPQ
    if (db_type == DB_TYPE_POSTGRESQL) {
        /* Real PostgreSQL connection via libpq — the connection_string is a
           valid libpq URI. Done WITHOUT the pool mutex so a blocking connect
           can't serialize all DB operations process-wide. */
        PGconn* pg = PQconnectdb(connection_string);
        if (!pg || PQstatus(pg) != CONNECTION_OK) {
            snprintf(response->error_message, sizeof(response->error_message),
                    "PostgreSQL connection failed: %s",
                    pg ? PQerrorMessage(pg) : "out of memory");
            if (pg) PQfinish(pg);
            response->success = false;
            response->status_code = 500;
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        handle = pg;
    }
#endif

#ifdef HAVE_MYSQL
    if (db_type == DB_TYPE_MYSQL) {
        /* Real MySQL/MariaDB connection via libmysqlclient. Done WITHOUT the
           pool mutex so a blocking connect can't serialize DB ops. */
        MYSQL* my = mysql_init(NULL);
        if (!my) {
            strcpy(response->error_message, "MySQL init failed: out of memory");
            response->success = false;
            response->status_code = 500;
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        /* Force TCP: with host "localhost" libmysqlclient otherwise ignores the
           port and dials a local unix socket. We always have a host:port from
           the connection string, matching the PostgreSQL/MongoDB behaviour. */
        unsigned int proto = MYSQL_PROTOCOL_TCP;
        mysql_options(my, MYSQL_OPT_PROTOCOL, &proto);
        if (!mysql_real_connect(my, host,
                                username[0] ? username : NULL,
                                password[0] ? password : NULL,
                                database[0] ? database : NULL,
                                port, NULL, 0)) {
            snprintf(response->error_message, sizeof(response->error_message),
                    "MySQL connection failed: %s", mysql_error(my));
            mysql_close(my);
            response->success = false;
            response->status_code = 500;
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        handle = my;
    }
#endif

#ifdef HAVE_MONGOC
    if (db_type == DB_TYPE_MONGODB) {
        pthread_once(&mongoc_init_once, mongoc_init_once_fn);
        mongoc_client_t* client = mongoc_client_new(connection_string);
        if (!client) {
            strcpy(response->error_message, "MongoDB connection failed: invalid URI");
            response->success = false;
            response->status_code = 500;
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        /* mongoc_client_new is lazy — ping the server to fail fast on connect. */
        bson_t ping = BSON_INITIALIZER;
        bson_append_int32(&ping, "ping", 4, 1);
        bson_error_t error;
        bool ok = mongoc_client_command_simple(client, "admin", &ping, NULL, NULL, &error);
        bson_destroy(&ping);
        if (!ok) {
            snprintf(response->error_message, sizeof(response->error_message),
                    "MongoDB connection failed: %.200s", error.message);
            mongoc_client_destroy(client);
            response->success = false;
            response->status_code = 500;
            response->response_time_us = get_time_us() - start_time;
            return -1;
        }
        handle = client;
    }
#endif

    /* --- Critical section 2: publish the live handle --- */
    pthread_mutex_lock(&db_pool_mutex);
    conn->is_connected = true;
    conn->connection_handle = handle;
    pthread_mutex_unlock(&db_pool_mutex);

    // Populate response
    response->success = true;
    response->status_code = 200;
    snprintf(response->body, sizeof(response->body),
            "Connected to %s database at %s:%d/%s",
            database_type_to_string(db_type), host, port, database);

    // Set database-specific response data
    database_response_data_t* db_data = &response->protocol_data.database;
    db_data->rows_affected = 0;
    db_data->rows_returned = 0;
    strcpy(db_data->result_set, "Connection established");

    response->response_time_us = get_time_us() - start_time;
    return 0;
}

int database_execute_query(const char* connection_string, const char* conn_id, const char* query, response_t* response) {
    if (!connection_string || !query || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_DATABASE;
    uint64_t start_time = get_time_us();

    /* --- Critical section: only the pool lookup needs the mutex. We capture the
       connection state (and, for real backends, the driver handle + type) under
       the lock, then release it before the blocking query so queries don't
       serialize process-wide. Slots are append-only and never moved. --- */
    pthread_mutex_lock(&db_pool_mutex);
    db_connection_t* conn = find_connection(connection_string, conn_id);
    bool connected = (conn && conn->is_connected);
    db_type_t conn_type = connected ? conn->type : DB_TYPE_UNKNOWN;
    void* handle = connected ? conn->connection_handle : NULL;
    (void)conn_type; (void)handle;
    pthread_mutex_unlock(&db_pool_mutex);

    if (!connected) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active database connection");
        response->response_time_us = get_time_us() - start_time;
        return -1;
    }

#ifdef HAVE_LIBPQ
    if (conn_type == DB_TYPE_POSTGRESQL && handle) {
        return database_pg_query((PGconn*)handle, query, response, start_time);
    }
#endif

#ifdef HAVE_MYSQL
    if (conn_type == DB_TYPE_MYSQL && handle && handle != (void*)1) {
        return database_mysql_query((MYSQL*)handle, query, response, start_time);
    }
#endif

#ifdef HAVE_MONGOC
    if (conn_type == DB_TYPE_MONGODB && handle && handle != (void*)1) {
        /* MongoDB commands run against a database; recover its name from the
           connection string (parsing touches only local buffers). */
        char h[256], db[256], u[256], p[256];
        int pt;
        database_parse_connection_string(connection_string, h, &pt, db, u, p);
        return database_mongo_query((mongoc_client_t*)handle, db, query, response, start_time);
    }
#endif

    // Simulate query execution based on query type
    // (non-PostgreSQL types, or builds without libpq)

    bool is_select = (strncasecmp(query, "SELECT", 6) == 0);
    bool is_insert = (strncasecmp(query, "INSERT", 6) == 0);
    bool is_update = (strncasecmp(query, "UPDATE", 6) == 0);
    bool is_delete = (strncasecmp(query, "DELETE", 6) == 0);

    // Simulate query execution time (100-500ms) using per-thread RNG
    get_thread_seed();
    usleep((100 + (rand_r(&thread_rng_seed) % 400)) * 1000);

    response->success = true;
    response->status_code = 200;

    // Set database-specific response data
    database_response_data_t* db_data = &response->protocol_data.database;

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

int database_disconnect(const char* connection_string, const char* conn_id, response_t* response) {
    if (!connection_string || !response) {
        return -1;
    }
    conn_id = effective_conn_id(conn_id);

    // Initialize response
    memset(response, 0, sizeof(response_t));
    response->protocol = PROTOCOL_DATABASE;
    uint64_t start_time = get_time_us();

    pthread_mutex_lock(&db_pool_mutex);

    // Find existing connection
    db_connection_t* conn = find_connection(connection_string, conn_id);
    if (!conn || !conn->is_connected) {
        response->success = false;
        response->status_code = 400;
        strcpy(response->error_message, "No active database connection to disconnect");
        response->response_time_us = get_time_us() - start_time;
        pthread_mutex_unlock(&db_pool_mutex);
        return -1;
    }

    // Disconnect — capture the driver handle/type, clear the slot under the
    // lock, then close the real handle (if any) after releasing the mutex.
    void* handle = conn->connection_handle;
    db_type_t type = conn->type;
    conn->is_connected = false;
    conn->connection_handle = NULL;
    pthread_mutex_unlock(&db_pool_mutex);

#ifdef HAVE_LIBPQ
    if (type == DB_TYPE_POSTGRESQL && handle && handle != (void*)1) {
        PQfinish((PGconn*)handle);
    }
#endif
#ifdef HAVE_MYSQL
    if (type == DB_TYPE_MYSQL && handle && handle != (void*)1) {
        mysql_close((MYSQL*)handle);
    }
#endif
#ifdef HAVE_MONGOC
    if (type == DB_TYPE_MONGODB && handle && handle != (void*)1) {
        mongoc_client_destroy((mongoc_client_t*)handle);
    }
#endif
#if !defined(HAVE_LIBPQ) && !defined(HAVE_MYSQL) && !defined(HAVE_MONGOC)
    (void)handle; (void)type;
#endif

    response->success = true;
    response->status_code = 200;
    strcpy(response->body, "Database connection closed successfully");
    response->response_time_us = get_time_us() - start_time;
    return 0;
}

void database_cleanup_all(void) {
    pthread_mutex_lock(&db_pool_mutex);
    for (int i = 0; i < db_connection_count; i++) {
        void* h = db_connections[i].connection_handle;
        bool real = (h && h != (void*)1);
        (void)real; (void)h;
#ifdef HAVE_LIBPQ
        if (real && db_connections[i].type == DB_TYPE_POSTGRESQL) {
            PQfinish((PGconn*)h);
        }
#endif
#ifdef HAVE_MYSQL
        if (real && db_connections[i].type == DB_TYPE_MYSQL) {
            mysql_close((MYSQL*)h);
        }
#endif
#ifdef HAVE_MONGOC
        if (real && db_connections[i].type == DB_TYPE_MONGODB) {
            mongoc_client_destroy((mongoc_client_t*)h);
        }
#endif
        db_connections[i].is_connected = false;
        db_connections[i].connection_handle = NULL;
    }
    db_connection_count = 0;
    pthread_mutex_unlock(&db_pool_mutex);
}
