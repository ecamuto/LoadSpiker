#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "engine.h"

typedef struct {
    PyObject_HEAD
    engine_t* engine;
} LoadTestEngineObject;

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
    int result = engine_execute_request_sync(self->engine, &request, &response);
    
    if (result != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Failed to execute request");
        return NULL;
    }
    
    PyObject* response_dict = PyDict_New();
    PyDict_SetItemString(response_dict, "status_code", PyLong_FromLong(response.status_code));
    PyDict_SetItemString(response_dict, "headers", PyUnicode_FromString(response.headers));
    PyDict_SetItemString(response_dict, "body", PyUnicode_FromString(response.body));
    PyDict_SetItemString(response_dict, "response_time_us", PyLong_FromUnsignedLongLong(response.response_time_us));
    PyDict_SetItemString(response_dict, "success", PyBool_FromLong(response.success));
    PyDict_SetItemString(response_dict, "error_message", PyUnicode_FromString(response.error_message));
    
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
    PyDict_SetItemString(metrics_dict, "total_requests", PyLong_FromUnsignedLongLong(metrics.total_requests));
    PyDict_SetItemString(metrics_dict, "successful_requests", PyLong_FromUnsignedLongLong(metrics.successful_requests));
    PyDict_SetItemString(metrics_dict, "failed_requests", PyLong_FromUnsignedLongLong(metrics.failed_requests));
    PyDict_SetItemString(metrics_dict, "total_response_time_us", PyLong_FromUnsignedLongLong(metrics.total_response_time_us));
    PyDict_SetItemString(metrics_dict, "min_response_time_us", PyLong_FromUnsignedLongLong(metrics.min_response_time_us));
    PyDict_SetItemString(metrics_dict, "max_response_time_us", PyLong_FromUnsignedLongLong(metrics.max_response_time_us));
    PyDict_SetItemString(metrics_dict, "requests_per_second", PyFloat_FromDouble(metrics.requests_per_second));
    
    if (metrics.total_requests > 0) {
        double avg_response_time = (double)metrics.total_response_time_us / metrics.total_requests / 1000.0;
        PyDict_SetItemString(metrics_dict, "avg_response_time_ms", PyFloat_FromDouble(avg_response_time));
    } else {
        PyDict_SetItemString(metrics_dict, "avg_response_time_ms", PyFloat_FromDouble(0.0));
    }
    
    return metrics_dict;
}

static PyObject* LoadTestEngine_reset_metrics(LoadTestEngineObject* self, PyObject* Py_UNUSED(ignored)) {
    engine_reset_metrics(self->engine);
    Py_RETURN_NONE;
}

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
        PyErr_SetString(PyExc_RuntimeError, response.error_message);
        return NULL;
    }
    
    PyObject* response_dict = PyDict_New();
    PyDict_SetItemString(response_dict, "protocol", PyUnicode_FromString("websocket"));
    PyDict_SetItemString(response_dict, "status_code", PyLong_FromLong(response.status_code));
    PyDict_SetItemString(response_dict, "headers", PyUnicode_FromString(response.headers));
    PyDict_SetItemString(response_dict, "body", PyUnicode_FromString(response.body));
    PyDict_SetItemString(response_dict, "response_time_us", PyLong_FromUnsignedLongLong(response.response_time_us));
    PyDict_SetItemString(response_dict, "success", PyBool_FromLong(response.success));
    PyDict_SetItemString(response_dict, "error_message", PyUnicode_FromString(response.error_message));
    
    // WebSocket-specific data
    PyObject* ws_data = PyDict_New();
    PyDict_SetItemString(ws_data, "subprotocol", PyUnicode_FromString(response.protocol_data.websocket.subprotocol));
    PyDict_SetItemString(ws_data, "messages_sent", PyLong_FromLong(response.protocol_data.websocket.messages_sent));
    PyDict_SetItemString(ws_data, "messages_received", PyLong_FromLong(response.protocol_data.websocket.messages_received));
    PyDict_SetItemString(ws_data, "bytes_sent", PyLong_FromUnsignedLongLong(response.protocol_data.websocket.bytes_sent));
    PyDict_SetItemString(ws_data, "bytes_received", PyLong_FromUnsignedLongLong(response.protocol_data.websocket.bytes_received));
    PyDict_SetItemString(response_dict, "websocket_data", ws_data);
    
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
        PyErr_SetString(PyExc_RuntimeError, response.error_message);
        return NULL;
    }
    
    PyObject* response_dict = PyDict_New();
    PyDict_SetItemString(response_dict, "protocol", PyUnicode_FromString("websocket"));
    PyDict_SetItemString(response_dict, "status_code", PyLong_FromLong(response.status_code));
    PyDict_SetItemString(response_dict, "body", PyUnicode_FromString(response.body));
    PyDict_SetItemString(response_dict, "response_time_us", PyLong_FromUnsignedLongLong(response.response_time_us));
    PyDict_SetItemString(response_dict, "success", PyBool_FromLong(response.success));
    PyDict_SetItemString(response_dict, "error_message", PyUnicode_FromString(response.error_message));
    
    // WebSocket-specific data
    PyObject* ws_data = PyDict_New();
    PyDict_SetItemString(ws_data, "messages_sent", PyLong_FromLong(response.protocol_data.websocket.messages_sent));
    PyDict_SetItemString(ws_data, "bytes_sent", PyLong_FromUnsignedLongLong(response.protocol_data.websocket.bytes_sent));
    PyDict_SetItemString(response_dict, "websocket_data", ws_data);
    
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
        PyErr_SetString(PyExc_RuntimeError, response.error_message);
        return NULL;
    }
    
    PyObject* response_dict = PyDict_New();
    PyDict_SetItemString(response_dict, "protocol", PyUnicode_FromString("websocket"));
    PyDict_SetItemString(response_dict, "status_code", PyLong_FromLong(response.status_code));
    PyDict_SetItemString(response_dict, "body", PyUnicode_FromString(response.body));
    PyDict_SetItemString(response_dict, "response_time_us", PyLong_FromUnsignedLongLong(response.response_time_us));
    PyDict_SetItemString(response_dict, "success", PyBool_FromLong(response.success));
    PyDict_SetItemString(response_dict, "error_message", PyUnicode_FromString(response.error_message));
    
    return response_dict;
}

static PyMethodDef LoadTestEngine_methods[] = {
    {"execute_request", (PyCFunction)(void(*)(void))LoadTestEngine_execute_request, METH_VARARGS | METH_KEYWORDS,
     "Execute a single HTTP request"},
    {"start_load_test", (PyCFunction)(void(*)(void))LoadTestEngine_start_load_test, METH_VARARGS | METH_KEYWORDS,
     "Start a load test with multiple requests"},
    {"get_metrics", (PyCFunction)LoadTestEngine_get_metrics, METH_NOARGS,
     "Get current performance metrics"},
    {"reset_metrics", (PyCFunction)LoadTestEngine_reset_metrics, METH_NOARGS,
     "Reset performance metrics"},
    {"websocket_connect", (PyCFunction)(void(*)(void))LoadTestEngine_websocket_connect, METH_VARARGS | METH_KEYWORDS,
     "Connect to a WebSocket server"},
    {"websocket_send", (PyCFunction)(void(*)(void))LoadTestEngine_websocket_send, METH_VARARGS | METH_KEYWORDS,
     "Send a message to a WebSocket connection"},
    {"websocket_close", (PyCFunction)(void(*)(void))LoadTestEngine_websocket_close, METH_VARARGS | METH_KEYWORDS,
     "Close a WebSocket connection"},
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

static PyModuleDef loadspiker_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "loadspiker",
    .m_doc = "High-performance load testing module",
    .m_size = -1,
};

PyMODINIT_FUNC PyInit_loadspiker(void) {
    PyObject* m;
    
    if (PyType_Ready(&LoadTestEngineType) < 0)
        return NULL;
    
    m = PyModule_Create(&loadspiker_module);
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
