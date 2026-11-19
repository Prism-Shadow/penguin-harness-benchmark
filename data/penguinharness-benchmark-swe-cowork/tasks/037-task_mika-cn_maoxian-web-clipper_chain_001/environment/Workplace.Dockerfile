FROM harbor.tokenwave.us/release/cowork-bench/037-workplace@sha256:aa59d2c76e42381b99fd90083783d797f6e2286d822799f7b170e4aac8ce8669
USER root
COPY workplace-repair/repair.py /tmp/repair-workplace.py
COPY public-contract.md /tmp/public-contract.md
RUN python3 /tmp/repair-workplace.py && rm /tmp/repair-workplace.py /tmp/public-contract.md
