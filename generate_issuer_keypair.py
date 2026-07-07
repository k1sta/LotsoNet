"""
One-off script: generates the network's single task-issuer keypair.

Run this once. issuer.pub is the public key every node trusts -- check it
into the repo/image. issuer.key is the private key -- do NOT check it in;
copy it only to whichever machine is authorized to issue "run" commands.
"""

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

PRIVATE_KEY_PATH = Path("issuer.key")
PUBLIC_KEY_PATH = Path("issuer.pub")


def main():
    if PRIVATE_KEY_PATH.exists() or PUBLIC_KEY_PATH.exists():
        raise SystemExit(
            f"{PRIVATE_KEY_PATH} or {PUBLIC_KEY_PATH} already exists. "
            "Refusing to overwrite an existing issuer keypair."
        )

    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    PRIVATE_KEY_PATH.write_text(private_bytes.hex())
    PUBLIC_KEY_PATH.write_text(public_bytes.hex())

    print(f"Wrote {PRIVATE_KEY_PATH} (keep this secret, do not commit) and {PUBLIC_KEY_PATH} (safe to commit).")


if __name__ == "__main__":
    main()
