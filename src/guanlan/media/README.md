# ParaView media sharing

Known PR #1 limitation: Fluent local validation/submission imports Linux-only
worker dependencies and currently fails on Windows. Representation captions also
need a Fluent-aware update. See the [cross-platform remediation plan](../../../docs/cross-platform-support.md).

Responsibility: turn an engineer's bounded preset into ParaView-rendered PNG frames,
transfer only media/metadata, and assemble a self-contained block-based HTML.
Optional local ffmpeg compilation makes one MP4 per block/field. No Matplotlib,
browser numerical CFD data, solver mutation, public hosting, or live monitoring.

## Interface

`python -m guanlan.media --help` lists `check`, `submit`, `status`, `fetch`,
`package`, `video`, and `cancel`. Commands emit JSON `{ok:true,data:...}`; failures
emit `{ok:false,error:{message:...}}` to stderr with nonzero exit. Check is local,
read-only. Submit deploys code/preset to a unique workspace and submits one bounded
job; no implicit submit on fetching or packaging. Use a new state directory for
each preset revision. A submission-in-progress record blocks ambiguous retries.

Inputs: runtime profile as in infrastructure/paraview, case profile, and preset
JSON. See `examples/media-preset.json`. Preset version 1 requires a public-safe
title/case_label, explicit existing `times` (1-24), image `size` (320-1920 by
240-1080), and 1-8 blocks. Geometry/mesh blocks use physical boundaries only;
optional `patches` restrict them. Slice blocks require plane xy/xz/yz, normalized
offset (strictly 0-1), fields (1-8), and palette Viridis/Cool to Warm.
Scalar-only, cell-associated values without point interpolation. `range` is
`data` (per-frame data range, clearly labeled) or a fixed increasing numeric pair
(recommended for temporal comparisons). Camera defaults to the slice plane or xy;
xy/xz/yz/isometric are supported. At most 192 rendered frames and 64 MiB media.
Planar blocks may set `focus: [u0, u1, v0, v1]` with normalized bounds in
the selected camera plane. This changes the captured camera region without
clipping source cells or changing field ranges. Use a separate block for the
full domain and an injector close-up when both are needed.

Outputs: remote `output/manifest.json`, PNGs, and `media.zip`; local selected
verified PNGs/manifest and HTML. Frames bind to block, field, timestep, physical
plane origin/normal, numeric range, units, and SHA-256. No case path is published;
source paths/job IDs remain in ignored operation state/logs. Labels/pictures may
still be sensitive; publishing artifacts requires its own recipient authorization.
Manifest is committed last, only after successful reads, rendering and unchanged
source signatures. Transfer and archive decode are bounded and hash-checked.
Existing output is never overwritten. Partial jobs require inspection/new state.

## Dependencies

`media.remote -> OpenSSH/SCP + Slurm + infrastructure/paraview/run.sh`.
`media.render -> ParaView 6.1.1 + worker.readiness/boundaries/protocol`.
`media.package -> contract` uses Python standard library, no renderer.
`media.video -> verified PNGs + optional ffmpeg/libx264`; no interpolation is
performed, playback uses uniform frame cadence with actual simulation times burned
into the frames. It does not claim uniform physical-time sampling.
Dependents: CLI, `guanlan-share` skill. The legacy live module is not used.

## Fluent CFF pilot

Set `source_format: "fluent-cff"` and an absolute local `source_index` path in
the ignored case profile. The source index has version 1, `format: "fluent-cff"`,
`frames` mapping each preset time to matching `.cas.h5`/`.dat.h5` basenames, and
`fields` mapping each public field label to a native scalar cell array and unit.
The two files for every time must live in the read-only case directory. The index
is deployed only to the private request workspace; the manifest and offline HTML
contain no source filenames. The CLI checks the mapping before submitting.

This pilot reads native planar XY CFF data with ParaView's FLUENTCFFReader. Its
geometry block shows the fluid domain; its mesh block shows original cell edges.
The `slice` block displays the native 2D plane at z=0; only `plane: "xy"` with
`offset: 0.5` is accepted. Vector operations, boundary patch selection, and
three-dimensional Fluent slicing require separate qualification. The currently
qualified ParaView reader drops Fluent species arrays with more than nine
components, so only scalar arrays actually present in the reader may be mapped.
It cannot claim OH or CH4 from such a dropped array.

## Example

Set PYTHONPATH to `src` from the repository root, then:

```text
python -m guanlan.media check --profile config/paraview.local.json --preset examples/media-preset.json
python -m guanlan.media submit --profile config/paraview.local.json --preset config/media.local.json --state state/media/run-01
python -m guanlan.media status --state state/media/run-01
python -m guanlan.media fetch --state state/media/run-01
python -m guanlan.media package --state state/media/run-01 --output state/media/run-01/snapshot.html
python -m guanlan.media video --state state/media/run-01 --output state/media/run-01/videos --ffmpeg D:/tools/ffmpeg.exe
python -m guanlan.media package --state state/media/run-01 --videos state/media/run-01/videos --output state/media/run-01/with-video.html
```

Verification: `scripts/verify.ps1` tests preset rejection, bounds, archive integrity,
safe offline packaging, frame coverage and failure behavior. Separately run an
authorized real-case render and inspect PNGs. HTML timeline is a prepared image
sequence, not interactive 3D. Browser visual checks and video qualification must
be reported separately; CLI tests do not prove them.
