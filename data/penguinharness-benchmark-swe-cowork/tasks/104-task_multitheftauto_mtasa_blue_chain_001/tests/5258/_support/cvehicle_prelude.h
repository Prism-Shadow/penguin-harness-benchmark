#pragma once
#include <cstdint>
#include <cstddef>
#include <array>
using BYTE = std::uint8_t;
using WORD = std::uint16_t;
using DWORD = std::uint32_t;
using uint = unsigned int;
using ushort = unsigned short;
using uchar = unsigned char;
constexpr float FLOAT_EPSILON = 0.0001f;
enum eBone { BONE_DUMMY = 0 };
namespace SharedUtil {
struct SColor {
    std::uint8_t R{0}, G{0}, B{0}, A{255};
};
}
using SColor = SharedUtil::SColor;
template <typename T, std::size_t N>
using SFixedArray = std::array<T, N>;
