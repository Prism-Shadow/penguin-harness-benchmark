#pragma once
#include <memory>
#define PRAGMA_DISABLE_UNDEFINED_IDENTIFIER_WARNINGS
#define PRAGMA_ENABLE_UNDEFINED_IDENTIFIER_WARNINGS
struct UObject {
    bool valid = true, pending = false;
    std::shared_ptr<int> life = std::make_shared<int>(1);
    bool IsValidLowLevelFast() const { return valid; }
    UObject* GetClass() { return this; }
};
inline bool UEObjectIsPendingKill(UObject* obj) { return obj->pending; }
inline int weak_live_count = 0;
template <typename T> struct TWeakObjectPtr {
    T* ptr;
    std::weak_ptr<int> life;
    explicit TWeakObjectPtr(T* p) : ptr(p), life(p ? p->life : std::weak_ptr<int>()) { ++weak_live_count; }
    ~TWeakObjectPtr() { --weak_live_count; }
    T* Get() const { return life.expired() ? nullptr : ptr; }
};
