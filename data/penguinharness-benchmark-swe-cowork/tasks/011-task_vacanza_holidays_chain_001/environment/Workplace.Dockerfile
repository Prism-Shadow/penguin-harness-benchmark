FROM harbor.tokenwave.us/release/cowork-bench/011-workplace@sha256:91c1f123dd49eb6ccbb0b2041d24269c421ef1e5164aa48e5d92137fc9beeead
USER root
COPY runtime_daemon.py /usr/local/bin/runtime_daemon.py
COPY resolve_workplace_scope.py /tmp/resolve_workplace_scope.py
RUN python3 /tmp/resolve_workplace_scope.py && rm /tmp/resolve_workplace_scope.py
