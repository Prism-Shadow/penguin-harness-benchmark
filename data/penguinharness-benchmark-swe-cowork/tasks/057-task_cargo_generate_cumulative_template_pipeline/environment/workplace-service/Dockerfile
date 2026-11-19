FROM harbor.tokenwave.us/release/cowork-bench/057-workplace@sha256:8945cbd1d1b9fe5732be6b04c2d6235254be4a0bfffcc073de1cd6831093897b
COPY original /opt/tokenwave-original
COPY runtime/ /usr/local/bin/
RUN PYTHONPATH=/usr/local/bin python3 -c 'from runtime_daemon import RuntimeState; from pathlib import Path; RuntimeState(Path("/opt/tokenwave-original/authoring"))'
