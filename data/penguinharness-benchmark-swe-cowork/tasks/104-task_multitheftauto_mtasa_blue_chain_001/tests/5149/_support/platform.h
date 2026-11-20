#pragma once
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <list>
#include <optional>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include "SharedUtil.Defines.h"
#include "CVector.h"
#include "CVector2D.h"
using uint=unsigned;
using std::list;
class CCoreInterface; class CGame; class CMultiplayer; class CNet;
constexpr float WORLD_SIZE=3000;
#define private public
#include "Client/mods/deathmatch/logic/CClientStreamer.h"
#undef private
class CClientManager;
struct StreamElementBoundary {
    virtual ~StreamElementBoundary() = default;
    CClientManager* m_pManager=nullptr;
    CClientStreamer* streamer=nullptr;
    bool streamed=false;
    float distance=0;
    float measuredDistance=0;
    int ins=0, outs=0;
    unsigned refs=0;
    virtual bool vehicle() const { return false; }
    virtual bool player() const { return false; }
    bool IsStreamedIn() const { return streamed; }
    float GetExpDistance() const { return distance; }
    float GetDistanceToBoundingBoxSquared(const CVector&) const { return measuredDistance; }
    void SetExpDistance(float value) { distance=value; }
    unsigned GetTotalStreamReferences() const { return refs; }
    void InternalStreamIn(bool) { ++ins; streamed=true; }
    void InternalStreamOut() { ++outs; streamed=false; }
    unsigned GetDimension() const { return 0; }
    bool IsVisibleInAllDimensions() const { return false; }
    StreamElementBoundary* GetAttachedTo() const { return nullptr; }
    unsigned GetLastStreamOutTime() const { return 0; }
};
class CClientManager { public: float ResolveStreamDistance(class CClientStreamElement*); };
#include "element.inc"
#ifdef STREAM_HAS_CUSTOM_RANGE
inline float CClientManager::ResolveStreamDistance(CClientStreamElement* p) { return p->GetCustomStreamDistance(); }
#endif
struct CClientPlayer : CClientStreamElement { int GetLastPuresyncType() { return 0; } };
struct CClientVehicle : CClientStreamElement {
    bool vehicle() const override { return true; }
    CClientPlayer* GetOccupant() const { return nullptr; }
    CClientVehicle* GetTowedByVehicle() const { return nullptr; }
};
struct CClientObject : CClientStreamElement { bool IsLowLod() { return false; } };
template<class T, class U> T* DynamicCast(U* p) { return dynamic_cast<T*>(p); }
#define IS_VEHICLE(p) ((p)->vehicle())
#define IS_PLAYER(p) ((p)->player())
constexpr int PURESYNC_TYPE_LIGHTSYNC=9;
struct CClientTime { static unsigned GetTime() { return 1000; } };
struct CClientStreamSector { bool DoesContain(const CVector&) const { return true; } };
struct CClientStreamSectorRow {
    bool DoesContain(const CVector&) const { return true; }
    CClientStreamSector* FindOrCreateSector(CVector&,CClientStreamSector* = nullptr) { static CClientStreamSector s; return &s; }
};
inline void CClientStreamer::CreateSectors(std::list<CClientStreamSectorRow*>*, CVector2D&, CVector2D&, CVector2D&) {}
inline CClientStreamSectorRow* CClientStreamer::FindOrCreateRow(CVector&,CClientStreamSectorRow*) { static CClientStreamSectorRow r; return &r; }
inline void CClientStreamer::OnEnterSector(CClientStreamSector* p) { m_pSector=p; }
#ifdef STREAM_HAS_CUSTOM_RANGE
inline void CClientStreamer::OnElementStreamDistanceChanged(CClientStreamElement*) {}
#endif
#include "element-impl.inc"
