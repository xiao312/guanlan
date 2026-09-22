# Offline viewer build

## Headed benchmark runner

`benchmark.mjs` is a user-run Playwright harness for Guanlan HTML (not Glance).
Input: a local HTML path. Output: screenshots, errors, CDP performance counters
and the page's measurement JSON under `state/portable/browser-runs/`. It launches
installed Edge headed in an isolated context, never connects to a personal
profile or a remote CDP endpoint, and blocks HTTP requests. No secrets are used.
Dependency: pinned playwright-core; dependent: manual qualification workflow.
Example: `node benchmark.mjs ../state/portable/guanlan-review.html`.
`--check` validates the input without launching a browser. Syntax verification:
`node --check benchmark.mjs`. Browser execution is still required to qualify it.
The trace exercises middle pan, rotation, wheel zoom, field/range changes and
two-column layout. Screenshots require human review; CDP counters and rAF are
not GPU completion or exact process/GPU memory. No performance SLA is inferred.

Responsibility: bundle vtk.js plus Guanlan's portable block controls into one IIFE.
No runtime service, CDN, full CFD reader, or custom rendering engine is included.
Inputs: `src/guanlan/portable/viewer.js`, pinned package.json/package-lock.json.
Output: ignored `state/portable/viewer.js` including dependency license notices.
Dependencies: Node/npm, vtk.js (BSD-3-Clause), esbuild (MIT); dependent: portable
HTML packager. All caches and dependencies stay within this project on D:.
No secrets or case data enter npm. Install scripts are disabled except esbuild's
required binary setup; the normal npm package supplies that platform binary.

Example: `npm ci --ignore-scripts --cache ../.npm-cache; npm run build`.
Verification: `npm run build`, project unit tests, then offline browser interaction.
`node check-fixture.mjs ../state/portable/scene.json ../state/portable/comparison`
reads the actual VTP comparison files with vtk.js and checks points, polygons,
cell fields byte-for-byte and the complete original edge set. This is numerical
interoperability verification only; it deliberately does not launch a browser.
The Glance wrapper has a separate small bundle, `state/portable/glance-controls.js`.
