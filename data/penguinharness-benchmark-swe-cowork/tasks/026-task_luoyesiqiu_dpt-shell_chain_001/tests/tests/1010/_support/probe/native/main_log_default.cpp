#include <cstdarg>
#include <cstdio>

static int calls = 0;
extern "C" int probe_android_log(int, const char *, const char *, ...) {
    ++calls;
    return 0;
}

const char *getThreadName() { return "probe-thread"; }

#include "common/dpt_log.h"

int main() {
    DLOGD("probe-%d", 7);
    return calls == 0 ? 0 : 16;
}
