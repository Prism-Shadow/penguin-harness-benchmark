from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / '_shared'))
from contract_lib import assert_contract

def test_pr_contract():
    assert_contract(4692)
