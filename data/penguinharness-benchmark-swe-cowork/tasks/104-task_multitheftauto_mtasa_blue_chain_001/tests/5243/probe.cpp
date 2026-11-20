#include "Client/sdk/game/CVehicle.h"
#include <iostream>
int main() {
    static_assert(SIREN_COUNT_MAX == 8);
    CVector position(0.0f, 0.0f, 0.0f);
    if (position.LengthSquared() != 0.0f) return 1;
    std::cout << "siren-boundary-interface\n";
    return 0;
}

