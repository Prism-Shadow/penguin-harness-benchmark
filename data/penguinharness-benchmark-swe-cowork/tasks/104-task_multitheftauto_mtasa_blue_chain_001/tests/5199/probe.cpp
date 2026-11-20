#include <cstdint>
#include "Shared/sdk/CVector.h"
#include <iostream>
int main() {
    CVector value(1.0f, 2.0f, 3.0f);
    value += CVector(2.0f, -1.0f, 4.0f);
    if (value.fX != 3.0f || value.fY != 1.0f || value.fZ != 7.0f) return 1;
    std::cout << value.LengthSquared() << "\n";
    return 0;
}
