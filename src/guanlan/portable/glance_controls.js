import { record, measurementControls, interaction, captureGPU, account } from './metrics.js';
// Thin qualification wrapper around the downloaded Glance application, not a replacement renderer.
const manifest=JSON.parse(document.querySelector('#manifest').textContent);
measurementControls(manifest);record('manifest-ready');
const note=document.querySelector('#comparison-status');
async function start() {
  const instance=Glance.createViewer(document.querySelector('#root-container'));
  instance.setSetting('noHistory',true);
  await instance.store.dispatch('views/initViews');
  instance.showApp();
  await new Promise(resolve=>requestAnimationFrame(resolve));
  const manager=instance.proxyManager;
  const sources={};
  for(const item of manifest.vtp_files) {
    const started=performance.now();
    const packed=Uint8Array.from(atob(document.getElementById('vtp-'+item.name).textContent.trim()),c=>c.charCodeAt(0));
    const data=await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
    const readers=await Glance.loadFiles([new File([data],item.name+'.vtp')]);
    sources[item.name]=Glance.registerReadersToProxyManager(readers,manager)[0];
    const dataset=sources[item.name].getDataset();
    let arrayBytes=dataset.getPoints().getData().byteLength+dataset.getPolys().getData().byteLength+dataset.getLines().getData().byteLength;
    for(const array of dataset.getCellData().getArrays())arrayBytes+=array.getData().byteLength;
    account('decodedBytes',arrayBytes);account('assetDecodes',1);
    record('vtp-registered',{name:item.name,xml_bytes:data.byteLength,array_bytes:arrayBytes,duration_ms:performance.now()-started});
  }
  const views=manager.getViews();
  const view=views.find(v=>v.getProxyName()==='View3D');
  if(!view)throw new Error('Glance did not initialize its 3D view');
  instance.store.commit('views/setGlobalBackground','#f1f3f5');
  const camera=view.getRenderer().getActiveCamera();camera.setParallelProjection(true);
  const reps={};
  for(const [name,source] of Object.entries(sources)) {
    reps[name]=manager.getRepresentation(source,view);
    reps[name].setInterpolateScalarsBeforeMapping(false);
    reps[name].setColor(name==='surface-edges'?[.16,.22,.26]:[.63,.71,.76]);
    if(name==='surface-edges')for(const actor of reps[name].getActors())actor.getMapper().setResolveCoincidentTopologyToPolygonOffset();
  }
  function reset() {
    const b=sources.surface.getDataset().getBounds();
    const center=[0,1,2].map(i=>(b[2*i]+b[2*i+1])/2);
    const size=Math.max(b[1]-b[0],b[3]-b[2],b[5]-b[4]);
    camera.setFocalPoint(...center);camera.setPosition(center[0],center[1],center[2]+2*size);camera.setViewUp(0,1,0);
    view.getRenderer().resetCamera();view.getRenderer().resetCameraClippingRange();manager.renderAllViews();
  }
  const mode=document.querySelector('#comparison-mode'),field=document.querySelector('#comparison-field');
  function change() {
    const began=performance.now();
    const visible=mode.value==='geometry'?['surface']:mode.value==='mesh'?['surface','surface-edges']:['xy'];
    for(const [name,rep] of Object.entries(reps))rep.setVisibility(visible.includes(name));
    const selected=manifest.datasets.xy.fields[field.value];
    reps.xy.setColorBy(field.value,'cellData');reps.xy.setUseShadow(false);
    const lut=manager.getLookupTable(field.value);lut.setPresetName('Cool to Warm');lut.setDataRange(...selected.range);
    manager.renderAllViews();
    record('field-render-submitted',{mode:mode.value,field:field.value,duration_ms:performance.now()-began});
    note.textContent=`${mode.value} · ${field.value} [${selected.units}] · frozen t=${manifest.simulation_time} s. Single-view Glance control; not a multi-block equivalent.`;
  }
  mode.onchange=()=>{change();reset();};field.onchange=change;document.querySelector('#comparison-reset').onclick=reset;
  for(const v of views){v.getRenderWindow().getInteractor().onStartAnimation(()=>interaction(true));v.getRenderWindow().getInteractor().onEndAnimation(()=>interaction(false));}
  change();reset();
  const canvas=document.querySelector('canvas');if(canvas)captureGPU(canvas);
  document.querySelectorAll('#comparison-bar select,#comparison-reset').forEach(n=>n.disabled=false);
  record('comparison-first-render-submitted');
}
start().catch(error=>{note.textContent='Glance comparison could not initialize: '+error.message;record('comparison-error',{message:error.message});});
