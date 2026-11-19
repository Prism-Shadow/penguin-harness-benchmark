#pragma once

#include <cstdint>
#include <list>
#include <unordered_map>
#include <unordered_set>

struct CVector
{
    float fX{0.0f};
    float fY{0.0f};
    float fZ{0.0f};
};

struct CVector2D
{
    float fX{0.0f};
    float fY{0.0f};
};

class CCoreInterface;
class CGame;
class CMultiplayer;
class CNet;
