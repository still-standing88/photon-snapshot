"""Create and verify PlayForm-compatible detached release signatures."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import zlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


PUBLIC_KEY = Path(__file__).resolve().parents[1] / "signing" / "release-public.pem"
SIGNATURE_PADDING = padding.PSS(
    mgf=padding.MGF1(hashes.SHA256()),
    salt_length=padding.PSS.MAX_LENGTH,
)


def sign_release(args, binary, public_key):
    pem = os.environ.get("PHOTON_SIGNING_PRIVATE_KEY")
    if not pem:
        raise ValueError("PHOTON_SIGNING_PRIVATE_KEY is missing")
    private_key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey) or private_key.key_size != 4096:
        raise ValueError("The signing key must be an RSA-4096 private key")
    if private_key.public_key().public_numbers() != public_key.public_numbers():
        raise ValueError("The signing key does not match the repository public key")

    file_info = {
        "path": args.member or args.binary.name,
        "crc32": f"{zlib.crc32(binary):08x}",
        "sha256": hashlib.sha256(binary).hexdigest(),
        "sha512": hashlib.sha512(binary).hexdigest(),
        "has_signature": True,
    }
    signature = private_key.sign(binary, SIGNATURE_PADDING, hashes.SHA256())
    public_key.verify(signature, binary, SIGNATURE_PADDING, hashes.SHA256())
    args.signature.write_bytes(signature)
    manifest = {"version": args.version, "files": [file_info]}
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Signed {args.binary} and wrote {args.signature} and {args.manifest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sign = commands.add_parser("sign", help="Sign a binary and generate its release manifest")
    verify = commands.add_parser("verify", help="Verify a binary against its detached signature")
    for command in (sign, verify):
        command.add_argument("binary", type=Path)
        command.add_argument("signature", type=Path)
        command.add_argument("--public-key", type=Path, default=PUBLIC_KEY)
    sign.add_argument("manifest", type=Path)
    sign.add_argument("--version", required=True)
    sign.add_argument("--member", help="Relative binary path in the distribution")
    args = parser.parse_args()

    try:
        public_key = serialization.load_pem_public_key(args.public_key.read_bytes())
        if not isinstance(public_key, rsa.RSAPublicKey) or public_key.key_size != 4096:
            raise ValueError("The verification key must be an RSA-4096 public key")
        binary = args.binary.read_bytes()
        if args.command == "sign":
            sign_release(args, binary, public_key)
        else:
            public_key.verify(args.signature.read_bytes(), binary, SIGNATURE_PADDING, hashes.SHA256())
            print(f"Verified {args.binary}")
    except InvalidSignature:
        parser.exit(1, f"Invalid signature for {args.binary}\n")
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
