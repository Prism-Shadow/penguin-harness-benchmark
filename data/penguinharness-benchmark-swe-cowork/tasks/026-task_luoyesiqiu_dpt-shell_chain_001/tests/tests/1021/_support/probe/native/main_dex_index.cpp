#include <cstdint>
#include "dex/MultiDexCode.h"

int main() {
    std::uint8_t buffer[] = {1, 0, 1, 0, 9, 0, 0, 0};
    auto *registry = dpt::data::MultiDexCode::getInst();
    registry->init(buffer, sizeof(buffer));
    int count = 0;
    auto *index = registry->readDexCodeIndex(&count);
    return count == 1 && index[0] == 9 ? 0 : 43;
}
