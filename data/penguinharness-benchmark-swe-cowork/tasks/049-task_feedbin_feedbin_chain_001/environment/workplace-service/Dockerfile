FROM harbor.tokenwave.us/release/cowork-bench/049-workplace@sha256:d7a9f6759038ba5d14a1d2eeea424c458c6e72b868d32469c817568cdeaec6c4
USER root
COPY runtime/runtime_daemon.py /usr/local/bin/runtime_daemon.py
COPY runtime/workplace-sidecar /usr/local/bin/workplace-sidecar
COPY original/authoring/corpus/docs.json /opt/tokenwave-original/authoring/corpus/docs.json
COPY original/authoring/orgchat_auto1/knowledge_packs/core-03.json /opt/tokenwave-original/authoring/orgchat_auto1/knowledge_packs/core-03.json
COPY original/authoring/orgchat_auto1/knowledge_packs/core-06.json /opt/tokenwave-original/authoring/orgchat_auto1/knowledge_packs/core-06.json
COPY original/authoring/orgchat_auto1/delivery_plan.json /opt/tokenwave-original/authoring/orgchat_auto1/delivery_plan.json
COPY original/harness/config/workplace.json /opt/tokenwave-original/harness/config/workplace.json
RUN chmod 555 /usr/local/bin/workplace-sidecar && chmod 444 /usr/local/bin/runtime_daemon.py /opt/tokenwave-original/authoring/corpus/docs.json /opt/tokenwave-original/harness/config/workplace.json
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original
