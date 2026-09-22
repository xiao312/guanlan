# Implementation milestones

## Real-case implementation status

The separate real-case path now implements a saved block page, OpenFOAM reader,
Slurm/SSH warm worker, bounded PNG delivery, persisted controls and portable HTML
snapshots. Geometry, mesh and pressure have been rendered from the supplied case;
see `publication.md` for qualification limits and `real-case-runbook.md` for use.
The initial backend uses ParaView filters and Matplotlib Agg because the installed
OpenGL renderer needs X. Fluent, moving meshes, runtime extracts and smooth 3D
interaction remain unqualified. An external live-sharing endpoint still requires
the recipient network/hostname; a local URL is not milestone completion.

Qualification still pending: corrected XZ velocity image, warm field-switch timing,
observation of a newly written timestep reaching the page, and recipient-network
live access. Busy Slurm queues prevented the follow-up render after protocol fixes.
The owner can retry using Reconnect; completed previews/snapshots stay accessible.

## 0 — Scaffold (this change)

Runnable synthetic viewer, saved recipes, automatic refresh, portable frozen SVG,
contract checks, scheduler tests, read-only Slurm discovery, and observed cases.
No real rendering, runtime extracts, model integration, or published service yet.

## 1 — Qualify one reader and warm worker

Select a supported case and obtain an explicit compute allocation authorization.
Check available reader versions, compatibility and licensing before choosing
ParaView/VTK, trame, or a Fluent-backed rendering path. Read one completed output,
then a newly completed output. Verify real field units and associations. Reuse the
worker/pipeline, handle partial files and mesh changes, bound memory and idle time.
Use fixtures for incomplete Fluent case/data pairs and missing OpenFOAM partitions.

In parallel, qualify OpenFOAM Foundation 8 surface extraction in a disposable,
authorized case. Specify fields, surface and independent write cadence; compare
solver runtime and output bytes with and without extraction. Do not edit the
observed running cases by default. Fluent runtime preview support needs its own
qualification, not an assumed equivalent configuration.

## 2 — Complete the real vertical slice

Connect the reader/worker to the saved view and latest-first scheduling. Publish
small images through an approved endpoint with access controls. Have a recipient
open the live view in another browser and download a frozen snapshot without
ParaView or full datasets. Demonstrate a control changing the view and the next
output appearing without manual commands. This is the first product milestone.

Record cold start, warm update age, cached interaction latency, new-extraction
latency, bytes per update, worker peak memory, storage growth, solver overhead,
setup actions, recurring interventions, and recipient setup steps. Set numerical
budgets from measured representative cases; do not claim arbitrary performance.

## 3 — Reduce interaction effort

Add bounded geometry only when it improves useful interactions. Evaluate language
requests against explicit field/preset candidates and structured recipe edits.
Measure first-attempt view creation, corrective interactions, and time saved.
Refresh must continue when the model endpoint is unavailable.

Future parallel implementation boundaries are acquisition/preview, viewer/sharing,
and language-to-view. Agree on recipe and envelope fixtures before parallel work.
