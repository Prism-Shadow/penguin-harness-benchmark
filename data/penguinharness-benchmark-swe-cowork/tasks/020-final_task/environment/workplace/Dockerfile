FROM harbor.tokenwave.us/release/cowork-bench/020-workplace@sha256:7e0ab00f89f483649f19d0ef6518d1b13335c747af9d200e4137ad3dab83b0f6
USER root
COPY runtime_daemon.py /usr/local/bin/runtime_daemon.py
RUN python3 -m py_compile /usr/local/bin/runtime_daemon.py
