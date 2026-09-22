"""Allocated scalar audit: native OpenFOAM internal arrays versus reader values.

Supports nonuniform scalar fields in ASCII or declared binary architecture.
Never interprets physical quality. Unsupported formats fail explicitly.
"""
import gzip
import re
from pathlib import Path


def native_scalar(path, legacy_lsb64=False):
    import numpy as np
    path=Path(path)
    if not path.exists():path=path.with_suffix('.gz')
    opener=gzip.open if path.suffix=='.gz' else open
    with opener(path,'rb') as stream: raw=stream.read(64*1024*1024+1)
    if len(raw)>64*1024*1024:raise ValueError('native audit file exceeds budget')
    match=re.search(rb'internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(',raw)
    if not match:
        uniform=re.search(rb'internalField\s+uniform\s+([^;]+);',raw)
        if not uniform:raise ValueError('unsupported native internalField')
        owner=path.parent.parent/'constant'/'polyMesh'/'owner'
        if not owner.exists():owner=owner.with_suffix('.gz')
        with (gzip.open if owner.suffix=='.gz' else open)(owner,'rb') as stream:header=stream.read(4096)
        cells=re.search(rb'nCells\s*:\s*(\d+)',header)
        if not cells:raise ValueError('uniform scalar audit requires native mesh nCells metadata')
        count=int(cells[1])
        if count>1000000:raise ValueError('native cell budget exceeded')
        values=np.full(count,float(uniform[1]),dtype=np.float64)
        if not np.isfinite(values).all():raise ValueError('non-finite uniform scalar')
        return values
    count=int(match[1]);start=match.end()
    if re.search(rb'format\s+ascii\s*;',raw[:4096]):
        end=raw.find(b')',start)
        values=np.fromstring(raw[start:end].decode('ascii'),sep=' ')
    else:
        arch=re.search(rb'arch\s+"(LSB|MSB);label=\d+;scalar=(32|64)"',raw[:4096])
        if not arch:
            if not legacy_lsb64:raise ValueError('binary header lacks architecture; explicit legacy profile required')
            dtype='<f8'
        else:
            dtype=('<' if arch[1]==b'LSB' else '>')+('f4' if arch[2]==b'32' else 'f8')
        end=start+count*np.dtype(dtype).itemsize
        if not re.match(rb'\s*\)\s*;',raw[end:end+32]):raise ValueError('binary scalar width/count does not match closing delimiter')
        values=np.frombuffer(raw,dtype=dtype,count=count,offset=start).astype(np.float64)
    if len(values)!=count or not np.isfinite(values).all():
        raise ValueError('invalid native scalar audit values')
    return values


def compare_scalar_values(actual, native):
    """Histogram and ordering are different checks; preserve both results."""
    import numpy as np
    if actual.dtype not in (np.dtype('float32'), np.dtype('float64')):
        raise ValueError('unsupported reader scalar precision')
    rounded = native.astype(actual.dtype)
    if actual.size != native.size or not np.array_equal(np.sort(actual), np.sort(rounded)):
        raise ValueError('native/reader scalar multiset mismatch')
    distinct, counts = np.unique(native, return_counts=True)
    return {'cells': int(native.size), 'min': float(native.min()), 'max': float(native.max()),
            'distinct_values': int(distinct.size), 'reader_dtype': str(actual.dtype),
            'native_reader_multiset_equal': bool(np.array_equal(np.sort(actual), np.sort(native))),
            'native_cast_reader_multiset_equal': True,
            'native_cast_reader_ordered_equal': bool(np.array_equal(actual, rounded)),
            'ordering_reference': 'numeric processor order, native local cell order',
            'max_abs_reader_rounding': float(np.max(np.abs(native-rounded.astype(np.float64)))),
            'most_frequent': [{'value': float(distinct[i]), 'cells': int(counts[i])}
                              for i in np.argsort(counts)[-5:][::-1]]}


def audit_reader(reader, case, time_name, fields, legacy_lsb64=False):
    import numpy as np
    from paraview import servermanager
    from vtkmodules.util.numpy_support import vtk_to_numpy
    from guanlan.worker.readiness import partition_paths
    data=servermanager.Fetch(reader)
    leaves=[]
    if data.IsA('vtkCompositeDataSet'):
        iterator=data.NewIterator();iterator.InitTraversal()
        while not iterator.IsDoneWithTraversal():
            leaf=iterator.GetCurrentDataObject()
            if leaf is not None and leaf.IsA('vtkDataSet'):leaves.append(leaf)
            iterator.GoToNextItem()
    else:leaves=[data]
    result={}
    for field in fields:
        actual=np.concatenate([vtk_to_numpy(leaf.GetCellData().GetArray(field)).reshape(-1) for leaf in leaves
                               if leaf.GetNumberOfCells()])
        native=np.concatenate([native_scalar(part/time_name/field,legacy_lsb64) for part in partition_paths(case)])
        try:
            result[field] = compare_scalar_values(actual, native)
        except ValueError as error:
            raise ValueError(field + ': ' + str(error)) from error
    return result
