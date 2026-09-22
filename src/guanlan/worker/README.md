# Allocated case renderer

New image/video sharing uses `media.render`, which depends on this module's
readiness, physical-boundary metadata and diagnostic protocol helpers. It uses
ParaView for both extraction and rendering. The older `main/pipeline/software`
Matplotlib service below is retained for compatibility, not selected by media skills.

Optional `extract --reference-images` renders direct ParaView slices using the
same cell association, Viridis range and orthographic plane camera. This requires
a qualified headless ParaView runtime and remains allocation-only. It writes
reference PNGs and a ParaView state beside the prepared store, not into the case.
It is an independent presentation baseline, not proof of browser pixel equality.
`reference.py` depends only on ParaView; image generation never uses Matplotlib.
The scalar audit additionally records ordered-array equality (not just a histogram);
ordering disagreement is reported, not hidden by the multiset check.

Selective extraction adds `--slice-only`, `--planes xy xz yz` and `--offset`
(normalized position). `--prepared` writes a source-side manifest/gzip store at
--output instead of a whole scene. Default slice field is the first selected field.
Dependencies include portable validation/assets and prepared.store, deployed as
Python modules. Source-store cap is 256 MiB; exceeding it fails publication.
`--audit-scalars` compares native scalar arrays with the internal reader cell-value
multiset inside the allocation. ASCII and declared-endian binary are supported;
uniform arrays require the native owner header's nCells metadata. For older files
without an architecture header, `--legacy-lsb64` explicitly selects little-endian
Float64; it is recorded and binary count/closing delimiters must match. Never
silently infer this profile for other installations. Unsupported vectors fail.
This verifies field reading, not cell-position correspondence or scientific quality.
The audit compares exactly after casting native values to the reader's actual
dtype and separately records exact-native equality and maximum rounding error.
VTK's OpenFOAM reader may output Float32 despite binary64 input; exported Float64
containers do not restore discarded precision. Field descriptors record reader_dtype.

`extract.py` is a separate one-shot, non-rendering export path for portable HTML.
Under an explicit Slurm allocation it reads selected fields (default p/T), extracts one exterior surface
and one XY slice, and writes a bounded version-1 scene JSON in Guanlan's workspace.
It does not import Matplotlib or create an OpenGL render window. Geometry and
mesh reuse the same exact surface polygons. Arrays keep cell association and
vector magnitudes use float64/hypot. Inputs: --case, --workspace, --output,
--title; output: scene JSON and extraction metrics. Dependents: portable packager.
Optional `--time-name` pins a completed timestep; no fallback to a newer time.
`--fields p T` selects arrays explicitly. Non-finite values fail a requested export;
they are never silently clamped or converted into plausible colors. The newer
real-case U slice failed that integrity check; U is not part of the p/T baseline.
`boundaries.py` parses only bounded small patch dictionaries. Export explicitly
selects physical reader patches and checks the emitted face count against their
sum, excluding processor interfaces. Merge-first was found to retain 6,350
processor-interface faces in this case and is not the qualified exterior route.
The slice is cut partition-by-partition and flattened without whole-volume merging
or coordinate welding. Patch/partition seam vertices may remain duplicated by
identity; coincident-but-distinct boundaries are not silently welded.
Baseline stages include reader, surface export, slice export and serialization.
Budget is explicitly 500,000 polygons per dataset (409,231 in this real surface),
not a measured browser performance limit.
Example: `srun ... pvpython -m guanlan.worker.extract --case /case --workspace
/work/guanlan --output /work/guanlan/scene.json --title Example`.
Verification: scheduled real-case export followed by portable validation/tests.
Extraction emits native-descriptor phase/count records and exceptions, since
ParaView can capture Python stdout/stderr. Remote stdout/stderr should be retained
in the dedicated workspace. A failed export must never replace a complete scene.

Reads one explicitly configured OpenFOAM case without modifying it. Uses the
installed ParaView reader and rendering pipeline on a separate Slurm allocation.
Non-goals: solver control, reconstruction, Fluent support without qualification,
login-node rendering, or public web serving.

Input: one JSON request per stdin line containing a validated case document.
Output: JSON messages prefixed `GUANLAN ` on stdout, with metadata and bounded PNG
images encoded as base64. Other stdout is diagnostic. The local session owns SSH
and Slurm process lifetime. One request renders the case's configured blocks.
No network listener or credentials exist on the compute worker.

Dependencies: ParaView 5.11 Python/VTK, OpenFOAM files, Slurm compute allocation.
Some builds require X for OpenGL; `software.py` instead uses bundled NumPy and
Matplotlib Agg to rasterize extracted polygons. This is an orthographic preview
with depth ordering, not full interactive 3D. No extra runtime is installed.
Mesh coordinates are treated as metres for this OpenFOAM case. Confirm coordinate
units when qualifying another solver or imported case. Cell-associated vector
magnitudes use float64/hypot; the renderer does not clamp stored values to physical
expectations. Fixed color limits affect presentation only.
Dependents: session transport; production API is implemented in this module.
Keep the reader warm, detect complete partition timesteps, validate successful
reads, and preserve last-good frames at the caller when a read fails. Case markers
and any symlinks belong only in the dedicated worker workspace, never the case.

`probe.py` is a one-shot capability check, run under `srun`, not on the login node.
It prints runtime version, reader properties and offscreen-render capability.
Verification: execute probe in a bounded allocation, then render real geometry,
mesh and a selected slice. Local tests cover readiness without requiring ParaView.

`readiness.py` screens matching partition times, required fields, settle time and
file signatures. `pipeline.py` owns the reader/filters; `main.py` owns transport and
idle lifetime. Static meshes are the initial scope. Time-directory mesh changes
are rejected until a moving-mesh reader policy is qualified.
`protocol.py` writes to native stdout/stderr descriptors: pvpython replaces its
Python console streams, which must not capture the SSH request/response protocol.
