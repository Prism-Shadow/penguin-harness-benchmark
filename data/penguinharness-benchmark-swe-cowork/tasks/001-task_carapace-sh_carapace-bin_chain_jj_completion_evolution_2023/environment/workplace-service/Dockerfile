FROM harbor.tokenwave.us/release/cowork-bench/001-workplace@sha256:2c5aa2852af2e10d3a020c37975d1415a649885f660a14b50bb2bfe77414c7b8
COPY harbor_dynamic_colleague_adapter.py semantic_colleague.py colleague_availability.py /usr/local/bin/
COPY workplace_sidecar.py /usr/local/bin/workplace-sidecar
RUN chmod 0555 /usr/local/bin/workplace-sidecar
