# SPDX-License-Identifier: GPL-3.0-or-later
"""Sign accepted release bytes using an external Ed25519 private key."""
import argparse
import base64
import json
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import release_artifact
from update_sources import canonical_manifest, descriptor_name, verify_descriptor
from version import VERSION


def descriptor_for(root, commit, key_path):
    root = Path(root)
    asset = root / release_artifact.artifact_name(VERSION)
    accepted = release_artifact.verify_release(asset, VERSION, root, Path(str(asset)+".sha256"),
        root / "build/release-receipts" / (asset.name+".json"), commit=commit)
    key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Expected Ed25519 private key")
    manifest = dict(schema=1, version=VERSION, tag="v"+VERSION, asset_name=asset.name,
        size=asset.stat().st_size, sha256=accepted["zip_sha256"], exe_sha256=accepted["exe_sha256"], commit=commit)
    raw = json.dumps(dict(manifest=manifest, signature=base64.b64encode(
        key.sign(canonical_manifest(manifest))).decode()), sort_keys=True, indent=2).encode()+b"\n"
    verify_descriptor(raw, manifest["tag"], asset.name)  # Reject a key different from the client trust key.
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["sign", "verify"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--key", type=Path)
    args = parser.parse_args()
    path = args.root / descriptor_name("v"+VERSION)
    if args.mode == "sign":
        if not args.key:
            parser.error("--key is required to sign")
        raw = descriptor_for(args.root, args.commit, args.key)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("Refusing to overwrite a different signed descriptor")
        path.write_bytes(raw)
    else:
        asset = args.root / release_artifact.artifact_name(VERSION)
        accepted = release_artifact.verify_release(asset, VERSION, args.root, Path(str(asset)+".sha256"),
            args.root / "build/release-receipts" / (asset.name+".json"), commit=args.commit)
        manifest = verify_descriptor(path.read_bytes(), "v"+VERSION, asset.name)
        if (manifest["commit"] != args.commit or manifest["sha256"] != accepted["zip_sha256"]
                or manifest["exe_sha256"] != accepted["exe_sha256"] or manifest["size"] != asset.stat().st_size):
            raise ValueError("Signed descriptor differs from accepted release")
    print("Signed descriptor verified:", path.name)


if __name__ == "__main__":
    main()
