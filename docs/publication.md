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

Portable viewers and numerical export checks are implemented. A completed real-case
test qualifies selected scalar slices, cross-reader triangle/value correspondence,
and the new media route's physical-patch face-count gate. This is not universal
solver qualification or a scientific validity assessment. The older live image
path is a legacy prototype; new sharing uses ParaView rendering, not Matplotlib.

The headed browser runner has passed syntax/dry-run checks, not browser execution.
No GPU performance claim, real CFD data or private benchmark report is included.

Selected source-side slices, content-addressed transfer planning and cache reuse
are implemented. Native scalar auditing records reader precision explicitly;
Float64 export containers do not imply a Float64 reader. See `minimal-assets.md`
for the reproducible workflow and current frozen-frame delivery boundary.

The media route has rendered geometry, boundary mesh and three scalar fields at
two explicit real timesteps; image-only fetch, offline packaging and MP4 encoding
passed. A native desktop launched by the expert launcher connected to an allocated
server, verified by a remote-connection receipt. Skills pass structural validation.
No connected browser was available for media HTML interaction checks; those and
browser/GPU performance remain unqualified. Timed jobs used CPU software rendering.
Generated artifacts and case-specific measurements remain private local state.
