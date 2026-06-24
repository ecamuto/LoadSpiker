/*
 * pool_common.h — shared helpers for the per-protocol connection pools.
 *
 * TCP, UDP, and MQTT each keep a fixed-size array of slots matched on
 * (host, port, <id>) and protected by their own mutex. The match condition and
 * the one-time "pool full" warning are identical across all three; this header
 * factors out just those two pieces. Slot allocation and the per-protocol field
 * initialisation stay in each translation unit, since the struct types and the
 * extra fields differ.
 *
 * All callers must already hold the relevant pool mutex — these helpers do no
 * locking of their own.
 */

#ifndef LOADSPIKER_POOL_COMMON_H
#define LOADSPIKER_POOL_COMMON_H

#include <stdio.h>
#include <string.h>

/*
 * Returns non-zero when the pool has no free slots, emitting a single stderr
 * warning the first time (tracked via *warned). `proto` and `cap_macro` only
 * shape the message text, e.g. pool_reserve_full(n, MAX, &warned, "TCP",
 * "MAX_TCP_CONNECTIONS").
 */
static inline int pool_reserve_full(int count, int max, int *warned,
                                    const char *proto, const char *cap_macro) {
    if (count >= max) {
        if (!*warned) {
            fprintf(stderr, "[LoadSpiker] %s pool full — increase %s\n",
                    proto, cap_macro);
            *warned = 1;
        }
        return 1;
    }
    return 0;
}

/*
 * True when `slot` matches (host, port, id). The id field name differs per
 * protocol (conn_id for TCP/UDP, client_id for MQTT), so it is passed in.
 */
#define POOL_SLOT_MATCHES(slot, host_, port_, idfield, id_)  \
    ((slot).port == (port_) &&                               \
     strcmp((slot).host, (host_)) == 0 &&                    \
     strcmp((slot).idfield, (id_)) == 0)

#endif /* LOADSPIKER_POOL_COMMON_H */
