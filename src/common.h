#ifndef COMMON_H
#define COMMON_H

#include <stdint.h>
#include <sys/time.h>
#include <time.h>

// Unified timing utility for all protocol implementations
static inline uint64_t get_time_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}

#endif // COMMON_H
