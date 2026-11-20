#!/bin/bash
set -euo pipefail
mkdir -p /opt/task-legacy-libs
while IFS= read -r binary; do
    dependencies=$(ldd "$binary")
    if grep -q 'not found' <<< "$dependencies"; then
        printf '%s\n%s\n' "$binary" "$dependencies" >&2
        exit 1
    fi
    while IFS= read -r library; do
        case "$(basename "$library")" in
            libc.so.*|libm.so.*|libdl.so.*|libpthread.so.*|librt.so.*|libutil.so.*|libresolv.so.*|libgcc_s.so.*|libstdc++.so.*|libcurl.so.*|libruby.so.*) continue ;;
        esac
        cp -L "$library" /opt/task-legacy-libs/
    done < <(awk '$2 == "=>" && $3 ~ /^\// { print $3 }' <<< "$dependencies")
done < <(printf '%s\n' /usr/local/bin/ruby /opt/task-mongodb/bin/mongod; find /usr/local/lib /opt/task-bundle/gems -type f -name '*.so*')
