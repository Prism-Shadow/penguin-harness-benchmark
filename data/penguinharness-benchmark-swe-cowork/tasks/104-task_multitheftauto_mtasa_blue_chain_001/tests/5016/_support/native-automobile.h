#pragma once
#include <array>
#include <cstdlib>
enum class eCarNodes { MISC_B };
constexpr int FRONT_LEFT_PANEL = 0;
struct NativePanelBoundary {
    std::uint16_t m_nFrameId = 0xFFFF;
    void SetPanel(std::int16_t, int, float) { std::abort(); }
};
struct NativeAutomobileBoundary {
    struct Chassis {
        float m_fOpenAngle, m_fClosedAngle;
        int m_nDirn, m_nAxis, m_nDoorState;
    } m_swingingChassis;
    std::array<void*, 1> m_aCarNodes{};
    std::array<NativePanelBoundary, 1> m_panels;
};
class CAutomobileSA : public CVehicleSA {
public:
    NativeAutomobileBoundary* GetAutomobileInterface() { std::abort(); }
};
