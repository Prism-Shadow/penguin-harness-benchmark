#pragma once
#define ANDROID_LOG_INFO 4
#define ANDROID_LOG_DEBUG 3
#define ANDROID_LOG_ERROR 6
#define ANDROID_LOG_WARN 5
extern "C" int probe_android_log(int, const char *, const char *, ...);
#define __android_log_print probe_android_log
