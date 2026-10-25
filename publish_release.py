# SPDX-License-Identifier: GPL-3.0-or-later
"""Publish identical accepted artifacts to GitHub and GitCode, then verify publicly.

Credentials come only from GITHUB_TOKEN / GITCODE_TOKEN environment variables.
A partial failure leaves drafts/prereleases for an explicit --resume retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import release_artifact as artifact
from update_sources import SOURCES, descriptor_name, download_url, verify_descriptor
from version import VERSION


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, values, newurl):
        target = require_https(newurl)
        origin = require_https(req.full_url)
        redirected = super().redirect_request(req, fp, code, msg, values, newurl)
        if redirected is not None and (origin.hostname, origin.port or 443) != (target.hostname, target.port or 443):
            redirected.remove_header("Authorization")
        return redirected


RELEASE_HTTP = urllib.request.build_opener(ReleaseRedirect())


class PublicationError(RuntimeError):
    pass


def require_https(url):
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()
        parsed.port  # Reject a malformed port before any network request.
    except ValueError:
        raise PublicationError("HTTPS URL required") from None
    return parsed


def release_state(source, release):
    """Read each provider's authoritative state, rejecting incomplete metadata."""
    if not isinstance(release, dict):
        raise PublicationError(f"{source} malformed release state")
    if source == "github":
        if type(release.get("draft")) is not bool or type(release.get("prerelease")) is not bool:
            raise PublicationError("github missing boolean release state")
        if release["prerelease"]:
            raise PublicationError("github stable release cannot be a prerelease")
        return "staged" if release["draft"] else "public"
    if source == "gitcode":
        state = release.get("release_status")
        if state in ("pre", "latest"):
            return "staged" if state == "pre" else "public"
    raise PublicationError(f"{source} unknown release state")


def require_release_state(source, release, expected):
    if release_state(source, release) != expected:
        raise PublicationError(f"{source} expected {expected} release")


def verify_frozen_file(path, expected):
    size, digest = expected
    if path.stat().st_size != size or artifact.sha256(path) != digest:
        raise PublicationError(f"Accepted attachment changed: {path.name}")


def verify_manifest_binding(raw, tag, path, accepted, commit):
    manifest = verify_descriptor(raw, tag, path.name)
    if (manifest["commit"] != commit or manifest["sha256"] != accepted["zip_sha256"]
            or manifest["exe_sha256"] != accepted["exe_sha256"] or manifest["size"] != path.stat().st_size):
        raise PublicationError("Descriptor differs from accepted release")
    return manifest


def request(url, *, method="GET", data=None, headers=None, limit=2*1024*1024):
    require_https(url)
    try:
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        with RELEASE_HTTP.open(req, timeout=120) as response:
            require_https(response.geturl())
            raw = response.read(limit+1)
            if len(raw)>limit:
                raise PublicationError("API response too large")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raise PublicationError(f"{method} {urllib.parse.urlsplit(url).hostname}: HTTP {exc.code}") from None
    except urllib.error.URLError:
        raise PublicationError(f"{method} {urllib.parse.urlsplit(url).hostname}: network failure") from None


def headers(source):
    token = os.environ.get("GITHUB_TOKEN" if source=="github" else "GITCODE_TOKEN")
    if not token:
        raise PublicationError(f"Missing release credential for {source}")
    return {"Authorization": "Bearer "+token, "User-Agent": "MyScreenDraw-release", "Accept": "application/json"}


def api(source, suffix="", *, method="GET", body=None):
    values=headers(source)
    if body is not None:values["Content-Type"]="application/json"
    return request(SOURCES[source][0]+suffix, method=method,
        data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None, headers=values)


def check_remote(source, commit, tag):
    host=SOURCES[source][1]
    url=f"https://{host}/wcr20140908/MyScreenDraw.git"
    raw=subprocess.check_output(["git","ls-remote",url,"refs/heads/main","refs/tags/"+tag],text=True,timeout=60)
    refs={line.split()[1]:line.split()[0] for line in raw.splitlines()}
    if refs.get("refs/heads/main")!=commit or refs.get("refs/tags/"+tag)!=commit:
        raise PublicationError(f"{source} main and release tag must match accepted commit")


def prepare(source, commit, tag, notes, resume):
    try:existing=api(source,"/tags/"+tag)
    except PublicationError as exc:
        if "HTTP 404" not in str(exc):raise
        existing=None
    if existing:
        if not resume:raise PublicationError(f"{source} release exists; refusing overwrite")
        if (existing.get("tag_name")!=tag or existing.get("body")!=notes
                or existing.get("name")!=f"MyScreenDraw {tag}"):
            raise PublicationError(f"{source} existing release differs from this publication")
        release_state(source, existing)
        return existing
    body=dict(tag_name=tag, target_commitish=commit, name=f"MyScreenDraw {tag}",body=notes)
    if source=="github":body.update(draft=True,prerelease=False)
    else:body["release_status"]="pre"
    created=api(source,method="POST",body=body)
    require_release_state(source, created, "staged")
    return created


def attachments(source, release):
    assets=release.get("assets")
    if source=="github":assets=assets.get("uploaded",[]) if isinstance(assets,dict) else assets
    if not isinstance(assets,list):raise PublicationError(f"{source} malformed assets")
    return [a for a in assets if isinstance(a,dict) and (source!="gitcode" or a.get("type")=="attach")]


def upload(source, release, tag, path, *, expected=None):
    if expected is not None:
        verify_frozen_file(path, expected)
    size = expected[0] if expected is not None else path.stat().st_size
    found=[a for a in attachments(source,release) if a.get("name")==path.name]
    if found:
        if len(found)!=1 or found[0].get("size")!=size:
            raise PublicationError(f"{source} existing attachment mismatch: {path.name}")
        return  # Full byte verification below determines whether resume is safe.
    if source=="github":
        url=release["upload_url"].split("{")[0]+"?name="+urllib.parse.quote(path.name,safe="")
        values=headers(source)
        method="POST"
    else:
        signed=api(source,"/"+tag+"/upload_url?file_name="+urllib.parse.quote(path.name,safe=""))
        url=signed["url"]
        if urllib.parse.urlsplit(url).hostname!="file.gitcode.com":
            raise PublicationError("Unexpected GitCode upload host")
        values=dict(signed["headers"])
        method="PUT"
    values["Content-Length"] = str(size)
    values.setdefault("Content-Type", "application/zip" if path.suffix==".zip" else "application/json" if path.suffix==".json" else "text/plain")
    with path.open("rb") as stream:request(url,method=method,data=stream,headers=values)
    if expected is not None:
        verify_frozen_file(path, expected)
    print(f"{source}: uploaded {path.name}",flush=True)


def verify_attachment(source, release, tag, path, *, public=False, expected=None):
    expected_size, expected_hash = expected if expected is not None else (path.stat().st_size, artifact.sha256(path))
    items=[a for a in attachments(source,release) if a.get("name")==path.name]
    if len(items)!=1 or items[0].get("size")!=expected_size:
        raise PublicationError(f"{source} attachment size mismatch: {path.name}")
    values={"User-Agent":"MyScreenDraw-release-verification"}
    if source=="github" and not public:
        url=items[0]["url"]
        values=headers(source);values["Accept"]="application/octet-stream"
    else:url=download_url(source,tag,path.name)
    require_https(url)
    try:
        with RELEASE_HTTP.open(urllib.request.Request(url,headers=values),timeout=120) as response:
            require_https(response.geturl())
            digest=hashlib.sha256();size=0
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>expected_size:raise PublicationError("Attachment larger than accepted bytes")
                digest.update(chunk)
    except (urllib.error.HTTPError, urllib.error.URLError):
        raise PublicationError(f"{source} attachment download failed: {path.name}") from None
    if size!=expected_size or digest.hexdigest()!=expected_hash:
        raise PublicationError(f"{source} attachment bytes mismatch: {path.name}")
    print(f"{source}: {'public ' if public else ''}verified {path.name} SHA256={digest.hexdigest()}",flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit",required=True)
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--verify-public",action="store_true")
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    tag="v"+VERSION; path=root/artifact.artifact_name(VERSION)
    checksum=Path(str(path)+".sha256"); receipt=root/"build/release-receipts"/(path.name+".json")
    accepted=artifact.verify_release(path,VERSION,root,checksum,receipt,commit=args.commit)
    descriptor=artifact.safe_path(root/descriptor_name(tag), root)
    descriptor_bytes = descriptor.read_bytes()
    manifest = verify_manifest_binding(descriptor_bytes, tag, path, accepted, args.commit)
    checksum_bytes = checksum.read_bytes()
    checksum_text = checksum_bytes.decode("ascii").replace("\r\n", "\n").replace("\r", "\n")
    if checksum_text != f"{accepted['zip_sha256']}  {path.name}\n":
        raise PublicationError("Checksum differs from accepted release")
    files=[path,checksum,descriptor]
    frozen = {
        path: (manifest["size"], accepted["zip_sha256"]),
        checksum: (len(checksum_bytes), hashlib.sha256(checksum_bytes).hexdigest()),
        descriptor: (len(descriptor_bytes), hashlib.sha256(descriptor_bytes).hexdigest()),
    }
    for file in files:verify_frozen_file(file, frozen[file])
    notes=(root/f"release-notes-{tag}.md").read_text("utf-8")
    for source in SOURCES:check_remote(source,args.commit,tag)
    if args.verify_public:
        for source in SOURCES:
            release=request(SOURCES[source][0]+"/tags/"+tag)
            require_release_state(source, release, "public")
            for file in files:verify_attachment(source,release,tag,file,public=True,expected=frozen[file])
        return
    releases={source:prepare(source,args.commit,tag,notes,args.resume) for source in SOURCES}
    staged = {source for source, release in releases.items() if release_state(source, release) == "staged"}
    # Already-public resume is verification only; check every public origin before any upload.
    for source, release in releases.items():
        if source not in staged:
            for file in files:verify_attachment(source, release, tag, file, public=True, expected=frozen[file])
    for source,release in releases.items():
        if source not in staged:
            continue
        for file in files:upload(source,release,tag,file,expected=frozen[file])
        releases[source]=api(source,"/tags/"+tag)
        require_release_state(source, releases[source], "staged")
        for file in files:verify_attachment(source,releases[source],tag,file,expected=frozen[file])
    accepted = artifact.verify_release(path,VERSION,root,checksum,receipt,commit=args.commit)
    for file in files:verify_frozen_file(file, frozen[file])
    verify_manifest_binding(descriptor.read_bytes(), tag, path, accepted, args.commit)
    for source,release in releases.items():
        if source not in staged:
            continue
        require_release_state(source, api(source, "/tags/"+tag), "staged")
        for file in files:verify_frozen_file(file, frozen[file])
        if source=="github":
            published=api(source,"/"+str(release["id"]),method="PATCH",body=dict(draft=False,prerelease=False))
        else:
            published=api(source,"/"+tag,method="PATCH",body=dict(name=f"MyScreenDraw {tag}",body=notes,release_status="latest"))
        require_release_state(source, published, "public")
        print(f"{source}: published {tag}",flush=True)
    for source in SOURCES:
        release=request(SOURCES[source][0]+"/tags/"+tag)
        require_release_state(source, release, "public")
        for file in files:verify_attachment(source,release,tag,file,public=True,expected=frozen[file])


if __name__=="__main__":
    try:main()
    except Exception as exc:
        # Error bodies and upload URL queries may contain presigned credentials.
        print(f"Release stopped: {exc if isinstance(exc,PublicationError) else type(exc).__name__}",flush=True)
        raise SystemExit(1)
