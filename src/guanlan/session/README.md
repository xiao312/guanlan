# Case session and compute transport

Runs one explicitly configured warm ParaView worker via SSH and `srun`. The worker
reads the case in its existing location; only PNG previews and metadata cross SSH.
No case data is copied. No heavy work runs on the login node. Allocation is bounded
by CPU, memory, walltime and idle timeout. SSH uses the user's existing credentials.

Input: ignored local JSON profile: case_id, title, ssh_alias, case_directory,
remote_workspace, pvpython, partition, cpus, memory_mb, walltime_minutes,
idle_seconds, refresh_seconds. All shell arguments are quoted; profiles are local
trusted configuration, never supplied by the browser. New worker files are deployed
only beneath the specified Guanlan workspace, never to the simulation directory.

Local request queue keeps the newest document while one render is active. When no
browser polls, the worker becomes idle and exits. An explicit reconnect starts a
new allocation. Last-good previews remain available when reads or SSH fail. Images
and page edits persist under project `state/`; the latest two generations only are
retained. Session state identifies preview and requested revisions separately.
The owner can reconnect from the page after exit; a running allocation cannot be
duplicated. Launch/deployment runs independently of cached-page HTTP delivery.

Dependencies: casepage, worker, SSH/SCP, Slurm. Dependents: live web server.
Example: `python -m guanlan.live --profile config/live.local.json --check` prints a
read-only launch plan. Without `--check`, deploys worker source and allocates compute.
Verification: unit tests for validation/coalescing and real-cluster qualification.
