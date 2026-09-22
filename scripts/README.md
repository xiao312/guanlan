# Local entry points

`verify.ps1` also checks media contracts, packaging, archive integrity, and media
JavaScript syntax; this does not claim browser interaction testing.

Responsibility: launch/verify the fixture and perform opt-in read-only discovery.
Non-goals: environment installation or solver case edits. `live.ps1` is the explicit
real-case path: deploy isolated Guanlan code and request a bounded allocation;
`-Check` prints the plan without connecting. Other scripts stay local/read-only.

Inputs: `demo.ps1 [-Check] [-Port 8765]`; `verify.ps1`; and
`discover.ps1 -Profile <JSON> [-Execute]`. Demo's check path validates recipes
without starting a server. Discovery defaults to printing its command plan as
JSON. Executing discovery outputs Slurm's human-readable and pipe-delimited rows.

Dependencies: Python 3.12+ for demo/tests, PowerShell, SSH for executed discovery.
Dependents: developers and project README. Scripts set Python bytecode off and
resolve project paths relative to themselves. Nothing is installed on C:.
The live worker copies code only to its configured Guanlan remote workspace.

Security: discovery accepts only simple SSH aliases and positive integer job IDs,
uses batch mode and a connection timeout, and performs no remote writes. Secrets
are supplied only by existing SSH configuration. Demo binds loopback only.

Example: `./scripts/demo.ps1 -Check`. Verification: `./scripts/verify.ps1`; expect
all unit tests to pass and recipe validation to print the three view identifiers.
