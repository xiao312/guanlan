# Guanlan architecture

## Offline interactive snapshots (current iteration)

`viewer/benchmark.mjs -> playwright-core -> isolated headed Edge + CDP counters`
is a user-run verification path, not a runtime dependency or a cluster operation.
It consumes frozen HTML and writes local benchmark artifacts without credentials.

The raw extraction scene is a baseline interchange, not the delivery format.
`portable.assets` builds an immutable manifest plus content-addressed binary arrays.
HTML embeds independently compressed assets; browser decoding is demand driven.
`portable.vtk_export` writes equivalent VTP files for Glance comparison from the
same fixture, with original polygon edges separated from rendering triangles.
No spatial LOD is implemented or justified until actual browser measurements exist.

`Slurm -> worker.extract (ParaView reader/filters, no server rendering)
-> scene.json -> portable (local packager + bundled vtk.js) -> standalone HTML`.
Extraction and presentation are independent: no allocation or SSH occurs when
opening/exporting an existing scene. Geometry/mesh share exterior polygon data;
prepared slices contain cell arrays for local field/color switching. A different
slice position requires a new extract. vtk.js provides WebGL camera/rasterization;
trame's local-view pattern informs the design, but trame is not a runtime dependency.
The existing live PNG path remains separate and still uses Matplotlib; it is not
silently replaced or claimed to provide the new portable behavior. Live-link work
is deferred. See portable/README.md for budgets and interface.

## Module dependency graph

The real case path adds these dependencies (the synthetic fixture remains separate):

```text
guanlan.live -> liveweb -> session -> casepage
                           |           ^
                           +-- SSH/srun worker -- ParaView / OpenFOAM
```

The real path supports static, decomposed OpenFOAM. ParaView supplies the reader
and filters; bundled Matplotlib Agg supplies headless polygon rasterization
because the installed OpenGL build requires X. Images are bounded orthographic
previews; trame and smooth 3D interaction remain future integrations.

Worker transport uses stdin/stdout through one persistent SSH connection; no
compute-node HTTP port is exposed. The browser reads a cached case-page state;
latest document revisions coalesce while an active render finishes. Explicit
snapshots freeze the current image generation in a standalone HTML artifact.

Arrows mean "depends on". Solid paths exist in this scaffold; planned components
are called out below and must not be mistaken for working solver integrations.

```text
scripts/demo.ps1 -> guanlan.cli -> delivery -> preview -> contracts
                                      |         |
                                      +------> contracts
tests ---------------------------------------> scheduling
scripts/discover.ps1 -> existing SSH configuration -> Slurm (read only)
```

`contracts` validates portable view recipes. `preview` renders synthetic fixture
images. `delivery` serves bounded local previews and frozen downloads, using its
own fixed browser assets. `scheduling` implements one active plus one newest
pending preview request for a future worker; the cheap synchronous demo renderer
does not need a worker queue. `cli` composes these modules. Each directory has a
local README with its interface and verification command.

## Planned production flow

```text
solver files / approved runtime extracts
  -> acquisition adapter -> readable output descriptor
  -> latest-first coordinator -> warm allocated rendering worker
  -> bounded image / optional extracted geometry
  -> publication endpoint -> browser

user controls / optional language adapter -> validated saved recipe -> coordinator
explicit export request -> separate bounded export queue -> frozen artifact
```

Acquisition supplies field metadata, units, associations, mesh identity, simulation
time, readiness, and dataset identity. Solver-specific readers resolve Fluent
case/data pairs or decomposed OpenFOAM timesteps. A file listing is only discovery;
a reader must establish readiness and handle partial output without losing the
last good preview. Avoid copying entire cases or reconstructing them on login nodes.

Workers live beside the simulation data on approved compute resources, reuse a
pipeline and mesh when safe, and have allocation, memory, walltime, and idle limits.
Do not submit a separate Slurm job for every frame. Mesh changes invalidate reuse.
Newest pending preview replaces older pending work; already active work may finish.
Never delete solver outputs. Exports are explicit, bounded, and never silently dropped.

The publication service receives small artifacts, not solver credentials. It must
have an approved recipient-reachable route and authentication/access policy before
live data sharing. Localhost is only the development fixture boundary. Preview
storage, snapshot retention, transfer sizes, and worker idle time require budgets.

The established live route delivers PNGs. The separate portable candidate embeds
prepared geometry and selected cell fields for local camera/color changes. It is
not yet browser-qualified. Data not resident but already prepared needs retrieval,
not another extraction; a genuinely unprepared slice needs bounded preparation.
Offline bundles have finite coverage. See `publication.md` for qualification
limits; no spatial LOD is currently implemented.

An optional language adapter can propose a recipe from metadata and permitted
operations. Jev candidate selection and generative multi-operation edits are
evaluation candidates, not dependencies. Deterministic validation precedes use;
routine refresh never invokes a model. No automatic scientific interpretation.

## Two acquisition modes

`attach-existing` is read-only. `runtime-extract` changes solver configuration and
needs explicit authorization, version qualification, and measured overhead. The
synthetic scaffold performs neither mutation nor extraction. The real-case command
deploys its worker and extracts existing data under the user's explicit task
authorization. It never alters solver cadence/configuration. A profile alone does
not authorize remote writes or allocation.
