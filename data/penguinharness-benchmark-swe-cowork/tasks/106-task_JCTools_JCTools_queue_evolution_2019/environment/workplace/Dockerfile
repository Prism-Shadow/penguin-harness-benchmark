FROM harbor.tokenwave.us/release/cowork-bench/106-workplace@sha256:0fbef017dc3b44c6df4174a688baa280d2be77cf300cde71f50a69a3f22cfc5b
USER root
COPY docs.json /opt/tokenwave-original/authoring/corpus/docs.json
COPY board.json /opt/tokenwave-original/authoring/corpus/board.json
COPY delivery_plan.json /opt/tokenwave-original/authoring/orgchat_auto1/delivery_plan.json
RUN chmod a=r /opt/tokenwave-original/authoring/corpus/docs.json /opt/tokenwave-original/authoring/corpus/board.json /opt/tokenwave-original/authoring/orgchat_auto1/delivery_plan.json
COPY overrides/ /opt/tokenwave-original/
RUN chmod a=r /opt/tokenwave-original/authoring/orgchat_auto1/knowledge_packs/core-03.json /opt/tokenwave-original/authoring/orgchat_auto1/knowledge_packs/core-06.json /opt/tokenwave-original/authoring/corpus/chat.json /opt/tokenwave-original/authoring/corpus/artifacts.json /opt/tokenwave-original/authoring/gitplan/reviews.json /opt/tokenwave-original/harness/config/workplace.json
