#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef void (*callback)(void *, void *);
typedef struct { int type; int value; } value;
typedef struct { intptr_t type; char name[128]; int kind; callback call; } member;
static member members[512];
static int member_count;
static int definitions[512];
static value arguments[2], returned;
static int argument_count, return_count;
static char error_text[2048];
static int active_type;
static const char *active_member;

/* These are assertions about values passed by the compiled production callback.
 * The dispatcher runs this complete native/managed chain in its own process.
 * Report the observed ABI mismatch instead of aborting without any evidence. */
static void require_value_type(value *entry, int expected, const char *getter)
{
    if (!entry || entry->type != expected)
    {
        fprintf(stderr, "AssertionError: generated wrapper selected incompatible native getter: "
                "class=%d member=%s argument_count=%d getter=%s expected_type=%d actual_type=%d\n",
                active_type, active_member ? active_member : "<none>", argument_count,
                getter, expected, entry ? entry->type : -1);
        fflush(stderr);
        exit(1);
    }
}
static void *create_registry(void) { return (void *)1; }
static void define_class(void *registry, void *type, void *parent, const char *module, const char *name,
                         void *constructor, void *finalize, void *data, int copy, int trace)
{
    intptr_t index = (intptr_t)type;
    if (index <= 0 || index >= 512) abort();
    definitions[index]++;
}
static void set_sizes(void *registry, void *type, int methods, int functions, int properties, int variables) { }
static void add_member(void *type, const char *name, int kind, callback call)
{
    if (!call) return;
    if (member_count >= 512) abort();
    member *entry = &members[member_count++];
    entry->type = (intptr_t)type; entry->kind = kind; entry->call = call;
    snprintf(entry->name, sizeof(entry->name), "%s", name);
}
static void set_method(void *registry, void *type, int index, const char *name, int is_static,
                       callback call, void *data, int copy) { add_member(type, name, 0, call); }
static void set_property(void *registry, void *type, int index, const char *name, int is_static,
                         callback getter, callback setter, void *getter_data, void *setter_data, int copy)
{ add_member(type, name, 1, getter); add_member(type, name, 2, setter); }
static void on_not_found(void *registry, void *call) { }
static unsigned char trace_lifecycle(void *registry, void *type, void *enter, void *exit) { return 1; }
typedef struct
{
    void *(*create_registry)(void);
    void *alloc_type_infos, *set_type_info, *create_signature_info;
    void (*define_class)(void *, void *, void *, const char *, const char *, void *, void *, void *, int, int);
    void (*set_sizes)(void *, void *, int, int, int, int);
    void (*set_method)(void *, void *, int, const char *, int, callback, void *, int);
    void (*set_property)(void *, void *, int, const char *, int, callback, callback, void *, void *, int);
    void *get_class_data;
    void (*on_not_found)(void *, void *);
    void *class_type_info, *find_type_id;
    unsigned char (*trace_lifecycle)(void *, void *, void *, void *);
} register_api;
static register_api registry_api = { create_registry, NULL, NULL, NULL, define_class, set_sizes,
    set_method, set_property, NULL, on_not_found, NULL, NULL, trace_lifecycle };
void *GetRegisterApi(void) { return &registry_api; }
int GetPapiVersion(void) { return 11; }
int probe_definitions(int type) { return type > 0 && type < 512 ? definitions[type] : -1; }
callback probe_callback(int type, const char *name, int kind)
{
    for (int index = 0; index < member_count; index++)
        if (members[index].type == type && members[index].kind == kind && strcmp(members[index].name, name) == 0)
            return members[index].call;
    return NULL;
}
int probe_invoke(int type, const char *name, int kind, int count, int first_type, int first, int second_type, int second)
{
    active_type = type; active_member = name;
    argument_count = count; return_count = 0; error_text[0] = 0;
    arguments[0] = (value){first_type, first}; arguments[1] = (value){second_type, second};
    callback call = probe_callback(type, name, kind);
    if (!call) { snprintf(error_text, sizeof(error_text), "missing registered member %s", name); return -1; }
    call((void *)1, (void *)2);
    return return_count;
}
int probe_return_value(void) { return returned.value; }
const char *probe_error(void) { return error_text; }
void *pesapi_get_env(void *apis, void *info) { return (void *)3; }
void *pesapi_get_env_private(void *apis, void *env) { return NULL; }
int pesapi_get_args_len(void *apis, void *info) { return argument_count; }
void *pesapi_get_arg(void *apis, void *info, int index) { return index >= 0 && index < argument_count && index < 2 ? &arguments[index] : NULL; }
int pesapi_get_value_int32(void *apis, void *env, value *entry) { require_value_type(entry, 1, "int32"); return entry->value; }
int pesapi_get_value_bool(void *apis, void *env, value *entry) { require_value_type(entry, 2, "bool"); return entry->value != 0; }
int pesapi_is_int32(void *apis, void *env, value *entry) { return entry && entry->type == 1; }
int pesapi_is_boolean(void *apis, void *env, value *entry) { return entry && entry->type == 2; }
int pesapi_is_double(void *apis, void *env, value *entry) { return entry && entry->type == 1; }
int pesapi_is_null(void *apis, void *env, value *entry) { return !entry; }
int pesapi_is_undefined(void *apis, void *env, value *entry) { return !entry; }
void *pesapi_create_int32(void *apis, void *env, int number) { returned = (value){1, number}; return &returned; }
void *pesapi_create_boolean(void *apis, void *env, int boolean) { returned = (value){2, boolean}; return &returned; }
void pesapi_add_return(void *apis, void *info, value *entry) { if (!entry) abort(); returned = *entry; return_count++; }
void pesapi_throw_by_string(void *apis, void *info, const char *message) { snprintf(error_text, sizeof(error_text), "%s", message); }
