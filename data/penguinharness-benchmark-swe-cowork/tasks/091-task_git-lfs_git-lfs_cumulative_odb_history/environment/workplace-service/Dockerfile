FROM harbor.tokenwave.us/release/cowork-bench/091-workplace@sha256:20b3d5f05c330bdff167c32eafca447784b70ef8003014721bd4fc3362d842e8
USER root
COPY original/ /opt/tokenwave-original/
COPY runtime_daemon.py /usr/local/bin/runtime_daemon.py
COPY harbor_dynamic_colleague_adapter.py /usr/local/bin/harbor_dynamic_colleague_adapter.py
RUN chmod -R a+rX /opt/tokenwave-original
