#include <cstring>

void getCodeCachePath(char *, size_t) __attribute__((weak));

int main() {
    if (getCodeCachePath == nullptr) return 12;
    char path[256] = {};
    getCodeCachePath(path, sizeof(path));
    if (std::strstr(path, "/code_cache/") == nullptr) return 13;
    return 0;
}
