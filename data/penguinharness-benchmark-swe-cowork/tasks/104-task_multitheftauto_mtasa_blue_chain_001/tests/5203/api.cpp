#include "Client/sdk/gui/CGUI.h"
struct GuiContract : CGUI {
    SString BidifyText(const char*) override;
};
int main() {
    SString (CGUI::*bidi)(const char*) = &CGUI::BidifyText;
    auto toggle = &CGUI::SetBidiEnabled;
    return bidi && toggle ? 0 : 1;
}
