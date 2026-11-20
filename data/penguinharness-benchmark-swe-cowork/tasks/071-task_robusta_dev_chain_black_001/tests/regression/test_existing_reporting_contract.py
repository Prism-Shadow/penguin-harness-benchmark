from robusta.core.reporting.blocks import BLOCK_SIZE_LIMIT, MarkdownBlock


def test_existing_markdown_block_truncation_contract():
    original = "x" * (BLOCK_SIZE_LIMIT + 50)
    rendered = MarkdownBlock(original)
    assert rendered.text == ("x" * BLOCK_SIZE_LIMIT) + "..."
