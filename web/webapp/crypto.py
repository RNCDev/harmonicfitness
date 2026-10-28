"""Envelope encryption: a data key per user, wrapped under the master key.

AES-256-GCM with a random 12-byte nonce prefixed to the ciphertext. The AAD
binds a value to its place: f"{user_id}:{table}:{key}".encode(). A wrapped data key is bound to
its user and key version: f"wt:data-key:{user_id}:{key_version}".
"""
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE = 12
TAG = 16


class Tampered(Exception):
    """The value was altered, sealed for another place, or sealed under another key."""


def _check(key: bytes) -> None:
    if not isinstance(key, (bytes, bytearray)) or len(key) != 32:
        raise ValueError("key must be 32 bytes")


def seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    _check(key)
    nonce = os.urandom(NONCE)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def open_(key: bytes, sealed: bytes, aad: bytes) -> bytes:
    _check(key)
    if len(sealed) < NONCE + TAG:
        raise Tampered("sealed value is too short")
    try:
        return AESGCM(key).decrypt(sealed[:NONCE], sealed[NONCE:], aad)
    except InvalidTag:
        raise Tampered("sealed value did not verify") from None


def _wrap_aad(user_id, key_version: int) -> bytes:
    if isinstance(key_version, bool) or not isinstance(key_version, int):
        raise ValueError("key_version must be an int")
    return f"wt:data-key:{user_id}:{key_version}".encode()


def new_data_key(master: bytes, user_id, key_version: int) -> tuple[bytes, bytes]:
    """A fresh data key and its wrap under `master`, bound to the user and key version."""
    _check(master)
    aad = _wrap_aad(user_id, key_version)
    key = AESGCM.generate_key(bit_length=256)
    return key, seal(master, key, aad)


def unwrap(master: bytes, wrapped: bytes, user_id, key_version: int) -> bytes:
    return open_(master, wrapped, _wrap_aad(user_id, key_version))
