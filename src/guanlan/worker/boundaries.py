"""Read bounded patch dictionaries, never points/faces or full field files."""
import gzip
import re
from guanlan.worker.readiness import partition_paths


def parse_boundary(text):
    patches = {}
    for match in re.finditer(r'(?:"([^"\n]+)"|([\w.-]+))\s*\{([^{}]*)\}', text):
        body = match[3]
        kind = re.search(r'\btype\s+([\w]+)\s*;', body)
        count = re.search(r'\bnFaces\s+(\d+)\s*;', body)
        if kind and count:
            patches[match[1] or match[2]] = {'type': kind[1], 'faces': int(count[1])}
    if not patches:
        raise ValueError('boundary dictionary has no supported patch records')
    return patches


def physical_boundaries(case):
    physical, processor_faces = {}, 0
    for partition in partition_paths(case):
        path = partition / 'constant/polyMesh/boundary'
        opener = open
        if not path.exists():
            path = path.with_suffix('.gz')
            opener = gzip.open
        with opener(path, 'rt', encoding='ascii') as stream:
            text = stream.read(256 * 1024 + 1)
        if len(text) > 256 * 1024:
            raise ValueError('boundary dictionary exceeds metadata budget')
        for name, patch in parse_boundary(text).items():
            if patch['type'].startswith('processor'):
                processor_faces += patch['faces']
            else:
                physical[name] = physical.get(name, 0) + patch['faces']
    return physical, processor_faces
