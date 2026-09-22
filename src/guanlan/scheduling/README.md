# Latest-first preview scheduling

Responsibility: bound pending work to the latest request for one view. Non-goals:
threads, Slurm allocation, worker execution, exports, or deleting solver outputs.

API: `LatestFirst.submit(request)`, `start()`, `finish()`, and `pending`/`active`.
Inputs are caller-owned request identities; outputs are the selected request.
Submit replaces obsolete pending work; it does not cancel active work. Caller must
serialize access and use one instance per view. No persistence or secrets.
Dependencies: standard library only. Dependents: tests now, future coordinator.

Example: submit A, start A, submit B, submit C, finish A, start C.
Verification: `./scripts/verify.ps1`; skipped B never runs and active A is retained.
