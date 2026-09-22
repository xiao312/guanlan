"""Validate and package already extracted CFD data; never starts computation."""
import base64
import html
import json
import math
from pathlib import Path
import struct
import re

MAX_SCENE_BYTES = 64 * 1024 * 1024


def array_bytes(value, item_size, count):
    if not isinstance(value, str) or len(value) > MAX_SCENE_BYTES:
        raise ValueError('invalid encoded array')
    data = base64.b64decode(value, validate=True)
    if len(data) != item_size * count:
        raise ValueError('array length does not match declared topology')
    return data


def validate_scene(scene):
    if scene.get('schema_version') != 1 or not math.isfinite(scene['simulation_time']):
        raise ValueError('invalid scene version/time')
    for key in ('title', 'case_directory', 'coordinate_units'):
        if not isinstance(scene.get(key), str) or not 1 <= len(scene[key]) <= 4096:
            raise ValueError('invalid scene ' + key)
    datasets, blocks = scene['datasets'], scene['blocks']
    if not isinstance(datasets, dict) or not 1 <= len(datasets) <= 8 or not 1 <= len(blocks) <= 8:
        raise ValueError('scene block/dataset budget exceeded')
    if any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name) for name in datasets):
        raise ValueError('invalid dataset identifier')
    for data in datasets.values():
        points, cells = data['point_count'], data['cell_count']
        if type(points) is not int or type(cells) is not int or not 1 <= points <= 1000000 or not 1 <= cells <= 500000:
            raise ValueError('invalid topology counts')
        positions = array_bytes(data['points'], 4, points * 3)
        if not all(math.isfinite(v[0]) for v in struct.iter_unpack('<f', positions)):
            raise ValueError('non-finite coordinates')
        connectivity = base64.b64decode(data['polys'], validate=True)
        if len(connectivity) % 4:
            raise ValueError('invalid polygon encoding')
        indices = [v[0] for v in struct.iter_unpack('<I', connectivity)]
        cursor = 0
        for _ in range(cells):
            if cursor >= len(indices):
                raise ValueError('missing polygon')
            size = indices[cursor]
            if size < 3 or cursor + size >= len(indices):
                raise ValueError('invalid polygon size')
            if any(index >= points for index in indices[cursor+1:cursor+1+size]):
                raise ValueError('point index outside dataset')
            cursor += size + 1
        if cursor != len(indices):
            raise ValueError('extra polygon entries')
        if len(data['fields']) > 8:
            raise ValueError('field budget exceeded')
        for name, field in data['fields'].items():
            if not isinstance(name, str) or not 1 <= len(name) <= 128 or field['association'] != 'cell':
                raise ValueError('unsupported field name/association')
            values = array_bytes(field['values'], 8, cells)
            if not all(math.isfinite(v[0]) for v in struct.iter_unpack('<d', values)):
                raise ValueError('non-finite field values')
            low, high = field['range']
            if not all(math.isfinite(v) for v in (low, high)) or low > high:
                raise ValueError('invalid field range')
            actual_min = min(v[0] for v in struct.iter_unpack('<d', values))
            actual_max = max(v[0] for v in struct.iter_unpack('<d', values))
            if (actual_min, actual_max) != (low, high):
                raise ValueError('field range does not match its numerical values')
            for key in ('units', 'label'):
                if not isinstance(field[key], str) or len(field[key]) > 256:
                    raise ValueError('invalid field metadata')
    if len({b['id'] for b in blocks}) != len(blocks):
        raise ValueError('duplicate block IDs')
    for block in blocks:
        if not isinstance(block.get('id'), str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', block['id']):
            raise ValueError('invalid block identifier')
        if block['kind'] not in ('geometry', 'mesh', 'slice') or block['dataset'] not in datasets:
            raise ValueError('invalid block dataset/kind')
        if block['camera'] not in ('xy', 'xz', 'yz', 'isometric'):
            raise ValueError('invalid camera')
        if block['kind'] == 'slice' and block.get('field') not in datasets[block['dataset']]['fields']:
            raise ValueError('slice field missing')
    return scene


def snapshot_html(scene, bundle, prepared=None):
    raw = json.dumps(scene, allow_nan=False, separators=(',', ':')).encode()
    if len(raw) > MAX_SCENE_BYTES:
        raise ValueError('scene exceeds 64 MiB')
    validate_scene(scene)
    from guanlan.portable.assets import prepare_assets
    manifest, payloads = prepared or prepare_assets(scene)
    return prepared_html(manifest, payloads, bundle)


def prepared_html(manifest, payloads, bundle, runtime_url=None):
    """Embed an already selected, integrity-checked prepared store; no raw scene."""
    manifest = dict(manifest)
    import hashlib
    manifest['viewer_sha256'] = hashlib.sha256(bundle.encode()).hexdigest()
    manifest_json = json.dumps(manifest, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    embedded = ''.join('<script type="application/octet-stream" id="asset-' + key + '">' +
                       item['payload'] + '</script>' for key, item in payloads.items())
    assets = Path(__file__).parent
    template = (assets / 'template.html').read_text(encoding='utf-8')
    substitutions = {'__TITLE__': html.escape(manifest['title']),
                     '__STYLE__': (assets / 'viewer.css').read_text(encoding='utf-8'),
                     '__SCENE__': manifest_json, '__ASSETS__': embedded,
                     '__VIEWER__': bundle.replace('</script', '<\\/script')}
    # Single-pass substitution prevents metadata containing template markers from
    # triggering a second replacement. Metadata is never interpreted as markup.
    result = re.sub(r'__(?:TITLE|STYLE|SCENE|ASSETS|VIEWER)__', lambda match: substitutions[match[0]], template)
    if runtime_url is not None:
        if not re.fullmatch(r'runtime/[0-9a-f]{64}\.js',runtime_url):
            raise ValueError('runtime URL must be a local content-addressed script')
        result = result.replace('<script>'+substitutions['__VIEWER__']+'</script>',
                                '<script src="'+runtime_url+'"></script>')
        result = result.replace("script-src 'unsafe-inline'", "script-src 'self'")
    encoded = result.encode('utf-8')
    if len(encoded) > 32 * 1024 * 1024:
        raise ValueError('HTML exceeds the 32 MiB artifact budget')
    return encoded
