# Known Edge Cases

## Purpose

Track high-risk scenarios that frequently cause cross-platform inconsistencies in user-mediated file access.

## Path and Encoding

- Unicode normalization differences
- Non-ASCII locale interaction
- Spaces and mixed separators in paths
- Extremely long filenames/paths
- Relative vs absolute path mismatch

## Permissions and Ownership

- Read-only files selected for write
- Permission denied on parent directory
- ACL-based access differences
- Runtime permission revocation

## Dialog Behavior

- Cancel semantics and error mapping
- Extension auto-append differences on save
- Filter behavior differences across toolkits
- Dialog timeout and stale window state

## Sandbox and Portal

- XDG portal returns URI while app expects path
- Access available during session but not after restart
- Document portal persistence mismatch
- Flatpak/Snap home access without grant

## Filesystem Topology

- Symlink target resolution differences
- Broken symlink handling
- Network share latency/availability race
- External drive mount lifecycle race

## Cloud-Backed Files

- Placeholder file selected but content unavailable
- Offline cloud file selected without local materialization
- Deferred download on first read
- Conflict file naming and versioning anomalies

## Guidance

Each edge case should map to one or more explicit test cases and produce structured evidence in run output.
