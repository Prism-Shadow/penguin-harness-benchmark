FROM harbor.tokenwave.us/release/cowork-bench/009-workplace@sha256:34eca521e3fb696e414ad5278e2fdcb487e191bd4f804baf19a9aaf2fb5d9a8f
COPY workplace-service/colleague_availability.py workplace-service/semantic_colleague.py workplace-service/harbor_dynamic_colleague_adapter.py /usr/local/bin/
COPY workplace-service/original/authoring/ /opt/tokenwave-original/authoring/
