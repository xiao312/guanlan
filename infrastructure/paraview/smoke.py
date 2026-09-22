"""Run only in an allocated environment; output directory supplied explicitly."""
import json
import os
import sys
from pathlib import Path

if not os.environ.get('SLURM_JOB_ID'):
    raise RuntimeError('An explicit Slurm allocation is required')
from paraview import simple as pvs

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
view = pvs.CreateView('RenderView')
view.ViewSize = [640, 480]
pvs.Show(pvs.Sphere(), view)
pvs.ResetCamera(view)
pvs.Render(view)
pvs.SaveScreenshot(str(output / 'sphere.png'), view)
report = {'version': str(pvs.GetParaViewVersion()),
          'job_id': os.environ['SLURM_JOB_ID'],
          'capabilities': view.GetRenderWindow().ReportCapabilities()}
(output / 'smoke.json').write_text(json.dumps(report, indent=2))
