import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent / 'harness'
sys.argv = [str(root / 'run_contracts.py')]
if os.environ.get('SEGPIPE_TARGET_PR'):
    sys.argv += ['--pr', os.environ['SEGPIPE_TARGET_PR']]
runpy.run_path(sys.argv[0], run_name='__main__')
