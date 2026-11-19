FROM harbor.tokenwave.us/release/cowork-bench/048-workplace@sha256:7162433522b603f860c6414a0344857a88afc2e959529323b6b858847637afcc
USER root
COPY usr/local/bin/ /usr/local/bin/
COPY opt/tokenwave-original/ /opt/tokenwave-original/
RUN chmod 0555 /usr/local/bin/workplace-sidecar \
 && python3 -m py_compile /usr/local/bin/workplace-sidecar /usr/local/bin/runtime_daemon.py /usr/local/bin/semantic_colleague.py /usr/local/bin/colleague_availability.py /usr/local/bin/harbor_dynamic_colleague_adapter.py
ENV TOKENWAVE_ORIGINAL_ROOT=/opt/tokenwave-original
ENTRYPOINT ["python3", "/usr/local/bin/workplace-sidecar"]
CMD ["--original-root", "/opt/tokenwave-original", "--host", "0.0.0.0", "--quiet"]
