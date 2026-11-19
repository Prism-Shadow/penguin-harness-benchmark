#include <string>

int parse_dex_number(std::string *location);

int main() {
    std::string value("base.apk!classes2.dex");
    return parse_dex_number(&value) == 1 ? 0 : 31;
}
