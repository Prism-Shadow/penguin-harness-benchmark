FROM harbor.tokenwave.us/release/cowork-bench/044-workplace@sha256:3dbf8f69b90fe8533eae6312d0e357ceb17665877d4c3bf4d6dbe996527e3a40
USER root
COPY runtime_daemon.py /usr/local/bin/runtime_daemon.py
RUN python3 -m py_compile /usr/local/bin/runtime_daemon.py
