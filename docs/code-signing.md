# Code signing and release integrity

The **v6.0.0** release is in preparation and has not been packaged or published.
The current build process does not sign binaries; published beta.8 builds are
unsigned. Windows SmartScreen or security
software may warn about an unfamiliar publisher. This alone proves neither
malware nor safety; check the source and investigate warnings rather than
instructing users to disable protection.

## What the checks establish when run

- The release `.zip.sha256` checks the ZIP against the published checksum.
- `RELEASE-MANIFEST.json` records the EXE hash and currently says `signature: none`.
- The updater validates archive structure, paths, and size limits. Those checks
  are not Authenticode verification or an independent proof of publisher identity.
- An attacker controlling both an asset and its checksum could replace both.
  HTTPS and checksums do not remove the trust placed in the release account.

The planned 6.0.0 manifest and checksums do not exist as verified release evidence
yet. See the [validation record](release-validation-6.0.0.md) for pending checks
and the [release guide](releasing.md) for packaging and verification steps. Pinned
application dependencies help rebuild the project, but do not promise byte-for-byte
identical binaries across machines or toolchains.

## If signed builds are introduced

Use a certificate controlled by the release owner. Keep signing keys outside the
repository, runtime data, and build output. Sign the executable before generating
its manifest and ZIP hashes; otherwise the recorded hashes will be stale.

The current build script does not perform signing and writes `signature: none`.
Add and verify a signing step before describing a release as signed. Validate the
signature and publisher identity on a clean Windows machine, then publish the
signing identity and final artifact checksums. Review any native-binary signing
requirements without overwriting third-party signatures indiscriminately.

Signing improves publisher identification; it does not guarantee that reputation
warnings disappear or that the software is free from vulnerabilities.
