# Case page design

The page is a persistent case notebook: one server case path, a small navigation
rail, geometry first, mesh second, followed by configurable result blocks. Geometry
means the mesh's domain boundary until actual CAD input is supported. Each block
has its own field, plane, camera and color range; edits persist across refreshes.

Use compact type, thin borders, restrained blue accents, neutral backgrounds,
light/dark presets, and monospace case paths. Avoid a marketing hero or scientific
assessment dashboard. Source inspirations inspected on 2026-09-22:

- OpenCode themes: https://dev.opencode.ai/docs/themes/
- Pi themes and exported session HTML: https://github.com/earendil-works/pi
- Paseo workspace rails and compact mobile controls: https://paseo.sh/

ParaView supplies a persistent reader/filter/display pipeline, named arrays,
orthogonal slices, surface-with-edges mesh display, lookup tables, scalar bars and
camera presets. It stays on allocated compute resources next to case data.

The delivery split follows trame's documented remote/local rendering model:
https://trame.readthedocs.io/en/latest/trame.widgets.vtk.html . Images bound network
payload and browser work; they do not inherently make extraction or rendering
faster. Warm readers and cached previews address server latency. Geometry delivery
can make rotation/recoloring faster after transfer, but has a larger initial payload.
This iteration uses image blocks; smooth remote orbit and small geometry delivery
can be added without changing the saved block model. trame is not yet a dependency.
