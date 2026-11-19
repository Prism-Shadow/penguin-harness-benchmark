#include <node.h>
#include "WeakObjectPtrWrapper.h"
#include "V8Utils.h"
#include <vector>
namespace {
std::vector<std::unique_ptr<UObject>> objects;
void NewObject(const v8::FunctionCallbackInfo<v8::Value>& info) {
    auto isolate = info.GetIsolate(); auto context = isolate->GetCurrentContext();
    objects.emplace_back(new UObject()); auto ptr = objects.back().get();
    auto t = v8::ObjectTemplate::New(isolate); t->SetInternalFieldCount(2);
    auto object = t->NewInstance(context).ToLocalChecked();
    object->SetAlignedPointerInInternalField(0, ptr);
    puerts::mapper.objects.emplace(ptr, v8::Global<v8::Object>(isolate, object));
    info.GetReturnValue().Set(object);
}
void State(const v8::FunctionCallbackInfo<v8::Value>& info) {
    auto ptr = static_cast<UObject*>(puerts::FV8Utils::GetPointer(info.GetIsolate()->GetCurrentContext(), info[0]));
    int state = info[1].As<v8::Int32>()->Value();
    if (state == 1) ptr->pending = true;
    if (state == 2) ptr->valid = false;
    if (state == 3) ptr->life.reset();
}
void Count(const v8::FunctionCallbackInfo<v8::Value>& info) { info.GetReturnValue().Set(weak_live_count); }
void Init(v8::Local<v8::Object> exports) {
    auto isolate = exports->GetIsolate();
    puerts::FWeakObjectPtrWrapper::Register(isolate, isolate->GetCurrentContext(), isolate->GetCurrentContext()->Global());
    node::AddEnvironmentCleanupHook(isolate, [](void*) { puerts::mapper.objects.clear(); objects.clear(); }, nullptr);
    NODE_SET_METHOD(exports, "newObject", NewObject); NODE_SET_METHOD(exports, "state", State); NODE_SET_METHOD(exports, "count", Count);
}
NODE_MODULE(weak_contract, Init)
}
