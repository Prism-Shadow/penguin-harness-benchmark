#pragma once
#include <v8.h>
#include "ObjectMapper.h"
namespace puerts {
struct FV8Utils {
    static v8::Local<v8::String> ToV8String(v8::Isolate* i, const char* s) { return v8::String::NewFromUtf8(i, s).ToLocalChecked(); }
    static void* GetPointer(v8::Local<v8::Context>, v8::Local<v8::Value> value) {
        return value.As<v8::Object>()->InternalFieldCount() ? value.As<v8::Object>()->GetAlignedPointerFromInternalField(0) : nullptr;
    }
    template <typename T> static T* GetPointerFast(v8::Local<v8::Object> value) { return static_cast<T*>(value->GetAlignedPointerFromInternalField(0)); }
    static bool IsReleasedPtr(void* ptr) { return ptr == reinterpret_cast<void*>(-1); }
    static void ThrowException(v8::Isolate* i, const char* s) { i->ThrowException(v8::Exception::TypeError(ToV8String(i, s))); }
    template <typename T> static T* IsolateData(v8::Isolate*) { return &mapper; }
};
struct DataTransfer {
    static void SetPointer(v8::Isolate*, v8::Local<v8::Object> o, void* ptr, int index) { o->SetAlignedPointerInInternalField(index, ptr); o->SetAlignedPointerInInternalField(index + 1, nullptr); }
    static void* MakeAddressWithHighPartOfTwo(void* low, void*) { return low; }
};
}
