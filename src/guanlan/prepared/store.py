"""Bounded gzip store, immutable content verification and atomic publication."""
import base64
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import struct
from guanlan.prepared import asset_id

DEFAULT_QUOTA = 256 * 1024 * 1024


def verify(key, meta, compressed):
    asset_id(key)
    size = meta['decoded_bytes']
    if type(size) is not int or not 0 < size <= 64*1024*1024:
        raise ValueError('decoded size exceeds budget')
    if len(compressed) != meta['compressed_bytes']:
        raise ValueError('compressed size mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(size + 1)
    if len(raw) != size:
        raise ValueError('decoded size mismatch')
    dtype = meta['dtype']
    widths = {'Float32Array':4, 'Uint32Array':4, 'Float64Array':8}
    if dtype not in widths or size % widths[dtype]:
        raise ValueError('invalid array type/length')
    if hashlib.sha256(dtype.encode() + b'\0' + raw).hexdigest() != key:
        raise ValueError('content hash mismatch')
    if dtype != 'Uint32Array' and not all(math.isfinite(v[0]) for v in struct.iter_unpack('<f' if widths[dtype]==4 else '<d',raw)):
        raise ValueError('non-finite prepared numerical array')
    return raw


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.pending')
    temporary.write_bytes(data)
    temporary.replace(path)


def publish(scene, root, quota=DEFAULT_QUOTA):
    from guanlan.portable import validate_scene
    from guanlan.portable.assets import prepare_assets
    manifest, assets = prepare_assets(validate_scene(scene))
    manifest['frame_id'] = manifest['fixture_sha256']
    for meta in manifest['assets'].values():
        meta.pop('encoding', None)
    root = Path(root)
    if len(list((root/'frames').glob('*.json'))) >= 256:
        raise ValueError('source frame-count quota reached; retain/archive frames explicitly')
    existing = sum(p.stat().st_size for p in root.rglob('*') if p.is_file()) if root.exists() else 0
    added = sum(item['compressed_bytes'] for key,item in assets.items() if not (root/'assets'/f'{key}.bin.gz').exists())
    encoded = json.dumps(manifest, allow_nan=False, separators=(',', ':')).encode()
    if existing + added + 2*len(encoded) > quota:
        raise ValueError('prepared store quota exceeded; retain/archive frames explicitly')
    for key, item in assets.items():
        path = root/'assets'/f'{key}.bin.gz'
        content = base64.b64decode(item['payload'])
        verify(key, item, content)
        if path.exists():
            verify(key, item, path.read_bytes())
        else:
            atomic(path, content)
    atomic(root/'frames'/f'{manifest["frame_id"]}.json', encoded)
    atomic(root/'latest.json', encoded)
    return manifest


def valid_cached(root, manifest):
    result = set()
    for key, meta in manifest['assets'].items():
        path = Path(root)/'assets'/f'{asset_id(key)}.bin.gz'
        try:
            if path.stat().st_size != meta['compressed_bytes']:
                continue
            verify(key, meta, path.read_bytes())
            result.add(key)
        except (OSError, ValueError, EOFError):
            continue
    return result


def reserve(root, chosen, quota, max_assets=512):
    """Evict only unselected cache objects; never source data or selected assets."""
    directory = Path(root)/'assets'
    if directory.exists() and directory.resolve().parent != Path(root).resolve():
        raise ValueError('cache assets directory must not redirect outside its root')
    wanted = chosen['assets']
    if len(wanted)>max_assets:
        raise ValueError('selection exceeds cache asset-count quota')
    required = sum(item['compressed_bytes'] for item in wanted.values())
    if required > quota:
        raise ValueError('selected assets exceed local compressed-cache quota')
    files = list(directory.glob('*.bin.gz')) if directory.exists() else []
    retained = sum(p.stat().st_size for p in files if p.name[:-7] not in wanted)
    unselected_count = sum(p.name[:-7] not in wanted for p in files)
    evicted = []
    for path in sorted(files, key=lambda p:p.stat().st_mtime):
        if retained + required <= quota and unselected_count + len(wanted) <= max_assets:
            break
        if path.name[:-7] in wanted:
            continue
        if path.is_symlink():
            raise ValueError('refusing to evict redirected cache entries')
        asset_id(path.name[:-7])
        retained -= path.stat().st_size
        unselected_count -= 1
        evicted.append(path.name)
        path.unlink()
    return evicted
