# Private owner data remains in the service image. Solver sees only its socket.
FROM harbor.tokenwave.us/release/cowork-bench/056-workplace@sha256:e842bddcb8f82cf1e3c22a5eb4ab8b49c43c3a16848d3011b3203265b766832a AS frozen
USER root
COPY runtime_daemon.py /usr/local/bin/runtime_daemon.py
COPY workplace_sidecar.py /usr/local/bin/workplace-sidecar
COPY original/ /opt/tokenwave-original/

FROM scratch
COPY --from=frozen / /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1 \
    TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original \
    WORKPLACE_SERVICE_SOCKET=/run/workplace/service.sock
CMD ["python3", "/usr/local/bin/workplace-sidecar", "--quiet"]
