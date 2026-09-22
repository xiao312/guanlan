---
name: guanlan-paraview
description: Start, inspect, open, and stop an allocated ParaView expert session for a configured CFD case. Use for native desktop exploration, new slices or filters, and SSH connection diagnosis; not offline sharing.
---

# ParaView expert session

Use Guanlan's deterministic launcher; do not reconstruct SSH/Slurm commands from
chat history. Resolve the repository as three parents above this skill directory.
Read [runtime contract](../../../infrastructure/paraview/README.md) and
[expert workflow](../../../docs/paraview-expert.md) before operating it.

## Discover and choose

- From the repository root, run `./infrastructure/paraview/Manage-Session.ps1 -Action Check -Json`.
- An ignored runtime profile binds the SSH alias, matching client/runtime, case
  profile and resources. If missing, use `session.example.json` and ask only for
  the missing host/case choices. Never place personal paths in tracked examples.
- Run `-Action Status -Json` before starting. Success is `ok:true` and exit 0;
  a submitted job or desktop process is not proof of an application connection.
- Opening files and reading fields are not authorization to change the solver.
  Obtain user authorization for a new bounded allocation if not already requested.

## Start, connect, open

1. `-Action Start -Minutes 60 -Json` submits one bounded job. Preserve its record.
2. `-Action Connect -Json` verifies running job/readiness and starts the owned
   loopback tunnel. If queued or unpacking, observe status/logs and retry Connect,
   **not Start**. Stop after a concrete error or the allotted startup window;
   report whether the allocation remains active. Never disable host-key checking.
3. When the user wants the application opened, run `-Action Open -Json`. This
   launches a visible matching ParaView with `--url` and a receipt script. It does
   not click or modify an existing window. If already connected, keep that window
   instead of opening a second client to a single-client server.
4. Read the returned receipt path: require `ok:true` and `remote:true`. Corroborate
   with the server log's client connection. If no receipt, diagnose—do not call
   it connected. Give the user the shadow `.foam` path and appropriate reader mode.

The client can now operate the source pipeline: arbitrary Slice/Clip/Contour,
fields, cameras, time and state. Use ParaView scripting for reproducible changes,
and preserve the user's existing GUI work. Native GUI automation beyond startup
requires an available supported control interface; do not pretend clicks happened.

## Finish or recover

- Leave a session running only when handing it to the user; state its limits.
- On request to release, use `-Action Stop -Json`, then verify the saved job is
  absent from squeue and no owned listener remains. Do not close the user's
  ParaView window automatically or cancel unrelated jobs.
- Refused localhost connection: inspect the listener, then tunnel, then allocation.
  Do not reinstall ParaView or weaken the firewall as a first response.
- A field comparison must pin time, plane origin/normal, cell/point association,
  interpolation and color range. Never infer spatial correctness from histograms.

Use the prepared media route when the user wants results available after allocation
ends. Expert sessions and prepared snapshots have different capabilities and costs.
