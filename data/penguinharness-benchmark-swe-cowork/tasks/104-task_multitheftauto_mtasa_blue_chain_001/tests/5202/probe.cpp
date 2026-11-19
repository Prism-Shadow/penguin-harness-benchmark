#include <cstdint>
#include <functional>
#include <string>
#include <unordered_set>
#include <vector>
#include "SString.h"
#include "SharedUtil.Defines.h"
#include "CVector2D.h"
struct IDirect3DTexture9;
using UINT = unsigned int;
using WPARAM = std::uintptr_t;
using LPARAM = std::intptr_t;
#include "Client/sdk/core/CWebViewInterface.h"
#include <iostream>
int main() {
    void (CWebViewInterface::*pause)(bool) = &CWebViewInterface::SetRenderingPaused;
    if (!pause) return 1;
    std::cout << "webview-resume-interface\n";
    return 0;
}
