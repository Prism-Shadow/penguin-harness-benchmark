import pytest

from test_support import ProcessCapture, load_chunker_pipeline, run


def invoke(module, items, delimiters, capture=None):
    params = module.TokenChunkerParam()
    params.delimiter_mode = 'delimiter'
    params.delimiters = delimiters
    capture = capture or ProcessCapture(params)
    capture._param = params
    run(module.TokenChunker._invoke(capture, name='source.json', output_format='json', json=items))
    return capture


def test_json_delimiter_positions_follow_contributors_and_flushes():
    module = load_chunker_pipeline()
    first = [1, 0, 10, 0, 10]
    second = [2, 0, 20, 10, 20]
    third = [3, 0, 30, 20, 30]
    capture = invoke(module, [
        {'text': 'left|shared', '_pdf_positions': [first]},
        {'text': 'tail|right@@2\t3\t4##', '_pdf_positions': [second]},
        {'text': 'TABLE', 'doc_type_kwd': 'table', 'img_id': 'table-image'},
        {'text': 'next|last', '_pdf_positions': [third]},
    ], ['`|`'])
    chunks = capture.outputs['chunks']
    assert [chunk['text'] for chunk in chunks] == ['left', 'shared\ntail', 'right', 'TABLE', 'next', 'last']
    assert [chunk.get('page_num_int', []) for chunk in chunks] == [[1], [1, 2], [2], [], [3], [3]]
    assert chunks[3]['doc_type_kwd'] == 'table'
    assert chunks[3]['img_id'] == 'table-image'
    invoke(module, [{'text': 'fresh|state'}], ['`|`'], capture)
    assert [chunk['text'] for chunk in capture.outputs['chunks']] == ['fresh', 'state']
    assert all(not chunk.get('page_num_int') for chunk in capture.outputs['chunks'])


def test_json_no_delimiter_retains_merge_and_error_recovery():
    module = load_chunker_pipeline()
    capture = invoke(module, [{'text': 'alpha'}, {'text': 'beta@@1\t2\t3##'}], [])
    assert len(capture.outputs['chunks']) == 1
    assert 'alpha' in capture.outputs['chunks'][0]['text']
    assert 'beta' in capture.outputs['chunks'][0]['text']
    assert '@@' not in capture.outputs['chunks'][0]['text']
    run(module.TokenChunker._invoke(capture, output_format='unsupported'))
    assert capture.outputs['_ERROR'].startswith('Input error:')
    capture.outputs.clear()
    invoke(module, [], [], capture)
    assert capture.outputs['chunks'] == []


@pytest.mark.parametrize('mode', ['delimiter', 'token_size'])
def test_json_normalized_mode_keeps_token_size_merging_connected(mode):
    module = load_chunker_pipeline()
    words = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta']
    outputs = []
    for size in (1, 1024):
        params = module.TokenChunkerParam()
        params.delimiter_mode = mode
        params.delimiters = []
        params.chunk_token_size = size
        params.check()
        capture = ProcessCapture(params)
        run(module.TokenChunker._invoke(capture, name='source.json', output_format='json',
                                       json=[{'text': word + '@@1\t2\t3##'} for word in words]))
        chunks = capture.outputs['chunks']
        assert ' '.join(chunk['text'] for chunk in chunks).split() == words
        assert all('@@' not in chunk['text'] for chunk in chunks)
        outputs.append(chunks)
    assert len(outputs[0]) > 1
    assert len(outputs[1]) == 1
