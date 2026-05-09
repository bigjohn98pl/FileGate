# File Access Behavior Spec 0.1

## Status

- Version: `0.1`
- Maturity: Draft (MVP baseline)
- Scope: Linux-first conformance baseline with cross-platform extension path

## Purpose

Define a shared behavior model for user-mediated file access so test outcomes are comparable across targets and environments.

## Resource Semantics

FileGate recognizes four resource-return categories:

- `path`: filesystem path string
- `uri`: URI string (for example `file://` or portal URI)
- `handle`: framework/platform handle object representation
- `unknown`: unclassified return type

Targets must record the observed `returned_resource_type` and an example value.

## Case Lifecycle Semantics

Each case should capture:

1. preconditions,
2. user/system action,
3. returned value/error,
4. access capability (`can_read`, `can_write`),
5. persistence expectations where relevant.

## Automation Levels

- `automatic`: no user interaction required
- `semi_automatic`: explicit user action in dialog required
- `manual`: human-driven verification with checklist

Automation level is mandatory for each case definition.

## Result Status Vocabulary

- `pass`
- `fail`
- `warn`
- `skip`
- `manual_required`
- `unsupported`
- `timeout`
- `blocked`
- `inconclusive`

## Error Code Vocabulary (Initial)

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

## Behavioral Rules (MVP)

1. **Explicitness over inference**: record observed behavior even if target abstraction hides internals.
2. **Cancel is not fail by default**: when cancel is expected, use semantic mapping (`pass` + `USER_CANCELLED` or policy-defined equivalent).
3. **Environment-coupled interpretation**: evaluate results with full environment metadata.
4. **Known differences are first-class**: represent valid platform differences as `warn`/notes where appropriate, not always `fail`.
5. **Persistence is case-specific**: only evaluate persistence in dedicated persistence cases.

## Open Areas for Next Versions

- URI/path normalization rules by platform
- weighted scoring policy for compatibility matrix
- stricter conformance profiles by target category
