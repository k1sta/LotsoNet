"""
Chunked transport for oversized task payloads in LotsoNet.

rpcudp caps a single RPC call (function name + args, msgpack-serialized)
at 8192 bytes (rpcudp/protocol.py). kademlia.network.Server.set() issues
one such RPC per k-closest node for the *entire* value, so any value
whose encoded form approaches that cap must be split into multiple
independent server.set() calls (one per chunk key), with a small signed
manifest (one more server.set()) pointing at them.

This module is transport-only: it does not decide whether to chunk
(node.py measures the actual announcement size and calls needs_chunking)
and does not perform authorization checks itself -- callers already hold
a real issuer_private_key (to write) or an authorized_pubkey (to read),
obtained the same way the unchunked task-announcement path already does.
"""

import asyncio
import hashlib

from envelope import make_envelope, open_envelope

CHUNK_SIZE_BYTES = 4096
TASK_ANNOUNCEMENT_SAFE_LIMIT = 6000
MANIFEST_ENVELOPE_TYPE = "task-chunks-manifest"
MAX_CHUNK_COUNT = 2000

CHUNK_FETCH_ROUNDS = 5
CHUNK_FETCH_DELAYS = (0.5, 1.0, 2.0, 4.0, 4.0)


class ChunkFetchError(Exception):
    """A task's chunked payload could not be reliably retrieved or verified."""


def chunk_key(task_id: str, index: int) -> str:
    return f"lotsonet:task:{task_id}:chunk:{index}"


def manifest_key(task_id: str) -> str:
    return f"lotsonet:task:{task_id}:manifest"


def split_into_chunks(data: bytes, chunk_size: int = CHUNK_SIZE_BYTES) -> list:
    """
    Split already-UTF-8-encoded bytes into fixed-size byte chunks. Never
    split a str -- a multi-byte character must never straddle a chunk
    boundary; decoding only happens after full reassembly.
    """
    if not data:
        return [b""]
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]


def needs_chunking(encoded_length: int, limit: int = TASK_ANNOUNCEMENT_SAFE_LIMIT) -> bool:
    """Single source of truth for the chunk/no-chunk decision."""
    return encoded_length > limit


async def store_chunks(server, task_id: str, code_bytes: bytes) -> dict:
    """
    Store code_bytes as a sequence of raw bytes values at chunk_key(task_id, i).
    Sequential, no swallowed exceptions -- a failure mid-loop must propagate
    rather than silently leave a manifest referencing incomplete data.
    Returns the manifest payload (caller stores the signed manifest after).
    """
    chunks = split_into_chunks(code_bytes)
    if len(chunks) > MAX_CHUNK_COUNT:
        raise ChunkFetchError(
            f"script too large: {len(chunks)} chunks exceeds MAX_CHUNK_COUNT={MAX_CHUNK_COUNT}"
        )

    for index, chunk in enumerate(chunks):
        ok = await server.set(chunk_key(task_id, index), chunk)
        if not ok:
            raise ChunkFetchError(f"failed to store chunk {index}/{len(chunks)} for task {task_id}")

    return {
        "task_id": task_id,
        "chunk_count": len(chunks),
        "total_bytes": len(code_bytes),
        "chunk_size": CHUNK_SIZE_BYTES,
        "sha256": hashlib.sha256(code_bytes).hexdigest(),
    }


async def build_and_store_manifest(server, task_id: str, code_bytes: bytes, issuer_private_key) -> None:
    """Write all chunks first, then the signed manifest pointing at them."""
    manifest_payload = await store_chunks(server, task_id, code_bytes)
    envelope_str = make_envelope(
        MANIFEST_ENVELOPE_TYPE, issuer_private_key, manifest_payload, context={"task_id": task_id}
    )
    await server.set(manifest_key(task_id), envelope_str)


async def _fetch_with_retry(getter, rounds=CHUNK_FETCH_ROUNDS, delays=CHUNK_FETCH_DELAYS):
    value = await getter()
    for attempt in range(rounds - 1):
        if value is not None:
            return value
        await asyncio.sleep(delays[attempt])
        value = await getter()
    return value


async def fetch_and_reassemble(server, task_id: str, authorized_pubkey: bytes) -> str:
    """
    Fetch and verify the manifest, then fetch and verify every chunk, and
    return the reassembled script as a decoded str. Raises ChunkFetchError
    (never returns partial/unverified content) on: manifest never found,
    manifest failing signature/authorization/context/freshness checks
    (open_envelope collapses these into one None, so the message says so
    plainly rather than guessing which sub-check failed), any chunk still
    missing after all retries, or an integrity (sha256/length) mismatch.
    """
    manifest_raw = await _fetch_with_retry(lambda: server.get(manifest_key(task_id)))
    if manifest_raw is None:
        raise ChunkFetchError(f"manifest not found for task {task_id} after {CHUNK_FETCH_ROUNDS} rounds")

    manifest = open_envelope(
        manifest_raw,
        MANIFEST_ENVELOPE_TYPE,
        authorized_pubkey=authorized_pubkey,
        expected_context={"task_id": task_id},
    )
    if manifest is None:
        raise ChunkFetchError(
            f"manifest for task {task_id} rejected "
            "(signature, authorization, task_id context, or freshness check failed)"
        )

    total = manifest["chunk_count"]
    keys = [chunk_key(task_id, i) for i in range(total)]
    chunks = [None] * total

    for attempt in range(CHUNK_FETCH_ROUNDS):
        missing = [i for i in range(total) if chunks[i] is None]
        if not missing:
            break
        fetched = await asyncio.gather(*(server.get(keys[i]) for i in missing))
        for i, value in zip(missing, fetched):
            if value is not None:
                chunks[i] = value
        still_missing = [i for i in range(total) if chunks[i] is None]
        if still_missing and attempt < CHUNK_FETCH_ROUNDS - 1:
            await asyncio.sleep(CHUNK_FETCH_DELAYS[attempt])

    missing_final = [i for i in range(total) if chunks[i] is None]
    if missing_final:
        raise ChunkFetchError(
            f"chunk(s) {missing_final} missing for task {task_id} after {CHUNK_FETCH_ROUNDS} rounds"
        )

    data = b"".join(chunks)

    if len(data) != manifest["total_bytes"]:
        raise ChunkFetchError(f"reassembled size mismatch for task {task_id}: tampered or corrupted chunk")
    if hashlib.sha256(data).hexdigest() != manifest["sha256"]:
        raise ChunkFetchError(f"reassembled content failed integrity check for task {task_id}")

    return data.decode("utf-8")
