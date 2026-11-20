from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from environment.probe_runtime import run_for_pr
if __name__ == '__main__': raise SystemExit(run_for_pr(1511))
