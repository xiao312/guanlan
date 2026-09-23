# CFD platform integration handoff

## Product and division of responsibility

Guanlan is an experimental visualization and delivery layer built around ParaView.
It prepares views near CFD data and delivers small images, sequences or selected
interactive assets. It does not own case records, run lineage, solver execution,
scientific interpretation, engineering acceptance or team permissions.

The proposed partner platform owns case/run/artifact identities, history, user
authentication, case-scoped authorization and the case-page UI. Guanlan can supply
bounded visualization work from the artifact's authorized HPC location. The
platform description supplied by the owner is integration context, not an audited
description of deployed APIs. No platform adapter is implemented yet.

## Existing routes and limitations

- Expert route: native ParaView client connected through an owned SSH tunnel to
  matching `pvserver` in a bounded Slurm allocation. Current desktop automation is
  Windows-specific. This is not an embeddable web session service.
- Media route: deterministic presets drive ParaView readers, boundary selection,
  slicing, cameras, palettes and PNG rendering in a Linux allocation. CLI operations
  are `check`, `submit`, `status`, `fetch`, `package`, `video`, `cancel`. Verified
  PNGs and metadata produce offline block HTML; optional ffmpeg compiles sequences.
  No full CFD dataset is transferred through this route. New media rendering does
  not use Matplotlib. The legacy live prototype is separate.
- Interactive snapshots: selected prepared geometry/scalar assets support local
  vtk.js interaction, with a Glance comparison path. These are not arbitrary
  server-side exploration or a production streaming service.
- OpenFOAM and a restricted native planar XY Fluent CFF pilot are present.
  Fluent uses explicit matching case/data pairs and scalar field mappings; 3D
  Fluent slicing, arbitrary species arrays and all solver versions are not qualified.
  A `.foam` marker locates a case but is not proof of readable/complete output.
- Protected public hosting, a multi-tenant session API and embedded web ParaView
  are not implemented. Browser/GPU performance remains separately qualified work.
  See [Windows/Linux support plan](cross-platform-support.md) for known merged
  portability and caption issues, including Windows Fluent check/submit failure.

## Recommended first integration: asynchronous images

Start with one registered artifact, an explicit completed timestep and one saved
view preset. A platform adapter resolves artifact -> approved host/case location,
authorizes the requester, submits a bounded Guanlan media job, polls status, fetches
verified media and registers a protected preview against the original case/run.
Use the platform's existing preview upload API; obtain its actual schema before
implementation. Its stated PNG/JPEG limit is 10 MiB per upload, whereas Guanlan's
64 MiB aggregate media budget does not guarantee that per-image constraint. Enforce
both limits explicitly and use PNG first. Do not assume HTML/MP4 upload is supported.

The adapter may run on ECS or a dedicated control worker with approved SSH access.
ECS handles control and authorized delivery, not routine raw CFD processing.
Heavy reading, filtering and rendering belong on SCNet compute allocations, never
on login nodes. Source cases are read-only; outputs live in separate workspaces.

## Proposed API contract (not existing endpoints)

A versioned request should carry case/run/artifact IDs, immutable artifact revision
or checksum when available, explicit timestep, validated preset, resource limits
and an idempotency key. Resolve `hpc://` URIs through a server-side host allowlist;
never accept arbitrary client-provided shell commands, hosts or executable paths.

Suggested lifecycle operations: create request, get status, cancel owned request,
list verified outputs. Distinguish queued, allocating, preparing, publishing, ready,
failed, cancelled and expired. Return actionable stage errors and output metadata:
source identity, actual timestep, field association/units, plane, range, representation,
checksum, bytes and protected preview reference. These states require an adapter;
they are not a claim about current CLI status values. Define retry, cancellation,
idempotency and allocation recovery semantics before enabling concurrent requests.

Authenticate service-to-service requests using the platform's agreed mechanism.
Recheck case access for output/session retrieval, including after permission changes.
Keep SSH keys, absolute HPC paths and scheduler details in private server state.
Do not expose them in public HTML, browser logs or user-visible URLs. Protected
preview delivery may use an authenticated proxy or short-lived scoped URLs with
explicit expiry/cache policy. Artifact hashes establish integrity, not access rights.

## Later interactive web sessions

Native `pvserver` is not a browser protocol. Browser exploration would need a new
ParaViewWeb/trame application/gateway, authenticated HTTP/WebSocket proxying and
session management. Budget allocation, RAM, walltime, idle expiry and per-user/case
concurrency; keep compute ports private. Avoid mixing differently authorized users
in a shared pipeline. Start with server-rendered images for large data; use local
geometry only under measured transfer/client-memory limits. No universal bandwidth
advantage is claimed for either approach.

Before choosing this route, agree on supported filters, input formats, version
matching, reconnect behavior and deployment/network reachability. Prepared media
must remain usable after the rendering allocation ends.

## First acceptance demonstration

An authorized case-page action renders a real registered OpenFOAM artifact on an
allocated worker, returns a protected PNG within the upload limit, and records
source/time/preset metadata. An unauthorized user cannot request or retrieve it.
Retry does not create duplicate allocations; cancellation and expiry release owned
resources. A failed/latest-incomplete output does not replace the last good preview.
Record queue, read/filter/render, transfer and display timings separately. Add the
Fluent pilot only after its portability and representation-label fixes are verified.

Next inputs needed from the platform team: artifact/session/upload API schemas,
authentication model, host/path authorization rules, network routes, retention and
quotas, worker deployment constraints and a non-sensitive test artifact.
