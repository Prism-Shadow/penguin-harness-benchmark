#pragma once
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "SharedUtil.Defines.h"
#include "CVector.h"
#include "CMatrix.h"
using uchar = unsigned char;
constexpr int MAX_DOORS = 6, MAX_WHEELS = 4, MAX_PANELS = 7, MAX_LIGHTS = 4;
constexpr int BLOCKING = 1, DT_WHEEL_INTACT_COLLISIONLESS = 3, CCLIENTPLAYER = 1;
enum eClientVehicleType { CLIENTVEHICLE_CAR, CLIENTVEHICLE_BIKE, CLIENTVEHICLE_TRAIN, CLIENTVEHICLE_PLANE };
enum eDoors { DOOR_FIRST };
enum eWheelPosition { WHEEL_FIRST };
enum ePanels { PANEL_FIRST };
enum eLights { LIGHT_FIRST };
enum class VehicleBlowState { INTACT, AWAITING_EXPLOSION_SYNC };
struct VehicleBlowFlags { bool withMovement, withExplosion; };
struct CTickCount
{
    static CTickCount Now() { return {}; }
    CTickCount operator-(const CTickCount&) const { return {}; }
    int ToInt() const { return 0; }
};
struct CControllerState { int ButtonCross = 0, ButtonSquare = 0; };
struct CClientPed
{
    int GetType() const { return CCLIENTPLAYER; }
    void GetControllerState(CControllerState&) {}
};
struct CLuaArguments { void PushBoolean(bool) {} };
struct Entity { void GetPosition(CVector&) {} };
struct World
{
    bool HasCollisionBeenLoaded(CVector*) { return true; }
    void FindWorldPositionForRailTrackPosition(float, uchar, CVector*) {}
};
struct CModelInfo
{
    unsigned short parent = 400;
    unsigned short GetParentID() const { return parent; }
    bool IsLoaded() const { return true; }
    void Request(int, const char*) {}
    void MakeCustomModel() {}
};
struct Handling
{
    void Assign(Handling*) {}
};
struct HandlingManager
{
    Handling value;
    Handling* GetOriginalHandlingData(unsigned) { return &value; }
    Handling* GetOriginalFlyingHandlingData(unsigned) { return &value; }
    Handling* GetOriginalBoatHandlingData(unsigned) { return nullptr; }
    Handling* GetOriginalBikeHandlingData(unsigned) { return nullptr; }
    Handling* CreateBoatHandlingData() { return &value; }
    Handling* CreateBikeHandlingData() { return &value; }
};
struct Game
{
    CModelInfo model;
    HandlingManager handling;
    World world;
    CModelInfo* GetModelInfo(unsigned) { return &model; }
    HandlingManager* GetHandlingManager() { return &handling; }
    World* GetWorld() { return &world; }
};
inline Game game;
inline Game* g_pGame = &game;
struct CClientVehicleManager
{
    static bool HasDoors(unsigned short model) { return model != 461; }
    static bool IsStandardModel(unsigned short model) { return model >= 400 && model <= 611; }
    static eClientVehicleType GetVehicleType(unsigned short model) { return model == 461 ? CLIENTVEHICLE_BIKE : CLIENTVEHICLE_CAR; }
    static bool HasDamageModel(eClientVehicleType type) { return type == CLIENTVEHICLE_CAR; }
    static void GetRandomVariation(unsigned, unsigned char& first, unsigned char& second) { first = 1; second = 2; }
    static bool HasAdjustableProperty(unsigned) { return false; }
    static unsigned char GetMaxPassengerCount(unsigned) { return 3; }
    bool IsSpawnFlyingComponentEnabled() const { return false; }
};
struct CDamageManager
{
    std::array<unsigned char, MAX_DOORS> doors{};
    std::array<unsigned char, MAX_WHEELS> wheels{};
    std::array<unsigned char, MAX_PANELS> panels{};
    std::array<unsigned char, MAX_LIGHTS> lights{};
    unsigned char GetDoorStatus(eDoors index) { return doors.at(index); }
    unsigned char GetWheelStatus(eWheelPosition index) { return wheels.at(index); }
    unsigned char GetPanelStatus(unsigned char index) { return panels.at(index); }
    unsigned char GetLightStatus(unsigned char index) { return lights.at(index); }
    int writes = 0;
    void SetDoorStatus(eDoors index, uchar value, bool) { doors.at(index) = value; ++writes; }
    void SetPanelStatus(ePanels index, uchar value, bool) { panels.at(index) = value; ++writes; }
    void SetLightStatus(eLights index, uchar value) { lights.at(index) = value; ++writes; }
};
struct CDoor { float GetAngleOpenRatio() const { return 0; } };
struct CVehicle
{
    CDamageManager damage;
    CDamageManager* GetDamageManager() { return &damage; }
    unsigned char GetBikeWheelStatus(unsigned char index) { return damage.wheels.at(index); }
    CVector position;
    bool IsVisible() const { return true; }
    void SetUsesCollision(bool) {}
    void SetMatrix(CMatrix*) {}
    void GetMatrix(CMatrix*) {}
    void SetMoveSpeed(const CVector&) {}
    void SetTurnSpeed(CVector*) {}
    void GetMoveSpeed(CVector*) {}
    void GetTurnSpeed(CVector*) {}
    CVector* GetPosition() { return &position; }
    void SetUnderwater(bool) {}
    float GetNitroLevel() const { return 0; }
    CDoor* GetDoor(uchar) { return nullptr; }
    void UpdateLandingGearPosition() {}
};
struct Upgrades { void RemoveAll(bool) {} };
struct ClientModel { unsigned short GetModelID() const { return 400; } };
struct Component { bool m_bVisible = true; };
class CClientVehicle
{
public:
#include "CClientVehicle-members.inc"
    bool local = false, streamed = false;
    unsigned short m_usModel = 400;
    CVehicle* m_pVehicle = nullptr;
    Upgrades* m_pUpgrades = nullptr;
    eClientVehicleType m_eVehicleType = CLIENTVEHICLE_CAR;
    unsigned char m_ucVariation = 0, m_ucVariation2 = 0, m_ucMaxPassengers = 0;
    ClientModel* m_clientModel = nullptr;
    bool m_bHasDamageModel = true, m_bJustStreamedIn = false;
    unsigned char m_ucDoorStates[MAX_DOORS]{};
    unsigned char m_ucWheelStates[MAX_WHEELS]{};
    unsigned char m_ucPanelStates[MAX_PANELS]{};
    unsigned char m_ucLightStates[MAX_LIGHTS]{};
    CClientVehicle* m_pNextLink = nullptr;
    CClientVehicle* m_pPreviousLink = nullptr;
    bool m_bHasLandingGear = false, m_bHasAdjustableProperty = false;
    unsigned short m_usAdjustablePropertyValue = 0;
    CModelInfo* m_pModelInfo = nullptr;
    Handling handling, flying;
    Handling* m_pOriginalHandlingEntry = nullptr;
    Handling* m_pOriginalFlyingHandlingEntry = nullptr;
    Handling* m_pOriginalBoatHandlingEntry = nullptr;
    Handling* m_pOriginalBikeHandlingEntry = nullptr;
    Handling* m_HandlingEntry = &handling;
    Handling* m_FlyingHandlingEntry = &flying;
    Handling* m_BoatHandlingEntry = nullptr;
    Handling* m_BikeHandlingEntry = nullptr;
    std::map<std::string, bool> m_ComponentVisibilityBackup;
    std::map<std::string, Component> m_ComponentData;
    bool m_copyDummyPositions = false;
    std::vector<int> m_dummyPositions;
    CClientVehicleManager manager;
    CClientVehicleManager* m_pVehicleManager = &manager;
    bool m_blowAfterStreamIn = false;
    VehicleBlowState m_blowState = VehicleBlowState::INTACT;
    std::map<eDoors, CTickCount> m_AutoReallowDoorRatioMap;
    bool m_bAllowDoorRatioSetting[MAX_DOORS]{};
    bool m_bIsCollisionEnabled = true, m_bIsFrozen = false, m_bNitroActivated = false;
    CMatrix m_matFrozen, m_Matrix;
    CClientPed* m_pDriver = nullptr;
    CClientVehicle* m_pTowedByVehicle = nullptr;
    Entity* m_pAttachedToEntity = nullptr;
    CVector m_vecAttachedPosition;
    float m_fDoorOpenRatio[MAX_DOORS]{};
    void Blow(VehicleBlowFlags) {}
    void AllowDoorRatioSetting(uchar, bool) {}
    CClientPed* GetOccupant() { return nullptr; }
    bool IsBlown() const { return false; }
    bool IsFrozenWaitingForGroundToLoad() const { return false; }
    void HandleWaitingForGroundToLoad() {}
    eClientVehicleType GetVehicleType() const { return m_eVehicleType; }
    bool IsDerailed() const { return false; }
    void RemoveTargetPosition() {}
    void RemoveTargetRotation() {}
    CClientVehicle* GetNextTrainCarriage() { return m_pNextLink; }
    CClientVehicle* GetPreviousTrainCarriage() { return m_pPreviousLink; }
    CClientPed* GetControllingPlayer() { return nullptr; }
    CClientVehicle* GetChainEngine() { return this; }
    void SetTrainSpeed(float) {}
    float GetTrainSpeed() const { return 0; }
    bool GetTrainDirection() const { return true; }
    float GetTrainPosition() const { return 0; }
    void SetTrainPosition(float) {}
    uchar GetTrainTrack() const { return 0; }
    void UpdatePedPositions(CVector&) {}
    void Interpolate() {}
    void ProcessDoorInterpolation() {}
    unsigned short GetEffectiveModelSpecialAbilityModel() const { return m_usModel; }
    bool IsBelowWater() const { return false; }
    void UpdateStreamPosition(CVector&) {}
    bool IsNitroInstalled() const { return false; }
    void CallEvent(const char*, CLuaArguments&, bool) {}
    unsigned short GetModel() const { return m_usModel; }
    bool HasLandingGear() const { return false; }
    void ResetModelSpecialAbility() {}
    void Destroy() { assert(false && "game allocation is outside this seam"); }
    void Create() { assert(false && "game allocation is outside this seam"); }
    bool IsLocalEntity() const { return local; }
    bool IsStreamedIn() const { return streamed; }
    bool HasDamageModel() const { return m_bHasDamageModel; }
    void GetInitialDoorStates(unsigned char* states) { std::fill(states, states + MAX_DOORS, 0); }
    void SetPreviousTrainCarriage(CClientVehicle*) {}
    void SetNextTrainCarriage(CClientVehicle*) {}
    bool DoCheckHasLandingGear() const { return false; }
    void ApplyHandling() {}
    void SetSirenOrAlarmActive(bool) {}
    void RefreshStreamDistance() {}
    void SetModelBlocking(unsigned short, unsigned char, unsigned char);
    unsigned char GetDoorStatus(unsigned char);
    unsigned char GetWheelStatus(unsigned char);
    unsigned char GetPanelStatus(unsigned char);
    unsigned char GetLightStatus(unsigned char);
    void StreamedInPulse();
};
inline void UpdateCustomPackerRampAngle(CClientVehicle*, CVehicle*, unsigned short) {}
inline void UpdateCustomFireTruckWaterCannon(CVehicle*, unsigned short) {}
inline void UpdateCustomFireTruckLadder(CVehicle*, unsigned short) {}
inline void DrawModelSpecialAbilityDebug(CClientVehicle*, CVehicle*, unsigned short) {}
