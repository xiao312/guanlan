# Guanlan · 观澜

Two supported workflow entry points are [agent skills](docs/agent-workflows.md):
native ParaView expert sessions and [ParaView-rendered media sharing](src/guanlan/media/README.md).
Media presets produce images/time sequences near the case, then assemble offline
blocks locally without transferring a CFD dataset or keeping an allocation alive.

For open-ended CFD exploration, see the [ParaView expert path](docs/paraview-expert.md).
Prepared views complement that allocated processing session; they do not claim
to replace ParaView or universally reduce bandwidth.

Set up the view once. See it update. Share it immediately.

Guanlan is an experimental, lightweight visualization layer for CFD. It separates
preparation near the simulation from presentation in a browser. It does not assess
scientific validity or manage engineering acceptance.

## Current focus

- Self-contained HTML with geometry, original mesh edges and scalar slices.
- Local vtk.js rotation, pan, zoom, field switching and color-range controls.
- Equivalent VTP export and a pinned Glance comparison wrapper.
- Read-only OpenFOAM extraction in a separately allocated Slurm worker.
- ParaView-only media presets, bounded cluster rendering, media-only fetch, offline
  block pages with time/field selection, and optional MP4 compilation.
- An older image-based live prototype; recipient-reachable hosting is deferred.

Real datasets and generated HTML are not bundled. Browser/GPU performance remains
unqualified; reader/media qualification is limited to tested cases. See
[publication and qualification limits](docs/publication.md).

## Development

Python 3.12+ and Node/npm are required. From the repository root:

```powershell
./scripts/verify.ps1
npm --prefix viewer ci --ignore-scripts --cache .npm-cache
npm --prefix viewer run build
node viewer/check-colors.mjs
```

The Python scaffold uses the standard library. Viewer dependencies are pinned.
See [viewer tooling](viewer/README.md) and
[portable packaging](src/guanlan/portable/README.md).

For a visibly synthetic, cluster-free demo:

```powershell
./scripts/demo.ps1 -Check
./scripts/demo.ps1
```

Open the loopback address printed by the service. This is a development demo,
not a recipient-reachable sharing service.

## Connecting a case

Copy `config/live.example.json` to ignored `config/live.local.json` and supply
your own SSH alias, case path, ParaView executable, workspace and resource limits.
Inspect `./scripts/live.ps1 -Check` before authorizing execution. Heavy work must
run through the scheduler, never on an HPC login node. Solver files remain
read-only. Fluent and runtime extraction integration are not yet qualified.

See [operation](docs/real-case-runbook.md), [architecture](docs/architecture.md),
[contracts](docs/contracts.md) and [milestones](docs/milestones.md).
For source-side preparation and selected missing-asset transfer, see
[minimal asset delivery](docs/minimal-assets.md).

## Layout and privacy

`src/guanlan/` contains modules with local READMEs; `tests/` contains deterministic
checks; `viewer/` contains build and benchmark tooling; `config/` contains sanitized
templates; `docs/` describes architecture and workflows.

Generated state, CFD data, local configuration, credentials, machine-specific
notes and session archives must not be published. See `.gitignore` and
[publication rules](docs/publication.md). Contributions use Conventional Commits.
