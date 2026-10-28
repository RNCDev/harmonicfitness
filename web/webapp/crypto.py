"""Envelope encryption: a data key per user, wrapped under the master key.

AES-256-GCM with a random 12-byte nonce prefixed to the ciphertext. The AAD
binds a value to its place: f"{user_id}:{table}:{key}".encode().
"""
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE = 12
TAG = 16
_WRAP_AAD = b"wt:data-key"


class Tampered(Exception):
    """The value was altered, sealed for another place, or sealed under another key."""


def seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def open_(key: bytes, sealed: bytes, aad: bytes) -> bytes:
    if len(sealed) < NONCE + TAG:
        raise Tampered("sealed value is too short")
    try:
        return AESGCM(key).decrypt(sealed[:NONCE], sealed[NONCE:], aad)
    except InvalidTag:
        raise Tampered("sealed value did not verify") from None


def new_data_key(master: bytes) -> tuple[bytes, bytes]:
    key = AESGCM.generate_key(bit_length=256)
    return key, seal(master, key, _WRAP_AAD)


def unwrap(master: bytes, wrapped: bytes) -> bytes:
    return open_(master, wrapped, _WRAP_AAD)
