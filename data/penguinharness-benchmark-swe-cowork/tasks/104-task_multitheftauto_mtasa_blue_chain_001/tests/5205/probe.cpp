#include "net/Packets.h"
#include <iostream>
int main() {
    if (PACKET_ID_PLAYER_CPUINFO <= PACKET_ID_PLAYER_JOIN) return 1;
    std::cout << static_cast<int>(PACKET_ID_PLAYER_CPUINFO) << "\n";
    return 0;
}
