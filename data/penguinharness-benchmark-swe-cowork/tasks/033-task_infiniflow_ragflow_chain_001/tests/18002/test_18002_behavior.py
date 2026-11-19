from test_support import ProcessCapture, load_chunker_pipeline, run


def test_coordinate_tags_are_removed_before_embedding_text_is_emitted():
    module = load_chunker_pipeline()
    param = module.TokenChunkerParam()
    param.delimiter_mode = "delimiter"
    param.delimiters = ["`END`"]
    capture = ProcessCapture(param)
    run(module.TokenChunker._invoke(capture, name="sample.json", output_format="json", json=[
        {"text": "before@@1\t2\t3##afterENDtail", "doc_type_kwd": "text"}]))
    assert "_ERROR" not in capture.outputs, capture.outputs
    text = "".join(c["text"] for c in capture.outputs["chunks"])
    assert "beforeafter" in text and "tail" in text
    assert "@@" not in text and "##" not in text
