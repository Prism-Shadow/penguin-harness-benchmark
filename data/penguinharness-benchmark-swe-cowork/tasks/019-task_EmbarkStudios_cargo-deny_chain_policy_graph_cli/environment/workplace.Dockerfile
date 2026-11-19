FROM harbor.tokenwave.us/release/cowork-bench/019-workplace@sha256:34bd5dcc58f12e295856465336b4f5afb5a3924ccbd5e046dce626a006a81b66
COPY workplace-service/original/harness/config/ /opt/tokenwave-original/harness/config/
COPY workplace-service/original/authoring/ /opt/tokenwave-original/authoring/
COPY workplace-service/runtime_daemon.py workplace-service/semantic_colleague.py workplace-service/harbor_dynamic_colleague_adapter.py workplace-service/colleague_availability.py /usr/local/bin/
