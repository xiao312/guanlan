"""Bounded immutable preview generations and atomic document writes."""
import base64
import json
import re
import shutil
import time
import uuid
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.previews = self.root / 'previews'
        self.previews.mkdir(exist_ok=True)

    def commit(self, result):
        generation = uuid.uuid4().hex
        destination = self.previews / generation
        metadata = dict(result)
        metadata['generation'] = generation
        metadata['published_at'] = time.time()
        metadata['blocks'] = []
        total = 0
        decoded = []
        for item in result['blocks']:
            if not re.fullmatch(r'[a-z0-9-]{1,40}', item['id']):
                raise ValueError('invalid worker block ID')
            payload = base64.b64decode(item['png'], validate=True)
            if not payload.startswith(b'\x89PNG\r\n\x1a\n') or len(payload) > 2 * 1024 * 1024:
                raise ValueError('worker returned an invalid or oversized PNG')
            total += len(payload)
            if total > 16 * 1024 * 1024:
                raise ValueError('page exceeds 16 MiB preview budget')
            decoded.append((item['id'], payload))
            metadata['blocks'].append({k: v for k, v in item.items() if k != 'png'})
        destination.mkdir()
        for block_id, payload in decoded:
            (destination / (block_id + '.png')).write_bytes(payload)
        write_json(self.root / 'preview.json', metadata)
        generations = sorted((p for p in self.previews.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in generations[2:]:
            # Only generated, validated UUID directories within this explicit cache.
            if re.fullmatch(r'[a-f0-9]{32}', old.name) and old.resolve().parent == self.previews:
                shutil.rmtree(old)
        return metadata

    def image(self, generation, block_id):
        if not re.fullmatch(r'[a-f0-9]{32}', generation) or not re.fullmatch(r'[a-z0-9-]{1,40}', block_id):
            raise ValueError('invalid image identifier')
        return (self.previews / generation / (block_id + '.png')).read_bytes()
