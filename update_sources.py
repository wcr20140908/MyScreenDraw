# SPDX-License-Identifier: GPL-3.0-or-later
"""Public update origins and authenticated release descriptors; no account credentials."""
import base64
import json
import re
import urllib.parse
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SOURCES = {
    "github": ("https://api.github.com/repos/wcr20140908/MyScreenDraw/releases", "github.com"),
    "gitcode": ("https://api.gitcode.com/api/v5/repos/wcr20140908/MyScreenDraw/releases", "gitcode.com"),
}
PUBLIC_KEY = "WtVLv6wgku6rc38O3uLPn1WJ6QnX85D4DG22Cq0y/cg="
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_DESCRIPTOR_BYTES = 16 * 1024


def releases_url(source):
    base = SOURCES[source][0]
    return base + ("?per_page=30" if source == "github" else "?page=1&per_page=100")


def official_asset_url(url, tag, name, source="github"):
    if source not in SOURCES or not all(isinstance(x, str) for x in (url, tag, name)):
        return False
    try:
        parsed = urllib.parse.urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == SOURCES[source][1]
                and parsed.port is None and not parsed.username and not parsed.password
                and not parsed.query and not parsed.fragment
                and parsed.path == f"/wcr20140908/MyScreenDraw/releases/download/{tag}/{name}")
    except ValueError:
        return False


def download_url(source, tag, name):
    # GitCode's public canonical attachment API follows a verified CDN redirect.
    # The browser URL is checked separately against the exact owner/repo/tag/name.
    if source == "gitcode":
        return SOURCES[source][0] + f"/{urllib.parse.quote(tag, safe='')}/attach_files/{urllib.parse.quote(name, safe='')}/download"
    return f"https://github.com/wcr20140908/MyScreenDraw/releases/download/{tag}/{name}"


def canonical_manifest(manifest):
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def descriptor_name(tag):
    return f"MyScreenDraw-{tag}-update.json"


def verify_descriptor(raw, tag, asset_name):
    if len(raw) > MAX_DESCRIPTOR_BYTES:
        raise ValueError("descriptor_too_large")
    try:
        envelope = json.loads(raw.decode("utf-8"))
        if not isinstance(envelope, dict) or set(envelope) != {"manifest", "signature"}:
            raise ValueError()
        manifest = envelope["manifest"]
        if not isinstance(manifest, dict):
            raise ValueError()
        signature = base64.b64decode(envelope["signature"], validate=True)
        Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY)).verify(signature, canonical_manifest(manifest))
    except (ValueError, TypeError, KeyError, UnicodeError, InvalidSignature, RecursionError) as exc:
        raise ValueError("invalid_update_signature") from exc
    if (manifest.get("schema") != 1 or manifest.get("tag") != tag
            or manifest.get("version") != tag.removeprefix("v")
            or manifest.get("asset_name") != asset_name
            or type(manifest.get("size")) is not int
            or not 0 < manifest["size"] <= MAX_ARCHIVE_BYTES
            or not isinstance(manifest.get("sha256"), str)
            or not re.fullmatch("[0-9a-f]{64}", manifest["sha256"])
            or not isinstance(manifest.get("exe_sha256"), str)
            or not re.fullmatch("[0-9a-f]{64}", manifest["exe_sha256"])
            or not isinstance(manifest.get("commit"), str)
            or not re.fullmatch("[0-9a-f]{40}", manifest["commit"])):
        raise ValueError("invalid_update_descriptor")
    return manifest


def verify_downloaded_manifest(path, integrity):
    """Bind the archive's local installer manifest and executable to signed metadata."""
    import hashlib
    import zipfile
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("RELEASE-MANIFEST.json")
        if info.file_size > MAX_DESCRIPTOR_BYTES:
            raise ValueError("invalid_package_manifest")
        manifest = json.loads(archive.read(info).decode("utf-8-sig"))
        if (not isinstance(manifest, dict) or manifest.get("app_version") != integrity["version"]
                or manifest.get("sha256") != integrity["exe_sha256"]):
            raise ValueError("package_manifest_mismatch")
        digest = hashlib.sha256()
        with archive.open("MyScreenDraw.exe") as stream:
            for chunk in iter(lambda: stream.read(64 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != integrity["exe_sha256"]:
            raise ValueError("package_exe_mismatch")
