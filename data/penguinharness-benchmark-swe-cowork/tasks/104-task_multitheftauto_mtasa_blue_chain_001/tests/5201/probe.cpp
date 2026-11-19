#include "Client/sdk/game/CVehicle.h"
#include <iostream>
int main() {
    auto getter = &CVehicle::GetNitroLevel;
    auto setter = &CVehicle::SetNitroLevel;
    if (!getter || !setter) return 1;
    CVector value(0.0f, 3.0f, 4.0f);
    return value.Length() == 5.0f ? 0 : 2;
}

