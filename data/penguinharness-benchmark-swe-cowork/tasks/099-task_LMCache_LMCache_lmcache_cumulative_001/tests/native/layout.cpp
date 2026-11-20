#include "engine_kv_format.h"
#include <cstdlib>
#include <iostream>

int main(int argc, char **argv) {
  if (argc != 2) return 2;
  const auto layout = static_cast<EngineKVFormat>(std::atoi(argv[1]));
  std::cout << is_cross_layer(layout) << ' ' << is_kv_list(layout) << ' '
            << is_layer_list(layout) << ' ' << is_mla(layout) << ' '
            << is_fused_packed(layout) << '\n';
  return 0;
}
