#pragma once
#include <jni.h>
typedef struct AAssetManager AAssetManager;
typedef struct AAsset AAsset;
#define AASSET_MODE_BUFFER 2
static inline AAsset *AAssetManager_open(AAssetManager *, const char *, int) { return nullptr; }
