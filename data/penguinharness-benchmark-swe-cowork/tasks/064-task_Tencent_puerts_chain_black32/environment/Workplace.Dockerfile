FROM harbor.tokenwave.us/release/cowork-bench/064-workplace@sha256:d34707636d9a3a0d8488a79b191942744ee233341a7a4f14f87c5f62a5973958
USER root
COPY workplace-service/original /opt/tokenwave-original
COPY workplace-service/runtime/runtime_daemon.py /usr/local/bin/runtime_daemon.py
