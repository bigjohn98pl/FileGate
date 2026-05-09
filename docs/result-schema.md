# Result Schema

## Purpose

Define the canonical JSON structure for FileGate case results.

## Version

- Schema version: `0.1`

## Structure

```json
{
  "schema_version": "0.1",
  "run_id": "2026-05-08T20-30-00Z-fedora-kde-electron",
  "platform": {
    "os": "linux",
    "distribution": "Fedora",
    "version": "43",
    "desktop_environment": "KDE Plasma",
    "session_type": "wayland",
    "sandbox": "flatpak"
  },
  "target": {
    "name": "electron",
    "version": "unknown",
    "sample_app": "samples/electron"
  },
  "case": {
    "id": "unicode_filename",
    "name": "Unicode filename",
    "automation_level": "semi_automatic"
  },
  "result": {
    "status": "pass",
    "duration_ms": 1842,
    "returned_resource_type": "path",
    "returned_value_example": "/home/user/FileGateTest/zażółć-gęślą-jaźń.txt",
    "can_read": true,
    "can_write": false,
    "error_code": null,
    "notes": []
  }
}
```

## Required Fields

- top-level: `schema_version`, `run_id`, `platform`, `target`, `case`, `result`
- `case`: `id`, `automation_level`
- `result`: `status`, `duration_ms`, `returned_resource_type`

## Enumerations

### `automation_level`

- `automatic`
- `semi_automatic`
- `manual`

### `status`

- `pass`
- `fail`
- `warn`
- `skip`
- `manual_required`
- `unsupported`
- `timeout`
- `blocked`
- `inconclusive`

### `returned_resource_type`

- `path`
- `uri`
- `handle`
- `unknown`

### `error_code` (if present)

- `USER_CANCELLED`
- `PERMISSION_DENIED`
- `RESOURCE_NOT_FOUND`
- `RESOURCE_UNAVAILABLE`
- `BACKEND_UNSUPPORTED`
- `PORTAL_UNAVAILABLE`
- `SANDBOX_DENIED`
- `PERSISTENCE_DENIED`
- `ACCESS_REVOKED`
- `UNKNOWN_ERROR`

## Validation Rules

1. `duration_ms` must be a non-negative integer.
2. `run_id` must be unique per execution run.
3. `status=pass` should not use non-null fatal error codes.
4. `manual` cases may legitimately return `manual_required`.
5. `notes` should remain structured and actionable.
