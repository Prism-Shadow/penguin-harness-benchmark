#include "Client/sdk/game/CVehicle.h"
struct VehicleContract : CVehicle {
    void SetModelSpecialAbilityModel(unsigned short, bool) override;
    unsigned short GetModelSpecialAbilityModel(unsigned short) const override;
};
int main() {
    void (CVehicle::*setter)(unsigned short, bool) = &CVehicle::SetModelSpecialAbilityModel;
    unsigned short (CVehicle::*resolver)(unsigned short) const = &CVehicle::GetModelSpecialAbilityModel;
    auto accessor = &CVehicle::GetModelIndex;
    return setter && resolver && accessor ? 0 : 1;
}
