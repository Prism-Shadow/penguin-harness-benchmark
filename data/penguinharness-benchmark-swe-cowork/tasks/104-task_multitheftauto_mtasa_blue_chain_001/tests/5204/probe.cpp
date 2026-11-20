#include "Client/sdk/game/CVehicle.h"
#include <iostream>
int main() {
    auto can_exit = &CVehicle::CanPedStepOutCar;
    if (!can_exit) return 1;
    std::cout << "exit-policy-interface\n";
    return 0;
}

