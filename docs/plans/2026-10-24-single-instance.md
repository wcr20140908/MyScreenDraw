# Single-instance startup implementation plan

**Goal:** Keep one ordinary MyScreenDraw process per Windows login session and make later launches reveal the existing interface.

**Architecture:** Use one stable Qt local-server endpoint shared by source and frozen builds. The first ordinary process owns the endpoint; later processes send an activation request and exit before constructing application windows. Teaching practice and bounded smoke modes remain independent. In-app restart passes the old PID so the replacement waits for the old owner to exit before claiming the endpoint and restoring the temporary document snapshot.

**Tech stack:** Python, PyQt6 `QLocalServer` / `QLocalSocket`, pytest.

## Tasks

1. Add failing subprocess tests for endpoint ownership, activation delivery, stale endpoint recovery and old-process replacement waiting.
2. Add a small `single_instance.py` module with a stable per-session endpoint, primary ownership, activation messages and bounded process-exit waiting.
3. Wire ordinary startup before window construction; connect activation to lifecycle restoration and foreground raising after the windows exist.
4. Pass `--replace-instance <pid>` from the existing restart path so restart does not get mistaken for a duplicate launch.
5. Run single-instance, lifecycle, teaching-process and startup-preference regressions. Existing already-built EXEs remain unchanged until a future package is built.
