import { manifest } from './loader.js';
import { createView } from './render.js';
import { measurementControls, record } from './metrics.js';

function element(tag, text, className) {
  const node=document.createElement(tag); if(text)node.textContent=text;if(className)node.className=className;return node;
}
function select(options, value) {
  const node=element('select');
  for(const [id,label] of options) { const option=element('option',label); option.value=id;node.append(option); }
  node.value=value;return node;
}
function labeled(parent, title, control) { const label=element('label',title+' ');label.append(control);parent.append(label); }
const numeric = value => Number(value).toPrecision(5);
function makeBlock(block,index) {
  const source=manifest.datasets[block.dataset];
  const section=element('section',null,'block');section.id='block-'+index;
  const title=block.kind==='geometry'?'Geometry':block.kind==='mesh'?'Mesh':block.plane.toUpperCase()+' slice';
  const heading=element('div',null,'block-title');heading.append(element('h2',title),element('span',`${source.cell_count.toLocaleString()} polygons`,'badge'));
  const viewport=element('div',null,'viewport');viewport.append(element('p','Prepared data · loading when visible','placeholder'));
  const controls=element('div',null,'controls');
  const camera=select(['xy','xz','yz','isometric'].map(s=>[s,s.toUpperCase()]),block.camera);labeled(controls,'Camera',camera);
  const reset=element('button','Reset');controls.append(reset);
  const status=element('div',block.kind==='mesh'?'Original extracted surface edges; no triangulation diagonals':'Original extracted surface; not CAD','status');
  const legend=element('div',null,'legend');
  const hint=element('p','Left-drag: rotate · Middle-drag or Shift-left-drag: pan · Scroll: zoom','hint');
  section.append(heading,viewport,controls,hint,legend,status);document.querySelector('#blocks').append(section);
  const link=element('a',`${String(index+1).padStart(2,'0')}  ${title}`);link.href='#'+section.id;document.querySelector('#nav').append(link);
  let view=null,field=null,palette=null,low=null,high=null,bins=null;
  const settings=[];
  function showLegend(info) {
    if(!info)return;legend.replaceChildren();
    const ramp=element('div',null,'ramp');ramp.style.background=info.gradient;
    legend.append(element('span',numeric(info.low)),ramp,element('span',numeric(info.high)),element('span',info.units));
    status.textContent=info.label+' · cell values, no interpolation · t = '+manifest.simulation_time+' s';
    if(info.distinctValues!==null) status.textContent+=` · Only ${info.distinctValues} distinct values in this prepared field`;
  }
  function limits() {
    if(!low.value&&!high.value)return null;
    const values=[Number(low.value),Number(high.value)];
    if(!low.value||!high.value||!values.every(Number.isFinite)||values[0]>=values[1])throw new Error('Enter both finite limits with minimum < maximum.');
    return values;
  }
  function guarded(fn) { return async()=>{try{await fn();}catch(error){status.textContent=error.message;}}; }
  if(block.kind==='slice') {
    field=select(Object.entries(source.fields).map(([id,f])=>[id,f.label]),block.field);
    palette=select([['Cool to Warm','Cool to warm'],['Viridis (matplotlib)','Viridis']],'Viridis (matplotlib)');
    bins=select([['0','Continuous'],['8','8 bands'],['12','12 bands'],['24','24 bands']],'0');
    labeled(controls,'Colors',bins);
    low=element('input');high=element('input');low.placeholder='Auto min';high.placeholder='Auto max';
    low.type=high.type='number';low.step=high.step='any';
    labeled(controls,'Field',field);labeled(controls,'Palette',palette);labeled(controls,'Min',low);labeled(controls,'Max',high);
    const apply=element('button','Apply range'),auto=element('button','Auto');controls.append(apply,auto);
    field.onchange=guarded(async()=>{low.value=high.value='';showLegend(await view.field(field.value,palette.value,null,Number(bins.value)));});
    palette.onchange=bins.onchange=guarded(()=>showLegend(view.colors(palette.value,limits(),Number(bins.value))));
    apply.onclick=guarded(()=>showLegend(view.colors(palette.value,limits(),Number(bins.value))));
    auto.onclick=guarded(()=>{low.value=high.value='';showLegend(view.colors(palette.value,null,Number(bins.value)));});
    settings.push(field,palette,bins,low,high,apply,auto);
  }
  if(block.kind==='mesh') {
    const edges=element('input');edges.type='checkbox';edges.checked=true;edges.style.width='auto';
    labeled(controls,'Original edges',edges);edges.onchange=()=>view.edges(edges.checked);settings.push(edges);
  }
  settings.push(camera,reset);settings.forEach(s=>s.disabled=true);
  reset.onclick=()=>view.reset(camera.value);camera.onchange=()=>view.reset(camera.value);
  const observer=new IntersectionObserver(async entries=>{
    if(!entries.some(e=>e.isIntersecting))return;observer.disconnect();
    try {
      view=await createView(viewport,block);
      if(field)showLegend(await view.field(field.value,palette.value,null));
      settings.forEach(s=>s.disabled=false);
    } catch(error) { viewport.replaceChildren(element('p','Cannot initialize interactive view: '+error.message,'placeholder'));status.textContent='Requires a modern browser with WebGL2 and gzip decompression.';record('block-error',{block:block.id,message:error.message}); }
  },{rootMargin:'100px'});observer.observe(section);
}
try {
  record('manifest-ready');
  document.querySelector('#subtitle').textContent=`Frozen at t = ${manifest.simulation_time} s · ${manifest.metrics.source} · no live connection`;
  if(!manifest.metrics.physical_patch_faces) document.querySelector('#subtitle').textContent+=' · DIAGNOSTIC: physical boundary not qualified';
  document.querySelector('#case-path').textContent=manifest.case_directory;
  document.querySelector('#coverage').textContent=manifest.coverage;
  document.querySelector('#details').textContent=JSON.stringify({fixture:manifest.fixture_sha256,viewer:manifest.viewer_sha256,fidelity:manifest.fidelity,metrics:manifest.metrics,blocks:manifest.blocks},null,2);
  document.querySelector('#theme').onchange=e=>document.body.dataset.theme=e.target.value;
  document.querySelector('#layout').onclick=()=>{const multi=document.querySelector('#blocks').classList.toggle('columns');document.querySelector('#layout').textContent=multi?'Switch to one column':'Switch to two columns';record('layout-changed',{columns:multi?2:1});};
  measurementControls(manifest);manifest.blocks.forEach(makeBlock);
} catch(error) {document.querySelector('#error').textContent=error.message;}
