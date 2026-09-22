#!/usr/bin/env bash
# Explicit allocation-only invocation. check prints the command without running it.
set -euo pipefail
mode=${1:?check, smoke, extract, qualify or server}
image=${2:?absolute SIF path}
case_dir=${3:?absolute read-only case directory}
workspace=${4:?absolute Guanlan workspace}
shift 4
[[ "$image" = /* && -f "$image" ]] || { echo 'SIF must exist at an absolute path' >&2; exit 2; }
case_dir=$(realpath -e "$case_dir")
workspace=$(realpath -e "$workspace")
[[ "$workspace" = */guanlan/* && "$workspace" != "$case_dir" && "$workspace" != "$case_dir/"* && "$case_dir" != "$workspace/"* ]] || {
  echo 'A separate existing Guanlan workspace is required' >&2; exit 2;
}
command=(apptainer exec --cleanenv --unsquash --no-home
  --bind "$case_dir:$case_dir:ro" --bind "$workspace:$workspace:rw"
  --env "SLURM_JOB_ID=${SLURM_JOB_ID:-}"
  --env "PYTHONPATH=$workspace/src" --env OMP_NUM_THREADS=2 --env LP_NUM_THREADS=2
  "$image")
case "$mode" in
  check) printf '%q ' "${command[@]}"; printf '\n'; exit 0 ;;
  smoke) command+=(pvpython --no-mpi --force-offscreen-rendering --opengl-window-backend=OSMesa "$workspace/smoke.py" "$workspace/smoke") ;;
  extract) command+=(pvpython --no-mpi --force-offscreen-rendering --opengl-window-backend=OSMesa -m guanlan.worker.extract
    --case "$case_dir" --workspace "$workspace" "$@") ;;
  qualify) command+=(bash -c 'set -e; workspace=$1; shift; pvpython --no-mpi --force-offscreen-rendering --opengl-window-backend=OSMesa "$workspace/smoke.py" "$workspace/smoke"; exec pvpython --no-mpi --force-offscreen-rendering --opengl-window-backend=OSMesa -m guanlan.worker.extract "$@"'
    guanlan-qualify "$workspace" --case "$case_dir" --workspace "$workspace" "$@") ;;
  server) command+=(pvserver --no-mpi --bind-address=127.0.0.1 --server-port=11111
    --timeout=15 --force-offscreen-rendering --opengl-window-backend=OSMesa) ;;
  media) command+=(pvpython --no-mpi --force-offscreen-rendering --opengl-window-backend=OSMesa -m guanlan.media.render
    --case "$case_dir" --workspace "$workspace" "$@") ;;
  *) echo 'Unknown operation' >&2; exit 2 ;;
esac
[[ -n "${SLURM_JOB_ID:-}" ]] || { echo 'Submit through Slurm; no login-node computation' >&2; exit 2; }
if ! command -v apptainer >/dev/null; then module load apps/apptainer/1.3.4; fi
scratch_root=${GUANLAN_SCRATCH_ROOT:-$workspace}
scratch_root=$(realpath -e "$scratch_root")
available_kib=$(df -Pk "$scratch_root" | awk 'NR==2 {print $4}')
[[ "$available_kib" =~ ^[0-9]+$ && "$available_kib" -ge 8388608 ]] || {
  echo 'Runtime expansion needs a scratch filesystem with at least 8 GiB free' >&2; exit 2;
}
export APPTAINER_TMPDIR
APPTAINER_TMPDIR=$(mktemp -d "$scratch_root/guanlan-${SLURM_JOB_ID}.XXXXXX")
export APPTAINER_CACHEDIR="$workspace/apptainer-cache"
mkdir -p "$APPTAINER_CACHEDIR"
trap 'rmdir -- "$APPTAINER_TMPDIR" 2>/dev/null || echo "Inspect retained runtime scratch: $APPTAINER_TMPDIR" >&2' EXIT
"${command[@]}"
