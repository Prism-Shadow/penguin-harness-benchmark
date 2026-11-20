#pragma once
#include <set>
#include <string>
#include <vector>
#include <type_traits>
#define FORCEINLINE inline
#define JSENV_API
#define TEXT(x) x
using FString = std::string;
class UObject {};
class FReferenceCollector {
public:
    std::set<UObject*> seen;
    template <typename T>
    void AddReferencedObjects(const T& objects) { for (auto item : objects) seen.insert(static_cast<UObject*>(item)); }
};
class FGCObject {
public:
    virtual ~FGCObject() = default;
    virtual void AddReferencedObjects(FReferenceCollector&) {}
    virtual FString GetReferencerName() const { return {}; }
};
template <typename T> class TSet : public std::set<T> {
public:
    using std::set<T>::set;

    bool Contains(const T& value) const { return this->find(value) != this->end(); }

    template <typename U>
    bool Contains(U* value) const { return this->find(T(value)) != this->end(); }

    void Add(const T& value) { this->insert(value); }

    template <typename U>
    void Add(U* value) { this->insert(T(value)); }

    void Remove(const T& value) { this->erase(value); }

    template <typename U>
    void Remove(U* value) { this->erase(T(value)); }

    void Empty() { this->clear(); }
};
template <typename T> class TObjectPtr {
    T* value = nullptr;
public:
    TObjectPtr() = default;
    explicit TObjectPtr(T* ptr) : value(ptr) {}
    operator T*() const { return value; }
    bool operator<(const TObjectPtr& other) const { return value < other.value; }
    bool operator==(const TObjectPtr& other) const { return value == other.value; }
};
