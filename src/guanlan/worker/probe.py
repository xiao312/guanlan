"""One-shot compute-node qualification. No case writes."""
import json
import os
import sys

from paraview import simple as pvs
from paraview import servermanager

print('GUANLAN ' + json.dumps({'python': sys.version, 'job': os.environ.get('SLURM_JOB_ID'),
                             'paraview': str(servermanager.vtkSMProxyManager.GetVersionMajor())}), flush=True)
view = pvs.CreateView('RenderView')
view.ViewSize = [320, 200]
sphere = pvs.Sphere()
pvs.Show(sphere, view)
pvs.ResetCamera(view)
pvs.SaveScreenshot(sys.argv[1], view, ImageResolution=[320, 200])
print('GUANLAN ' + json.dumps({'rendered': os.path.getsize(sys.argv[1])}), flush=True)
