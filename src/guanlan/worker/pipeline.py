"""Persistent ParaView OpenFOAM reader and bounded image production."""
import base64
import os
import resource
import time
from pathlib import Path

from paraview import simple as pvs
from vtkmodules.vtkCommonCore import vtkOutputWindow, vtkStringOutputWindow
from guanlan.worker.readiness import latest_candidate, unchanged, field_units, partition_paths
from guanlan.worker.software import rasterize


class Pipeline:
    def __init__(self, case, workspace):
        self.case = Path(case)
        self.workspace = Path(workspace)
        shadow = self.workspace / "reader-case"
        shadow.mkdir(exist_ok=True)
        # Only workspace links are created. The solver directory is never modified.
        for target in [self.case / "constant", self.case / "system"] + partition_paths(case):
            link = shadow / target.name
            if not link.exists():
                link.symlink_to(target, target_is_directory=True)
        marker = shadow / "case.foam"
        marker.touch(exist_ok=True)
        self.reader = pvs.OpenFOAMReader(FileName=str(marker))
        self.reader.CaseType = 'Decomposed Case'
        self.reader.MeshRegions = ['internalMesh']
        self.reader.SkipZeroTime = 1
        self.reader.UpdatePipelineInformation()
        self.fields = list(self.reader.CellArrays.Available)
        self.reader.CellArrays = ['U']
        self.merged = pvs.MergeBlocks(Input=self.reader)
        self.merged.MergePoints = 1
        self.surface = pvs.ExtractSurface(Input=self.merged)
        self.slice = pvs.Slice(Input=self.merged)
        self.slice.SliceType = 'Plane'
        self.last_time = None
        self.cached_key = None
        self.cached_result = None
        self.block_cache = {}

    def catalog(self):
        return self.fields

    def render(self, document):
        import json
        started = time.monotonic()
        errors = vtkStringOutputWindow()
        vtkOutputWindow.SetInstance(errors)
        requested_fields = sorted(set([b['field'] for b in document['blocks'] if b['field']] + ['U']))
        time_name, signature = latest_candidate(self.case, requested_fields)
        key = (time_name, json.dumps(document, sort_keys=True), tuple(signature))
        if key == self.cached_key:
            return dict(self.cached_result, cache_hit=True)
        self.reader.CellArrays = requested_fields
        if float(time_name) not in list(self.reader.TimestepValues):
            self.reader.SMProxy.InvokeCommand('Refresh')
            self.reader.UpdatePipelineInformation()
        self.reader.UpdatePipeline(float(time_name))
        self.last_time = time_name
        if 'ERROR' in errors.GetOutput():
            self.last_time = None
            raise ValueError('ParaView could not read the complete output: ' + errors.GetOutput()[-1500:])
        info = self.reader.GetDataInformation()
        if info.GetNumberOfCells() <= 0:
            raise ValueError('ParaView returned an empty mesh; keeping the last good preview')
        if not unchanged(signature):
            self.last_time = None
            raise ValueError('output changed while being read; retrying later')
        bounds = list(info.GetBounds())
        units = field_units(self.case, time_name, requested_fields)
        blocks = []
        mesh_signature = tuple(entry for entry in signature if '/polyMesh/' in entry[0])
        self.block_cache = {key: value for key, value in self.block_cache.items()
                            if key in {item['id'] for item in document['blocks']}}
        for block in document['blocks']:
            block_key = (json.dumps(block, sort_keys=True), mesh_signature,
                         (time_name, tuple(signature)) if block['kind'] == 'slice' else None)
            cached = self.block_cache.get(block['id'])
            if cached and cached[0] == block_key:
                blocks.append(cached[1])
                continue
            source = self.surface
            if block['kind'] == 'slice':
                normal_axis = {'xy': 2, 'xz': 1, 'yz': 0}[block['plane']]
                origin = [(bounds[i * 2] + bounds[i * 2 + 1]) / 2 for i in range(3)]
                origin[normal_axis] = bounds[normal_axis * 2] + block['offset'] * (bounds[normal_axis * 2 + 1] - bounds[normal_axis * 2])
                self.slice.SliceType.Origin = origin
                self.slice.SliceType.Normal = [int(i == normal_axis) for i in range(3)]
                source = self.slice
            source.UpdatePipeline(float(time_name))
            if 'ERROR' in errors.GetOutput():
                raise ValueError('ParaView extraction failed: ' + errors.GetOutput()[-1500:])
            payload, data_range = rasterize(source, block, units.get(block['field'], {}).get('units', ''))
            if len(payload) > 2 * 1024 * 1024:
                raise ValueError('preview exceeds the 2 MiB block budget')
            item = {'id': block['id'], 'png': base64.b64encode(payload).decode('ascii'),
                    'bytes': len(payload), 'range': data_range,
                    'units': units.get(block['field'], {}).get('units'), 'recipe': block}
            blocks.append(item)
            self.block_cache[block['id']] = (block_key, item)
        result = {'simulation_time': float(time_name), 'time_name': time_name, 'bounds': bounds,
                  'cells': info.GetNumberOfCells(), 'points': info.GetNumberOfPoints(),
                  'fields': self.fields, 'blocks': blocks, 'cache_hit': False,
                  'render_seconds': round(time.monotonic() - started, 3),
                  'worker_peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'source_modified_at': max(stamp / 1e9 for _, _, stamp in signature),
                  'job_id': os.environ.get('SLURM_JOB_ID'), 'source_kind': 'openfoam',
                  'rendered_at': time.time(), 'document': document}
        self.cached_key, self.cached_result = key, result
        return result
