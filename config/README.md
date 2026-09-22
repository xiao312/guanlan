# Machine configuration

Responsibility: describe management discovery and explicit live-worker profiles.
Configuration alone does not authorize deployment, allocation, or solver edits.
No credentials or solver configuration changes belong here.

Schema: `schema_version: 1`, `ssh_alias` (existing SSH config name), and `job_ids`
(one to twenty positive Slurm job numbers). `scnet.example.json` is sanitized;
`scnet.local.json` stores this machine's actual alias and sample IDs and is ignored.
No key material, credentials, or connection tokens belong in these files.

`cases.example.json` documents the separate inventory shape: observation date,
SSH alias, and cases with job ID, solver family, observed state, run directory and
optional case directory. `cases.local.json` contains the actual observed paths.
This inventory is documentation for future adapters, not an executable connection
or rendering configuration; `discover.ps1` accepts only the Slurm profile above.

Dependency: existing SSH client/config and Slurm on the selected remote endpoint.
Dependent: `scripts/discover.ps1`. No runtime dependency on the demo.

Example/verification: `./scripts/discover.ps1 -Profile config/scnet.example.json`
prints a read-only plan without connecting. Add `-Execute` only to execute the
listed `squeue`/`sacct` queries. It never reads entire case datasets or changes jobs.

`live.example.json` documents the worker profile. `live.local.json` records the
selected real case and bounded allocation. Schema and validation live in
`src/guanlan/session/profile.py`; see that module's README. `scripts/live.ps1
-Check` validates it and prints the exact launch command without remote writes.
