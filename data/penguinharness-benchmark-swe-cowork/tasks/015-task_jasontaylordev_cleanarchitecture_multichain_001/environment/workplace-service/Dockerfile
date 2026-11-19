FROM harbor.tokenwave.us/release/cowork-bench/015-workplace@sha256:8b8eeaa957205fa7686f32b861871695348a8e921c9b81b298c8df87f9694165
USER root
COPY original/authoring/ /opt/tokenwave-original/authoring/
COPY original/harness/ /opt/tokenwave-original/harness/
COPY assignment_scope.py colleague_availability.py harbor_dynamic_colleague_adapter.py runtime_daemon.py semantic_colleague.py /usr/local/bin/
COPY workplace_sidecar.py /usr/local/bin/workplace-sidecar
RUN chmod 755 /usr/local/bin/workplace-sidecar
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original
