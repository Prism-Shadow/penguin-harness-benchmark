#include "Client/sdk/game/CVehicle.h"
#include <type_traits>
int main() {
    auto health = &CVehicle::GetHealth;
    static_assert(std::is_same_v<decltype(health), float (CVehicle::*)()>);
    CVector value(3.0f, 4.0f, 0.0f);
    return value.LengthSquared() == 25.0f ? 0 : 1;
}

