"""Fluent CFF source index and allocated ParaView media renderer.

The index lives only in the private request workspace. Public manifests contain
field labels and physical times, never source filenames or case paths.
"""

import argparse
import json
import math
import os
from pathlib import Path
import re
import resource
import time
import zipfile

from guanlan.media.contract import MAX_BYTES, digest, name, validate, validate_manifest
from guanlan.media.render import camera
from guanlan.worker.protocol import emit, report_exception


def validate_index(index, preset):
    if (not isinstance(index, dict) or set(index) != {'version', 'format', 'frames', 'fields'}
            or index['version'] != 1 or index['format'] != 'fluent-cff'):
        raise ValueError('expected version 1 Fluent CFF source index')
    frames = index['frames']
    if (not isinstance(frames, list) or len(frames) != len(preset['times'])
            or [f.get('time') for f in frames if isinstance(f, dict)] != preset['times']):
        raise ValueError('source index times must exactly match preset times')
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != {'time', 'case', 'data'}:
            raise ValueError('each source frame needs time, case and data')
        for key, suffix in (('case', '.cas.h5'), ('data', '.dat.h5')):
            value = frame[key]
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value) or not value.endswith(suffix):
                raise ValueError('source files must be safe Fluent CFF basenames')
        if frame['case'][:-7] != frame['data'][:-7]:
            raise ValueError('Fluent case/data basenames must match')
    requested = {field for block in preset['blocks'] for field in block.get('fields', [])}
    fields = index['fields']
    if not isinstance(fields, dict) or set(fields) != requested:
        raise ValueError('source field map must exactly cover requested fields')
    for alias, metadata in fields.items():
        name(alias)
        if (not isinstance(metadata, dict) or set(metadata) != {'array', 'units'}
                or not isinstance(metadata['array'], str)
                or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', metadata['array'])
                or not isinstance(metadata['units'], str)
                or not 1 <= len(metadata['units']) <= 40
                or any(ord(c) < 32 for c in metadata['units'])):
            raise ValueError('invalid Fluent field mapping')
    for block in preset['blocks']:
        if block.get('patches'):
            raise ValueError('Fluent CFF boundary patch selection is not qualified')
        if block['kind'] == 'slice' and (block['plane'] != 'xy' or block['offset'] != 0.5):
            raise ValueError('this Fluent CFF route supports only the native XY plane at offset 0.5')
    return index


def source_files(case, frame):
    case_file, data_file = case / frame['case'], case / frame['data']
    signature = []
    for path in (case_file, data_file):
        stat = path.stat()
        if not path.is_file() or stat.st_size == 0 or time.time() - stat.st_mtime < 10:
            raise ValueError('Fluent pair is absent or still being written')
        signature.append((path, stat.st_size, stat.st_mtime_ns))
    return case_file, signature


def unchanged(signature):
    return all((path.stat().st_size, path.stat().st_mtime_ns) == (size, stamp)
               for path, size, stamp in signature)


def run(case_path, workspace_path, preset_path, index_path):
    if not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('render requires a Slurm allocation')
    from paraview import servermanager
    from paraview import simple as pvs
    from vtkmodules.vtkCommonCore import vtkOutputWindow, vtkStringOutputWindow
    from vtkmodules.util.numpy_support import vtk_to_numpy
    import numpy as np

    preset = validate(json.loads(Path(preset_path).read_text(encoding='utf-8-sig')))
    index = validate_index(json.loads(Path(index_path).read_text(encoding='utf-8-sig')), preset)
    case, workspace = Path(case_path).resolve(), Path(workspace_path).resolve()
    if ('guanlan' not in workspace.parts or case == workspace or case in workspace.parents
            or workspace in case.parents):
        raise ValueError('use a separate Guanlan workspace')
    output = workspace / 'output'
    output.mkdir(exist_ok=False)
    signatures = []
    for frame in index['frames']:
        _, signature = source_files(case, frame)
        signatures.extend(signature)
    errors = vtkStringOutputWindow()
    vtkOutputWindow.SetInstance(errors)
    started = time.monotonic()
    frames, files, total_bytes = [], set(), 0

    for source_frame in index['frames']:
        time_name = source_frame['time']
        case_file, _ = source_files(case, source_frame)
        reader = pvs.OpenDataFile(str(case_file))
        if reader is None or reader.GetXMLName() != 'FLUENTCFFReader':
            raise ValueError('ParaView did not select the Fluent CFF reader')
        reader.UpdatePipeline()
        bounds = reader.GetDataInformation().GetBounds()
        if (not all(math.isfinite(v) for v in bounds) or bounds[4] != bounds[5]
                or reader.GetDataInformation().GetNumberOfCells() <= 0):
            raise ValueError('expected a nonempty planar Fluent CFF case')
        plane = {'origin': [(bounds[0]+bounds[1])/2, (bounds[2]+bounds[3])/2, bounds[4]],
                 'normal': [0, 0, 1], 'coordinate_units': 'm'}

        for block in preset['blocks']:
            view = pvs.CreateView('RenderView')
            view.ViewSize = preset['size']
            view.UseColorPaletteForBackground = 0
            view.Background = [0.945, 0.953, 0.961]
            display = pvs.Show(reader, view)
            display.Representation = 'Surface With Edges' if block['kind'] == 'mesh' else 'Surface'
            display.DiffuseColor = [0.56, 0.64, 0.72]
            display.EdgeColor = [0.1, 0.13, 0.18]
            display.InterpolateScalarsBeforeMapping = 0
            is_field = block['kind'] == 'slice'
            if is_field:
                display.Ambient, display.Diffuse, display.Specular = 1, 0, 0
            camera(pvs, view, bounds, block['camera'], block.get('focus'), is_field)
            caption = pvs.Text()
            caption_display = pvs.Show(caption, view)
            caption_display.Color = [0.15, 0.18, 0.22]
            caption_display.FontSize = 12
            caption_display.WindowLocation = 'Upper Left Corner'

            for alias in block.get('fields', ['']):
                frame_started = time.monotonic()
                limits = data_range = None
                if alias:
                    actual = index['fields'][alias]['array']
                    info = reader.CellData.GetArray(actual)
                    if info is None or info.GetNumberOfComponents() != 1:
                        raise ValueError('missing scalar cell field: ' + actual)
                    data = servermanager.Fetch(reader)
                    leaves = [data]
                    if data.IsA('vtkCompositeDataSet'):
                        leaves = []
                        iterator = data.NewIterator(); iterator.InitTraversal()
                        while not iterator.IsDoneWithTraversal():
                            leaves.append(iterator.GetCurrentDataObject()); iterator.GoToNextItem()
                    valid_cells = 0
                    for leaf in leaves:
                        if leaf is None or not leaf.GetNumberOfCells():
                            continue
                        array = leaf.GetCellData().GetArray(actual)
                        if array is None:
                            continue
                        if not np.isfinite(vtk_to_numpy(array)).all():
                            raise ValueError('non-finite scalar data: ' + actual)
                        valid_cells += leaf.GetNumberOfCells()
                    if valid_cells == 0:
                        raise ValueError('field has no readable cells: ' + actual)
                    data_range = list(info.GetRange())
                    if not all(math.isfinite(v) for v in data_range):
                        raise ValueError('non-finite field range')
                    limits = list(data_range if block['range'] == 'data' else block['range'])
                    if limits[0] == limits[1]:
                        epsilon = max(abs(limits[0])*1e-6, 1e-12)
                        limits = [limits[0]-epsilon, limits[1]+epsilon]
                    pvs.ColorBy(display, ('CELLS', actual))
                    lut = pvs.GetColorTransferFunction(actual)
                    if not lut.ApplyPreset(block['palette'], True):
                        raise ValueError('palette unavailable in runtime')
                    lut.AutomaticRescaleRangeMode = 'Never'
                    lut.RescaleTransferFunction(*limits)
                    lut.Discretize = 0
                    display.SetScalarBarVisibility(view, True)
                    bar = pvs.GetScalarBar(lut, view)
                    bar.Title = alias + ' [' + index['fields'][alias]['units'] + ']'
                    bar.ComponentTitle = ''
                    bar.TitleColor = bar.LabelColor = [0.15, 0.18, 0.22]
                    bar.Orientation = 'Horizontal'; bar.WindowLocation = 'Lower Center'; bar.ScalarBarLength = 0.6
                caption.Text = block['title'] + ' | t=' + time_name + ' s' + (' | cell values' if alias else '')
                temporary = output / 'frame.png'
                pvs.SaveScreenshot(str(temporary), view, ImageResolution=preset['size'])
                if 'ERROR' in errors.GetOutput():
                    raise ValueError(errors.GetOutput()[-2000:])
                payload = temporary.read_bytes()
                sha = digest(payload)
                filename = sha + '.png'
                if filename not in files:
                    files.add(filename)
                    total_bytes += len(payload)
                if total_bytes > MAX_BYTES:
                    raise ValueError('media exceeds 64 MiB; reduce preset')
                temporary.replace(output / filename)
                frames.append({'block': block['id'], 'field': alias, 'time': time_name,
                               'file': filename, 'sha256': sha, 'bytes': len(payload),
                               'range': limits, 'data_range': data_range,
                               'units': index['fields'][alias]['units'] if alias else '',
                               'plane': plane if alias else None,
                               'cells': valid_cells if alias else reader.GetDataInformation().GetNumberOfCells(),
                               'render_seconds': time.monotonic()-frame_started})
                if alias:
                    display.SetScalarBarVisibility(view, False)
                emit({'stage': 'media-frame', 'block': block['id'], 'field': alias, 'time': time_name})
            pvs.Delete(caption); pvs.Delete(view)
        pvs.Delete(reader)

    if not unchanged(signatures):
        raise ValueError('source changed; refusing publication')
    archive_path = output / 'media.zip'
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for filename in sorted(files):
            archive.write(output / filename, filename)
    manifest = {'version': 1, 'preset': preset, 'frames': frames,
                'bundle': {'bytes': archive_path.stat().st_size, 'sha256': digest(archive_path.read_bytes())},
                'metrics': {'seconds': time.monotonic()-started,
                            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'png_bytes': total_bytes, 'paraview': str(pvs.GetParaViewVersion()),
                            'source_format': 'fluent-cff'}}
    validate_manifest(manifest)
    (output / 'manifest.json').write_text(json.dumps(manifest, allow_nan=False), encoding='utf-8')
    emit({'stage': 'media-complete', 'metrics': manifest['metrics']})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('case', 'workspace', 'preset', 'index'):
        parser.add_argument('--' + option, required=True)
    args = parser.parse_args()
    try:
        run(args.case, args.workspace, args.preset, args.index)
    except Exception:
        report_exception()
        raise SystemExit(1)
