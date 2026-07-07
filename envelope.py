"""
Signed envelope format for data LotsoNet nodes exchange through the DHT.

Every value a node stores under a lotsonet:* key that another node must
trust (who produced it, that it hasn't been tampered with, that it isn't
a replay of something stale) is wrapped in one of these envelopes instead
of being stored as plain JSON. The envelope itself is just a string, and
travels as an ordinary opaque DHT value -- Kademlia never parses it.
"""

import hashlib
import json
import time
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

FRESHNESS_WINDOW_SECONDS = 120


def load_or_create_keypair(path: Path) -> Ed25519PrivateKey:
    if path.exists():
        raw = bytes.fromhex(path.read_text().strip())
        return Ed25519PrivateKey.from_private_bytes(raw)
    private_key = Ed25519PrivateKey.generate()
    raw = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    path.write_text(raw.hex())
    return private_key


def public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def node_id_for_pubkey(pubkey_bytes: bytes) -> str:
    return hashlib.sha1(pubkey_bytes).hexdigest()


def node_id_bytes_for_key(private_key: Ed25519PrivateKey) -> bytes:
    return hashlib.sha1(public_key_bytes(private_key)).digest()


def node_id_for_key(private_key: Ed25519PrivateKey) -> str:
    return node_id_bytes_for_key(private_key).hex()


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def make_envelope(env_type: str, private_key: Ed25519PrivateKey, payload, context: dict = None) -> str:
    """
    Build a signed envelope of the given type, carrying payload and an
    optional context dict (identifiers that a verifier can cross-check
    against the DHT key this envelope ends up stored under, e.g. task_id).
    """
    pubkey_bytes = public_key_bytes(private_key)
    body = {
        "type": env_type,
        "node_id": node_id_for_pubkey(pubkey_bytes),
        "context": context or {},
        "timestamp": time.time(),
        "payload": payload,
        "pubkey": pubkey_bytes.hex(),
    }
    body["signature"] = private_key.sign(_canonical(body)).hex()
    return json.dumps(body)


def open_envelope(
    raw_value,
    expected_type: str,
    expected_node_id: str = None,
    expected_context: dict = None,
    max_age: float = FRESHNESS_WINDOW_SECONDS,
):
    """
    Verify a signed envelope and return its payload, or None if anything
    doesn't check out: malformed data, bad signature, node_id not matching
    the embedded pubkey, type/context mismatch with what the caller
    expected (e.g. the DHT key it was fetched from), or a stale timestamp
    outside the freshness window.
    """
    try:
        body = json.loads(raw_value)
        pubkey_bytes = bytes.fromhex(body["pubkey"])
        signature = bytes.fromhex(body["signature"])
        node_id = body["node_id"]
        env_type = body["type"]
        context = body["context"]
        timestamp = body["timestamp"]
        payload = body["payload"]
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None

    if node_id_for_pubkey(pubkey_bytes) != node_id:
        return None

    signed_body = {k: v for k, v in body.items() if k != "signature"}
    try:
        Ed25519PublicKey.from_public_bytes(pubkey_bytes).verify(signature, _canonical(signed_body))
    except InvalidSignature:
        return None

    if env_type != expected_type:
        return None
    if expected_node_id is not None and node_id != expected_node_id:
        return None
    if expected_context:
        for key, value in expected_context.items():
            if context.get(key) != value:
                return None
    if time.time() - timestamp > max_age:
        return None

    return payload
