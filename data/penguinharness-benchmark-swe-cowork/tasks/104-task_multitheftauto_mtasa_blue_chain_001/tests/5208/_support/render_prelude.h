#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

using uint = unsigned int;
using ushort = unsigned short;
using uchar = unsigned char;
using BYTE = unsigned char;
using WORD = unsigned short;
using DWORD = unsigned long;
using UINT = unsigned int;
using SString = std::string;
using LPCSTR = const char*;
using HRESULT = long;
#ifndef FLOAT_EPSILON
constexpr float FLOAT_EPSILON = 0.0001f;
#endif
#define CONST const
struct RECT
{
    long left;
    long top;
    long right;
    long bottom;
};
constexpr DWORD DEFAULT_QUALITY = 0;
class CBuffer
{
};
enum eAspectRatio
{
    ASPECT_RATIO_DEFAULT = 0,
};
template <typename T>
struct FakeClassInit
{
    explicit FakeClassInit(T*) {}
};
#define DECLARE_BASE_CLASS(name) public: FakeClassInit<name> ClassInit;
#define DECLARE_CLASS(name, base) public: FakeClassInit<name> ClassInit;
