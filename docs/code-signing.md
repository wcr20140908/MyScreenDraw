# Code signing and update integrity

The 6.3.0 build does not apply Windows Authenticode signatures to MyScreenDraw.exe. Its package manifest continues to record signature: none. The Ed25519 signature on update metadata is a separate mechanism.

## What the update checks establish

- Both GitHub and GitCode publish identical accepted ZIP bytes, a ZIP SHA-256 file and MyScreenDraw-v6.3.0-update.json.
- The client verifies the descriptor with its embedded Ed25519 public key. The signed manifest binds version/tag, exact ZIP name, size and SHA-256, executable SHA-256 and the accepted source commit.
- Downloads are checked against the signed size and hash. Archive paths, member limits, required executable, package manifest and executable hash are checked locally before installation.
- A maintainer signs only a package that already has a valid build receipt. The private key stays outside tracked source and release output; account credentials are not embedded in the client.
- Legacy GitHub releases through 6.2.0 remain readable for version and release-note compatibility. New releases from 6.3.0 require signed descriptors.

A checksum alone can be replaced together with an asset by an attacker controlling its hosting account. The signed descriptor protects the new client from that replacement while the independent private signing key remains secure. It does not replace build review, make the executable Authenticode-signed or guarantee security in every environment. Existing older clients do not gain this verification until they are upgraded.

See the [release guide](releasing.md) for receipt verification and dual-platform publishing. Pinned dependencies do not promise identical binaries across different build machines.

## If Windows code signing is introduced

Sign the executable before generating its manifest and archive hashes. Verify the certificate and publisher identity on the resulting executable and keep that key separate from runtime data and published source. Metadata signing must still use the client-compatible update key. Publishing a new key without a compatible client migration would make updates fail verification.
