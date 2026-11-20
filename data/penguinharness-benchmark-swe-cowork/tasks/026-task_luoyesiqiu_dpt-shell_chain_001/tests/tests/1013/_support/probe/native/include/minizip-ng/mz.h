#pragma once
#include <cstdint>
struct mz_zip_file { const char *filename = nullptr; int64_t uncompressed_size = 0; int32_t compression_method = 0; };
#define MZ_OK 0
#define MZ_OPEN_MODE_READ 1
static inline void *mz_zip_create() { return nullptr; }
static inline void mz_zip_create(void **p) { if (p) *p = nullptr; }
static inline int32_t mz_zip_open(void *, void *, int32_t) { return -1; }
static inline int32_t mz_zip_goto_first_entry(void *) { return -1; }
static inline int32_t mz_zip_goto_next_entry(void *) { return -1; }
static inline int32_t mz_zip_entry_get_info(void *, mz_zip_file **) { return -1; }
static inline int32_t mz_zip_entry_read_open(void *, int32_t, const char *) { return -1; }
static inline int32_t mz_zip_entry_read(void *, void *, int32_t) { return -1; }
static inline void mz_zip_close(void *) {}
static inline void mz_zip_delete(void **) {}
