"""Direct ParaView reference presentation; never reads portable browser assets."""
from pathlib import Path


def render_slice(source, fields, plane, time_value, output):
    from paraview import simple as pvs
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    view = pvs.CreateView('RenderView')
    view.ViewSize = [1400, 500]
    view.ViewTime = time_value
    view.UseColorPaletteForBackground = 0
    view.Background = [0.945, 0.953, 0.961]
    view.OrientationAxesVisibility = 1
    display = pvs.Show(source, view)
    display.Representation = 'Surface'
    display.InterpolateScalarsBeforeMapping = 0
    # ParaView exposes material coefficients, not vtkActor's Lighting flag.
    display.Ambient = 1
    display.Diffuse = 0
    display.Specular = 0
    bounds = source.GetDataInformation().GetBounds()
    center = [(bounds[2*i] + bounds[2*i+1])/2 for i in range(3)]
    size = max(bounds[2*i+1]-bounds[2*i] for i in range(3))
    direction = {'xy':[0,0,1], 'xz':[0,-1,0], 'yz':[1,0,0]}[plane]
    view.CameraParallelProjection = 1
    view.CameraFocalPoint = center
    view.CameraPosition = [center[i] + 2*size*direction[i] for i in range(3)]
    view.CameraViewUp = [0,1,0] if plane == 'xy' else [0,0,1]
    pvs.ResetCamera(view)
    for field in fields:
        pvs.ColorBy(display, ('CELLS', field))
        lut = pvs.GetColorTransferFunction(field)
        lut.ApplyPreset('Viridis', True)
        limits = source.CellData[field].GetRange()
        lut.RescaleTransferFunction(*limits)
        lut.Discretize = 0
        display.SetScalarBarVisibility(view, True)
        bar = pvs.GetScalarBar(lut, view)
        bar.Title = field + ' | cell values | t=' + str(time_value)
        bar.TitleColor = [0.15, 0.18, 0.22]
        bar.LabelColor = [0.15, 0.18, 0.22]
        bar.Orientation = 'Horizontal'
        bar.WindowLocation = 'Lower Center'
        bar.ScalarBarLength = 0.6
        pvs.SaveScreenshot(str(output / (plane+'-'+field+'.png')), view)
        display.SetScalarBarVisibility(view, False)
    pvs.SaveState(str(output / (plane+'.pvsm')))
    pvs.Delete(view)
