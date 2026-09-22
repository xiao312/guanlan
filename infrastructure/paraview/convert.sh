#!/usr/bin/env bash
# Convert a verified OCI archive under a dedicated release root; never overwrite.
set -euo pipefail
action=${1:?check or build}
release_root=$(realpath -e "${2:?existing release directory}")
archive_sha=${3:?expected archive SHA256}
[[ "$release_root" = */paraview/6.1.1 && "$archive_sha" =~ ^[a-f0-9]{64}$ ]] || exit 2
archive="$release_root/imports/paraview.oci.tar"
image="$release_root/images/paraview.sif"
[[ -f "$archive" && ! -e "$image" && ! -e "$image.partial" ]] || {
  echo 'Archive missing or target already exists; inspect before continuing' >&2; exit 2;
}
if [[ "$action" = check ]]; then
  printf 'Verify %s, then build %s inside Slurm\n' "$archive" "$image"
  exit 0
fi
[[ "$action" = build && -n "${SLURM_JOB_ID:-}" ]] || {
  echo 'Build requires an explicit allocation' >&2; exit 2;
}
module load apps/apptainer/1.3.4
export APPTAINER_TMPDIR="$release_root/build-tmp"
export APPTAINER_CACHEDIR="$release_root/build-cache"
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"
printf '%s  %s\n' "$archive_sha" "$archive" | sha256sum -c -
apptainer build --disable-cache "$image.partial" "oci-archive://$archive"
mv -- "$image.partial" "$image"
sha256sum "$image"
