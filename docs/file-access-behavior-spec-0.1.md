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

## Compatibility Matrix Baseline (Phase 4 First Iteration)

The first compatibility-matrix layer uses a deterministic **summary baseline** rather than a weighted conformance score.

### Aggregation Units

- Matrix input is a set of completed run directories containing `run-summary.json`.
- Each matrix cell represents one case aggregated across one grouping dimension set.
- The initial implementation supports grouping by:
  - target + environment,
  - target only,
  - environment only.

### Aggregated Cell Status Rule

- If every observation contributing to a cell has the same `result.status`, the cell keeps that status.
- If contributing observations disagree, the cell status becomes derived status `mixed`.
- Resource-type differences are preserved as notes/metadata even when statuses agree.

### Summary Baseline Buckets

The first publication-oriented baseline uses explicit buckets instead of a numeric score:

- `compatible`: aggregated status `pass`
- `caution`: aggregated status `warn`
- `problematic`: aggregated status `fail`, `timeout`, or `blocked`
- `unavailable`: aggregated status `skip`, `unsupported`, `manual_required`, or `inconclusive`
- `mixed`: derived cell status `mixed`
- `missing`: case absent from a matrix group

### Why No Weighted Score Yet

Weighted scoring remains intentionally open because the project does not yet have enough cross-platform evidence to justify stable case weights or target-category-specific scoring rules.

Until that policy matures, FileGate should:

- publish explicit bucket counts,
- preserve per-run observations for reproducibility,
- avoid implying stronger conformance precision than the evidence supports.

### Data Contract for Future Targets

Future framework/platform tasks should continue emitting normalized per-case results using the existing result schema, especially:

- complete environment metadata,
- stable `target.name` and `target.version`,
- canonical `case.id`,
- normalized `result.status`,
- `returned_resource_type`,
- structured notes for known differences and environment-specific caveats.

That allows additional frameworks and platforms to feed the matrix layer without introducing special aggregation formats.
