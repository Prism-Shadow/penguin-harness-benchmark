FROM harbor.tokenwave.us/release/cowork-bench/082-workplace@sha256:619f15ab1c929cb0a8ac11330e6e9bb14609287fb3befd31376c9dc6eaae5e63
USER root
COPY original/authoring/ /opt/tokenwave-original/authoring/
COPY original/harness/config/workplace.json /opt/tokenwave-original/harness/config/workplace.json
COPY semantic_colleague.py harbor_dynamic_colleague_adapter.py colleague_availability.py runtime_daemon.py agent_defaults.py workplace_sidecar.py /usr/local/bin/
COPY workplace_sidecar.py /usr/local/bin/workplace-sidecar
RUN chmod 755 /usr/local/bin/workplace-sidecar
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original
