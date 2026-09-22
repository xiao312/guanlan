# Public repository boundary

Publish implementation, tests, synthetic examples and generic configuration only.
Native CFD cases, prepared arrays and HTML snapshots may contain confidential
geometry, field values and server paths; do not commit them.

Machine configuration belongs in ignored `*.local.*` files. Credentials remain
outside the repository. Generated state, caches, recoverable trash, session-derived
research and case-specific qualification records are excluded by `.gitignore`.

Use Conventional Commits, for example `feat(viewer): add mesh inspection` or
`fix(portable): restore automatic scalar range`. Review the complete staged diff
and file list before committing; ignore rules are not a secret scanner.

## Qualification limits

Portable viewers and numerical export checks are implemented. Browser performance
and source-to-extract correctness still require qualification with your own data.
A diagnostic extraction retained processor interfaces; physical-patch selection
and a face-count gate were added but have not passed real-case qualification yet.
The older image path is also a prototype, not a validated engineering tool.

The headed browser runner has passed syntax/dry-run checks, not browser execution.
No GPU performance claim, real CFD data or private benchmark report is included.
