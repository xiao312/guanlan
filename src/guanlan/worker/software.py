"""Orthographic polygon rasterizer using ParaView's bundled Matplotlib Agg.

No OpenGL/X server is needed. Geometry is projected and depth sorted; this is an
image preview, not an interactive depth-buffered 3D renderer.
"""
import io
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import PolyCollection
from matplotlib.colors import Normalize
from paraview import servermanager
from vtkmodules.vtkFiltersGeometry import vtkCompositeDataGeometryFilter
from vtkmodules.util.numpy_support import vtk_to_numpy


def rasterize(source, block, units):
    data = servermanager.Fetch(source)
    if data.IsA('vtkCompositeDataSet'):
        geometry = vtkCompositeDataGeometryFilter()
        geometry.SetInputData(data)
        geometry.Update()
        data = geometry.GetOutput()
    if not data.IsA('vtkPolyData') or not data.GetNumberOfCells():
        raise ValueError('no surface polygons to render')
    points = vtk_to_numpy(data.GetPoints().GetData())
    polys = data.GetPolys()
    offsets = vtk_to_numpy(polys.GetOffsetsArray())
    indices = vtk_to_numpy(polys.GetConnectivityArray())
    camera = block['plane'] if block['camera'] == 'plane' else block['camera']
    axes = {'xy': (0, 1, 2), 'xz': (0, 2, 1), 'yz': (1, 2, 0)}
    if camera == 'isometric':
        # Orthogonal basis with x to the right, z up; painter ordering by depth.
        matrix = np.array([[0.7071, 0.7071, 0], [-0.4082, 0.4082, 0.8165], [0.5774, -0.5774, 0.5774]])
        projected = points @ matrix.T
        labels = ('projected coordinate [m]', 'projected coordinate [m]')
    else:
        order = axes[camera]
        projected = points[:, order]
        labels = ('xyz'[order[0]] + ' [m]', 'xyz'[order[1]] + ' [m]')
    vertices = [projected[indices[offsets[i]:offsets[i + 1]]] for i in range(len(offsets) - 1)]
    depth = np.array([v[:, 2].mean() for v in vertices])
    ordering = np.argsort(depth)
    polygons = [vertices[i][:, :2] for i in ordering]
    figure = Figure(figsize=(11, 4.4), dpi=100, facecolor='#f7f8fa')
    canvas = FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    axis.set_facecolor('#f7f8fa')
    data_range = None
    if block['kind'] == 'slice':
        array = data.GetCellData().GetArray(block['field'])
        if array is None:
            raise ValueError('requested cell field missing: ' + block['field'])
        # VTK may expose float32 arrays even when the solver writes doubles.
        # Accumulate magnitude in float64 with hypot to avoid square overflow.
        values = vtk_to_numpy(array).astype(np.float64, copy=False)
        if values.ndim == 2:
            values = np.hypot.reduce(values, axis=1)
        if not np.isfinite(values).all():
            raise ValueError('field contains non-finite values; keeping last-good preview')
        data_range = [float(values.min()), float(values.max())]
        limits = block['range'] or data_range
        collection = PolyCollection(polygons, array=values[ordering], cmap=block['palette'],
                                    norm=Normalize(*limits), edgecolors='none', rasterized=True)
        figure.colorbar(collection, ax=axis, fraction=0.035, pad=0.025,
                        label=block['field'] + ' [' + units + ']')
    else:
        collection = PolyCollection(polygons, facecolors='#b1bac5',
                                    edgecolors='#425065' if block['kind'] == 'mesh' else 'none',
                                    linewidths=0.12, rasterized=True)
    axis.add_collection(collection)
    axis.autoscale_view()
    axis.set_aspect('equal', adjustable='box')
    axis.set_xlabel(labels[0], color='#617083', fontsize=9)
    axis.set_ylabel(labels[1], color='#617083', fontsize=9)
    axis.tick_params(labelsize=8, colors='#617083')
    for spine in axis.spines.values():
        spine.set_color('#dce1e7')
    figure.tight_layout(pad=1.4)
    buffer = io.BytesIO()
    canvas.print_png(buffer)
    return buffer.getvalue(), data_range
