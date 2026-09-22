# Prepared asset delivery

Select block/field dependencies, publish immutable compressed arrays near the
source, and retrieve only missing validated assets into a bounded local cache.
No CFD reading, scheduler submission, inference or rendering in this module.

Inputs: v2 manifest; selections map block IDs to fields (empty for geometry/mesh).
Outputs: selected manifest, required/missing IDs, byte counts, frames and assets.
Geometry identity binds ordered coordinates/connectivity; fields declare that
binding and tuple count. Frame identity is separate. Codec is gzip; HTML adds
base64. Preserve prepared Float32 coordinates and Float64 fields.

Dependencies: standard library, portable validation/assets/HTML adapter.
Dependents: worker.extract, transfer CLI, offline packager, read-only server.
Source stores fail at quota; local caches evict only unselected immutable assets.
Oversized selections fail. Received/cached bytes require hash and length checks.

Security: IDs are not authorization. Existing SSH aliases provide access; only
configured prepared stores are read. Metadata can contain private case paths.
The optional HTTP server binds loopback only, is read-only, and is not public
hosting. No credentials, automatic scheduler requests or solver writes.

Example: `python -m guanlan.prepared --store state/prepared --select xy:p
--cache state/cache --output state/slice.html --check`. Add `--host cluster-alias`
for remote prepared files. Omit --check to retrieve and package. Serve connected
assets with `python -m guanlan.prepared.serve --root state/cache --port 8767`.

Verification: `./scripts/verify.ps1` covers selection, stable IDs, integrity,
bindings and quotas. Browser/GPU qualification is separate. Source manifests are
published last. No continuous frame polling or arbitrary new extraction endpoint.
