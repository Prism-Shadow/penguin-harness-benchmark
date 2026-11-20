FROM harbor.tokenwave.us/release/cowork-bench/040-workplace@sha256:182bf13a14f227777327fb774cef7e2893cf1374e8a11025dbbcd735ce2ecdcc
COPY original/ /opt/tokenwave-original/
COPY runtime_daemon.py agent_defaults.py semantic_colleague.py colleague_availability.py harbor_dynamic_colleague_adapter.py /usr/local/bin/
COPY workplace-sidecar /usr/local/bin/workplace-sidecar
RUN chmod 0555 /usr/local/bin/workplace-sidecar && chmod 0444 /usr/local/bin/*colleague*.py /usr/local/bin/runtime_daemon.py /usr/local/bin/agent_defaults.py
