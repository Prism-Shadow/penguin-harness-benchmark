#include "net/bitstream.h"
#include <iostream>
int main() {
    const auto value = static_cast<unsigned short>(eBitStreamVersion::VoiceDecodeBurstLimit);
    const auto latest = static_cast<unsigned short>(eBitStreamVersion::Latest);
    if (latest != value) return 1;
    if (value <= static_cast<unsigned short>(eBitStreamVersion::Unk)) return 2;
    std::cout << value << "\n";
    return 0;
}

