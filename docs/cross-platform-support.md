# Windows and Linux support plan

Status: planned remediation, not a claim of platform parity. PR #1 was merged
with known review findings on 2026-09-23 at the owner's request.

## Support boundary

All user-facing validation, orchestration, artifact transfer, packaging and test
entry points must work on Windows and Linux with Python 3.12+. Browser presentation
must work on qualified browsers on both systems. Native ParaView client launching
must have platform-specific adapters behind the same documented lifecycle.
Linux Slurm/Apptainer workers remain Linux execution components; Windows callers
must be able to drive them without importing Linux-only runtime dependencies.
This does not require running Slurm or Apptainer natively on Windows.

## Ordered implementation

1. Separate portable Fluent index validation from allocated rendering. Move
   `resource`, ParaView and other worker-only imports behind the worker boundary.
   Moving only `fluent.py`'s `resource` import is insufficient: its imported
   `render.py` also imports `resource`. Add Windows/Linux import and CLI-check tests
   that run without ParaView, SSH or a scheduler.
2. Carry explicit representation metadata through render, manifest, packaging and
   captions. Fluent's planar domain/original cell mesh must not inherit the
   OpenFOAM-only "Physical boundaries; processor interfaces excluded" caption.
3. Add one portable verification entry point and a Windows/Linux CI matrix for
   Python tests, recipe validation and Node checks. Keep PowerShell as a convenience
   wrapper, not the only documented way to verify on Linux. Test subprocess quoting,
   paths with spaces, temporary directories, archive handling and failed commands.
4. Separate expert-session lifecycle logic from desktop launch adapters. Preserve
   Windows automation; add Linux launch/connect/stop with explicit executable
   configuration. Windows UI Automation must never be imported on Linux. Limit
   cleanup to owned clients, tunnels and allocations; provide check/dry-run modes.
5. Qualify media packaging/video and headed browser automation on both platforms.
   Configure browser/ffmpeg paths explicitly rather than assume Edge or Windows
   paths. Track GPU/browser versions and test multi-block controls independently
   of headless correctness tests. Keep real CFD qualification separate from CI.

## Acceptance and current evidence

The PR #1 Windows Python 3.12 review ran 53 tests: 52 passed and one Fluent test
module failed to import (`ModuleNotFoundError: resource`). Fluent local `check`
and `submit` share that failing import. Node media syntax/control checks passed;
they are not browser/GPU qualification. Linux test/render results in the PR are
author-reported and were not independently rerun during review.

Release parity requires passing both OS test jobs, successful local check and
packaging without HPC dependencies, and separately recorded platform launch and
browser qualification. Do not silently skip portability failures. Worker-only
integration tests may be explicitly gated on a supported allocated Linux runtime.

Owners are the existing media, infrastructure/paraview and viewer modules. Update
their READMEs and the architecture graph with each implemented boundary change.
