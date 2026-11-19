#include "ObjectRetainer.h"
#if ENGINE_MAJOR_VERSION != 5 || ENGINE_MINOR_VERSION != 7
#error "UE version contract was not imported by the production header"
#endif
int main() {
    puerts::FObjectRetainer retainer;
    retainer.SetName("compatibility-probe");
    return retainer.GetReferencerName() == "compatibility-probe" ? 0 : 1;
}
