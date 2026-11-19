#!/usr/bin/env bash
set -euo pipefail
family=${1:?backend family required}
repo=${2:?repository required}
build=$(mktemp -d "${TMPDIR:-/tmp}/rmlui-backend.XXXXXX")
trap 'rm -rf -- "$build"' EXIT
case "$family" in
  SDL) backends=(SDL_GL2 SDL_GL3 SDL_SDLrenderer SDL_VK) ;;
  SFML) backends=(SFML_GL2) ;;
  *) exit 2 ;;
esac
for major in 2 3; do
  for backend in "${backends[@]}"; do
    directory="$build/$major-$backend"
    launcher=()
    if command -v ccache >/dev/null; then launcher=(-DCMAKE_CXX_COMPILER_LAUNCHER=ccache); fi
    cmake -S "$repo" -B "$directory" -G Ninja \
      -DRMLUI_SHELL=ON -DRMLUI_SAMPLES=OFF -DBUILD_TESTING=OFF \
      -DRMLUI_FONT_ENGINE=none -DRMLUI_PRECOMPILED_HEADERS=OFF \
      -DRMLUI_BACKEND="$backend" -DRMLUI_${family}_VERSION_MAJOR="$major" \
      -DCMAKE_PREFIX_PATH="${SDL3_PREFIX:-/opt/sdl3};/opt/sdl3-image;${SFML3_PREFIX:-/opt/sfml3}" \
      "${launcher[@]}" || { echo 'PROBE_FAILURE_KIND configuration_error'; exit 1; }
    cmake --build "$directory" --target rmlui_shell -j2 \
      || { echo 'PROBE_FAILURE_KIND solver_compile_error'; exit 1; }
  done
done
