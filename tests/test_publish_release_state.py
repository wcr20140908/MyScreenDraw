# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline publication gates using synthetic artifacts and an in-memory release API."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import publish_release as publisher
import update_sources


class Response(io.BytesIO):
    def __init__(self, value, url):
        super().__init__(json.dumps(value).encode() if isinstance(value, (dict, list)) else value)
        self.url = url

    def geturl(self):
        return self.url


class ReleaseService:
    """Only HTTPS API/storage boundaries are replaced; publication logic stays real."""
    def __init__(self, files, tag, notes):
        self.files = files
        self.tag = tag
        self.notes = notes
        self.releases = {source: None for source in publisher.SOURCES}
        self.contents = {source: {} for source in publisher.SOURCES}
        self.mutations = []
        self.created_overrides = {}
        self.patch_overrides = {}
        self.public_overrides = {}
        self.on_upload = None

    def metadata(self, source, public=False):
        release = copy.deepcopy(self.releases[source])
        if release is not None:
            release['assets'] = [dict(name=name, size=len(raw), type='attach',
                url=f'https://api.github.com/assets/{name}')
                for name, raw in self.contents[source].items()]
            if public:
                release.update(self.public_overrides.get(source, {}))
        return release

    def seed(self, source, public=False):
        self.releases[source] = dict(id=1, tag_name=self.tag,
            name=f'MyScreenDraw {self.tag}', body=self.notes,
            upload_url='https://uploads.github.com/releases/1/assets{?name}')
        if source == 'github':
            self.releases[source].update(draft=not public, prerelease=False)
        else:
            self.releases[source].update(release_status='latest' if public else 'pre', prerelease=not public)
        self.contents[source] = {path.name: path.read_bytes() for path in self.files}

    def open(self, request, timeout=120):
        parsed = urllib.parse.urlsplit(request.full_url)
        method = request.get_method()
        source = 'gitcode' if parsed.hostname in {'api.gitcode.com', 'file.gitcode.com'} else 'github'
        if method in {'POST', 'PUT', 'PATCH'}:
            self.mutations.append((source, method, parsed.path))
        if parsed.hostname in {'uploads.github.com', 'file.gitcode.com'}:
            name = urllib.parse.parse_qs(parsed.query)['name'][0]
            self.contents[source][name] = request.data.read()
            if self.on_upload:
                self.on_upload(source, name)
            return Response(b'', request.full_url)
        if parsed.path.startswith('/assets/'):
            name = parsed.path.rsplit('/', 1)[1]
            return Response(self.contents[source][name], request.full_url)
        if '/attach_files/' in parsed.path or '/releases/download/' in parsed.path:
            name = (parsed.path.split('/attach_files/', 1)[1].split('/download', 1)[0]
                if '/attach_files/' in parsed.path else parsed.path.rsplit('/', 1)[1])
            return Response(self.contents[source][urllib.parse.unquote(name)], request.full_url)
        if parsed.path.endswith('/upload_url'):
            name = urllib.parse.parse_qs(parsed.query)['file_name'][0]
            return Response(dict(url='https://file.gitcode.com/upload?name=' + urllib.parse.quote(name),
                headers={'Content-Type': 'application/octet-stream', 'x-obs-acl': 'public-read'}), request.full_url)
        if parsed.path.endswith('/tags/' + self.tag):
            value = self.metadata(source, public=not request.has_header('Authorization'))
            if value is None:
                raise urllib.error.HTTPError(request.full_url, 404, 'missing', {}, None)
            return Response(value, request.full_url)
        if method == 'POST' and parsed.path.endswith('/releases'):
            self.seed(source)
            self.contents[source] = {}
            self.releases[source].update(self.created_overrides.get(source, {}))
            return Response(self.metadata(source), request.full_url)
        if method == 'PATCH':
            self.releases[source].update(json.loads(request.data))
            if source == 'gitcode':
                self.releases[source]['prerelease'] = False
            self.releases[source].update(self.patch_overrides.get(source, {}))
            return Response(self.metadata(source), request.full_url)
        raise AssertionError(f'Unexpected synthetic request: {method} {request.full_url}')


@pytest.fixture
def publication(monkeypatch, tmp_path):
    tag = 'v' + publisher.VERSION
    commit = 'c' * 40
    archive = tmp_path / publisher.artifact.artifact_name(publisher.VERSION)
    archive.write_bytes(b'synthetic accepted portable bytes')
    checksum = Path(str(archive) + '.sha256')
    checksum.write_bytes(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n'.encode('ascii'))
    descriptor = tmp_path / publisher.descriptor_name(tag)
    key = Ed25519PrivateKey.generate()  # Ephemeral synthetic trust key, never persisted.
    monkeypatch.setattr(update_sources, 'PUBLIC_KEY', base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    accepted = dict(zip_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), exe_sha256='a' * 64)
    manifest = dict(schema=1, version=publisher.VERSION, tag=tag, asset_name=archive.name,
        commit=commit, size=archive.stat().st_size, sha256=accepted['zip_sha256'], exe_sha256=accepted['exe_sha256'])
    descriptor.write_text(json.dumps(dict(manifest=manifest, signature=base64.b64encode(
        key.sign(update_sources.canonical_manifest(manifest))).decode())), encoding='utf-8')
    notes = 'Synthetic accepted release notes'
    (tmp_path / f'release-notes-{tag}.md').write_text(notes, encoding='utf-8')
    service = ReleaseService([archive, checksum, descriptor], tag, notes)
    monkeypatch.setattr(publisher, '__file__', str(tmp_path / 'publish_release.py'))
    # Accepted build/repository evidence has its own complete synthetic regression suite.
    monkeypatch.setattr(publisher.artifact, 'verify_release', lambda *a, **k: accepted)
    monkeypatch.setattr(publisher.subprocess, 'check_output', lambda *a, **k:
        f'{commit}\trefs/heads/main\n{commit}\trefs/tags/{tag}\n')
    monkeypatch.setattr(publisher, 'headers', lambda source: {'Authorization': 'Bearer SYNTHETIC'})
    monkeypatch.setattr(publisher.RELEASE_HTTP, 'open', service.open)
    def run(*options):
        monkeypatch.setattr(sys, 'argv', ['publish_release.py', '--commit', commit, *options])
        return publisher.main()
    service.run = run
    return service


def test_verify_public_rejects_gitcode_pre_even_when_prerelease_is_false(publication):
    for source in publisher.SOURCES:
        publication.seed(source, public=True)
    publication.releases['gitcode'].update(release_status='pre', prerelease=False)
    with pytest.raises(publisher.PublicationError):
        publication.run('--verify-public')
    assert not publication.mutations


@pytest.mark.parametrize('state', [None, 'unknown'])
def test_resume_rejects_unknown_gitcode_state_without_writes(publication, state):
    for source in publisher.SOURCES:
        publication.seed(source)
    publication.releases['gitcode']['release_status'] = state
    with pytest.raises(publisher.PublicationError):
        publication.run('--resume')
    assert not publication.mutations


@pytest.mark.parametrize('field,value', [('draft', None), ('draft', 0), ('draft', 'false'),
    ('prerelease', None), ('prerelease', 0), ('prerelease', 'false')])
def test_resume_rejects_non_boolean_github_state(publication, field, value):
    for source in publisher.SOURCES:
        publication.seed(source)
    publication.releases['github'][field] = value
    with pytest.raises(publisher.PublicationError):
        publication.run('--resume')
    assert not publication.mutations


def test_gitcode_creation_requires_pre_status(publication):
    publication.created_overrides['gitcode'] = dict(release_status='latest', prerelease=True)
    with pytest.raises(publisher.PublicationError):
        publication.run()
    assert not any(method == 'PUT' or host == 'github' and 'assets' in path
        for host, method, path in publication.mutations)


def test_gitcode_patch_must_confirm_latest(publication):
    publication.patch_overrides['gitcode'] = dict(release_status='pre', prerelease=False)
    with pytest.raises(publisher.PublicationError):
        publication.run()


def test_final_anonymous_metadata_must_confirm_latest(publication):
    publication.public_overrides['gitcode'] = dict(release_status='pre', prerelease=False)
    with pytest.raises(publisher.PublicationError):
        publication.run()


def test_both_platforms_publish_and_verify_accepted_bytes(publication):
    publication.run()
    assert publication.releases['github']['draft'] is False
    assert publication.releases['gitcode']['release_status'] == 'latest'
    assert publication.contents['github'] == publication.contents['gitcode']


def test_public_resume_is_read_only(publication):
    for source in publisher.SOURCES:
        publication.seed(source, public=True)
    publication.run('--resume')
    assert not publication.mutations


@pytest.mark.parametrize('source', ['github', 'gitcode'])
@pytest.mark.parametrize('file_index', [0, 1, 2])
def test_public_resume_missing_attachment_never_uploads(publication, source, file_index):
    for origin in publisher.SOURCES:
        publication.seed(origin, public=True)
    del publication.contents[source][publication.files[file_index].name]
    with pytest.raises(publisher.PublicationError):
        publication.run('--resume')
    assert not publication.mutations


def test_mixed_resume_publishes_only_the_staged_platform(publication):
    publication.seed('github', public=True)
    publication.seed('gitcode')
    publication.run('--resume')
    assert all(source == 'gitcode' for source, method, path in publication.mutations)
    assert publication.releases['gitcode']['release_status'] == 'latest'


def test_staged_resume_uploads_missing_accepted_attachment(publication):
    for source in publisher.SOURCES:
        publication.seed(source)
    del publication.contents['gitcode'][publication.files[2].name]
    publication.run('--resume')
    assert publication.contents['github'] == publication.contents['gitcode']


def test_resume_never_replaces_a_same_size_different_attachment(publication):
    for source in publisher.SOURCES:
        publication.seed(source)
    name = publication.files[0].name
    publication.contents['gitcode'][name] = b'x' * len(publication.contents['gitcode'][name])
    with pytest.raises(publisher.PublicationError, match='bytes mismatch'):
        publication.run('--resume')
    assert not publication.mutations


def test_staged_release_changed_to_public_during_upload_is_rejected(publication):
    def change_state(source, name):
        if source == 'gitcode' and name == publication.files[2].name:
            publication.releases[source].update(release_status='latest', prerelease=False)
    publication.on_upload = change_state
    with pytest.raises(publisher.PublicationError):
        publication.run()
    assert not any(method == 'PATCH' for source, method, path in publication.mutations)


@pytest.mark.parametrize('url', ['http://api.github.com/synthetic', 'http://file.gitcode.com/synthetic',
    'ftp://file.gitcode.com/synthetic'])
def test_initial_request_rejects_https_downgrade_before_sending(monkeypatch, url):
    opened = []
    monkeypatch.setattr(publisher.RELEASE_HTTP, 'open', lambda *a, **k:
        opened.append(a) or Response({}, 'https://api.github.com/synthetic'))
    with pytest.raises(publisher.PublicationError):
        publisher.request(url, method='PUT', data=b'accepted', headers={'Authorization': 'Bearer SYNTHETIC'})
    assert not opened


@pytest.mark.parametrize('target', ['http://api.github.com/synthetic', 'http://untrusted.example/synthetic'])
def test_redirect_rejects_https_downgrade(target):
    request = publisher.urllib.request.Request('https://api.github.com/synthetic',
        headers={'Authorization': 'Bearer SYNTHETIC'})
    with pytest.raises(publisher.PublicationError):
        publisher.ReleaseRedirect().redirect_request(request, None, 302, 'Found', {}, target)


@pytest.mark.parametrize('target', ['https://other.example/synthetic', 'https://api.github.com:444/synthetic'])
def test_cross_origin_redirect_removes_authorization(target):
    request = publisher.urllib.request.Request('https://api.github.com/synthetic',
        headers={'Authorization': 'Bearer SYNTHETIC'})
    redirected = publisher.ReleaseRedirect().redirect_request(request, None, 302, 'Found', {}, target)
    assert not redirected.has_header('Authorization')


def test_same_origin_redirect_preserves_authorization():
    request = publisher.urllib.request.Request('https://api.github.com/synthetic',
        headers={'Authorization': 'Bearer SYNTHETIC'})
    redirected = publisher.ReleaseRedirect().redirect_request(request, None, 302, 'Found', {},
        'https://api.github.com:443/other')
    assert redirected.has_header('Authorization')


def test_private_attachment_rejects_insecure_api_url_before_download(publication, monkeypatch):
    publication.seed('github')
    release = publication.metadata('github')
    release['assets'][0]['url'] = 'http://api.github.com/assets/' + publication.files[0].name
    opened = []
    monkeypatch.setattr(publisher.RELEASE_HTTP, 'open', lambda *a, **k:
        opened.append(a) or Response(publication.files[0].read_bytes(), 'https://api.github.com/synthetic'))
    with pytest.raises(publisher.PublicationError):
        publisher.verify_attachment('github', release, publication.tag, publication.files[0])
    assert not opened


def test_descriptor_changed_during_upload_never_becomes_public(publication):
    def tamper(source, name):
        if source == 'github' and name == publication.files[0].name:
            path = publication.files[2]
            value = json.loads(path.read_text('utf-8'))
            value['manifest']['commit'] = 'd' * 40
            path.write_text(json.dumps(value), encoding='utf-8')
    publication.on_upload = tamper
    with pytest.raises(publisher.PublicationError):
        publication.run()
    assert not any(method == 'PATCH' for source, method, path in publication.mutations)


def test_descriptor_changed_at_final_receipt_gate_never_becomes_public(publication, monkeypatch):
    accepted = publisher.artifact.verify_release(None)
    checks = 0
    def receipt(*args, **kwargs):
        nonlocal checks
        checks += 1
        if checks == 2:
            path = publication.files[2]
            value = json.loads(path.read_text('utf-8'))
            value['manifest']['exe_sha256'] = 'b' * 64
            path.write_text(json.dumps(value), encoding='utf-8')
        return accepted
    monkeypatch.setattr(publisher.artifact, 'verify_release', receipt)
    with pytest.raises(publisher.PublicationError):
        publication.run()
    assert not any(method == 'PATCH' for source, method, path in publication.mutations)


@pytest.mark.parametrize('file_index', [0, 1, 2])
def test_same_size_input_change_during_upload_stops_before_publication(publication, file_index):
    path = publication.files[file_index]
    def tamper(source, name):
        if source == 'github' and name == publication.files[0].name:
            path.write_bytes(b'x' * path.stat().st_size)
    publication.on_upload = tamper
    with pytest.raises(publisher.PublicationError):
        publication.run()
    assert not any(method == 'PATCH' for source, method, path in publication.mutations)
    if file_index != 0:
        assert path.name not in publication.contents['github']


def test_freezes_the_actual_accepted_checksum_bytes(publication):
    checksum = publication.files[1]
    checksum.write_bytes(checksum.read_bytes().replace(b'\n', b'\r\n'))
    publication.run()
    assert publication.contents['github'][checksum.name] == checksum.read_bytes()
    assert publication.contents['gitcode'][checksum.name] == checksum.read_bytes()


def test_gitcode_latest_state_is_authoritative_over_prerelease_flag(publication):
    for source in publisher.SOURCES:
        publication.seed(source, public=True)
    publication.releases['gitcode']['prerelease'] = True
    publication.run('--verify-public')
    assert not publication.mutations


def test_gitcode_pre_creation_uses_status_even_without_prerelease_flag(publication):
    publication.created_overrides['gitcode'] = dict(prerelease=None)
    publication.run()
    assert publication.releases['gitcode']['release_status'] == 'latest'
