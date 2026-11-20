#include "Client/sdk/game/CVehicle.h"
int main()
{
    auto health = &CVehicle::GetHealth;
    CVector value(2.0f, 3.0f, 6.0f);
    return health && value.LengthSquared() == 49.0f ? 0 : 1;
}
