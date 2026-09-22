# Real case operation

## Owner workflow

1. Keep host/path details in `config/live.local.json`; use the sanitized example
   when adding another installation. The page has one configured case path.
2. Run `./scripts/live.ps1 -Check` and inspect the case, workspace and resource plan.
3. Run `./scripts/live.ps1`. This uploads only the worker Python package under the
   dedicated Guanlan directory and requests one separate allocation.
4. Open `http://127.0.0.1:8766/case/<configured-case-id>`. Cached images open even if the
   renderer is waiting. Initial reader startup is distinct from warm rendering.
5. Configure blocks and apply changes. The server persists the page; the newest
   pending revision replaces obsolete pending revisions. Active work may finish,
   but an obsolete revision cannot overwrite the current page.
6. Download Snapshot for a portable, frozen HTML artifact. It includes the exact
   source timestep, original block settings and embedded PNGs.

The service retains two preview generations (at most 16 MiB each). The worker
retains one reader and bounded per-block images. Geometry and mesh previews are
reused while their mesh signature/settings remain unchanged. Unchanged polls
return metadata only across SSH. Solver data never crosses the connection.

## Allocation lifetime

After observing a peak below 1 GiB in initial qualification, the local profile
requests 1 CPU, 3 GiB, 60 minutes maximum and a 300-second
worker idle timeout. After 45 seconds without page activity, periodic requests
stop; the compute-side idle timer then releases the worker. A first render is
allowed even before the first browser visit. Closing the service closes stdin;
Slurm also enforces the walltime. Use the owner's Reconnect button after idle/exit,
or restart the local service. Reconnect requests cannot duplicate an active worker.

No worker runs inside the solver's allocation. No solver files, cadence, jobs or
runtime controls are modified. Guanlan uses its own workspace symlinks to expose
the decomposed case to the reader without creating a marker inside the case.

## Sharing boundaries

Standalone snapshots are usable by a recipient with only a browser, without a
cluster account, ParaView, Python or this service. Sharing the file is an explicit
user action; there is no automatic external upload.

Live sharing requires choosing a recipient network and approved endpoint. The
initial server defaults to loopback. `-Bind <explicit-private-IP>` serves the same
case to that private interface; nonlocal clients are read-only. The workstation
and service must remain running and network/firewall reachability must be tested
from the recipient network. Do not infer reachability from a local request.

This first HTTP service has no internet-facing authentication/TLS. For external
collaborators, deploy behind an approved authenticated TLS proxy and explicitly
configure trusted proxy/owner semantics; do not forward external writes through
a loopback proxy that would make them appear to be owner requests.

## Troubleshooting

- Waiting for allocation: inspect the named Slurm job, not the solver job.
- Loading: ParaView imports and scans the case; this is not yet a displayed frame.
- Waiting for output: every requested field must exist on all partitions and pass
  the read check. The worker rejects unsupported moving meshes and extraction
  errors, retaining the last complete preview.
- Invalid field values: the renderer reports inability to represent a field, not
  a scientific health assessment. Magnitudes use float64/hypot to avoid incidental
  float32 squaring overflow. Values are never clipped to plausible physics.
- Idle/ended worker: the saved page and cached snapshots remain; use Reconnect
  for another bounded allocation.

Bounded worker diagnostics are in `state/live/worker-diagnostics.json` and contain
only the last 20 stderr lines. Local state is ignored; credentials remain solely
in existing SSH configuration.
