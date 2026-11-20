FROM harbor.tokenwave.us/release/cowork-bench/039-workplace@sha256:0a7d0e7b6e143d1c76a49f61adf38f6a2682b111b2c0e2fa2f4774f213fbaa09
USER root
COPY runtime_daemon.py semantic_colleague.py colleague_availability.py harbor_dynamic_colleague_adapter.py agent_defaults.py workplace-sidecar /usr/local/bin/
COPY original/ /opt/tokenwave-original/
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python3", "/usr/local/bin/workplace-sidecar", "--original-root", "/opt/tokenwave-original"]
