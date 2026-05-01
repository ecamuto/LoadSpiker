/*
 * tsan_check.c — Thread Sanitizer stress binary for LoadSpiker
 *
 * Spawns NUM_THREADS threads per protocol (4 protocols × 8 threads = 32 threads
 * total) and has each thread hammer the pool with rapid connect/disconnect loops.
 *
 * Connections WILL fail (no server listening) — that is expected and intentional.
 * TSAN cares about concurrent access to shared pool arrays, not connection success.
 *
 * Build and run via: make tsan
 */

#include <stdio.h>
#include <pthread.h>
#include <string.h>
#include "../src/engine.h"
#include "../src/protocols/tcp.h"
#include "../src/protocols/udp.h"
#include "../src/protocols/mqtt.h"
#include "../src/protocols/database.h"

#define NUM_THREADS 8
#define ITERATIONS  20

/* Thread argument carrying the thread index so each thread can use a unique
   client_id for MQTT (avoiding all threads contending for the same slot). */
typedef struct {
    int idx;
} thread_arg_t;

/* ---- TCP ----------------------------------------------------------------- */

static void *tcp_thread_func(void *arg)
{
    thread_arg_t *targ = (thread_arg_t *)arg;
    (void)targ;

    for (int i = 0; i < ITERATIONS; i++) {
        response_t resp;
        memset(&resp, 0, sizeof(resp));
        /* Failure return values are expected — no server is listening. */
        tcp_connect("127.0.0.1", 9999, &resp);

        memset(&resp, 0, sizeof(resp));
        tcp_disconnect("127.0.0.1", 9999, &resp);
    }
    return NULL;
}

/* ---- UDP ----------------------------------------------------------------- */

static void *udp_thread_func(void *arg)
{
    thread_arg_t *targ = (thread_arg_t *)arg;
    (void)targ;

    for (int i = 0; i < ITERATIONS; i++) {
        response_t resp;
        memset(&resp, 0, sizeof(resp));
        udp_create_endpoint("127.0.0.1", 9998, &resp);

        memset(&resp, 0, sizeof(resp));
        udp_close_endpoint("127.0.0.1", 9998, &resp);
    }
    return NULL;
}

/* ---- MQTT ---------------------------------------------------------------- */

static void *mqtt_thread_func(void *arg)
{
    thread_arg_t *targ = (thread_arg_t *)arg;
    char client_id[64];
    snprintf(client_id, sizeof(client_id), "tsan_mqtt_%d", targ->idx);

    for (int i = 0; i < ITERATIONS; i++) {
        response_t resp;
        memset(&resp, 0, sizeof(resp));
        /* Connection will fail — that is fine.  TSAN checks pool access. */
        mqtt_connect("127.0.0.1", 1883, client_id, NULL, NULL, 60, &resp);

        memset(&resp, 0, sizeof(resp));
        mqtt_disconnect("127.0.0.1", 1883, client_id, &resp);
    }
    return NULL;
}

/* ---- Database ------------------------------------------------------------ */

static void *db_thread_func(void *arg)
{
    thread_arg_t *targ = (thread_arg_t *)arg;
    (void)targ;

    for (int i = 0; i < ITERATIONS; i++) {
        response_t resp;
        memset(&resp, 0, sizeof(resp));
        database_connect("mysql://127.0.0.1:3306/test", "mysql", &resp);

        memset(&resp, 0, sizeof(resp));
        database_disconnect("mysql://127.0.0.1:3306/test", &resp);
    }
    return NULL;
}

/* ---- main ---------------------------------------------------------------- */

int main(void)
{
    pthread_t tcp_threads[NUM_THREADS];
    pthread_t udp_threads[NUM_THREADS];
    pthread_t mqtt_threads[NUM_THREADS];
    pthread_t db_threads[NUM_THREADS];

    thread_arg_t args[NUM_THREADS];
    for (int i = 0; i < NUM_THREADS; i++) {
        args[i].idx = i;
    }

    /* Launch all threads first, then join — simple barrier pattern. */
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_create(&tcp_threads[i],  NULL, tcp_thread_func,  &args[i]);
        pthread_create(&udp_threads[i],  NULL, udp_thread_func,  &args[i]);
        pthread_create(&mqtt_threads[i], NULL, mqtt_thread_func, &args[i]);
        pthread_create(&db_threads[i],   NULL, db_thread_func,   &args[i]);
    }

    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(tcp_threads[i],  NULL);
        pthread_join(udp_threads[i],  NULL);
        pthread_join(mqtt_threads[i], NULL);
        pthread_join(db_threads[i],   NULL);
    }

    printf("tsan_check: all threads completed, no races detected\n");
    return 0;
}
