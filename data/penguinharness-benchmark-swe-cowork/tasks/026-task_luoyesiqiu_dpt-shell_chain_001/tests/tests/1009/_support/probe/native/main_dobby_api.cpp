#include <cstdint>
#include "dobby/dobby.h"

int main() {
    if (sizeof(addr_t) != sizeof(void *)) return 50;
#if defined(__x86_64__)
    DobbyRegisterContext context{};
    context.rsp = 0;
    return sizeof(context) >= sizeof(std::uintptr_t) ? 0 : 51;
#else
    return sizeof(DobbyRegisterContext) > 0 ? 0 : 52;
#endif
}
