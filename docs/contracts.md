# Contract version 1

This describes the original synthetic fixture. Real case pages use document
version 2, implemented in `src/guanlan/casepage/`: one configured case ID, geometry
and mesh first, then up to six slice blocks. Each block records kind, field, plane,
normalized interior offset, camera preset, palette and optional fixed range.
The local server maps the case ID to the profile's exact server directory.

Real preview metadata includes the document revision, solver time, mesh counts
and bounds, field catalog, render duration, allocation ID and image generation.
An image generation commits atomically after every requested block succeeds.
Previous complete content remains visible on read/extraction/transport failure.
Portable HTML snapshots embed that generation's images and its original document.

The executable validator in `src/guanlan/contracts/` is the source of truth for
the supported demo subset. Unknown keys are rejected. JSON examples are complete
inputs, not fragments. Production adapters must expand the contract deliberately.

## Saved view recipe

`schema_version` is 1; `id` is a portable identifier; `case_id` identifies a source.
`panels` has one or two panels, each with `field`, `operation`, `association`,
`units`, and `color_range` [minimum, maximum]. `plane` has `origin` and `normal`;
`camera` has `position`, `target`, and `up`. `refresh` has `policy: latest` and
`interval_seconds`. `limits` has `max_preview_bytes`.

The fixture supports point-associated `U` magnitude in m/s and scalar `p` in Pa;
only the supplied center plane and orthographic camera are supported. Real field
catalogs must distinguish cell/point data, scalar/vector components, pressure
conventions, coordinate systems, and unknown units; do not infer these from names.

## Preview envelope

`schema_version`, `view_id`, `recipe_digest`, `case_id`, `frame_id`,
`simulation_time`, `simulation_time_units`, `source_kind`, `image_url`, and
`poll_interval_seconds` accompany each preview. The demo labels source kind as
`synthetic`. Demo frame IDs are an elapsed-time fixture index, not solver step IDs.

Production must additionally record output identity, data-ready timestamp,
render-complete timestamp, publication timestamp, mesh identity, and actual
payload size. Those separate cold start, cached opening, and fresh-data latency.
Last-good content stays visible while newer output is pending or unavailable.

Snapshots freeze frame and complete recipe, including colors and camera. The demo
SVG embeds these in metadata and includes the synthetic label and simulation time.
Live URLs refer to a saved view that advances. Snapshots are portable downloads;
the local live URL is not a public sharing service.

## Future adapter and worker interfaces

Acquisition: `discover(profile) -> case metadata`, `catalog(case) -> fields`,
`latest_readable(case, requirements) -> output descriptor | waiting`.
An output descriptor must identify every required partition and dependency;
statistics sidecars alone cannot supply an image. Failed reads remain retryable.

Worker: `render(output, validated_recipe, budget) -> preview artifacts`.
Coordinator submissions carry recipe revision and output identity. A stale recipe
revision must never overwrite a newer revision's preview. One active request and
one replaceable pending request per view are the initial scheduling bound; global
view/worker limits are still required. Explicit exports use a separate queue.

Publication: atomically commit artifact plus envelope after validation and size
checks, preserving the previous complete preview on failure. Cache keys include
case/output identity, recipe digest, and renderer version. Production access
policy applies equally to metadata, images, geometry, and snapshot downloads.
