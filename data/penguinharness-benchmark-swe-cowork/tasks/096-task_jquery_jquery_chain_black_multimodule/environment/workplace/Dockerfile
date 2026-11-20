FROM harbor.tokenwave.us/release/cowork-bench/096-workplace@sha256:ffb8fa0741ced5a84d88da47486ebcd5b3318c307c63f46e0d2af0c25ab031a7
USER root
COPY harbor_dynamic_colleague_adapter.py semantic_colleague.py /usr/local/bin/
COPY authoring/ /opt/tokenwave-original/authoring/
RUN python3 -m py_compile /usr/local/bin/harbor_dynamic_colleague_adapter.py /usr/local/bin/semantic_colleague.py
