#pragma once
#include <v8.h>
#include <map>
#include "CoreMinimal.h"
namespace puerts {
struct IObjectMapper {
    std::map<UObject*, v8::Global<v8::Object>> objects;
    v8::Local<v8::Value> FindOrAdd(v8::Isolate* isolate, v8::Local<v8::Context>, UObject*, UObject* object) {
        return objects.at(object).Get(isolate);
    }
};
inline IObjectMapper mapper;
}
