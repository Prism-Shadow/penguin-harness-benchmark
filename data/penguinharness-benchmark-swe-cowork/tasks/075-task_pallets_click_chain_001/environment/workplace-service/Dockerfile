FROM harbor.tokenwave.us/release/cowork-bench/075-workplace@sha256:d73b1d1c3baac13b20d368a5e9549b06e0db86dd5b166a40956a88a0b305ddf5
USER root
COPY runtime/ /usr/local/bin/
RUN rm -rf /opt/tokenwave-original
COPY original/ /opt/tokenwave-original/
RUN chmod 755 /usr/local/bin/workplace-sidecar && chmod -R a+rX /opt/tokenwave-original
ENTRYPOINT ["/usr/local/bin/workplace-sidecar"]
CMD ["--original-root", "/opt/tokenwave-original", "--socket", "/run/workplace/service.sock", "--host", "127.0.0.1"]
