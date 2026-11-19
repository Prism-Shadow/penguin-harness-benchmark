FROM harbor.tokenwave.us/release/cowork-bench/013-workplace@sha256:fd9726e934e9fba998f3926d216f28b45072c9a3034fa6b4a8c3d8393c6f8a31
COPY workplace-service/original/ /opt/tokenwave-original/
COPY workplace-service/runtime/runtime_daemon.py /usr/local/bin/runtime_daemon.py
RUN chmod -R a=rX /opt/tokenwave-original && chmod 0444 /usr/local/bin/runtime_daemon.py
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original
CMD ["python3", "/usr/local/bin/workplace-sidecar", "--original-root", "/opt/tokenwave-original", "--quiet"]
