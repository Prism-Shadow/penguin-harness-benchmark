#include <cstdint>
#include "dex/MultiDexCode.h"

int main() {
    std::uint8_t buffer[] = {7, 0, 2, 0, 0, 0, 0, 0};
    auto *registry = dpt::data::MultiDexCode::getInst();
    registry->init(buffer, sizeof(buffer));
    if (registry->readVersion() != 7) return 41;
    if (registry->readDexCount() != 2) return 42;
    return 0;
}
