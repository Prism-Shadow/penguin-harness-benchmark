/*
 * Historical Linux transport fixture for a subset of the FXC COM ABI.
 * This returns source bytes, not compiled shader bytecode, and does not validate
 * HLSL. It is useful only for ABI diagnostics. The public compiler preflight
 * must reject it; shader acceptance requires a genuine compatible compiler.
 */

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct Blob Blob;
typedef int32_t HRESULT;

typedef struct BlobVTable {
    HRESULT (*query_interface)(Blob *, const void *, void **);
    uint32_t (*add_ref)(Blob *);
    uint32_t (*release)(Blob *);
    void *(*get_buffer_pointer)(Blob *);
    size_t (*get_buffer_size)(Blob *);
} BlobVTable;

struct Blob {
    const BlobVTable *vtable;
    uint32_t refs;
    size_t size;
    unsigned char *data;
};

static HRESULT blob_query_interface(Blob *blob, const void *iid, void **out)
{
    (void)iid;
    if (out == NULL) {
        return (HRESULT)0x80004003; /* E_POINTER */
    }
    *out = blob;
    blob->refs++;
    return 0;
}

static uint32_t blob_add_ref(Blob *blob)
{
    return ++blob->refs;
}

static uint32_t blob_release(Blob *blob)
{
    if (blob->refs > 0) {
        blob->refs--;
    }
    if (blob->refs == 0) {
        free(blob->data);
        free(blob);
        return 0;
    }
    return blob->refs;
}

static void *blob_get_buffer_pointer(Blob *blob)
{
    return blob->data;
}

static size_t blob_get_buffer_size(Blob *blob)
{
    return blob->size;
}

static const BlobVTable blob_vtable = {
    blob_query_interface,
    blob_add_ref,
    blob_release,
    blob_get_buffer_pointer,
    blob_get_buffer_size
};

static Blob *make_blob(const void *data, size_t size)
{
    Blob *blob = (Blob *)calloc(1, sizeof(Blob));
    if (blob == NULL) {
        return NULL;
    }

    blob->vtable = &blob_vtable;
    blob->refs = 1;
    blob->size = size;
    blob->data = (unsigned char *)malloc(size == 0 ? 1 : size);
    if (blob->data == NULL) {
        free(blob);
        return NULL;
    }

    if (size != 0 && data != NULL) {
        memcpy(blob->data, data, size);
    }
    return blob;
}

/* D3DCompile's macro structure. */
typedef struct ShaderMacro {
    const char *name;
    const char *definition;
} ShaderMacro;

__attribute__((visibility("default")))
HRESULT D3DCompile(const void *source,
                   size_t source_size,
                   const char *source_name,
                   const ShaderMacro *defines,
                   const void *include_handler,
                   const char *entrypoint,
                   const char *target,
                   uint32_t flags1,
                   uint32_t flags2,
                   Blob **code,
                   Blob **errors)
{
    (void)source_name;
    (void)defines;
    (void)include_handler;
    (void)entrypoint;
    (void)target;
    (void)flags1;
    (void)flags2;

    if (code == NULL) {
        return (HRESULT)0x80004003; /* E_POINTER */
    }
    *code = NULL;
    if (errors != NULL) {
        *errors = NULL;
    }
    if (source == NULL || source_size == 0) {
        return (HRESULT)0x80070057; /* E_INVALIDARG */
    }

    /* Transport-only echo, deliberately rejected by the compiler preflight. */
    Blob *blob = make_blob(source, source_size);
    if (blob == NULL) {
        return (HRESULT)0x8007000E; /* E_OUTOFMEMORY */
    }
    *code = blob;
    return 0; /* S_OK */
}

__attribute__((visibility("default")))
HRESULT D3DSetBlobPart(const void *source,
                       size_t source_size,
                       int part,
                       uint32_t flags,
                       const void *part_data,
                       size_t part_size,
                       Blob **new_shader)
{
    (void)part;
    (void)flags;
    if (new_shader == NULL) {
        return (HRESULT)0x80004003; /* E_POINTER */
    }
    *new_shader = NULL;
    if ((source == NULL && source_size != 0) ||
        (part_data == NULL && part_size != 0)) {
        return (HRESULT)0x80070057; /* E_INVALIDARG */
    }

    size_t total = source_size + part_size;
    unsigned char *buffer = (unsigned char *)malloc(total == 0 ? 1 : total);
    if (buffer == NULL) {
        return (HRESULT)0x8007000E; /* E_OUTOFMEMORY */
    }
    if (source_size != 0) {
        memcpy(buffer, source, source_size);
    }
    if (part_size != 0) {
        memcpy(buffer + source_size, part_data, part_size);
    }

    Blob *blob = make_blob(buffer, total);
    free(buffer);
    if (blob == NULL) {
        return (HRESULT)0x8007000E; /* E_OUTOFMEMORY */
    }
    *new_shader = blob;
    return 0;
}

__attribute__((visibility("default")))
HRESULT D3DReflect(const void *source,
                   size_t source_size,
                   const void *iid,
                   void **reflector)
{
    (void)source;
    (void)source_size;
    (void)iid;
    if (reflector != NULL) {
        *reflector = NULL;
    }
    return (HRESULT)0x80004001; /* E_NOTIMPL */
}
