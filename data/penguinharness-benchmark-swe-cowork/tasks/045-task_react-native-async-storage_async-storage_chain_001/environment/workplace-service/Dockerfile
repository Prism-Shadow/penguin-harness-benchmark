FROM harbor.tokenwave.us/release/cowork-bench/045-workplace@sha256:2e130dd733780feb0f5fad340e51e3940fe3fafca4927ad877c4a0b4c26d7a3b
COPY semantic_colleague.py /usr/local/bin/semantic_colleague.py
COPY harbor_dynamic_colleague_adapter.py /usr/local/bin/harbor_dynamic_colleague_adapter.py
COPY original/ /opt/tokenwave-original/
RUN python3 -m py_compile /usr/local/bin/semantic_colleague.py /usr/local/bin/harbor_dynamic_colleague_adapter.py
