"""Allocated ParaView-only slicing and rendering; publishes manifest last."""
import argparse
import json
import math
import os
from pathlib import Path
import resource
import time
import zipfile

from guanlan.media.contract import MAX_BYTES, digest, validate, validate_manifest
from guanlan.worker.readiness import partition_paths, latest_candidate, unchanged, field_units
from guanlan.worker.boundaries import physical_boundaries
from guanlan.worker.protocol import emit, report_exception


def camera(pvs, view, bounds, preset, focus=None, reserve_legend=False):
    center = [(bounds[2*i] + bounds[2*i+1])/2 for i in range(3)]
    size = max(bounds[2*i+1]-bounds[2*i] for i in range(3))
    direction = {'xy': [0, 0, 1], 'xz': [0, -1, 0], 'yz': [1, 0, 0], 'isometric': [1, -1, 1]}[preset]
    view.CameraParallelProjection = 1
    view.CameraFocalPoint = center
    view.CameraPosition = [center[i] + 2*size*direction[i] for i in range(3)]
    view.CameraViewUp = [0, 1, 0] if preset == 'xy' else [0, 0, 1]
    pvs.ResetCamera(view)
    if focus is not None:
        axes = {'xy': (0, 1), 'xz': (0, 2), 'yz': (1, 2)}[preset]
        focal = list(center)
        spans = []
        for axis, lower, upper in zip(axes, focus[::2], focus[1::2]):
            extent = bounds[2*axis+1] - bounds[2*axis]
            focal[axis] = bounds[2*axis] + (lower + upper)*extent/2
            spans.append((upper - lower)*extent)
        if reserve_legend:
            # Leave clear bands above and below focused scalar views for
            # the title and legend without clipping the field.
            focal[axes[1]] -= 0.03*spans[1]
        view.CameraFocalPoint = focal
        view.CameraPosition = [focal[i] + 2*size*direction[i] for i in range(3)]
        aspect = view.ViewSize[0] / view.ViewSize[1]
        view.CameraParallelScale = (0.78 if reserve_legend else 0.54)*max(spans[1], spans[0]/aspect)


def run(case_path, workspace_path, preset_path):
    if not os.environ.get('SLURM_JOB_ID'): raise ValueError('render requires a Slurm allocation')
    from paraview import simple as pvs
    from vtkmodules.vtkCommonCore import vtkOutputWindow, vtkStringOutputWindow
    p = validate(json.loads(Path(preset_path).read_text(encoding='utf-8-sig')))
    case, workspace = Path(case_path).resolve(), Path(workspace_path).resolve()
    if 'guanlan' not in workspace.parts or case == workspace or case in workspace.parents or workspace in case.parents:
        raise ValueError('use a separate Guanlan workspace')
    output = workspace / 'output'
    output.mkdir(exist_ok=False)
    shadow = workspace / 'reader'
    shadow.mkdir(exist_ok=False)
    for target in [case / 'constant', case / 'system'] + partition_paths(case):
        (shadow / target.name).symlink_to(target, target_is_directory=True)
    marker = shadow / 'case.foam'
    marker.touch()
    errors = vtkStringOutputWindow()
    vtkOutputWindow.SetInstance(errors)
    started = time.monotonic()
    fields = sorted({f for b in p['blocks'] for f in b.get('fields', [])})
    signatures = [latest_candidate(case, fields, time_name=t)[1] for t in p['times']]
    patch_counts, excluded = physical_boundaries(case)
    reader = pvs.OpenFOAMReader(FileName=str(marker))
    reader.CaseType = 'Decomposed Case'
    reader.Createcelltopointfiltereddata = 0
    reader.SkipZeroTime = 1
    reader.UpdatePipelineInformation()
    if any(not any(math.isclose(float(t), value, rel_tol=1e-9, abs_tol=1e-12) for value in reader.TimestepValues) for t in p['times']):
        raise ValueError('requested time absent from ParaView reader')
    available = set(reader.MeshRegions.Available)
    frames, total_bytes, files = [], 0, set()
    for block in p['blocks']:
        is_slice = block['kind'] == 'slice'
        patches = block.get('patches') or list(patch_counts)
        if not is_slice and (not patches or any(k not in patch_counts or 'patch/' + k not in available for k in patches)):
            raise ValueError('requested physical boundary is absent')
        reader.MeshRegions = ['internalMesh'] if is_slice else ['patch/' + k for k in patches]
        reader.CellArrays = block.get('fields', [])
        reader.UpdatePipeline(float(p['times'][0]))
        source = pvs.Slice(Input=reader) if is_slice else pvs.ExtractSurface(Input=reader)
        bounds = reader.GetDataInformation().GetBounds()
        if not all(math.isfinite(v) for v in bounds): raise ValueError('invalid source bounds')
        plane = None
        if is_slice:
            axis = {'xy': 2, 'xz': 1, 'yz': 0}[block['plane']]
            origin = [(bounds[2*i]+bounds[2*i+1])/2 for i in range(3)]
            origin[axis] = bounds[2*axis] + block['offset']*(bounds[2*axis+1]-bounds[2*axis])
            normal = [int(i == axis) for i in range(3)]
            source.SliceType = 'Plane'
            source.SliceType.Origin, source.SliceType.Normal = origin, normal
            plane = {'origin': origin, 'normal': normal, 'coordinate_units': 'm'}
        source.UpdatePipeline(float(p['times'][0]))
        view = pvs.CreateView('RenderView')
        view.ViewSize = p['size']
        view.UseColorPaletteForBackground = 0
        view.Background = [0.945, 0.953, 0.961]
        display = pvs.Show(source, view)
        display.Representation = 'Surface With Edges' if block['kind'] == 'mesh' else 'Surface'
        display.DiffuseColor = [0.56, 0.64, 0.72]
        display.EdgeColor = [0.1, 0.13, 0.18]
        display.InterpolateScalarsBeforeMapping = 0
        if is_slice:
            display.Ambient, display.Diffuse, display.Specular = 1, 0, 0
        camera(pvs, view, source.GetDataInformation().GetBounds(), block['camera'], block.get('focus'), is_slice)
        caption = pvs.Text()
        caption_display = pvs.Show(caption, view)
        caption_display.Color = [0.15, 0.18, 0.22]
        caption_display.FontSize = 12
        caption_display.WindowLocation = 'Upper Left Corner'
        for time_name in p['times']:
            frame_started = time.monotonic()
            view.ViewTime = float(time_name)
            source.UpdatePipeline(float(time_name))
            cells = source.GetDataInformation().GetNumberOfCells()
            if cells <= 0: raise ValueError('empty surface/slice')
            if not is_slice and cells != sum(patch_counts[k] for k in patches):
                raise ValueError('physical surface face count mismatch; refusing images')
            units = field_units(case, time_name, block.get('fields', []))
            for field in block.get('fields', ['']):
                limits, data_range = None, None
                if field:
                    info = source.CellData.GetArray(field)
                    if info is None or info.GetNumberOfComponents() != 1:
                        raise ValueError('expected scalar cell field: ' + field)
                    # Native VTK validation catches non-finite samples, which a range alone can hide.
                    from paraview import servermanager
                    from vtkmodules.util.numpy_support import vtk_to_numpy
                    import numpy as np
                    data = servermanager.Fetch(source)
                    leaves = [data]
                    if data.IsA('vtkCompositeDataSet'):
                        leaves = []
                        iterator = data.NewIterator(); iterator.InitTraversal()
                        while not iterator.IsDoneWithTraversal():
                            leaves.append(iterator.GetCurrentDataObject()); iterator.GoToNextItem()
                    for leaf in leaves:
                        if leaf is not None and leaf.GetNumberOfCells():
                            array = leaf.GetCellData().GetArray(field)
                            if array is None or not np.isfinite(vtk_to_numpy(array)).all():
                                raise ValueError('missing/non-finite scalar data: ' + field)
                    data_range = list(info.GetRange())
                    if not all(math.isfinite(v) for v in data_range): raise ValueError('non-finite field range')
                    limits = list(data_range if block['range'] == 'data' else block['range'])
                    if limits[0] == limits[1]:
                        epsilon = max(abs(limits[0])*1e-6, 1e-12)
                        limits = [limits[0]-epsilon, limits[1]+epsilon]
                    pvs.ColorBy(display, ('CELLS', field))
                    lut = pvs.GetColorTransferFunction(field)
                    if not lut.ApplyPreset(block['palette'], True): raise ValueError('palette unavailable in runtime')
                    lut.AutomaticRescaleRangeMode = 'Never'
                    lut.RescaleTransferFunction(*limits)
                    lut.Discretize = 0
                    display.SetScalarBarVisibility(view, True)
                    bar = pvs.GetScalarBar(lut, view)
                    bar.Title = field + ' [' + units[field]['units'] + ']'
                    bar.ComponentTitle = ''
                    bar.TitleColor = bar.LabelColor = [0.15, 0.18, 0.22]
                    bar.Orientation = 'Horizontal'; bar.WindowLocation = 'Lower Center'; bar.ScalarBarLength = 0.6
                caption.Text = block['title'] + ' | t=' + time_name + (' | cell values' if field else '')
                temporary = output / 'frame.png'
                pvs.SaveScreenshot(str(temporary), view, ImageResolution=p['size'])
                if 'ERROR' in errors.GetOutput(): raise ValueError(errors.GetOutput()[-2000:])
                payload = temporary.read_bytes(); sha = digest(payload); filename = sha + '.png'
                if filename not in files:
                    total_bytes += len(payload); files.add(filename)
                if total_bytes > MAX_BYTES: raise ValueError('media exceeds 64 MiB; reduce preset')
                temporary.replace(output / filename)
                frames.append({'block': block['id'], 'field': field, 'time': time_name, 'file': filename,
                               'sha256': sha, 'bytes': len(payload), 'range': limits, 'data_range': data_range,
                               'units': units[field]['units'] if field else '', 'plane': plane,
                               'cells': cells, 'render_seconds': time.monotonic()-frame_started})
                if field: display.SetScalarBarVisibility(view, False)
                emit({'stage': 'media-frame', 'block': block['id'], 'field': field, 'time': time_name})
        pvs.Delete(caption); pvs.Delete(view); pvs.Delete(source)
    if not all(unchanged(s) for s in signatures): raise ValueError('source changed; refusing publication')
    archive_path = output / 'media.zip'
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for filename in sorted(files): archive.write(output / filename, filename)
    manifest = {'version': 1, 'preset': p, 'frames': frames,
                'bundle': {'bytes': archive_path.stat().st_size, 'sha256': digest(archive_path.read_bytes())},
                'metrics': {'seconds': time.monotonic()-started, 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'png_bytes': total_bytes, 'paraview': str(pvs.GetParaViewVersion()),
                            'excluded_processor_faces': excluded}}
    validate_manifest(manifest)
    (output / 'manifest.json').write_text(json.dumps(manifest, allow_nan=False), encoding='utf-8')
    emit({'stage': 'media-complete', 'metrics': manifest['metrics']})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('case', 'workspace', 'preset'): parser.add_argument('--'+option, required=True)
    args = parser.parse_args()
    try: run(args.case, args.workspace, args.preset)
    except Exception:
        report_exception()
        raise SystemExit(1)
