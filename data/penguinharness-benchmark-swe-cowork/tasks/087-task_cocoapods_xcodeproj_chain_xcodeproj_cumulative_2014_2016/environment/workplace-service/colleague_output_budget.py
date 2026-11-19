"""Read the bounded colleague output budget without rewriting installed source."""
import os


def max_output_tokens():
    raw = os.environ.get('COWORK_COLLEAGUE_MAX_OUTPUT_TOKENS', '32768')
    if not raw.isdecimal() or not 1 <= int(raw) <= 131072:
        raise ValueError('Invalid COWORK_COLLEAGUE_MAX_OUTPUT_TOKENS')
    return int(raw)
