from test_support import load_title_chunker
import pytest


def test_title_chunker_exposes_a_hard_token_cap():
    module = load_title_chunker()
    assert module is not None
    param = module.TitleChunkerParam()
    assert param.chunk_token_cap == 512
    param.levels = [[r'^#']]
    param.method = 'group'
    for cap in (128, 512, 8000, 0, None):
        param.chunk_token_cap = cap
        param.check()
    for cap in (127, 8001, -1):
        param.chunk_token_cap = cap
        with pytest.raises(ValueError):
            param.check()
