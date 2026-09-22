# Guanlan development rules

Read `README.md`, `docs/architecture.md`, and the owning module README before edits.
The product promise is: set up the view once, see it update, share it immediately.
Do not add scientific assessment, claims, health scores, or acceptance workflows.

Keep routine refresh deterministic and independent of inference. Preserve the
difference between attach-only access and explicitly authorized runtime extracts.
No rendering or sustained polling on HPC login nodes. No remote writes are
authorized by the existence of a host profile or a Slurm job ID.

Keep demo data visibly synthetic. Never describe the local demonstration URL as
a recipient-reachable deployment. Never treat stable file sizes or JSON statistics
as proof that a CFD dataset is complete and readable.

Run `./scripts/verify.ps1` from this directory. Keep generated files under this
project on D:. Update module docs and the dependency graph when interfaces change.
