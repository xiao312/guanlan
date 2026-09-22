# Minimal prepared-asset delivery

Prepare beside the CFD case; select before transferring. Raw scene JSON remains
an optional debug/import format, not the production transfer unit.

## Source preparation

Deploy the Python package to a dedicated worker workspace. Inside an explicitly
authorized Slurm allocation, with ParaView's Python and the package on PYTHONPATH:

```sh
pvpython -m guanlan.worker.extract --case /path/to/case \
  --workspace /path/to/guanlan --output /path/to/guanlan/prepared \
  --title Example --fields p T --planes xy xz --slice-only --prepared
```

`--time-name` pins a completed output. `--offset` chooses a normalized plane
position. `--audit-scalars` checks supported native scalar arrays against the
reader's internal-cell multiset; this does not prove cell-position correspondence.
Slices preserve cell-associated values, not interpolated colors. Non-finite
fields and unsupported native-audit formats fail explicitly. No case writes.
For legacy files without architecture metadata, the explicit `--legacy-lsb64`
audit profile is available. Reader dtype and native-to-reader rounding are recorded:
Float64 asset storage does not imply native Float64 precision. The audit checks
both exact native equality and exact equality after the reader's declared cast.

The source stores `latest.json`, immutable `frames/<id>.json` and independently
compressed `assets/<id>.bin.gz`. Its 256 MiB quota fails publication rather than
silently deleting frames. Only deliberate selected fields/planes are extracted.
Source history also stops at 256 frame manifests; archival remains explicit.
Geometry/exterior is optional; a full geometry+mesh preset still exists.

## Select, plan, retrieve

From the repository root after building the viewer:

```powershell
$env:PYTHONPATH='src'
python -m guanlan.prepared --host cluster-alias --store /path/to/guanlan/prepared --select xz:p --cache state/cache --output state/xz-pressure.html --check
# Omit --check to retrieve and package.
```

`--select xz:p,T` explicitly includes local switching between those two fields.
The first selected field is the initial display; remaining fields are optional
local switching capabilities, independently retrieved in the connected viewer.
`--select geometry: mesh:` chooses only context geometry and original edges when
those blocks were prepared. Unsupported regions/history are not synthesized.

The dry run reads metadata and validates local cache bytes, but transfers no
binary assets or writes files. Actual retrieval uses one bounded SSH stream for
all missing immutable gzip files, framed by declared lengths and verified hashes.
Reopening revalidates metadata; binary transfer is zero only while valid cached
assets remain. No retrieval operation invokes ParaView or submits a Slurm job.

Reports distinguish metadata, compressed transfer, retained compressed assets,
decoded arrays, runtime bundle and output HTML bytes. Counts exclude SSH/HTTP
protocol framing. A self-contained HTML necessarily repeats the viewer runtime.
`retained_bytes` is the selected compressed working set; actual cache occupancy
including reusable unselected assets is `cache_total_compressed_bytes`.

## Offline and connected adapters

The requested output HTML includes exactly the selected dependencies. It works
offline. `state/cache/index.html` uses the same manifest but fetches individual
gzip files on demand. Serve it with:

```powershell
python -m guanlan.prepared.serve --root state/cache --port 8767
```

This server is loopback-only, read-only, and performs no extraction. Assets are
private-cacheable; manifests are no-store. Gzip is a file codec, not an HTTP
Content-Encoding, so the client decompresses once. This is not recipient-facing
hosting, an authenticated service, or automatic live-frame following.
Connected HTML references a separately cached content-addressed viewer script,
so frame reloads need not repeat the runtime. Keep at most two runtime versions
(4 MiB each) locally; this budget is separate from numerical assets.

## Identity, integrity and resource limits

- Asset IDs hash dtype, NUL separator and exact canonical numerical bytes.
- Geometry IDs hash ordered point/connectivity asset IDs; fields bind to them
  with association, tuple count and components. Equal counts alone are insufficient.
- Frame IDs identify a preparation; camera changes do not change numerical IDs.
- Local compressed-cache quota defaults to 256 MiB. Only unselected content is
  evicted; at most 512 numerical assets are retained. Offline exports are
  user-owned artifacts, outside that cache quota.
- Browser selected arrays are capped at 64 MiB and decoded serially. Hash and
  length checks reject recompressed same-length corruption. The cap excludes
  temporary copies, JavaScript bookkeeping and GPU buffers.
- This iteration opens frozen manifests, with at most eight blocks. It does not
  accumulate frames. A new frame requires a page reload; continuous generation
  updates and offscreen-view disposal remain separate work, not claimed complete.

No precision reduction, scalar resampling or spatial LOD is introduced. Native
cell ordering still depends on a qualified preparer; content identity is not
proof of scientific correctness or permission to retrieve confidential data.

## Verification

`./scripts/verify.ps1` tests selection, field/topology bindings, same-length
corruption rejection, cache quotas, reuse across synthetic frames and the
read-only binary endpoint. `node viewer/check-loader.mjs` exercises the production
loader without a browser. Actual browser/GPU performance remains a separate gate.
