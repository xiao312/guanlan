"""Content-addressed prepared assets, independent of HTML or transport."""
import base64
import gzip
import hashlib
import json
import struct


def original_edges(polygons):
    indices = [v[0] for v in struct.iter_unpack('<I', polygons)]
    pairs = set()
    cursor = 0
    while cursor < len(indices):
        count = indices[cursor]
        face = indices[cursor + 1:cursor + count + 1]
        for i, a in enumerate(face):
            b = face[(i + 1) % count]
            if a != b:
                pairs.add((min(a, b), max(a, b)))
        cursor += count + 1
    return b''.join(struct.pack('<III', 2, a, b) for a, b in sorted(pairs))


def prepare_assets(scene):
    assets = {}

    def add(raw, dtype):
        digest = hashlib.sha256(dtype.encode() + b'\0' + raw).hexdigest()
        if digest not in assets:
            zipped = gzip.compress(raw, mtime=0)
            assets[digest] = {'encoding': 'gzip+base64', 'dtype': dtype,
                             'decoded_bytes': len(raw), 'compressed_bytes': len(zipped),
                             'payload': base64.b64encode(zipped).decode('ascii')}
        return digest

    datasets = {}
    for name, source in scene['datasets'].items():
        polygons = base64.b64decode(source['polys'])
        dataset = {key: source[key] for key in ('point_count', 'cell_count')}
        dataset.update(points=add(base64.b64decode(source['points']), 'Float32Array'),
                       polys=add(polygons, 'Uint32Array'), fields={})
        if any(b['kind'] == 'mesh' and b['dataset'] == name for b in scene['blocks']):
            edges = original_edges(polygons)
            dataset.update(edges=add(edges, 'Uint32Array'), edge_count=len(edges) // 12)
        for field_name, field in source['fields'].items():
            dataset['fields'][field_name] = {k: v for k, v in field.items() if k != 'values'}
            dataset['fields'][field_name]['asset'] = add(base64.b64decode(field['values']), 'Float64Array')
        datasets[name] = dataset
    manifest = {k: v for k, v in scene.items() if k not in ('datasets', 'schema_version')}
    manifest.update(schema_version=2, datasets=datasets,
                    assets={k: {p: v for p, v in item.items() if p != 'payload'} for k, item in assets.items()},
                    fixture_sha256=hashlib.sha256(json.dumps(scene, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                    coverage='Frozen exterior surface and prepared slices only; no arbitrary new planes.',
                    fidelity='Original extracted polygons and cell values; no decimation or scalar interpolation.')
    return manifest, assets
