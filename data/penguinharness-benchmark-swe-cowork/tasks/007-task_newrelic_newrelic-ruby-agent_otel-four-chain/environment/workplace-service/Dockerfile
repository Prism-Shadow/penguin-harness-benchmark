FROM harbor.tokenwave.us/release/cowork-bench/007-workplace@sha256:6248e9b29797341b5eebfc5f1c5267fc34b96394044566c20e8771727f1abe11
USER root
COPY original /opt/tokenwave-original
COPY workplace-sidecar /usr/local/bin/workplace-sidecar
COPY harbor_dynamic_colleague_adapter.py runtime_daemon.py semantic_colleague.py colleague_availability.py /usr/local/bin/
RUN chmod -R a+rX /opt/tokenwave-original && chmod a+rx /usr/local/bin/workplace-sidecar && python3 -m py_compile /usr/local/bin/harbor_dynamic_colleague_adapter.py /usr/local/bin/runtime_daemon.py /usr/local/bin/semantic_colleague.py /usr/local/bin/colleague_availability.py
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original
CMD ["/usr/local/bin/workplace-sidecar", "--quiet"]
