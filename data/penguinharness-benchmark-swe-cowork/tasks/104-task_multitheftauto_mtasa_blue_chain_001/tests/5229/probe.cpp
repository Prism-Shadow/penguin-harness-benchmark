#include "Client/sdk/game/CVehicle.h"
#include <iostream>
int main() {
    auto health = &CVehicle::GetHealth;
    if (!health) return 1;
    CVector value(1.0f, 2.0f, 2.0f);
    return value.LengthSquared() == 9.0f ? 0 : 1;
}

