#include <string>
#include "reflect/android_app_ContextImpl.h"

static std::string observed_name;
static std::string observed_signature;

namespace dpt::jni {
void SetObjectField(JNIEnv *, jobject, const JNINativeField *field, jobject) {
    observed_name = field == nullptr ? "" : field->name;
    observed_signature = field == nullptr ? "" : field->signature;
}
}

int main() {
    dpt::reflect::android_app_ContextImpl wrapper(nullptr, nullptr);
    wrapper.setOuterContext(nullptr);
    return observed_name == "mOuterContext" && observed_signature == "Landroid/content/Context;" ? 0 : 15;
}
