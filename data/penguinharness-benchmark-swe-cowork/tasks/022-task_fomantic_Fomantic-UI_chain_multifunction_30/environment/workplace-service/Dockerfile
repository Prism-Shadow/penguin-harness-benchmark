FROM harbor.tokenwave.us/release/cowork-bench/022-workplace@sha256:3ebbaf9c238855d9a8fd50e9cc318cea71811a17081501c33364adcde492d34b
USER root
COPY original/ /opt/tokenwave-original/
COPY semantic_colleague.py colleague_availability.py harbor_dynamic_colleague_adapter.py runtime_daemon.py agent_defaults.py /usr/local/bin/
COPY workplace-sidecar /usr/local/bin/workplace-sidecar
RUN chmod -R a+rX /opt/tokenwave-original && chmod 755 /usr/local/bin/workplace-sidecar
