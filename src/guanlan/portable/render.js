import '@kitware/vtk.js/Rendering/Profiles/Geometry';
import vtkGenericRenderWindow from '@kitware/vtk.js/Rendering/Misc/GenericRenderWindow';
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray';
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';
import colorMaps from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction/ColorMaps';
import { loadAsset, manifest } from './loader.js';
import { record, account, interaction, captureGPU } from './metrics.js';

export async function createView(container, block) {
  const source = manifest.datasets[block.dataset];
  const [points, polys] = await Promise.all([loadAsset(source.points), loadAsset(source.polys)]);
  if(points.length!==source.point_count*3 || !points.every(Number.isFinite))throw new Error('Invalid point array');
  let cursor=0, cells=0;
  while(cursor<polys.length) {
    const size=polys[cursor++];
    if(size<3 || cursor+size>polys.length)throw new Error('Invalid polygon structure');
    for(let i=0;i<size;i++)if(polys[cursor++]>=source.point_count)throw new Error('Invalid point reference');
    cells++;
  }
  if(cells!==source.cell_count)throw new Error('Polygon count mismatch');
  if(source.geometry_id) {
    const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source.points+':'+source.polys));
    const geometry=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
    if(geometry!==source.geometry_id)throw new Error('Geometry identity mismatch');
  }
  const data = vtkPolyData.newInstance();
  data.getPoints().setData(points, 3); data.getPolys().setData(polys);
  account('topologyBuilds', 1);
  const generic = vtkGenericRenderWindow.newInstance({ background:[.945,.953,.961] });
  container.replaceChildren(); generic.setContainer(container);
  // TrackballCamera binds shift-left pan, but does not bind the middle button.
  const style = generic.getInteractor().getInteractorStyle();
  style.handleMiddleButtonPress = event => style.handleLeftButtonPress({...event, shiftKey:true, controlKey:false, altKey:false});
  style.handleMiddleButtonRelease = () => style.handleLeftButtonRelease();
  container.addEventListener('auxclick', event => { if(event.button===1) event.preventDefault(); });
  const renderer = generic.getRenderer(), window = generic.getRenderWindow();
  const mapper = vtkMapper.newInstance({ scalarVisibility:false }); mapper.setInputData(data);
  const actor = vtkActor.newInstance(); actor.setMapper(mapper);
  actor.getProperty().setColor(.63,.71,.76);
  actor.getProperty().setInterpolationToFlat();
  renderer.addActor(actor);
  let edgeActor = null;
  if (block.kind === 'mesh') {
    const edges = vtkPolyData.newInstance(); edges.getPoints().setData(points,3);
    edges.getLines().setData(await loadAsset(source.edges));
    const edgeMapper = vtkMapper.newInstance({ scalarVisibility:false }); edgeMapper.setInputData(edges);
    edgeMapper.setResolveCoincidentTopologyToPolygonOffset();
    edgeActor = vtkActor.newInstance(); edgeActor.setMapper(edgeMapper);
    edgeActor.getProperty().setColor(.16,.22,.26); edgeActor.getProperty().setLineWidth(1);
    renderer.addActor(edgeActor);
  }
  const camera = renderer.getActiveCamera(); camera.setParallelProjection(true);
  const lut = vtkColorTransferFunction.newInstance(); mapper.setLookupTable(lut);
  mapper.setUseLookupTableScalarRange(true);
  mapper.setInterpolateScalarsBeforeMapping(false);
  let selected = null, requestVersion = 0, distinctValues = null;
  function draw(reason) {
    const start = performance.now(); window.render();
    record('render-submitted', { block:block.id, reason, cpu_ms:performance.now()-start });
  }
  function reset(pose=block.camera) {
    const b = data.getBounds(), center = [0,1,2].map(i=>(b[i*2]+b[i*2+1])/2);
    const size = Math.max(b[1]-b[0],b[3]-b[2],b[5]-b[4],1e-6);
    const direction = {xy:[0,0,1],xz:[0,-1,0],yz:[1,0,0],isometric:[1,-1,1]}[pose];
    camera.setFocalPoint(...center); camera.setPosition(...center.map((v,i)=>v+direction[i]*size*2));
    camera.setViewUp(...(pose === 'xy' ? [0,1,0] : [0,0,1]));
    renderer.resetCamera(); renderer.resetCameraClippingRange(); draw('camera-preset');
  }
  function colors(palette, limits, bins=0) {
    if (!selected) return null;
    const field = source.fields[selected];
    const [low, high] = limits || field.range;
    const upper = high === low ? low + Math.max(1, Math.abs(low)*1e-6) : high;
    lut.applyColorMap(colorMaps.getPresetByName(palette));
    lut.setDiscretize(bins > 0); lut.setNumberOfValues(bins || 256);
    lut.setMappingRange(low,upper); lut.updateRange(); mapper.setScalarRange(low,upper);
    mapper.modified();
    record('scalar-mapping',{block:block.id,field:selected,range:[low,upper],palette,bins});
    const stops=[];
    for (let i=0;i<=16;i++) {
      const rgb=[]; lut.getColor(low+(upper-low)*i/16,rgb);
      stops.push(`rgb(${rgb.map(c=>Math.round(c*255)).join(',')}) ${i/16*100}%`);
    }
    draw('palette-range');
    return { low, high, distinctValues, reader_dtype:field.reader_dtype, units:field.units, label:field.label, gradient:`linear-gradient(to right,${stops.join(',')})` };
  }
  async function field(name, palette, limits, bins=0) {
    const version=++requestVersion, start=performance.now();
    const descriptor=source.fields[name];
    if(source.geometry_id && (descriptor.geometry_id!==source.geometry_id || descriptor.tuples!==source.cell_count || descriptor.components!==1)) {
      throw new Error('Field geometry binding mismatch');
    }
    const values=await loadAsset(descriptor.asset);
    if (version !== requestVersion) return null;
    if(values.length!==source.cell_count || !values.every(Number.isFinite))throw new Error('Invalid cell values');
    const distinct = new Set();
    for(const value of values) { distinct.add(value); if(distinct.size>24)break; }
    distinctValues = distinct.size<=24 ? distinct.size : null;
    const old=data.getCellData().getScalars();
    data.getCellData().removeAllArrays();
    data.getCellData().setScalars(vtkDataArray.newInstance({name,numberOfComponents:1,values}));
    if (old) old.delete();
    selected=name; mapper.setScalarVisibility(true); mapper.setScalarModeToUseCellData();
    mapper.setColorModeToMapScalars(); actor.getProperty().setLighting(false);
    const legend=colors(palette,limits,bins); account('fieldSelections',1);
    record('field-render-submitted',{block:block.id,field:name,duration_ms:performance.now()-start});
    return legend;
  }
  generic.getInteractor().onStartAnimation(()=>interaction(true));
  generic.getInteractor().onEndAnimation(()=>interaction(false));
  const resize = new ResizeObserver(()=>generic.resize()); resize.observe(container);
  container.addEventListener('webglcontextlost',event=>{event.preventDefault(); record('context-lost',{block:block.id});},true);
  generic.resize(); reset();
  captureGPU(container.querySelector('canvas'));
  record('block-first-render-submitted',{block:block.id,cells:source.cell_count,points:source.point_count});
  return { reset, field, colors, edges(show) { if(edgeActor){edgeActor.setVisibility(show);draw('edges');} } };
}
