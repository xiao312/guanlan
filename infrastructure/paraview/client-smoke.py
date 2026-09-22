"""Native client protocol check through an already established loopback tunnel."""
import sys
from pathlib import Path
from paraview import simple as pvs

output = Path(sys.argv[1]).resolve()
if output.suffix != '.png' or not output.parent.is_dir():
    raise ValueError('Supply a PNG path in an existing output directory')
connection = pvs.Connect('127.0.0.1', 11111)
if connection is None:
    raise RuntimeError('No allocated server reachable through the SSH tunnel')
try:
    view = pvs.CreateView('RenderView')
    view.RemoteRenderThreshold = 0
    view.ViewSize = [640, 480]
    pvs.Show(pvs.Sphere(), view)
    pvs.ResetCamera(view)
    pvs.SaveScreenshot(str(output), view)
finally:
    pvs.Disconnect()
