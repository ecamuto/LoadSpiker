/*
 * asan_check.c — AddressSanitizer harness for LoadSpiker
 *
 * Injecting ASan into a stock (non-instrumented) CPython on macOS does not work
 * reliably — the runtime loads too late and reports "Interceptors are not
 * working". So, mirroring tests/tsan_check.c, this is a standalone binary with a
 * NATIVE instrumented main(): ASan initializes first and its malloc/memcpy
 * interceptors install correctly.
 *
 * It drives the previously-vulnerable MQTT packet encoders (V1 CONNECT,
 * V2 PUBLISH, V3 SUBSCRIBE) at their MAXIMUM permitted input lengths so ASan
 * watches the fixed-size stack buffers at the boundary, and also exercises the
 * over-length rejection guards. A tiny in-process mock broker provides the
 * CONNACK/SUBACK bytes the encoders' send/recv paths require.
 *
 * Build and run via: make test-asan
 *
 * NOTE: the Python refcount-leak fix (V9) lives in python_extension.c and needs
 * a live interpreter, so it is NOT covered here (macOS also lacks LeakSanitizer).
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>

#include "../src/engine.h"
#include "../src/protocols/tcp.h"
#include "../src/protocols/udp.h"
#include "../src/protocols/mqtt.h"
#include "../src/protocols/database.h"

static int g_failures = 0;

#define CHECK(cond, msg) do {                                   \
    if (!(cond)) { printf("  FAIL: %s\n", (msg)); g_failures++; } \
    else         { printf("  ok:   %s\n", (msg)); }             \
} while (0)

/* ---- Mock MQTT broker --------------------------------------------------- */
/*
 * Listens on an ephemeral port. On each accepted connection it writes a valid
 * 4-byte CONNACK (0x20 0x02 0x00 0x00) followed by a valid 5-byte SUBACK
 * (0x90 0x03 0x00 0x01 0x00), then drains until the client hangs up.
 *
 * mqtt_connect reads exactly the 4 CONNACK bytes; the QoS-0 PUBLISH reads
 * nothing; mqtt_subscribe then reads exactly the 5 SUBACK bytes left buffered.
 */
static int  g_broker_port = 0;
static pthread_mutex_t g_port_mutex  = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t  g_port_ready   = PTHREAD_COND_INITIALIZER;

static void *broker_thread(void *arg)
{
    (void)arg;
    int lfd = socket(AF_INET, SOCK_STREAM, 0);
    if (lfd < 0) { perror("broker socket"); return NULL; }

    int one = 1;
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port        = 0; /* ephemeral */
    if (bind(lfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("broker bind"); close(lfd); return NULL;
    }
    socklen_t alen = sizeof(addr);
    getsockname(lfd, (struct sockaddr *)&addr, &alen);
    listen(lfd, 4);

    pthread_mutex_lock(&g_port_mutex);
    g_broker_port = ntohs(addr.sin_port);
    pthread_cond_signal(&g_port_ready);
    pthread_mutex_unlock(&g_port_mutex);

    static const unsigned char connack_suback[9] = {
        0x20, 0x02, 0x00, 0x00,             /* CONNACK: accepted */
        0x90, 0x03, 0x00, 0x01, 0x00,       /* SUBACK:  packet 1, QoS 0 */
    };

    for (;;) {
        int cfd = accept(lfd, NULL, NULL);
        if (cfd < 0) continue;
        ssize_t w = write(cfd, connack_suback, sizeof(connack_suback));
        (void)w;
        char drain[512];
        while (read(cfd, drain, sizeof(drain)) > 0) { /* discard client packets */ }
        close(cfd);
    }
    return NULL;
}

static int wait_for_broker(void)
{
    pthread_mutex_lock(&g_port_mutex);
    while (g_broker_port == 0) pthread_cond_wait(&g_port_ready, &g_port_mutex);
    int port = g_broker_port;
    pthread_mutex_unlock(&g_port_mutex);
    return port;
}

/* Build a heap string of `len` repeated 'a' (avoids huge stack arrays). */
static char *make_str(size_t len)
{
    char *s = malloc(len + 1);
    if (!s) { perror("malloc"); exit(2); }
    memset(s, 'a', len);
    s[len] = '\0';
    return s;
}

int main(void)
{
    response_t resp;

    printf("asan_check: starting\n");

    /* --- Over-length rejection guards (V1/V2/V3 input bound-checks) -------- */
    /* These return before any socket work, so no broker is needed. */
    {
        char *too_long_id = make_str(MAX_MQTT_CLIENT_ID_LENGTH + 64);
        memset(&resp, 0, sizeof(resp));
        int rc = mqtt_connect("127.0.0.1", 1883, too_long_id, NULL, NULL, 60, &resp);
        CHECK(rc == -1 && resp.status_code == 400, "over-length client_id rejected");
        free(too_long_id);

        char *too_long_topic = make_str(MAX_MQTT_TOPIC_LENGTH + 64);
        char *short_msg = make_str(4);
        memset(&resp, 0, sizeof(resp));
        rc = mqtt_publish("127.0.0.1", 1883, "id", too_long_topic, short_msg,
                          MQTT_QOS_0, false, &resp);
        CHECK(rc == -1 && resp.status_code == 400, "over-length publish topic rejected");
        free(too_long_topic); free(short_msg);
    }

    /* --- Boundary encoder paths (max-length valid input) ------------------ */
    pthread_t broker;
    pthread_create(&broker, NULL, broker_thread, NULL);
    int port = wait_for_broker();
    printf("asan_check: mock broker on 127.0.0.1:%d\n", port);

    /* CONNECT (V1): client_id, username, password all at their max length so
       the 1024-byte CONNECT buffer is filled as far as the API permits. */
    char *id   = make_str(MAX_MQTT_CLIENT_ID_LENGTH - 1);
    char *user = make_str(MAX_MQTT_USERNAME_LENGTH - 1);
    char *pass = make_str(MAX_MQTT_PASSWORD_LENGTH - 1);
    memset(&resp, 0, sizeof(resp));
    int rc = mqtt_connect("127.0.0.1", port, id, user, pass, 60, &resp);
    CHECK(rc == 0 && resp.success, "max-length CONNECT encodes and handshakes");

    /* PUBLISH (V2): topic and payload at max length → fills the
       MAX_MQTT_MESSAGE_LENGTH+512 buffer near its boundary. QoS 0 = no ack. */
    char *topic = make_str(MAX_MQTT_TOPIC_LENGTH - 1);
    char *msg   = make_str(MAX_MQTT_MESSAGE_LENGTH - 1);
    memset(&resp, 0, sizeof(resp));
    rc = mqtt_publish("127.0.0.1", port, id, topic, msg, MQTT_QOS_0, false, &resp);
    CHECK(rc == 0 && resp.success, "max-length PUBLISH encodes");

    /* SUBSCRIBE (V3): topic at max length → fills the 512-byte buffer. Reads
       the buffered SUBACK. */
    memset(&resp, 0, sizeof(resp));
    rc = mqtt_subscribe("127.0.0.1", port, id, topic, MQTT_QOS_0, &resp);
    CHECK(rc == 0 && resp.success, "max-length SUBSCRIBE encodes");

    memset(&resp, 0, sizeof(resp));
    mqtt_disconnect("127.0.0.1", port, id, &resp);

    free(id); free(user); free(pass); free(topic); free(msg);

    /* --- General heap/buffer coverage for the other protocols ------------- */
    memset(&resp, 0, sizeof(resp));
    tcp_connect("127.0.0.1", 9999, "asan_tcp", &resp);
    memset(&resp, 0, sizeof(resp));
    tcp_disconnect("127.0.0.1", 9999, "asan_tcp", &resp);

    memset(&resp, 0, sizeof(resp));
    udp_create_endpoint("127.0.0.1", 9998, "asan_udp", &resp);
    memset(&resp, 0, sizeof(resp));
    udp_close_endpoint("127.0.0.1", 9998, "asan_udp", &resp);

    memset(&resp, 0, sizeof(resp));
    database_connect("mysql://127.0.0.1:3306/test", "asan_db", "mysql", &resp);
    memset(&resp, 0, sizeof(resp));
    database_disconnect("mysql://127.0.0.1:3306/test", "asan_db", &resp);

    if (g_failures == 0) {
        printf("asan_check: all checks passed, no memory errors detected\n");
        return 0;
    }
    printf("asan_check: %d check(s) FAILED\n", g_failures);
    return 1;
}
