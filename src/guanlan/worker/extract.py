"""One bounded extraction job; no Matplotlib, OpenGL context, or HTTP service."""
import argparse
import base64
import json
import os
from pathlib import Path
import resource
import time
from guanlan.worker.protocol import emit, report_exception


def encode_array(array, dtype):
    return base64.b64encode(array.astype(dtype, copy=False).tobytes()).decode('ascii')


def export_polydata(source, fields, units):
    import numpy as np
    from paraview import servermanager
    from vtkmodules.util.numpy_support import vtk_to_numpy
    from vtkmodules.vtkFiltersGeometry import vtkCompositeDataGeometryFilter
    data = servermanager.Fetch(source)
    if data.IsA('vtkCompositeDataSet'):
        flatten = vtkCompositeDataGeometryFilter()
        flatten.SetInputData(data)
        flatten.Update()
        data = flatten.GetOutput()
    emit({'stage': 'fetched', 'type': data.GetClassName(), 'fields': fields,
          'cells': data.GetNumberOfCells(), 'points': data.GetNumberOfPoints()})
    if not data.IsA('vtkPolyData') or not data.GetNumberOfPolys():
        raise ValueError('extraction did not produce surface polygons')
    if data.GetNumberOfCells() != data.GetNumberOfPolys():
        raise ValueError('mixed non-polygon topology is not supported')
    if data.GetNumberOfCells() > 500000 or data.GetNumberOfPoints() > 1000000:
        raise ValueError('surface exceeds portable budget; choose a smaller region')
    points = vtk_to_numpy(data.GetPoints().GetData())
    if not np.isfinite(points).all():
        raise ValueError('non-finite mesh coordinates')
    result = {'points': encode_array(points, '<f4'),
              'polys': encode_array(vtk_to_numpy(data.GetPolys().GetData()), '<u4'),
              'point_count': data.GetNumberOfPoints(), 'cell_count': data.GetNumberOfCells(),
              'fields': {}}
    for name in fields:
        array = data.GetCellData().GetArray(name)
        if array is None:
            raise ValueError('missing cell array: ' + name)
        values = vtk_to_numpy(array).astype(np.float64, copy=False)
        magnitude = values.ndim == 2
        if magnitude:
            values = np.hypot.reduce(values, axis=1)
        if not np.isfinite(values).all():
            raise ValueError('non-finite values in ' + name)
        result['fields'][name] = {'values': encode_array(values, '<f8'),
                                  'range': [float(values.min()), float(values.max())],
                                  'units': units[name]['units'], 'association': 'cell',
                                  'label': name + (' magnitude' if magnitude else '')}
    return result


def extract(case, workspace, title, time_name=None, fields=None):
    if not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('extract must run in an explicit Slurm allocation, never on a login node')
    from paraview import simple as pvs
    from vtkmodules.vtkCommonCore import vtkOutputWindow, vtkStringOutputWindow
    from guanlan.worker.readiness import partition_paths, latest_candidate, unchanged, field_units
    from guanlan.worker.boundaries import physical_boundaries
    started = time.monotonic()
    case, workspace = Path(case).resolve(), Path(workspace).resolve()
    if 'guanlan' not in workspace.parts or case == workspace or case in workspace.parents or workspace in case.parents:
        raise ValueError('workspace must be a separate Guanlan directory')
    fields = fields or ['p', 'T']
    time_name, signature = latest_candidate(case, fields, time_name=time_name)
    emit({'stage': 'ready', 'time': time_name, 'job_id': os.environ['SLURM_JOB_ID']})
    shadow = workspace / 'portable-reader'
    shadow.mkdir(parents=True, exist_ok=True)
    for target in [case / 'constant', case / 'system'] + partition_paths(case):
        link = shadow / target.name
        if link.is_symlink() and link.resolve() != target.resolve():
            raise ValueError('reader workspace is bound to another case')
        if not link.exists():
            link.symlink_to(target, target_is_directory=True)
    marker = shadow / 'case.foam'
    marker.touch(exist_ok=True)
    errors = vtkStringOutputWindow()
    vtkOutputWindow.SetInstance(errors)
    reader = pvs.OpenFOAMReader(FileName=str(marker))
    reader.CaseType = 'Decomposed Case'
    reader.SkipZeroTime = 1
    reader.UpdatePipelineInformation()
    patch_counts, processor_faces = physical_boundaries(case)
    available = list(reader.MeshRegions.Available)
    patches = [name for name in available if name.startswith('patch/') and name[6:] in patch_counts]
    missing = {name for name, count in patch_counts.items() if count and 'patch/' + name not in patches}
    if missing or not patches:
        raise ValueError('physical patch selection mismatch: missing=' + str(missing) + ' available=' + str(available))
    emit({'stage': 'physical-patches', 'patches': patches, 'expected_faces': sum(patch_counts.values()),
          'excluded_processor_faces': processor_faces})
    reader.MeshRegions = patches
    reader.CellArrays = []
    reader.UpdatePipeline(float(time_name))
    read_done = time.monotonic()
    emit({'stage': 'read', 'elapsed_seconds': time.monotonic() - started,
          'errors': errors.GetOutput()[-2000:]})
    bounds = reader.GetDataInformation().GetBounds()
    surface = pvs.ExtractSurface(Input=reader)
    surface.UpdatePipeline(float(time_name))
    emit({'stage': 'surface', 'elapsed_seconds': time.monotonic() - started})
    units = field_units(case, time_name, fields)
    datasets = {'surface': export_polydata(surface, [], units)}
    if datasets['surface']['cell_count'] != sum(patch_counts.values()):
        raise ValueError('surface count does not match physical boundary faces; refusing publication')
    surface_done = time.monotonic()
    reader.MeshRegions = ['internalMesh']
    reader.CellArrays = fields
    reader.UpdatePipeline(float(time_name))
    field_read_done = time.monotonic()
    blocks = [{'id': 'geometry', 'kind': 'geometry', 'dataset': 'surface', 'camera': 'xy'},
              {'id': 'mesh', 'kind': 'mesh', 'dataset': 'surface', 'camera': 'xy'}]
    slice_metrics = {}
    for plane, axis in [('xy', 2)]:
        slice_started = time.monotonic()
        sliced = pvs.Slice(Input=reader)
        sliced.SliceType = 'Plane'
        sliced.SliceType.Origin = [(bounds[i*2] + bounds[i*2+1]) / 2 for i in range(3)]
        sliced.SliceType.Normal = [int(i == axis) for i in range(3)]
        sliced.UpdatePipeline(float(time_name))
        datasets[plane] = export_polydata(sliced, fields, units)
        slice_metrics[plane] = time.monotonic() - slice_started
        blocks.append({'id': plane, 'kind': 'slice', 'dataset': plane, 'camera': plane,
                       'field': 'p', 'plane': plane, 'offset': 0.5})
        pvs.Delete(sliced)
    if 'ERROR' in errors.GetOutput():
        raise ValueError('ParaView extraction failed: ' + errors.GetOutput()[-1500:])
    if not unchanged(signature):
        raise ValueError('case changed during extraction; retry without publishing partial data')
    return {'schema_version': 1, 'title': title, 'case_directory': str(case),
            'simulation_time': float(time_name), 'coordinate_units': 'm', 'datasets': datasets,
            'blocks': blocks, 'metrics': {'extraction_seconds': round(time.monotonic()-started, 3),
            'reader_seconds': read_done-started, 'surface_export_seconds': surface_done-read_done,
            'field_reader_seconds': field_read_done-surface_done,
            'slice_export_seconds': slice_metrics, 'paraview_version': str(pvs.GetParaViewVersion()),
            'physical_patch_faces': patch_counts, 'excluded_processor_faces': processor_faces,
            'surface_policy': 'selected physical patches; no volume merge or coordinate welding',
            'volume_cells': reader.GetDataInformation().GetNumberOfCells(),
            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'job_id': os.environ['SLURM_JOB_ID'], 'source': 'OpenFOAM / ParaView'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('case', 'workspace', 'output', 'title'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--time-name', help='Pin an existing completed timestep for a reproducible fixture')
    parser.add_argument('--fields', nargs='+', default=['p', 'T'], help='Selected arrays; default p T')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    workspace = Path(args.workspace).resolve()
    if workspace not in output.parents:
        raise ValueError('output must stay inside the dedicated workspace')
    if any(not name.replace('_', '').isalnum() for name in args.fields):
        raise ValueError('field names must be alphanumeric with optional underscores')
    result = extract(args.case, args.workspace, args.title, args.time_name, args.fields)
    serialize_started = time.monotonic()
    payload = json.dumps(result, allow_nan=False, separators=(',', ':')).encode()
    result['metrics']['serialization_seconds'] = time.monotonic() - serialize_started
    payload = json.dumps(result, allow_nan=False, separators=(',', ':')).encode()
    if len(payload) > 64 * 1024 * 1024:
        raise ValueError('scene exceeds the 64 MiB decoded budget')
    temporary = output.with_suffix('.pending')
    temporary.write_bytes(payload)
    temporary.replace(output)
    from guanlan.worker.protocol import emit
    emit({'scene_bytes': len(payload), 'metrics': result['metrics'],
          'datasets': {k: {'cells': v['cell_count'], 'points': v['point_count']} for k, v in result['datasets'].items()}})


if __name__ == '__main__':
    try:
        main()
    except Exception:
        report_exception()
        raise SystemExit(1)
