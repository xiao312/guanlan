"""Strict, bounded media preset and manifest contracts (standard library only)."""
import copy
import hashlib
import math
import re

MAX_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 192


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', value):
        raise ValueError('expected a simple identifier (letters, digits, underscore, hyphen)')
    return value


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def label(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 160 or any(ord(c) < 32 for c in value):
        raise ValueError('labels must be 1-160 printable characters')
    return value


def validate(preset):
    p = copy.deepcopy(preset)
    if not isinstance(p, dict) or set(p) != {'version', 'title', 'case_label', 'times', 'size', 'blocks'} or p['version'] != 1:
        raise ValueError('expected version 1 preset: title, case_label, times, size, blocks')
    label(p['title']); label(p['case_label'])
    times = p['times']
    if not isinstance(times, list) or not 1 <= len(times) <= 24:
        raise ValueError('select 1-24 existing timesteps')
    if any(not isinstance(t, str) or not re.fullmatch(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', t) or not math.isfinite(float(t)) or float(t) <= 0 for t in times):
        raise ValueError('times must be positive numeric directory names')
    if any(float(a) >= float(b) for a, b in zip(times, times[1:])):
        raise ValueError('times must be unique and strictly increasing')
    size = p['size']
    if not isinstance(size, list) or len(size) != 2 or any(type(v) is not int for v in size) or not (320 <= size[0] <= 1920 and 240 <= size[1] <= 1080):
        raise ValueError('image size must be 320-1920 by 240-1080 pixels')
    if not isinstance(p['blocks'], list) or not 1 <= len(p['blocks']) <= 8:
        raise ValueError('select 1-8 blocks')
    ids, frames = set(), 0
    for b in p['blocks']:
        if not isinstance(b, dict) or not {'id', 'kind', 'title'} <= b.keys():
            raise ValueError('block requires id, kind, title')
        name(b['id']); label(b['title'])
        if b['id'] in ids:
            raise ValueError('duplicate block id')
        ids.add(b['id'])
        if b['kind'] not in ('geometry', 'mesh', 'slice'):
            raise ValueError('unsupported block kind')
        allowed = {'id', 'kind', 'title', 'camera', 'patches'} if b['kind'] != 'slice' else {'id', 'kind', 'title', 'camera', 'plane', 'offset', 'fields', 'palette', 'range'}
        if set(b) - allowed:
            raise ValueError('unknown block options: ' + str(set(b) - allowed))
        if b['kind'] == 'slice':
            if b.get('plane') not in ('xy', 'xz', 'yz') or not number(b.get('offset')) or not 0 < b['offset'] < 1:
                raise ValueError('slice needs xy/xz/yz plane and normalized offset strictly inside 0-1')
            fields = b.get('fields')
            if not isinstance(fields, list) or not 1 <= len(fields) <= 8:
                raise ValueError('slice requires 1-8 scalar fields')
            for field in fields: name(field)
            if len(set(fields)) != len(fields): raise ValueError('duplicate field')
            b.setdefault('palette', 'Viridis')
            if b['palette'] not in ('Viridis', 'Cool to Warm', 'Inferno (matplotlib)'):
                raise ValueError('unsupported palette')
            b.setdefault('range', 'data')
            r = b['range']
            if r != 'data' and (not isinstance(r, list) or len(r) != 2 or not all(number(v) for v in r) or r[0] >= r[1]):
                raise ValueError('range must be data or [minimum, maximum]')
            frames += len(fields) * len(times)
        else:
            patches = b.get('patches', [])
            if not isinstance(patches, list) or len(patches) > 128 or any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', v) for v in patches):
                raise ValueError('invalid patch selection')
            if len(set(patches)) != len(patches): raise ValueError('duplicate patch')
            frames += len(times)
        b.setdefault('camera', b.get('plane', 'xy'))
        if b['camera'] not in ('xy', 'xz', 'yz', 'isometric'):
            raise ValueError('unsupported camera preset')
    if frames > MAX_FRAMES: raise ValueError('preset exceeds 192 frames')
    return p


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_manifest(m):
    p = validate(m['preset'])
    frames = m['frames']
    expected = {(b['id'], f, t) for b in p['blocks'] for f in b.get('fields', ['']) for t in p['times']}
    actual, files, total = set(), {}, 0
    if not isinstance(frames, list) or len(frames) != len(expected): raise ValueError('incomplete frame set')
    for f in frames:
        key = (f['block'], f['field'], f['time'])
        if key in actual: raise ValueError('duplicate frame')
        actual.add(key)
        if not re.fullmatch(r'[a-f0-9]{64}\.png', f['file']) or f['file'] != f['sha256'] + '.png':
            raise ValueError('invalid content-addressed image name')
        if type(f['bytes']) is not int or not 0 < f['bytes'] <= MAX_BYTES: raise ValueError('invalid image size')
        if f['field']:
            for key in ('range', 'data_range'):
                r = f.get(key)
                if not isinstance(r, list) or len(r) != 2 or not all(number(v) for v in r) or r[0] > r[1]:
                    raise ValueError('invalid field range metadata')
            label(f['units'])
            plane = f.get('plane')
            if not isinstance(plane, dict) or any(not isinstance(plane.get(k), list) or len(plane[k]) != 3 or not all(number(v) for v in plane[k]) for k in ('origin', 'normal')):
                raise ValueError('invalid slice plane metadata')
        elif any(f.get(k) is not None for k in ('range', 'data_range', 'plane')):
            raise ValueError('non-field frame has scalar metadata')
        if f['file'] in files and files[f['file']] != f['bytes']: raise ValueError('inconsistent repeated image size')
        if f['file'] not in files:
            total += f['bytes']; files[f['file']] = f['bytes']
    if actual != expected or total > MAX_BYTES: raise ValueError('frame coverage or byte budget mismatch')
    return m
