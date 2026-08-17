# Code signing notes

The published portable build is currently unsigned. Windows SmartScreen may therefore
show an unfamiliar-publisher warning even when the artifact was built from this source.
That warning is a distribution-trust issue, not evidence that the application uploads data
or contains an updater.

For a signed release, the maintainer should sign `MyScreenDraw.exe` and any required
native binaries with a certificate held by the release owner, verify the signature on a
clean Windows machine, and publish the certificate identity and SHA-256 hash with the
release manifest. The signing key must never be committed to the repository or placed in
`data/`, `build/`, or `dist/`.

Until signing is available, users can build from source with the pinned lock files and
verify the generated package using `build.ps1` and `RELEASE-MANIFEST.json`.
