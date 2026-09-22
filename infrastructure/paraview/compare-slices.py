"""Read-only cross-version triangle/field correspondence check on frozen assets."""
import json
import sys
from pathlib import Path
import numpy as np
from guanlan.prepared.store import verify


def array(manifest, key, cache, dtype):
    raw = verify(key, manifest['assets'][key], (cache/'assets'/(key+'.bin.gz')).read_bytes())
    return np.frombuffer(raw, dtype=dtype)


def canonical_triangles(manifest, dataset, cache):
    values = array(manifest, dataset['polys'], cache, '<u4')
    if len(values) != dataset['cell_count']*4:
        raise ValueError('Only pure triangle fixtures are supported')
    values = values.reshape(-1,4)
    if not np.all(values[:,0] == 3):
        raise ValueError('Non-triangle topology')
    vertices = np.sort(values[:,1:], axis=1)
    order = np.lexsort((vertices[:,2],vertices[:,1],vertices[:,0]))
    canonical = vertices[order]
    if np.any(np.all(canonical[1:] == canonical[:-1], axis=1)):
        raise ValueError('Duplicate triangles prevent unambiguous correspondence')
    return canonical, order


def compare(old, new, cache):
    result = {}
    for name, first in old['datasets'].items():
        second = new['datasets'][name]
        if first['points'] != second['points']:
            raise ValueError(name + ': point identities differ')
        array(old, first['points'], cache, '<f4')
        left, left_order = canonical_triangles(old, first, cache)
        right, right_order = canonical_triangles(new, second, cache)
        if not np.array_equal(left, right):
            raise ValueError(name + ': canonical triangle sets differ')
        fields = {}
        for field, descriptor in first['fields'].items():
            a = array(old, descriptor['asset'], cache, '<f8')[left_order]
            b = array(new, second['fields'][field]['asset'], cache, '<f8')[right_order]
            fields[field] = {'exact_by_triangle': bool(np.array_equal(a,b)),
                             'max_abs_difference': float(np.max(np.abs(a-b)))}
        result[name] = {'triangles':len(left),'fields':fields}
    return result


if __name__ == '__main__':
    old, new = [json.loads(Path(path).read_text()) for path in sys.argv[1:3]]
    result = compare(old, new, Path(sys.argv[3]))
    print(json.dumps(result, indent=2))
    if not all(field['exact_by_triangle'] for dataset in result.values() for field in dataset['fields'].values()):
        raise SystemExit(1)
