#include "net/rpc_enums.h"
#include <iostream>
int main() {
    if (SET_VEHICLE_NITRO_COLOR <= SET_VEHICLE_NITRO_ACTIVATED) return 1;
    std::cout << static_cast<int>(SET_VEHICLE_NITRO_COLOR) << "\n";
    return 0;
}

