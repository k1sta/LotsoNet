"""
Signed envelope format for authorizing task commands in LotsoNet.

Every node trusts exactly one, pre-shared public key (distributed out of
band -- checked into the repo/image, not learned from the DHT). Only
whoever holds the matching private key can produce a task envelope that
any node will accept and execute. The envelope itself is just a string,
and travels as an ordinary opaque DHT value -- Kademlia never parses it.
"""

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


def load_private_key_if_present(path: Path) -> Ed25519PrivateKey:
    if not path.exists():
        return None
    raw = bytes.fromhex(path.read_text().strip())
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_public_key(path: Path) -> bytes:
    return bytes.fromhex(path.read_text().strip())


def public_key_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def make_envelope(env_type: str, private_key: Ed25519PrivateKey, payload, context: dict = None) -> str:
    """
    Build a signed envelope of the given type, carrying payload and an
    optional context dict (identifiers a verifier can cross-check against
    where this envelope ends up stored, e.g. task_id).
    """
    body = {
        "type": env_type,
        "context": context or {},
        "timestamp": time.time(),
        "payload": payload,
        "pubkey": public_key_bytes(private_key).hex(),
    }
    body["signature"] = private_key.sign(_canonical(body)).hex()
    return json.dumps(body)


def open_envelope(
    raw_value,
    expected_type: str,
    authorized_pubkey: bytes = None,
    expected_context: dict = None,
    max_age: float = FRESHNESS_WINDOW_SECONDS,
):
    """
    Verify a signed envelope and return its payload, or None if anything
    doesn't check out: malformed data, bad signature, the embedded pubkey
    not matching the one caller-supplied authorized_pubkey (this is what
    makes it an authorization check, not just an authenticity check --
    anyone can sign a well-formed envelope, only the one trusted key is
    accepted), type/context mismatch with what the caller expected, or a
    stale timestamp outside the freshness window.
    """
    try:
        body = json.loads(raw_value)
        pubkey_bytes = bytes.fromhex(body["pubkey"])
        signature = bytes.fromhex(body["signature"])
        env_type = body["type"]
        context = body["context"]
        timestamp = body["timestamp"]
        payload = body["payload"]
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None

    if authorized_pubkey is not None and pubkey_bytes != authorized_pubkey:
        return None

    signed_body = {k: v for k, v in body.items() if k != "signature"}
    try:
        Ed25519PublicKey.from_public_bytes(pubkey_bytes).verify(signature, _canonical(signed_body))
    except InvalidSignature:
        return None

    if env_type != expected_type:
        return None
    if expected_context:
        for key, value in expected_context.items():
            if context.get(key) != value:
                return None
    if time.time() - timestamp > max_age:
        return None

    return payload
