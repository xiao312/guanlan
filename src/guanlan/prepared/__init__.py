"""Deterministic prepared-asset selection; no I/O or inference."""
import copy
import hashlib
import re


def asset_id(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid content ID')
    return value


def select(manifest, selections):
    if manifest.get('schema_version') != 2 or not 1 <= len(selections) <= 8:
        raise ValueError('version-2 manifest and explicit selection required')
    if len(manifest.get('assets', {})) > 128:
        raise ValueError('manifest asset budget exceeded')
    result = copy.deepcopy(manifest)
    result['blocks'], result['datasets'], result['assets'] = [], {}, {}
    blocks = {block['id']: block for block in manifest['blocks']}
    categories = {}

    def include(key, category):
        asset_id(key)
        meta = manifest['assets'][key]
        if meta['dtype'] not in ('Float32Array', 'Uint32Array', 'Float64Array') or meta.get('codec', 'gzip') != 'gzip':
            raise ValueError('unsupported asset type/codec')
        if any(type(meta[k]) is not int or not 0 < meta[k] <= 64*1024*1024 for k in ('decoded_bytes', 'compressed_bytes')):
            raise ValueError('asset size exceeds budget')
        result['assets'][key] = copy.deepcopy(meta)
        categories.setdefault(key, category)

    for name, fields in selections.items():
        if not isinstance(fields,list) or len(fields)>8 or len(set(fields))!=len(fields):
            raise ValueError('invalid selected field list')
        block = copy.deepcopy(blocks[name])
        source = manifest['datasets'][block['dataset']]
        if block['kind'] not in ('geometry','mesh','slice') or block['camera'] not in ('xy','xz','yz','isometric'):
            raise ValueError('unsupported block')
        if (type(source['point_count']) is not int or not 0 < source['point_count'] <= 1000000
                or type(source['cell_count']) is not int or not 0 < source['cell_count'] <= 500000):
            raise ValueError('topology count budget exceeded')
        geometry = hashlib.sha256((source['points'] + ':' + source['polys']).encode()).hexdigest()
        if source['geometry_id'] != geometry:
            raise ValueError('geometry binding mismatch')
        dataset = result['datasets'].setdefault(block['dataset'],
            {k: source[k] for k in ('points', 'polys', 'point_count', 'cell_count', 'geometry_id')})
        dataset.setdefault('fields', {})
        for key in ('points', 'polys'):
            include(source[key], 'geometry')
        if (result['assets'][source['points']]['dtype'] != 'Float32Array'
                or result['assets'][source['points']]['decoded_bytes'] != source['point_count'] * 12
                or result['assets'][source['polys']]['dtype'] != 'Uint32Array'):
            raise ValueError('geometry array shape/type mismatch')
        if block['kind'] == 'mesh':
            dataset.update(edges=source['edges'], edge_count=source['edge_count'])
            include(source['edges'], 'edges')
            if (result['assets'][source['edges']]['dtype'] != 'Uint32Array'
                    or result['assets'][source['edges']]['decoded_bytes'] != source['edge_count'] * 12):
                raise ValueError('edge array shape mismatch')
        if block['kind'] == 'slice':
            if not fields:
                raise ValueError('slice requires explicit fields')
            block['field'] = fields[0]
        elif fields:
            raise ValueError('fields are supported only for slice blocks')
        for field_name in fields:
            field = source['fields'][field_name]
            if (field['geometry_id'] != geometry or field['tuples'] != source['cell_count']
                    or field['components'] != 1 or field['association'] != 'cell'):
                raise ValueError('field/topology binding mismatch')
            include(field['asset'], 'fields')
            if (result['assets'][field['asset']]['decoded_bytes'] != field['tuples'] * 8
                    or result['assets'][field['asset']]['dtype'] != 'Float64Array'):
                raise ValueError('field tuple byte mismatch')
            dataset['fields'][field_name] = copy.deepcopy(field)
        result['blocks'].append(block)
    result['coverage'] = 'Included selections: ' + ', '.join(k + ':' + '/'.join(v) for k,v in selections.items())
    result['asset_categories'] = categories
    return result


def plan_assets(manifest, selections, valid_cache=()):
    chosen = select(manifest, selections)
    required = sorted(chosen['assets'])
    missing = [key for key in required if key not in valid_cache]
    def size(keys, kind):
        return sum(chosen['assets'][key][kind] for key in keys)
    return chosen, {'required': required, 'missing': missing,
        'transfer_bytes': size(missing, 'compressed_bytes'),
        'retained_bytes': size(required, 'compressed_bytes'),
        'decoded_bytes': size(required, 'decoded_bytes'),
        'by_category': {category: sum(chosen['assets'][key]['compressed_bytes'] for key in missing
            if chosen['asset_categories'][key] == category) for category in ('geometry','edges','fields')}}
