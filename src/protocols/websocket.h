#ifndef WEBSOCKET_H
#define WEBSOCKET_H

#include "../engine.h"
#include <pthread.h>
#include <sys/time.h>

// WebSocket connection functions
int websocket_connect(const char* url, const char* subprotocol, response_t* response);
int websocket_send_message(const char* url, const char* message, response_t* response);
int websocket_close_connection(const char* url, response_t* response);

#endif
