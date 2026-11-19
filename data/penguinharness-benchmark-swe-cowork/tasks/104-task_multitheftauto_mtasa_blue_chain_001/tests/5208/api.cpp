#include "Client/sdk/core/CRenderItemManagerInterface.h"
#include <iostream>
#include <type_traits>
template<class T, class=void> struct Raw : std::false_type {};
template<class T> struct Raw<T,std::void_t<decltype(std::declval<T&>().ReplaceFileTextureFromMemory(
    static_cast<CTextureItem*>(nullptr),static_cast<const void*>(nullptr),0u,false,RFORMAT_UNKNOWN,false))>> : std::true_type {};
template<class T, class=void> struct Pixels : std::false_type {};
template<class T> struct Pixels<T,std::void_t<decltype(std::declval<T&>().ReplaceFileTextureFromMemory(
    static_cast<CTextureItem*>(nullptr),std::declval<const CPixels&>()))>> : std::true_type {};
int main() { static_assert(Raw<CRenderItemManagerInterface>::value || Pixels<CRenderItemManagerInterface>::value); }
