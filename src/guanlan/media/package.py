"""Offline media blocks. Only explicitly safe presentation metadata is embedded."""
import base64
import html
import json
import re
from pathlib import Path
from guanlan.media.contract import MAX_BYTES, digest, validate_manifest
from guanlan.media.remote import read_json


def verified_frames(state):
    state = Path(state)
    manifest = validate_manifest(read_json(state/'manifest.json'))
    payloads = {}
    for frame in manifest['frames']:
        if frame['file'] in payloads: continue
        path = state/'frames'/frame['file']
        if path.is_symlink() or path.stat().st_size != frame['bytes']: raise ValueError('local frame size/path mismatch')
        data = path.read_bytes()
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or digest(data) != frame['sha256']: raise ValueError('local frame hash mismatch')
        payloads[frame['file']] = data
    return manifest, payloads


def package(state, output, videos=None):
    output = Path(output)
    if output.exists(): raise ValueError('output exists; choose a new snapshot path')
    manifest, payloads = verified_frames(state)
    # Do not embed arbitrary upstream keys, metrics, source paths, or operation records.
    public = {'preset': manifest['preset'], 'frames': [{key: f[key] for key in
              ('block', 'field', 'time', 'file', 'range', 'data_range', 'units', 'plane')} for f in manifest['frames']]}
    encoded = {key: 'data:image/png;base64,'+base64.b64encode(value).decode() for key, value in payloads.items()}
    clips, video_bytes = {}, 0
    if videos:
        index = read_json(Path(videos)/'videos.json')
        if index['preset'] != manifest['preset']: raise ValueError('video preset does not match image preset')
        expected = {(b['id'], f) for b in manifest['preset']['blocks'] for f in b.get('fields', [''])}
        seen = set()
        for clip in index['videos']:
            key = (clip['block'], clip['field'])
            if key not in expected or key in seen: raise ValueError('unexpected/duplicate video')
            seen.add(key)
            filename = key[0]+('-'+key[1] if key[1] else '')+'.mp4'
            path = Path(videos)/filename
            if clip['file'] != filename or path.is_symlink() or path.stat().st_size != clip['bytes']:
                raise ValueError('video file/size mismatch')
            video_bytes += clip['bytes']
            if video_bytes + sum(map(len, payloads.values())) > MAX_BYTES: raise ValueError('combined media exceeds budget')
            content = path.read_bytes()
            if digest(content) != clip['sha256']: raise ValueError('video hash mismatch')
            clips['|'.join(key)] = 'data:video/mp4;base64,'+base64.b64encode(content).decode()
        if seen != expected: raise ValueError('incomplete video coverage')
    data = json.dumps(dict(public, images=encoded, videos=clips), ensure_ascii=True, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (Path(__file__).with_name('template.html')).read_text(encoding='utf-8')
    javascript = (Path(__file__).with_name('viewer.js')).read_text(encoding='utf-8')
    replacements = {'__TITLE__': html.escape(public['preset']['title']), '__VIEWER__': javascript, '__DATA__': data}
    page = re.sub(r'__TITLE__|__VIEWER__|__DATA__', lambda match: replacements[match[0]], template).encode()
    if len(page) > MAX_BYTES*1.4 + 128*1024: raise ValueError('HTML exceeds packaging budget')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream: stream.write(page)
    return {'output': str(output), 'html_bytes': len(page), 'png_bytes': sum(map(len, payloads.values())),
            'video_bytes': video_bytes, 'frames': len(manifest['frames'])}
