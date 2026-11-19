FROM harbor.tokenwave.us/release/cowork-bench/104-workplace@sha256:c50a552057bd7773e6077146819075aee1367cae2f7d8e882c046a23711752b6
USER root
COPY repair-scope.py /tmp/repair-scope.py
RUN python3 /tmp/repair-scope.py && rm /tmp/repair-scope.py
