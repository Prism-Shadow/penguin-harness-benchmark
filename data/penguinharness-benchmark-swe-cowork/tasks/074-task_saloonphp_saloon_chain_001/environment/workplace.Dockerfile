FROM harbor.tokenwave.us/release/cowork-bench/074-workplace@sha256:b7085bcf79fc66ce5a876bb360e4d9a6cac62c916bd8f8a3d987132c42baafab
COPY delivery_plan.fixed.json /opt/tokenwave-original/authoring/orgchat_auto1/delivery_plan.json
COPY workplace-service/runtime_daemon.py /usr/local/bin/runtime_daemon.py
COPY workplace-service/original/authoring/orgchat_auto1/knowledge_packs/core-04.json /opt/tokenwave-original/authoring/orgchat_auto1/knowledge_packs/core-04.json
COPY workplace-service/original/authoring/corpus/docs.json /opt/tokenwave-original/authoring/corpus/docs.json
