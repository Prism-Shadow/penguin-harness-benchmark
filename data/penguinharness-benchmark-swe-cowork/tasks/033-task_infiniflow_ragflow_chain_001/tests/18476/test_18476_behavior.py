from types import SimpleNamespace

import pytest

from test_support import ProcessCapture, load_chunker_pipeline, run


@pytest.mark.parametrize('kind', ['group', 'hierarchy'])
@pytest.mark.parametrize('text', ['界🙂e\u0301漢字' * 180, 'alpha beta. ' * 300, 'literal�字符' * 150])
def test_title_invoke_bounds_unicode_without_losing_source(kind, text):
    common, implementation = load_chunker_pipeline(kind, real_tokens=True)
    params = common.TitleChunkerParam()
    params.chunk_token_cap = 128
    params.levels = [[r'^#']]
    params.hierarchy = 1
    process = ProcessCapture(params)
    upstream = SimpleNamespace(output_format='markdown', markdown_result=text, file=None)
    chunker_type = getattr(implementation, kind.title() + 'TitleChunker')
    run(chunker_type(process, upstream).invoke())
    chunks = process.outputs['chunks']
    assert len(chunks) > 1
    assert ''.join(chunk['text'] for chunk in chunks) == text + '\n'
    assert all(common.num_tokens_from_string(chunk['text']) <= 128 for chunk in chunks)
    params.chunk_token_cap = 0
    run(chunker_type(process, upstream).invoke())
    assert ''.join(chunk['text'] for chunk in process.outputs['chunks']) == text + '\n'


@pytest.mark.parametrize('kind', ['group', 'hierarchy'])
def test_title_media_remains_atomic_and_positions_do_not_spread(kind):
    common, implementation = load_chunker_pipeline(kind, real_tokens=True)
    params = common.TitleChunkerParam()
    params.chunk_token_cap = 128
    params.levels = [[r'^#']]
    params.hierarchy = 1
    process = ProcessCapture(params)
    text = '世界🙂' * 300
    media = {'text': 'table ' * 300, 'doc_type_kwd': 'table', 'img_id': 'media-1'}
    upstream = SimpleNamespace(output_format='json', name='example.json', file=None, json_result=[
        {'text': text, '_pdf_positions': [[2, 0, 10, 20, 30]]}, media])
    run(getattr(implementation, kind.title() + 'TitleChunker')(process, upstream).invoke())
    chunks = process.outputs['chunks']
    text_chunks = [chunk for chunk in chunks if chunk.get('doc_type_kwd', 'text') == 'text']
    assert ''.join(chunk['text'] for chunk in text_chunks) == text + '\n'
    assert text_chunks[0]['page_num_int'] == [2]
    assert all(not chunk.get('page_num_int') for chunk in text_chunks[1:])
    assert chunks[-1]['text'] == media['text']
    assert chunks[-1]['img_id'] == 'media-1'
