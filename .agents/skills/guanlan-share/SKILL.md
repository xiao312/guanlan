---
name: guanlan-share
description: Prepare CFD images and time sequences with ParaView on allocated resources, retrieve only rendered media, and assemble engineer-preset offline HTML blocks or MP4s. Use for repeatable sharing without an active ParaView session.
---

# Prepared CFD media

Resolve the Guanlan repository as three parents above this skill directory. Read
[media contract](../../../src/guanlan/media/README.md) and
[example preset](../../../examples/media-preset.json). Set `PYTHONPATH` to its
`src` directory and run `python -m guanlan.media --help` to inspect commands.
Use existing local profiles; never embed SSH identities or source paths in a
tracked preset. These commands are independent of the older live image service.

## Intent to preset

Map the engineer's requested blocks, fields, camera, plane and timesteps into a
validated JSON preset. Prefer geometry + original boundary mesh + requested slices
as a layout preset, not a mandatory format. Slice-only output is legitimate.
Select explicit settled times. A normalized plane offset is relative to source
bounds, not a physical distance; captions retain the physical origin/normal.

For comparison sequences prefer a user-approved fixed range. If `range:data` is
requested or used for discovery, state that each frame independently rescales.
Do not imply a color change alone proves a value change. Scalar-only cell fields
are currently supported; reject unsupported vector operations instead of guessing.

## Execute the smallest operation

| Need | Command | Boundary |
| --- | --- | --- |
| Validate plan | `check --profile PROFILE --preset PRESET` | Local, read-only |
| New prepared frames | `submit --profile PROFILE --preset PRESET --state STATE` | Authorized deployment + bounded Slurm job |
| Inspect completion | `status --state STATE` | Read-only queue/accounting |
| Retrieve prepared output | `fetch --state STATE` | Verified PNG/metadata transfer only |
| Offline block page | `package --state STATE --output PAGE.html` | Local assembly, no compute session |
| MP4 sequences | `video --state STATE --output VIDEO_DIR --ffmpeg EXE` | Optional local encoding, not plotting |
| Release unfinished job | `cancel --state STATE` | Only the recorded matching job |

Success is exit 0 with `ok:true`. Check before Submit. New preparation requires
user authorization unless already included in their request. Never retry an
ambiguous submission by creating another job; inspect the operation record and
queue. Failed/partial jobs must not replace a last-good snapshot.

## Verify and hand off

Require completed job, validated manifest, complete frame coverage, matching hashes,
and bounded transferred bytes. Inspect representative ParaView PNGs, including mesh
and each requested field. Check physical plane, time, range, units and labels.
Report rendered pixels separately from any browser testing; opening a PNG does not
test HTML controls. When browser control is available, verify field/timeline changes
and offline operation through that interface. Otherwise state the limitation.

These are images: local field switching only chooses already rendered frames.
Image zoom does not reveal new mesh detail. A new plane or camera requires separate
preparation. MP4 advances samples at uniform playback cadence; it does not interpolate
CFD time. ffmpeg may encode ParaView frames, never substitute Matplotlib for slicing
or field rendering.

Return the local artifact, case label/time coverage, bytes and qualification limits.
Do not publish it, upload it to Git, message recipients, or start a public endpoint
unless separately requested. Reuse existing prepared media for layout changes.
