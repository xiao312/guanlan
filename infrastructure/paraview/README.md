# ParaView runtime

## Desktop session launcher

`Manage-Session.ps1` owns one bounded Slurm job and its Windows SSH tunnel.
`-Json` returns an `ok`/`data` envelope for agents (failures: nonzero exit and
`ok:false` on stderr). `-Action Open` launches a new visible matching desktop with
`--url=cs://127.0.0.1:11111` and a startup receipt script; it does not drive another
user window. It requires the owned tunnel and a running job.
The launcher uses Windows UI Automation only to dismiss the known welcome dialog
in its new process; it never toggles saved preferences or clicks another window.
Inspect `state/paraview/session/desktop-receipt.local.json` for actual application connection,
not just process creation. Stop leaves desktop windows alone to preserve user work.
It does not modify Pi/Paseo, SSH configuration, solver files, or the runtime image.
Dependencies: Windows OpenSSH/PowerShell, existing authenticated SSH alias,
Windows UI Automation for welcome-dialog dismissal, Slurm, and this module's
deployed `run.sh`. The native desktop is its consumer.

Inputs: `-Profile` JSON (default `config/paraview.local.json`) containing
`ssh_alias`, `remote_runtime`, `image`, `client_directory`, and `case_profile`.
The referenced case JSON supplies `case_directory`, `remote_workspace`, `partition`,
`cpus`, and `memory_mb`. Paths are absolute remotely; case_profile is project-relative.
Outputs: ignored `state/paraview/session/` job identity, host keys and tunnel logs.
No secret contents are read/copied. SSH identity paths come from `ssh -G`.
Compute host keys must already be known to the authenticated login node.

From the project root:

```powershell
./infrastructure/paraview/Manage-Session.ps1 -Action Check
./infrastructure/paraview/Manage-Session.ps1 -Action Start -Minutes 60
./infrastructure/paraview/Manage-Session.ps1 -Action Connect
./infrastructure/paraview/Manage-Session.ps1 -Action Open -Json
./infrastructure/paraview/Manage-Session.ps1 -Action Status
./infrastructure/paraview/Manage-Session.ps1 -Action Stop
```

Check is local read-only discovery. Start submits once and saves its job ID;
Connect can be retried while queued/starting, without submitting another job.
Connect verifies server readiness in the job log, pins the compute host key and
opens a loopback-only tunnel. It never probes pvserver with a synthetic client
connection, which could consume this single-client session. Launch ParaView and
use the supplied pvsc after Connect succeeds. Status reports job and local listener;
neither guarantees a healthy application protocol after a later network failure.
Stop cancels only the recorded job after validating its name/work directory, and
stops only the recorded matching SSH process. A one-hour walltime is the default;
the server also has a 15-minute no-client timeout and exits on client disconnect.
Keep this managed session singular; concurrent launcher invocations are unsupported.

Verification: PowerShell parse check, Check with the local profile, then an authorized
Start/Connect/Status cycle. Expect a RUNNING job, server waiting in its log, and an
owned loopback listener on 11111. Stop should remove only that job/tunnel.

Responsibility: a dedicated, headless-capable ParaView image for allocated case
preparation and expert pvserver sessions. Not a solver image or public service.

Inputs: official Linux binary archive, verified against Kitware's published
checksum; a pinned Debian base digest. Output: local Docker image / OCI archive,
then a versioned Apptainer SIF. Keep generated downloads, archives and locks in
ignored `state/paraview/`; host paths belong in ignored local profiles.

Dependencies: Docker/Buildx for local build, Apptainer and Slurm on the cluster.
The Debian base is pinned by digest through the Docker library mirror on Amazon
ECR Public after Docker Hub connections failed. Apt package versions are captured
in the built image, not independently locked; preserve the qualified SIF hash.
Dependents: worker extraction and optional native ParaView clients. Single-process
qualification comes first; bundled MPI must not be assumed ABI-compatible with
the site's MPI. No host MPI or scheduler libraries are required inside this image.

The `media` operation runs `guanlan.media.render` using the same read-only case
binding and headless backend. The media CLI deploys a code-only copy of run.sh to
its own request workspace, so preparation does not overwrite an active session.

Security: build context contains only this Dockerfile and public binary archive.
No credentials or case data in image layers. Bind cases read-only; bind a separate
Guanlan output directory read-write. Run computation only in explicit allocations.
pvserver must bind loopback and be reached through SSH; a connect ID is not an
authentication substitute. Do not expose its default all-interface listener.

Example (after archive checksum verification):

```sh
docker build --build-arg BASE_IMAGE=debian:bookworm-slim@sha256:... \
  -t guanlan-paraview:6.1.1 -f infrastructure/paraview/Dockerfile state/paraview
```

Use the pinned default base by omitting that illustrative override. Export with
`docker buildx build --output type=oci,dest=state/paraview/paraview.oci.tar ...`
using the same Dockerfile/context. Hash the archive, copy it into the dedicated
remote release's `imports/paraview.oci.tar`, then use `convert.sh check ROOT HASH`
before submitting `convert.sh build ROOT HASH` through Slurm. Conversion refuses
existing outputs; retain failed partials for diagnosis rather than overwriting.

`run.sh check IMAGE CASE WORKSPACE` prints the read-only invocation plan. The
`smoke`, `extract`, `qualify`, and `server` operations require SLURM_JOB_ID, read-only case
binding and a separate Guanlan workspace. Extraction passes remaining arguments
to the worker. Server mode listens only on the compute node's loopback: use SSH
through the login host to that node (if permitted), forwarding local 11111 to
compute 127.0.0.1:11111. Never substitute an all-interface listener when tunneling
fails. No live session is left running by qualification.
`qualify` runs the sphere check followed by the requested extraction inside one
container invocation, avoiding a second full `--unsquash` startup on this cluster.
Optional `GUANLAN_SCRATCH_ROOT` selects an existing scratch filesystem for temporary
expansion (at least 8 GiB free). Default is the dedicated workspace. A unique job
directory is created; Apptainer cleans its own contents, then the launcher removes
only the empty directory. Nonempty leftovers are reported, never recursively erased.
Import `guanlan.pvsc` into the matching native client after allocation and tunnel
are ready. It is deliberately manual: opening it does not submit a job, change a
case, or make a server publicly reachable.
`client-smoke.py OUTPUT.png` connects only to local forwarded port 11111, forces
remote rendering of a synthetic sphere, saves the returned image and disconnects.
It tests the client/server path, not CFD correctness or interactive performance.
`compare-slices.py OLD_MANIFEST NEW_MANIFEST CACHE` is a read-only numerical check
for equivalent triangle slices with identical point identities. It compares scalar
values after matching triangles by vertex IDs, allowing cell reorderings. NumPy
and Guanlan's integrity verifier are required. Different triangulations or duplicate
faces fail explicitly instead of being called equivalent. Output is JSON on stdout.

Discovery is read-only: `docker version`, `apptainer --version`, and official
release listings. Build/deploy are explicit mutations. Never update the existing
agent runtime to install visualization dependencies.

Verification: run `pvpython --version`, `pvserver --version`, and `smoke.py` with
`--force-offscreen-rendering --opengl-window-backend=OSMesa` inside an allocation.
Expect a sphere PNG and recorded OpenGL backend, then qualify native case fields
and slices separately. A sphere does not qualify a CFD reader or GPU performance.

As checked on 2026-09-22, official downloads list stable 6.1.1 and preview
6.2.0-RC2. The baseline uses stable 6.1.1, not an assumed final 6.2. Matching client
and server versions are required for the expert path.

Qualification completed on 2026-09-22: allocated Apptainer execution, OSMesa /
llvmpipe sphere rendering, a matched Windows client receiving a remote-rendered
image through a loopback SSH tunnel, and native OpenFOAM slice/reference extraction.
The test server exits on disconnect; no persistent allocation is part of delivery.
This does not qualify EGL/GPU, multiple MPI ranks, browser performance or a general
performance advantage. Private case details and observations remain in ignored state.

`Install-WindowsClient.ps1 -Archive ZIP -Destination D:\path\pv611` verifies the
published checksum and prints its plan by default; `-Apply` extracts into a new,
short directory without the archive's long top-level name. It rejects traversal,
non-D: destinations and existing outputs. It does not alter system installations,
PATH, file associations or registry settings. Verification: `bin/pvpython.exe
--version` and `bin/paraview.exe --version` must both report the pinned version.
