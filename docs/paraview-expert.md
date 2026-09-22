# ParaView expert path

Use native ParaView + allocated pvserver for open-ended filters, arbitrary slice
positions and access to source fields. Use Guanlan assets for deliberately prepared
views that remain useful without a running cluster session. Neither path is assumed
faster or lower-bandwidth: remote images can be cheaper than numerical assets.

## Runtime boundary

The reproducible baseline is ParaView 6.1.1 with a Debian/Mesa userspace in a
dedicated Apptainer image. See [runtime module](../infrastructure/paraview/README.md)
for build, checksum, read-only discovery and allocation-only commands. Keep it
separate from solver images and coding-agent runtimes. As checked on 2026-09-22,
the official listing has 6.1.1 stable and 6.2.0-RC2 preview; no final 6.2 binary
was present in that listing.

Sources: [release announcement](https://discourse.paraview.org/t/paraview-6-1-1-released/17582)
and [download directory](https://www.paraview.org/files/v6.1/).

## Connection workflow

On Windows, use `infrastructure/paraview/Manage-Session.ps1`: `-Action Check`
prints the plan, `-Action Start -Minutes 60` submits the allocation, and
`-Action Connect` establishes the tunnel once the server is ready. Retry Connect
if the allocation is queued or the container is still starting. `-Action Status`
reports the recorded job/listener; `-Action Stop` ends only that managed session.
Importing the pvsc alone does **not** start either a job or a tunnel.

1. Submit `run.sh server IMAGE CASE WORKSPACE` through a bounded Slurm allocation.
   The case is read-only; the server binds compute loopback, not 0.0.0.0.
2. Verify the assigned compute host key through the existing authenticated cluster
   route. Keep per-project known-host state ignored; never disable checking.
3. Forward workstation loopback port 11111 through SSH to compute loopback 11111.
   Reuse the existing SSH identity by reference; do not copy keys into the project.
4. Open the matching native client and import `infrastructure/paraview/guanlan.pvsc`.
   It is manual and assumes the allocation/tunnel already exist.
5. Open the shadow case marker in the dedicated workspace, or load the prepared
   reference `.pvsm`. The original case needs no marker or configuration edits.
6. Disconnect and close the owned tunnel; observe the server job ending. Walltime
   remains a hard resource bound if a client or connection fails.

Renderer flags: [ParaView command-line guide](https://docs.paraview.org/en/latest/UsersGuide/commandLineArguments.html).
The baseline explicitly uses OSMesa software rendering and a single process.
GPU/EGL and distributed MPI are separate qualifications, not inferred capabilities.

## Field comparison rules

Pin case, timestep, physical plane position, cell/point association, interpolation,
palette and numerical range. A camera preset does not move a prepared slice.
For a wedge aligned along X, XY and XZ may be very different physical sections.

Native-value multisets establish neither spatial placement nor appearance.
The worker records both multiset and ordered-array comparisons against native
processor/local-cell order. Reader Float32 rounding is recorded explicitly.
`--reference-images` creates direct ParaView PNGs and state from the same source
slice, without the custom browser renderer or Matplotlib. These are a presentation
reference, not browser pixel-equality or scientific checks.

Measure cold allocation/read time separately from warm interactions and from
opening an already prepared artifact. Reference-image generation is timed
separately from reading and slice export. Browser/GPU and bandwidth comparisons
remain unclaimed until measured with equivalent content.
