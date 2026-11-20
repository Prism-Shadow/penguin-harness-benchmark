from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_support"))
from lifecycle_contracts import check

if __name__ == "__main__":
    check(sys.argv[1])
