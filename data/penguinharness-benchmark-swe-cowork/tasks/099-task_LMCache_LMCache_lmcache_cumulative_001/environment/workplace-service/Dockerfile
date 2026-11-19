# Private sidecar corpus and topic-scoped legacy disclosure runtime.
# This material must never be copied into the solver's environment image.
FROM harbor.tokenwave.us/release/cowork-bench/099-workplace@sha256:2d46088d8f08ef52b1d5698c9589b61867c1c176e6489d4627c8a441cf1fcbf7
LABEL org.cowork.task.repair_version="quality-repair-099-20260926-v4"
COPY original/authoring/ /opt/tokenwave-original/authoring/
COPY original/bin/runtime_daemon.py /usr/local/bin/runtime_daemon.py
