#!/usr/bin/env bash
set -euo pipefail
repo=${1:-/app/code}
cd "$repo"
export GOTOOLCHAIN=local GOMAXPROCS=2 GOMEMLIMIT=3GiB
export GOMODCACHE=/opt/ragflow-go-modules GOCACHE=/tmp/ragflow-go-preflight
export GOENV=off GOAUTH=off GO111MODULE=on GOWORK=off GOFLAGS= GOINSECURE= GOPRIVATE= GONOSUMDB= GONOPROXY=
test "$(go env GOVERSION)" = go1.27.0
sha256sum go.mod go.sum > /tmp/ragflow-go-inputs.sha256
GOPROXY=$(python3 /opt/ragflow-development-inputs/select-go-proxy.py --repo "$repo" \
    --receipt /opt/ragflow-native-libs/go-proxy-receipt.json)
export GOPROXY GOSUMDB="sum.golang.org ${GOPROXY}/sumdb/sum.golang.org"
native_options=()
case "${RAGFLOW_NATIVE_OFFLINE:-0}" in
    0) ;;
    1) native_options+=(--offline) ;;
    *) echo 'RAGFLOW_NATIVE_OFFLINE must be 0 or 1' >&2; exit 1 ;;
esac
native_cache_directory=${RAGFLOW_NATIVE_CACHE_DIRECTORY:-/opt/ragflow-native-cache}
native_archive_directory=${RAGFLOW_NATIVE_ARCHIVE_DIRECTORY:-/opt/ragflow-development-inputs/native-archives}
python3 /opt/ragflow-development-inputs/prepare-native.py "${native_options[@]}" \
    --archive-directory "$native_archive_directory" \
    --cache-directory "$native_cache_directory"
cmake -S internal/binding/cpp -B internal/binding/cpp/cmake-build-release -DCMAKE_BUILD_TYPE=Release
cmake --build internal/binding/cpp/cmake-build-release --target rag_tokenizer_c_api --parallel 2
go list -mod=readonly -m all > /opt/ragflow-native-libs/go-module-graph.txt
go list -mod=readonly -deps -test ./internal/agent/harness ./internal/service > /opt/ragflow-native-libs/go-packages.txt
module_downloads=$(mktemp -d /tmp/ragflow-go-downloads.XXXXXX)
while IFS= read -r module; do
    (cd "$module_downloads" && go mod download -json "$module")
done < /opt/ragflow-development-inputs/offline-go-modules.txt > /opt/ragflow-native-libs/optional-modules.jsonl
(
    cd "$module_downloads"
    printf 'module ragflow-offline-options\n\ngo 1.27\n' > go.mod
    while IFS= read -r module; do
        go mod edit "-require=$module"
    done < /opt/ragflow-development-inputs/offline-go-modules.txt
    go list -mod=mod -m all
) > /opt/ragflow-native-libs/optional-module-graph.txt
rm -rf "$module_downloads"
sha256sum --check /tmp/ragflow-go-inputs.sha256
export GOPROXY=off
HOME=/tmp/ragflow-go-home bash build.sh --test -p=2 -vet=off -run '^$' ./internal/agent/harness
go mod verify
sha256sum --check /tmp/ragflow-go-inputs.sha256
python3 /task/audit_runtime.py --go-repo "$repo" --go-module-cache "$GOMODCACHE" "$GOMODCACHE"
rm -rf "$GOCACHE" /tmp/ragflow-go-home /tmp/ragflow-go-inputs.sha256
