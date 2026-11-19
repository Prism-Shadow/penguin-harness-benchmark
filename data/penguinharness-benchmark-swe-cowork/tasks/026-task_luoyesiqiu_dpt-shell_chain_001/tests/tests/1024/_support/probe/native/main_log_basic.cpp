#include <cstdarg>
#include <cstdio>
#include <cstring>

static char captured[1024] = {};
extern "C" int probe_android_log(int, const char *, const char *format, ...) {
    va_list args;
    va_start(args, format);
    std::vsnprintf(captured, sizeof(captured), format, args);
    va_end(args);
    return 0;
}

const char *getThreadName() { return "probe-thread"; }

#include "common/dpt_log.h"

int main() {
    DLOGD("stable-%d", 8);
    return std::strstr(captured, "stable-8") == nullptr ? 33 : 0;
}
