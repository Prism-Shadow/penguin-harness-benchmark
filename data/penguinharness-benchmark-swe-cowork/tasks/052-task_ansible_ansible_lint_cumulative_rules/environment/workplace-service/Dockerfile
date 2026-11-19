FROM harbor.tokenwave.us/release/cowork-bench/052-workplace@sha256:906be1c9af8bc4018735cdfba5436be728eb5cd5ccc31d2fddaf907328a451e8
COPY original/ /opt/tokenwave-original/
COPY semantic_colleague.py runtime_daemon.py harbor_dynamic_colleague_adapter.py colleague_availability.py agent_defaults.py /usr/local/bin/
COPY workplace_sidecar.py /usr/local/bin/workplace-sidecar
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original
RUN chmod 755 /usr/local/bin/workplace-sidecar && python3 -m py_compile /usr/local/bin/semantic_colleague.py /usr/local/bin/workplace-sidecar
