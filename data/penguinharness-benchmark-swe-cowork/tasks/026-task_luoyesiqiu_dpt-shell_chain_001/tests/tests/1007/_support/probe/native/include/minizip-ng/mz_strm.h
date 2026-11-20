#pragma once
#include <cstdint>
#include "mz.h"
static inline void *mz_stream_mem_create() { return nullptr; }
static inline void mz_stream_mem_create(void **p) { if (p) *p = nullptr; }
static inline void mz_stream_mem_set_buffer(void *, void *, int64_t) {}
static inline int32_t mz_stream_open(void *, const char *, int32_t) { return -1; }
static inline void mz_stream_mem_delete(void **) {}
