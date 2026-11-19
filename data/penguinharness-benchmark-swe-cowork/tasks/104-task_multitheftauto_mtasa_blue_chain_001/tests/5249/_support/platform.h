#pragma once
#include "Client/core/CSteamClient.h"
#include <cassert>
#include <cstdint>
#include <cwchar>
#include <memory>
#include <optional>
#include <string>
#include <type_traits>
#include <vector>

using DWORD = unsigned long;
using LONG = long;
struct FakeHandle {};
using HANDLE = FakeHandle*;
inline HANDLE INVALID_HANDLE_VALUE = reinterpret_cast<HANDLE>(-1);
constexpr int GENERIC_READ = 1, FILE_SHARE_READ = 1, OPEN_EXISTING = 1, FILE_ATTRIBUTE_NORMAL = 1;
constexpr DWORD WTD_UI_NONE = 2, WTD_REVOKE_NONE = 0, WTD_CHOICE_FILE = 1;
constexpr DWORD WTD_STATEACTION_VERIFY = 1, WTD_STATEACTION_CLOSE = 2;
constexpr DWORD WTD_SAFER_FLAG = 0x100, WTD_REVOCATION_CHECK_NONE = 0x10, WTD_CACHE_ONLY_URL_RETRIEVAL = 0x1000;
constexpr LONG ERROR_SUCCESS = 0, CERT_E_UNTRUSTEDROOT = 0x800B0109, CERT_E_CHAINING = 0x800B010A;
constexpr LONG TRUST_E_TIME_STAMP = 0x80096005, CERT_E_EXPIRED = 0x800B0101, TRUST_E_BAD_DIGEST = 0x80096010;
struct GUID { int value; };
inline GUID WINTRUST_ACTION_GENERIC_VERIFY_V2{1};
struct WINTRUST_FILE_INFO { DWORD cbStruct{}; const wchar_t* pcwszFilePath{}; };
struct WINTRUST_DATA
{
    DWORD cbStruct{}, dwUIChoice{}, fdwRevocationChecks{}, dwUnionChoice{};
    WINTRUST_FILE_INFO* pFile{};
    DWORD dwStateAction{}, dwProvFlags{};
};
struct SString : std::string
{
    SString() = default;
    SString(const char* text) : std::string(text) {}
    template<class... Args> SString(const char* format, const Args&...) : std::string(format) {}
    const char* operator*() const { return c_str(); }
};
inline SString ToUTF8(const std::wstring&) { return "steamclient.dll"; }
inline SString GetSystemErrorMessage(DWORD) { return "load failure"; }
inline void WriteErrorEvent(const SString&) {}
inline void WriteDebugEvent(const SString&) {}
inline DWORD GetLastError() { return 126; }

struct Platform
{
    bool installed = true, running = true, verifiedProcess = true, lock = true;
    bool library = true, interfaceExport = true, createInterface = true, addDirectory = true;
    std::optional<std::wstring> path = L"C:\\Steam\\steamclient.dll";
    std::optional<std::wstring> signer = L"Valve Corp.";
    LONG trust = ERROR_SUCCESS;
    int loads = 0, frees = 0, locks = 0, closes = 0, factories = 0, pipes = 0, users = 0;
    std::vector<DWORD> trustActions;
};
inline Platform platform;
inline bool IsGameInstalledOnSteam() { return platform.installed; }
inline std::optional<DWORD> GetSteamProcessFromRegistry() { return platform.running ? std::optional<DWORD>(1234) : std::nullopt; }
inline bool IsSteamProcess(DWORD) { return platform.verifiedProcess; }
inline std::optional<std::wstring> GetSteamClientPathFromRegistry() { return platform.path; }
inline std::optional<std::wstring> GetCertificateDisplayName(const wchar_t*) { return platform.signer; }
inline LONG WinVerifyTrust(void*, GUID*, WINTRUST_DATA* data)
{
    assert(data->pFile && data->pFile->pcwszFilePath);
    assert(data->dwUIChoice == WTD_UI_NONE);
    assert(data->dwProvFlags & WTD_CACHE_ONLY_URL_RETRIEVAL);
    platform.trustActions.push_back(data->dwStateAction);
    return platform.trust;
}
inline void* AddDllDirectory(const wchar_t*) { return reinterpret_cast<void*>(1); }
inline HMODULE GetModuleHandleW(const wchar_t*) { return reinterpret_cast<HMODULE>(1); }
inline bool SetEnvironmentVariableW(const wchar_t*, const wchar_t*) { return true; }
inline DWORD GetEnvironmentVariableW(const wchar_t*, wchar_t* buffer, DWORD) { buffer[0] = 0; return 0; }
inline HANDLE CreateFileW(const wchar_t*, int, int, void*, int, int, void*)
{
    ++platform.locks;
    return platform.lock ? reinterpret_cast<HANDLE>(1) : INVALID_HANDLE_VALUE;
}
inline void CloseHandle(HANDLE) { ++platform.closes; }
struct HandleDeleter { void operator()(HANDLE handle) const { CloseHandle(handle); } };
using HandleScope = std::unique_ptr<std::remove_pointer_t<HANDLE>, HandleDeleter>;
inline HMODULE LoadLibraryW(const wchar_t*)
{
    ++platform.loads;
    return platform.library ? reinterpret_cast<HMODULE>(2) : nullptr;
}
constexpr DWORD LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR = 0x100;
constexpr DWORD LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x1000;
inline HMODULE LoadLibraryExW(const wchar_t* path, HANDLE, DWORD flags)
{
    // Windows rejects a relative lpFileName with LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR.
    // A caller may legitimately delegate this validation to the platform API.
    const std::wstring filename = path ? path : L"";
    const bool absolute = (filename.size() > 2 && filename[1] == L':' &&
                           (filename[2] == L'\\' || filename[2] == L'/')) ||
                          filename.rfind(L"\\\\", 0) == 0;
    if ((flags & LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR) && !absolute)
        return nullptr;
    return LoadLibraryW(path);
}
inline bool FreeLibrary(HMODULE) { ++platform.frees; return true; }
class ISteamClient
{
public:
    bool BReleaseSteamPipe(HSteamPipe pipe) { assert(pipe == 7); return true; }
    HSteamPipe CreateSteamPipe() { ++platform.pipes; return 7; }
    HSteamUser ConnectToGlobalUser(HSteamPipe pipe) { assert(pipe == 7); ++platform.users; return 9; }
};
inline ISteamClient steam;
inline ISteamClient* CreateInterface(const char* version, int*)
{
    assert(std::string(version) == "SteamClient017");
    ++platform.factories;
    return platform.createInterface ? &steam : nullptr;
}
namespace SharedUtil
{
inline bool TryGetProcAddress(HMODULE, const char*, decltype(&AddDllDirectory)& result)
{
    result = platform.addDirectory ? AddDllDirectory : nullptr;
    return result != nullptr;
}
inline bool TryGetProcAddress(HMODULE, const char*, decltype(&CreateInterface)& result)
{
    result = platform.interfaceExport ? CreateInterface : nullptr;
    return result != nullptr;
}
}
#define STEAM_GTASA_APP_ID "12120"
