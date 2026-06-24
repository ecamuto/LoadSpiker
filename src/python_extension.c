#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <string.h>
#include "engine.h"
#include "protocols/tcp.h"
#include "protocols/udp.h"

typedef struct {
    PyObject_HEAD
    engine_t* engine;
} LoadTestEngineObject;

/* ---------------------------------------------------------------------------
 * Reference-counting helpers
 * ---------------------------------------------------------------------------
 * PyDict_SetItemString does NOT steal a reference, so the temporary objects
 * created by PyLong_FromLong()/PyUnicode_FromString()/... must be released
 * after insertion. dict_set() centralizes this so every dict we build is
 * leak-free even under sustained load. */
static int dict_set(PyObject* dict, const char* key, PyObject* value) {
    if (!value) {
        return -1; /* propagate allocation failure; caller may ignore */
    }
    int rc = PyDict_SetItemString(dict, key, value);
    Py_DECREF(value);
    return rc;
}

/* Build a Python str from a C string without ever raising on invalid UTF-8
 * (protocol bodies may carry arbitrary bytes). Invalid sequences are replaced. */
static PyObject* safe_str(const char* s) {
    if (!s) return PyUnicode_FromString("");
    PyObject* o = PyUnicode_DecodeUTF8(s, (Py_ssize_t)strlen(s), "replace");
    if (!o) {
        PyErr_Clear();
        o = PyUnicode_FromString("");
    }
    return o;
}

/* Build the common response dictionary shared by every protocol method. */
static PyObject* build_response_dict(const response_t* r) {
    PyObject* d = PyDict_New();
    if (!d) return NULL;
    dict_set(d, "status_code", PyLong_FromLong(r->status_code));
    dict_set(d, "headers", safe_str(r->headers));
    dict_set(d, "body", safe_str(r->body));
    dict_set(d, "response_time_us", PyLong_FromUnsignedLongLong(r->response_time_us));
    dict_set(d, "response_time_ms", PyFloat_FromDouble(r->response_time_us / 1000.0));
    dict_set(d, "success", PyBool_FromLong(r->success));
    dict_set(d, "error_message", safe_str(r->error_message));
    return d;
}

static void LoadTestEngine_dealloc(LoadTestEngineObject* self) {
    if (self->engine) {
        engine_destroy(self->engine);
    }
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject* LoadTestEngine_new(PyTypeObject* type, PyObject* Py_UNUSED(args), PyObject* Py_UNUSED(kwds)) {
    LoadTestEngineObject* self;
    self = (LoadTestEngineObject*)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->engine = NULL;
    }
    return (PyObject*)self;
}

static int LoadTestEngine_init(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    int max_connections = 1000;
    int worker_threads = 10;

    static char* kwlist[] = {"max_connections", "worker_threads", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|ii", kwlist,
                                     &max_connections, &worker_threads)) {
        return -1;
    }

    self->engine = engine_create(max_connections, worker_threads);
    if (!self->engine) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to create load test engine");
        return -1;
    }

    return 0;
}

static PyObject* LoadTestEngine_execute_request(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* method = "GET";
    const char* url;
    const char* headers = "";
    const char* body = "";
    int timeout_ms = 30000;

    static char* kwlist[] = {"url", "method", "headers", "body", "timeout_ms", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|sssi", kwlist,
                                     &url, &method, &headers, &body, &timeout_ms)) {
        return NULL;
    }

    http_request_t request = {0};
    strncpy(request.method, method, sizeof(request.method) - 1);
    strncpy(request.url, url, sizeof(request.url) - 1);
    strncpy(request.headers, headers, sizeof(request.headers) - 1);
    strncpy(request.body, body, sizeof(request.body) - 1);
    request.timeout_ms = timeout_ms;

    http_response_t response = {0};
    int result;
    Py_BEGIN_ALLOW_THREADS
    result = engine_execute_request_sync(self->engine, &request, &response);
    Py_END_ALLOW_THREADS

    if (result != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to execute request");
        return NULL;
    }

    PyObject* response_dict = PyDict_New();
    if (!response_dict) return NULL;
    dict_set(response_dict, "status_code", PyLong_FromLong(response.status_code));
    dict_set(response_dict, "headers", safe_str(response.headers));
    dict_set(response_dict, "body", safe_str(response.body));
    dict_set(response_dict, "response_time_us", PyLong_FromUnsignedLongLong(response.response_time_us));
    dict_set(response_dict, "response_time_ms", PyFloat_FromDouble(response.response_time_us / 1000.0));
    dict_set(response_dict, "success", PyBool_FromLong(response.success));
    dict_set(response_dict, "error_message", safe_str(response.error_message));

    return response_dict;
}

static PyObject* LoadTestEngine_start_load_test(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    PyObject* requests_list;
    int concurrent_users = 10;
    int duration_seconds = 60;

    static char* kwlist[] = {"requests", "concurrent_users", "duration_seconds", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|ii", kwlist,
                                     &requests_list, &concurrent_users, &duration_seconds)) {
        return NULL;
    }

    if (!PyList_Check(requests_list)) {
        PyErr_SetString(PyExc_TypeError, "requests must be a list");
        return NULL;
    }

    Py_ssize_t num_requests = PyList_Size(requests_list);
    if (num_requests == 0) {
        PyErr_SetString(PyExc_ValueError, "requests list cannot be empty");
        return NULL;
    }

    http_request_t* requests = malloc(sizeof(http_request_t) * num_requests);
    if (!requests) {
        PyErr_SetString(PyExc_MemoryError, "Failed to allocate memory for requests");
        return NULL;
    }

    for (Py_ssize_t i = 0; i < num_requests; i++) {
        PyObject* req_dict = PyList_GetItem(requests_list, i);
        if (!PyDict_Check(req_dict)) {
            free(requests);
            PyErr_SetString(PyExc_TypeError, "Each request must be a dictionary");
            return NULL;
        }

        memset(&requests[i], 0, sizeof(http_request_t));

        PyObject* method_obj = PyDict_GetItemString(req_dict, "method");
        if (method_obj && PyUnicode_Check(method_obj)) {
            const char* method = PyUnicode_AsUTF8(method_obj);
            strncpy(requests[i].method, method, sizeof(requests[i].method) - 1);
        } else {
            strcpy(requests[i].method, "GET");
        }

        PyObject* url_obj = PyDict_GetItemString(req_dict, "url");
        if (!url_obj || !PyUnicode_Check(url_obj)) {
            free(requests);
            PyErr_SetString(PyExc_ValueError, "Each request must have a 'url' field");
            return NULL;
        }
        const char* url = PyUnicode_AsUTF8(url_obj);
        strncpy(requests[i].url, url, sizeof(requests[i].url) - 1);

        PyObject* headers_obj = PyDict_GetItemString(req_dict, "headers");
        if (headers_obj && PyUnicode_Check(headers_obj)) {
            const char* headers = PyUnicode_AsUTF8(headers_obj);
            strncpy(requests[i].headers, headers, sizeof(requests[i].headers) - 1);
        }

        PyObject* body_obj = PyDict_GetItemString(req_dict, "body");
        if (body_obj && PyUnicode_Check(body_obj)) {
            const char* body = PyUnicode_AsUTF8(body_obj);
            strncpy(requests[i].body, body, sizeof(requests[i].body) - 1);
        }

        PyObject* timeout_obj = PyDict_GetItemString(req_dict, "timeout_ms");
        if (timeout_obj && PyLong_Check(timeout_obj)) {
            requests[i].timeout_ms = PyLong_AsLong(timeout_obj);
        } else {
            requests[i].timeout_ms = 30000;
        }
    }

    Py_BEGIN_ALLOW_THREADS
    engine_start_load_test(self->engine, requests, num_requests, concurrent_users, duration_seconds);
    Py_END_ALLOW_THREADS

    free(requests);

    Py_RETURN_NONE;
}

static PyObject* LoadTestEngine_get_metrics(LoadTestEngineObject* self, PyObject* Py_UNUSED(ignored)) {
    metrics_t metrics;
    engine_get_metrics(self->engine, &metrics);

    PyObject* metrics_dict = PyDict_New();
    if (!metrics_dict) return NULL;
    dict_set(metrics_dict, "total_requests", PyLong_FromUnsignedLongLong(metrics.total_requests));
    dict_set(metrics_dict, "successful_requests", PyLong_FromUnsignedLongLong(metrics.successful_requests));
    dict_set(metrics_dict, "failed_requests", PyLong_FromUnsignedLongLong(metrics.failed_requests));
    dict_set(metrics_dict, "total_response_time_us", PyLong_FromUnsignedLongLong(metrics.total_response_time_us));
    dict_set(metrics_dict, "min_response_time_us", PyLong_FromUnsignedLongLong(metrics.min_response_time_us));
    dict_set(metrics_dict, "max_response_time_us", PyLong_FromUnsignedLongLong(metrics.max_response_time_us));
    dict_set(metrics_dict, "min_response_time_ms", PyFloat_FromDouble(metrics.min_response_time_us / 1000.0));
    dict_set(metrics_dict, "max_response_time_ms", PyFloat_FromDouble(metrics.max_response_time_us / 1000.0));
    dict_set(metrics_dict, "requests_per_second", PyFloat_FromDouble(metrics.requests_per_second));
    dict_set(metrics_dict, "p95_us", PyLong_FromUnsignedLongLong(metrics.p95_us));
    dict_set(metrics_dict, "p99_us", PyLong_FromUnsignedLongLong(metrics.p99_us));

    if (metrics.total_requests > 0) {
        double avg_response_time = (double)metrics.total_response_time_us / metrics.total_requests / 1000.0;
        dict_set(metrics_dict, "avg_response_time_ms", PyFloat_FromDouble(avg_response_time));
    } else {
        dict_set(metrics_dict, "avg_response_time_ms", PyFloat_FromDouble(0.0));
    }

    return metrics_dict;
}

static PyObject* LoadTestEngine_reset_metrics(LoadTestEngineObject* self, PyObject* Py_UNUSED(ignored)) {
    engine_reset_metrics(self->engine);
    Py_RETURN_NONE;
}

/* ===========================================================================
 * WebSocket methods
 * =========================================================================== */
static PyObject* LoadTestEngine_websocket_connect(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* url;
    const char* subprotocol = "";

    static char* kwlist[] = {"url", "subprotocol", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|s", kwlist, &url, &subprotocol)) {
        return NULL;
    }

    response_t response = {0};
    int result = engine_websocket_connect(self->engine, url, subprotocol, &response);

    if (result != 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        response.error_message[0] ? response.error_message : "WebSocket connect failed");
        return NULL;
    }

    PyObject* response_dict = build_response_dict(&response);
    if (!response_dict) return NULL;
    dict_set(response_dict, "protocol", PyUnicode_FromString("websocket"));

    PyObject* ws_data = PyDict_New();
    dict_set(ws_data, "subprotocol", safe_str(response.protocol_data.websocket.subprotocol));
    dict_set(ws_data, "messages_sent", PyLong_FromLong(response.protocol_data.websocket.messages_sent));
    dict_set(ws_data, "messages_received", PyLong_FromLong(response.protocol_data.websocket.messages_received));
    dict_set(ws_data, "bytes_sent", PyLong_FromUnsignedLongLong(response.protocol_data.websocket.bytes_sent));
    dict_set(ws_data, "bytes_received", PyLong_FromUnsignedLongLong(response.protocol_data.websocket.bytes_received));
    dict_set(response_dict, "websocket_data", ws_data);

    return response_dict;
}

static PyObject* LoadTestEngine_websocket_send(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* url;
    const char* message;

    static char* kwlist[] = {"url", "message", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "ss", kwlist, &url, &message)) {
        return NULL;
    }

    response_t response = {0};
    int result = engine_websocket_send(self->engine, url, message, &response);

    if (result != 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        response.error_message[0] ? response.error_message : "WebSocket send failed");
        return NULL;
    }

    PyObject* response_dict = build_response_dict(&response);
    if (!response_dict) return NULL;
    dict_set(response_dict, "protocol", PyUnicode_FromString("websocket"));

    PyObject* ws_data = PyDict_New();
    dict_set(ws_data, "messages_sent", PyLong_FromLong(response.protocol_data.websocket.messages_sent));
    dict_set(ws_data, "bytes_sent", PyLong_FromUnsignedLongLong(response.protocol_data.websocket.bytes_sent));
    dict_set(response_dict, "websocket_data", ws_data);

    return response_dict;
}

static PyObject* LoadTestEngine_websocket_close(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* url;

    static char* kwlist[] = {"url", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &url)) {
        return NULL;
    }

    response_t response = {0};
    int result = engine_websocket_close(self->engine, url, &response);

    if (result != 0) {
        PyErr_SetString(PyExc_RuntimeError,
                        response.error_message[0] ? response.error_message : "WebSocket close failed");
        return NULL;
    }

    PyObject* response_dict = build_response_dict(&response);
    if (!response_dict) return NULL;
    dict_set(response_dict, "protocol", PyUnicode_FromString("websocket"));
    return response_dict;
}

/* ===========================================================================
 * TCP methods (host/port based, matching the Python API)
 * =========================================================================== */
static PyObject* LoadTestEngine_tcp_connect(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    int timeout_ms = 30000;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "timeout_ms", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "si|is", kwlist, &hostname, &port, &timeout_ms, &conn_id)) {
        return NULL;
    }
    (void)timeout_ms; /* tcp.c uses a fixed select() timeout */

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    tcp_connect(hostname, port, conn_id, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    return build_response_dict(&response);
}

static PyObject* LoadTestEngine_tcp_send(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    const char* data;
    int timeout_ms = 30000;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "data", "timeout_ms", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "sis|is", kwlist, &hostname, &port, &data, &timeout_ms, &conn_id)) {
        return NULL;
    }
    (void)timeout_ms;

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    tcp_send(hostname, port, conn_id, data, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "bytes_sent", PyLong_FromUnsignedLongLong(response.protocol_data.tcp.bytes_sent));
    dict_set(pd, "connection_established", PyBool_FromLong(response.success));
    dict_set(d, "protocol_data", pd);
    return d;
}

static PyObject* LoadTestEngine_tcp_receive(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    int timeout_ms = 30000;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "timeout_ms", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "si|is", kwlist, &hostname, &port, &timeout_ms, &conn_id)) {
        return NULL;
    }
    (void)timeout_ms;

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    tcp_receive(hostname, port, conn_id, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "bytes_received", PyLong_FromUnsignedLongLong(response.protocol_data.tcp.bytes_received));
    dict_set(pd, "received_data", safe_str(response.body));
    dict_set(pd, "connection_established", PyBool_FromLong(1));
    dict_set(d, "protocol_data", pd);
    return d;
}

static PyObject* LoadTestEngine_tcp_disconnect(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "si|s", kwlist, &hostname, &port, &conn_id)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    tcp_disconnect(hostname, port, conn_id, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    return build_response_dict(&response);
}

/* ===========================================================================
 * UDP methods
 * =========================================================================== */
static PyObject* LoadTestEngine_udp_create_endpoint(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "si|s", kwlist, &hostname, &port, &conn_id)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    udp_create_endpoint(hostname, port, conn_id, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    return build_response_dict(&response);
}

static PyObject* LoadTestEngine_udp_send(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    const char* data;
    int timeout_ms = 30000;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "data", "timeout_ms", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "sis|is", kwlist, &hostname, &port, &data, &timeout_ms, &conn_id)) {
        return NULL;
    }
    (void)timeout_ms;

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    udp_send(hostname, port, conn_id, data, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "bytes_sent", PyLong_FromUnsignedLongLong(response.protocol_data.udp.bytes_sent));
    dict_set(pd, "datagram_sent", PyBool_FromLong(response.success));
    dict_set(pd, "remote_host", safe_str(hostname));
    dict_set(pd, "remote_port", PyLong_FromLong(port));
    dict_set(d, "protocol_data", pd);
    return d;
}

static PyObject* LoadTestEngine_udp_receive(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    int timeout_ms = 30000;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "timeout_ms", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "si|is", kwlist, &hostname, &port, &timeout_ms, &conn_id)) {
        return NULL;
    }
    (void)timeout_ms;

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    udp_receive(hostname, port, conn_id, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "bytes_received", PyLong_FromUnsignedLongLong(response.protocol_data.udp.bytes_received));
    dict_set(pd, "received_data", safe_str(response.body));
    dict_set(pd, "remote_host", safe_str(response.protocol_data.udp.sender_address));
    dict_set(pd, "remote_port", PyLong_FromLong(response.protocol_data.udp.sender_port));
    dict_set(d, "protocol_data", pd);
    return d;
}

static PyObject* LoadTestEngine_udp_close_endpoint(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* hostname;
    int port;
    const char* conn_id = "default";
    static char* kwlist[] = {"hostname", "port", "conn_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "si|s", kwlist, &hostname, &port, &conn_id)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    udp_close_endpoint(hostname, port, conn_id, &response);
    Py_END_ALLOW_THREADS
    engine_record_metrics(self->engine, response.response_time_us, response.success);

    return build_response_dict(&response);
}

/* ===========================================================================
 * MQTT methods (engine_* wrappers already fold metrics)
 * =========================================================================== */
static PyObject* LoadTestEngine_mqtt_connect(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* broker_host;
    int broker_port = 1883;
    const char* client_id = "loadspiker_client";
    const char* username = "";
    const char* password = "";
    int keep_alive = 60;
    static char* kwlist[] = {"broker_host", "broker_port", "client_id", "username", "password", "keep_alive", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|isssi", kwlist,
                                     &broker_host, &broker_port, &client_id, &username, &password, &keep_alive)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_mqtt_connect(self->engine, broker_host, broker_port, client_id, username, password, keep_alive, &response);
    Py_END_ALLOW_THREADS

    return build_response_dict(&response);
}

static PyObject* LoadTestEngine_mqtt_publish(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* broker_host;
    int broker_port = 1883;
    const char* client_id = "loadspiker_client";
    const char* topic = "";
    const char* payload = "";
    int qos = 0;
    int retain = 0;
    static char* kwlist[] = {"broker_host", "broker_port", "client_id", "topic", "payload", "qos", "retain", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|isssip", kwlist,
                                     &broker_host, &broker_port, &client_id, &topic, &payload, &qos, &retain)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_mqtt_publish(self->engine, broker_host, broker_port, client_id, topic, payload, qos, retain ? true : false, &response);
    Py_END_ALLOW_THREADS

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "topic", safe_str(topic));
    dict_set(pd, "payload_size", PyLong_FromLong((long)strlen(payload)));
    dict_set(pd, "qos", PyLong_FromLong(qos));
    dict_set(pd, "retain", PyBool_FromLong(retain));
    dict_set(pd, "published", PyBool_FromLong(response.success));
    dict_set(d, "protocol_data", pd);
    return d;
}

static PyObject* LoadTestEngine_mqtt_subscribe(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* broker_host;
    int broker_port = 1883;
    const char* client_id = "loadspiker_client";
    const char* topic = "";
    int qos = 0;
    static char* kwlist[] = {"broker_host", "broker_port", "client_id", "topic", "qos", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|issi", kwlist,
                                     &broker_host, &broker_port, &client_id, &topic, &qos)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_mqtt_subscribe(self->engine, broker_host, broker_port, client_id, topic, qos, &response);
    Py_END_ALLOW_THREADS

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "topic", safe_str(topic));
    dict_set(pd, "qos", PyLong_FromLong(qos));
    dict_set(pd, "subscribed", PyBool_FromLong(response.success));
    dict_set(d, "protocol_data", pd);
    return d;
}

static PyObject* LoadTestEngine_mqtt_unsubscribe(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* broker_host;
    int broker_port = 1883;
    const char* client_id = "loadspiker_client";
    const char* topic = "";
    static char* kwlist[] = {"broker_host", "broker_port", "client_id", "topic", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|iss", kwlist,
                                     &broker_host, &broker_port, &client_id, &topic)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_mqtt_unsubscribe(self->engine, broker_host, broker_port, client_id, topic, &response);
    Py_END_ALLOW_THREADS

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "topic", safe_str(topic));
    dict_set(pd, "unsubscribed", PyBool_FromLong(response.success));
    dict_set(d, "protocol_data", pd);
    return d;
}

static PyObject* LoadTestEngine_mqtt_disconnect(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* broker_host;
    int broker_port = 1883;
    const char* client_id = "loadspiker_client";
    static char* kwlist[] = {"broker_host", "broker_port", "client_id", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|is", kwlist,
                                     &broker_host, &broker_port, &client_id)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_mqtt_disconnect(self->engine, broker_host, broker_port, client_id, &response);
    Py_END_ALLOW_THREADS

    PyObject* d = build_response_dict(&response);
    if (!d) return NULL;
    PyObject* pd = PyDict_New();
    dict_set(pd, "broker_host", safe_str(broker_host));
    dict_set(pd, "broker_port", PyLong_FromLong(broker_port));
    dict_set(pd, "client_id", safe_str(client_id));
    dict_set(pd, "disconnected", PyBool_FromLong(response.success));
    dict_set(d, "protocol_data", pd);
    return d;
}

/* ===========================================================================
 * Database methods
 * =========================================================================== */
static PyObject* build_database_dict(const response_t* r) {
    PyObject* d = build_response_dict(r);
    if (!d) return NULL;
    const database_response_data_t* db =
        (const database_response_data_t*)r->protocol_data.protocol_data;
    PyObject* dd = PyDict_New();
    dict_set(dd, "rows_affected", PyLong_FromLong(db->rows_affected));
    dict_set(dd, "rows_returned", PyLong_FromLong(db->rows_returned));
    dict_set(dd, "result_set", safe_str(db->result_set));
    dict_set(d, "database_data", dd);
    return d;
}

static PyObject* LoadTestEngine_database_connect(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* connection_string;
    const char* db_type = "mysql";
    static char* kwlist[] = {"connection_string", "db_type", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s|s", kwlist, &connection_string, &db_type)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_database_connect(self->engine, connection_string, db_type, &response);
    Py_END_ALLOW_THREADS

    return build_database_dict(&response);
}

static PyObject* LoadTestEngine_database_query(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* connection_string;
    const char* query;
    static char* kwlist[] = {"connection_string", "query", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "ss", kwlist, &connection_string, &query)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_database_query(self->engine, connection_string, query, &response);
    Py_END_ALLOW_THREADS

    return build_database_dict(&response);
}

static PyObject* LoadTestEngine_database_disconnect(LoadTestEngineObject* self, PyObject* args, PyObject* kwds) {
    const char* connection_string;
    static char* kwlist[] = {"connection_string", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &connection_string)) {
        return NULL;
    }

    response_t response;
    Py_BEGIN_ALLOW_THREADS
    engine_database_disconnect(self->engine, connection_string, &response);
    Py_END_ALLOW_THREADS

    return build_response_dict(&response);
}

#define KW_METH(name) (PyCFunction)(void(*)(void))name, METH_VARARGS | METH_KEYWORDS

static PyMethodDef LoadTestEngine_methods[] = {
    {"execute_request", KW_METH(LoadTestEngine_execute_request), "Execute a single HTTP request"},
    {"start_load_test", KW_METH(LoadTestEngine_start_load_test), "Start a load test with multiple requests"},
    {"get_metrics", (PyCFunction)LoadTestEngine_get_metrics, METH_NOARGS, "Get current performance metrics"},
    {"reset_metrics", (PyCFunction)LoadTestEngine_reset_metrics, METH_NOARGS, "Reset performance metrics"},
    {"websocket_connect", KW_METH(LoadTestEngine_websocket_connect), "Connect to a WebSocket server"},
    {"websocket_send", KW_METH(LoadTestEngine_websocket_send), "Send a message to a WebSocket connection"},
    {"websocket_close", KW_METH(LoadTestEngine_websocket_close), "Close a WebSocket connection"},
    {"tcp_connect", KW_METH(LoadTestEngine_tcp_connect), "Connect to a TCP server"},
    {"tcp_send", KW_METH(LoadTestEngine_tcp_send), "Send data over a TCP connection"},
    {"tcp_receive", KW_METH(LoadTestEngine_tcp_receive), "Receive data from a TCP connection"},
    {"tcp_disconnect", KW_METH(LoadTestEngine_tcp_disconnect), "Disconnect a TCP connection"},
    {"udp_create_endpoint", KW_METH(LoadTestEngine_udp_create_endpoint), "Create a UDP endpoint"},
    {"udp_send", KW_METH(LoadTestEngine_udp_send), "Send a UDP datagram"},
    {"udp_receive", KW_METH(LoadTestEngine_udp_receive), "Receive a UDP datagram"},
    {"udp_close_endpoint", KW_METH(LoadTestEngine_udp_close_endpoint), "Close a UDP endpoint"},
    {"mqtt_connect", KW_METH(LoadTestEngine_mqtt_connect), "Connect to an MQTT broker"},
    {"mqtt_publish", KW_METH(LoadTestEngine_mqtt_publish), "Publish an MQTT message"},
    {"mqtt_subscribe", KW_METH(LoadTestEngine_mqtt_subscribe), "Subscribe to an MQTT topic"},
    {"mqtt_unsubscribe", KW_METH(LoadTestEngine_mqtt_unsubscribe), "Unsubscribe from an MQTT topic"},
    {"mqtt_disconnect", KW_METH(LoadTestEngine_mqtt_disconnect), "Disconnect from an MQTT broker"},
    {"database_connect", KW_METH(LoadTestEngine_database_connect), "Connect to a database"},
    {"database_query", KW_METH(LoadTestEngine_database_query), "Execute a database query"},
    {"database_disconnect", KW_METH(LoadTestEngine_database_disconnect), "Disconnect from a database"},
    {NULL, NULL, 0, NULL}
};

static PyTypeObject LoadTestEngineType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "loadspiker.Engine",
    .tp_doc = "Load testing engine",
    .tp_basicsize = sizeof(LoadTestEngineObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_new = LoadTestEngine_new,
    .tp_init = (initproc)LoadTestEngine_init,
    .tp_dealloc = (destructor)LoadTestEngine_dealloc,
    .tp_methods = LoadTestEngine_methods,
};

static PyModuleDef loadspiker_c_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "loadspiker_c",
    .m_doc = "High-performance load testing C module",
    .m_size = -1,
};

PyMODINIT_FUNC PyInit_loadspiker_c(void) {
    PyObject* m;

    if (PyType_Ready(&LoadTestEngineType) < 0)
        return NULL;

    m = PyModule_Create(&loadspiker_c_module);
    if (m == NULL)
        return NULL;

    Py_INCREF(&LoadTestEngineType);
    if (PyModule_AddObject(m, "Engine", (PyObject*)&LoadTestEngineType) < 0) {
        Py_DECREF(&LoadTestEngineType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
