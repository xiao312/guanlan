# Portable interactive case snapshots

Single-block exports are supported; geometry+mesh is a preset, not mandatory.
For minimal cluster transfer use `guanlan.prepared`: it selects dependencies from
a source manifest before retrieving binary data. `prepared_html` embeds validated
selected assets without rebuilding edges or requiring the raw source scene.
The browser loader accepts either embedded gzip or same-origin `assets/` files,
verifies SHA-256 over dtype+NUL+canonical bytes, and serializes decodes. Total
selected decoded arrays are capped at 64 MiB; this is not a total browser/GPU
memory guarantee. Frozen manifests never accumulate timesteps; a new frame opens
a new page. Live generation updates and offscreen renderer eviction are deferred.
Node loader integrity checks: `node viewer/check-loader.mjs` (not a browser test).

Responsibility: package an already extracted scene into one offline HTML file.
This module never connects to SSH, starts a worker, or reads solver files. Camera,
mesh edges, field selection, and color ranges are rendered locally by vtk.js.
Middle-drag and Shift-left-drag pan; left-drag rotates; wheel zooms. The scalar
lookup table owns its range and is explicitly invalidated on presentation edits.
Continuous Viridis is the default; optional 8/12/24 bands quantize colors only,
not the original cell values. Auto uses the full prepared field minimum/maximum,
not percentiles. `node viewer/check-colors.mjs` verifies numeric mapping and reset.
Non-goals: full-volume processing, new slice extraction, live links, solver control.

Input: version-1 scene JSON from `worker.extract`, plus a locally built viewer
bundle. Scene contains title, case directory, simulation time, datasets keyed by
ID (Float32 points, Uint32 VTK polygon cells, Float64 cell fields, base64 little
endian), and blocks referencing datasets. Geometry and mesh share one surface.
Fields retain cell association; no smoothing/interpolation is implied. Units and
vector-magnitude semantics accompany arrays. Coordinates are metres for this case.
Output: self-contained HTML, with a small manifest and independently gzip-compressed
binary assets (points, polygon cells, original edges, each field). `assets.py`
derives content-addressed assets and exact original polygon edges from the scene.
Identical assets are embedded once. Decoding is lazy per visible block/selected
field, not one whole-scene gzip. Inline JS/CSS includes all viewer dependencies.
`vtk_export.py` produces standard VTP equivalents for an independent Glance
comparison; it never reruns CFD extraction. Original edges are separate lines.
Modern browser with WebGL2 and DecompressionStream required. No CDN/network calls.

Dependencies: Python standard library for packaging; pinned vtk.js/esbuild in
`viewer/` for build-time bundling. Dependents: portable export CLI and users opening
the artifact. Security: trusted local extraction only, schema/budget validation,
escaped metadata, no executable user markup. Embedded CFD data and server path are
visible to anyone receiving the file. No credentials are included.

Limits: 64 MiB uncompressed scene; 32 MiB final HTML; 500,000 cells per dataset;
1,000,000 points per dataset; at most 8 blocks and 8 datasets. Reject over-budget
exports rather than silently simplifying the displayed mesh. Render on demand;
initialize a block only near the viewport; share decoded data between blocks.
The cell cap was raised explicitly from 300,000 after the real fixture's exterior
measured 409,231 polygons. It is still a safety cap, not a browser-speed promise.

Example (from project root, after building viewer and qualifying the physical fixture):
`$env:PYTHONPATH='src'; python -m guanlan.portable --scene state/portable/physical-scene.json
--output state/portable/case-interactive.html`

Build: `cd viewer; npm ci --cache ../.npm-cache; npm run build`.
Verification: `./scripts/verify.ps1`; browser manually open the HTML offline,
rotate/zoom geometry and mesh, switch included fields and ranges, reset view.
Rendering checks require a connected browser; fixture tests do not prove GPU output.
The HTML includes explicit measurement/export controls for manual browser testing
when CLI browser automation is unavailable. Reports label animation-frame timing
as a scheduling proxy, not GPU completion; exact GPU/process memory remains null.
Separate canvases may duplicate GPU buffers despite shared decoded CPU arrays.

`comparison.py` packages both candidates from one validated scene. It pins the
downloaded Glance HTML by SHA-256, removes the optional external ITK/service-worker
scripts (VTP only), embeds data and control code, and denies network via CSP.
Glance's full application is the single-view baseline; Guanlan also has a multi-
block layout. These are not equivalent multi-view workloads. Glance is BSD-3-Clause;
the source license is included in comparison outputs. Source inspection does not
replace browser compatibility testing. `--check` validates inputs without writing.
The comparison command rejects fixtures without matching physical-boundary face
counts. This integrity gate does not substitute for visual verification.
Example: `python -m guanlan.portable.comparison --scene state/portable/physical-scene.json
--output-dir state/portable/comparison --glance state/portable/vendor/ParaViewGlance.html
--glance-license state/portable/vendor/glance-source/LICENSE`.
