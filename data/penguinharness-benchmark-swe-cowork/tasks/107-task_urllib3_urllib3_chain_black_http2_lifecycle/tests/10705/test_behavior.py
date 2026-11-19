from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_support"))
from transport_edges import check_http2_large_body

def test_behavior_contract():
    check_http2_large_body()
