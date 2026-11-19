"""Legacy sha3 import compatibility with actual SHA-3 and Keccak algorithms.

SHA-3 and Ethereum Keccak use different padding and are never interchangeable.
The Keccak backend is mandatory; missing native dependencies fail on import.
"""
from hashlib import sha3_224, sha3_256, sha3_384, sha3_512, shake_128, shake_256
from Crypto.Hash import keccak as _keccak


def keccak_224(data=b''):
    return _keccak.new(digest_bits=224, data=data, update_after_digest=True)


def keccak_256(data=b''):
    return _keccak.new(digest_bits=256, data=data, update_after_digest=True)


def keccak_384(data=b''):
    return _keccak.new(digest_bits=384, data=data, update_after_digest=True)


def keccak_512(data=b''):
    return _keccak.new(digest_bits=512, data=data, update_after_digest=True)

__all__ = ['sha3_224', 'sha3_256', 'sha3_384', 'sha3_512', 'shake_128', 'shake_256',
           'keccak_224', 'keccak_256', 'keccak_384', 'keccak_512']
