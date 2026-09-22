const $ = selector => document.querySelector(selector);
let state;
let renderedRevision;
let displayedGeneration;
let renderedCatalog;
let dirty = false;
const labels = {geometry: 'Geometry', mesh: 'Mesh', slice: 'Slice'};
const names = {U: 'Velocity magnitude', p: 'Pressure', T: 'Temperature'};
const number = index => String(index + 1).padStart(2, '0');

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function fieldName(field) { return names[field] || field; }
function title(block) { return block.kind === 'slice' ? fieldName(block.field) : labels[block.kind]; }
function notice(message) { $('#notice').textContent = message; $('#notice').hidden = !message; }

function select(label, name, values, current) {
  const wrapper = node('label', label);
  const input = node('select'); input.name = name;
  for (const [value, text] of values) {
    const option = node('option', text); option.value = value; input.append(option);
  }
  input.value = current; wrapper.append(input); return wrapper;
}
function numeric(label, name, value, min, max) {
  const wrapper = node('label', label), input = node('input');
  input.type = 'number'; input.name = name; input.step = 'any'; input.value = value ?? '';
  if (min !== undefined) input.min = min;
  if (max !== undefined) input.max = max;
  wrapper.append(input); return wrapper;
}

async function save(document) {
  const response = await fetch('/api/document', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({document, revision: state.revision})});
  if (!response.ok) throw new Error(response.status === 403 ? 'This shared view is read-only. Edit from the owner’s local page.' : 'Could not save. Check the ranges or reload if another tab changed this case.');
  state = {...state, ...await response.json()};
  dirty = false; renderedRevision = undefined; displayedGeneration = undefined;
  update(); notice(['idle','unavailable'].includes(state.status)
    ? 'View saved. Use Reconnect to render the updated blocks; the last completed images remain available.'
    : 'View saved. Preparing the updated blocks; the previous images remain visible until ready.');
}

function buildBlock(block, index) {
  const card = node('section', undefined, 'block'); card.id = `block-${block.id}`;
  const head = node('div', undefined, 'block-head'), heading = node('div', undefined, 'block-title');
  heading.append(node('span', number(index), 'number'), node('h2', title(block)), node('small', block.kind === 'slice' ? `${block.plane.toUpperCase()} · ${block.offset * 100}%` : block.kind === 'geometry' ? 'Domain boundary' : 'Surface edges'));
  const tools = node('div', undefined, 'block-tools');
  const expand = node('button', 'Expand'); expand.onclick = () => card.requestFullscreen?.(); tools.append(expand);
  const settings = node('div', undefined, 'settings'); settings.hidden = true;
  const configure = node('button', 'Configure'); configure.disabled = !state.editable;
  configure.onclick = () => { settings.hidden = !settings.hidden; }; tools.append(configure);
  if (index > 1 && state.editable) {
    const remove = node('button', 'Remove');
    remove.onclick = async () => { const document = structuredClone(state.document); document.blocks = document.blocks.filter(b => b.id !== block.id); try { await save(document); } catch (error) { notice(error.message); } };
    tools.append(remove);
  }
  head.append(heading, tools); card.append(head);
  const imageArea = node('div', undefined, 'image-area');
  imageArea.append(node('div', 'Preparing the real case preview…', 'waiting'));
  card.append(imageArea, node('div', 'Waiting for readable output', 'block-caption'));
  const form = node('form');
  if (block.kind === 'slice') {
    form.append(select('Field', 'field', state.fields.map(f => [f, fieldName(f)]), block.field));
    form.append(select('Plane', 'plane', ['xz', 'xy', 'yz'].map(p => [p, p.toUpperCase()]), block.plane));
    form.append(numeric('Position (%)', 'offset', block.offset * 100, 0.1, 99.9));
    form.append(select('Colors', 'palette', [['viridis','Viridis'],['coolwarm','Cool / warm']], block.palette));
    form.append(numeric('Minimum (auto if blank)', 'low', block.range?.[0]), numeric('Maximum (auto if blank)', 'high', block.range?.[1]));
  }
  form.append(select('Camera', 'camera', ['plane','xy','xz','yz','isometric'].map(c => [c, c === 'plane' ? 'Face plane' : c.toUpperCase()]), block.camera));
  const apply = node('button', 'Apply'); apply.className = 'primary'; form.append(apply);
  form.addEventListener('input', () => { dirty = true; });
  form.onsubmit = async event => {
    event.preventDefault(); const values = new FormData(form), document = structuredClone(state.document);
    const target = document.blocks.find(b => b.id === block.id);
    target.camera = values.get('camera');
    if (block.kind === 'slice') {
      for (const key of ['field','plane','palette']) target[key] = values.get(key);
      target.offset = Number(values.get('offset')) / 100;
      const low = values.get('low'), high = values.get('high');
      if ((low === '') !== (high === '')) { notice('Enter both color-range bounds, or leave both blank for automatic scaling.'); return; }
      target.range = low === '' ? null : [Number(low), Number(high)];
    }
    try { await save(document); } catch (error) { notice(error.message); }
  };
  settings.append(form); card.append(settings); return card;
}

function update() {
  $('#share').disabled = false;
  $('#title').textContent = state.title; $('#rail-title').textContent = state.case_id;
  $('#case-name').textContent = state.case_id; $('#case-path').textContent = state.case_directory;
  $('#connection').textContent = state.status === 'following' ? 'Live' : state.status;
  $('#worker').textContent = state.job_id ? `Worker ${state.job_id} · allocated compute` : 'Waiting for allocation';
  $('#summary').textContent = state.message;
  $('#snapshot').hidden = !state.preview;
  $('#reconnect').hidden = !state.editable || !['idle','unavailable'].includes(state.status);
  for (const id of ['#add-block','#add-bottom']) $(id).disabled = !state.editable || !state.fields.length || state.document.blocks.length >= 8;
  if ((renderedRevision !== state.revision || renderedCatalog !== state.fields.join(',')) && !dirty) {
    $('#blocks').replaceChildren(...state.document.blocks.map(buildBlock));
    $('#block-nav').replaceChildren(...state.document.blocks.map((block, index) => {
      const link = node('a'); link.href = `#block-${block.id}`;
      link.append(node('span', number(index), 'number'), node('span', title(block), 'nav-name')); return link;
    }));
    $('#block-count').textContent = String(state.document.blocks.length).padStart(2,'0');
    renderedRevision = state.revision; displayedGeneration = undefined;
    renderedCatalog = state.fields.join(',');
  }
  if (state.preview) {
    const preview = state.preview;
    $('#sim-time').textContent = `${preview.simulation_time.toFixed(7)} s`;
    if (displayedGeneration !== preview.generation) {
      for (const item of preview.blocks) {
        const card = document.getElementById(`block-${item.id}`); if (!card) continue;
        const img = node('img'); img.alt = `${title(item.recipe)} at simulation time ${preview.simulation_time} seconds`;
        img.src = `/image/${preview.generation}/${item.id}.png`;
        img.onload = () => { if (state.preview?.generation === preview.generation) card.querySelector('.image-area').replaceChildren(img); };
        const pending = preview.revision !== state.revision;
        const description = item.recipe.field ? `${item.recipe.field} · ${item.units} · ${item.recipe.plane.toUpperCase()} plane` : item.recipe.kind === 'geometry' ? 'CFD domain boundary · not original CAD' : 'Surface mesh · actual cell edges';
        card.querySelector('.block-caption').replaceChildren(node('span', description), node('span', `${(item.bytes / 1024).toFixed(0)} KB · t = ${preview.simulation_time} s${pending ? ' · updating settings' : ''}`));
      }
      displayedGeneration = preview.generation;
    }
  }
}

async function poll() {
  try {
    const response = await fetch('/api/state', {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('unavailable');
    const incoming = await response.json();
    if (!incoming.fields.length && incoming.preview?.fields) incoming.fields = incoming.preview.fields;
    if (dirty && state && incoming.revision !== state.revision) notice('Another tab changed the page. Reload before applying your draft edits.');
    else { state = incoming; update(); }
  } catch { $('#connection').textContent = 'Disconnected'; notice('The case service is unavailable. Keeping the displayed images.'); }
  setTimeout(poll, 3000);
}

function addDialog() {
  $('#new-field').replaceChildren(...state.fields.map(field => { const option = node('option', fieldName(field)); option.value = field; return option; }));
  $('#new-field').value = state.fields.includes('p') ? 'p' : state.fields[0];
  $('#add-dialog').showModal();
}
$('#add-block').onclick = addDialog; $('#add-bottom').onclick = addDialog;
$('#cancel-add').onclick = () => $('#add-dialog').close();
$('#add-form').onsubmit = async event => {
  event.preventDefault(); const document = structuredClone(state.document);
  document.blocks.push({id: `slice-${Date.now()}`, kind:'slice', field:$('#new-field').value, plane:$('#new-plane').value, offset:Number($('#new-offset').value)/100, camera:'plane', palette:'viridis', range:null});
  try { await save(document); $('#add-dialog').close(); } catch (error) { notice(error.message); }
};
$('#theme').onchange = () => { document.documentElement.dataset.theme = $('#theme').value; localStorage.setItem('guanlan-theme', $('#theme').value); };
const storedTheme = localStorage.getItem('guanlan-theme');
if (['paper','graphite','midnight'].includes(storedTheme)) { $('#theme').value = storedTheme; document.documentElement.dataset.theme = storedTheme; }
$('#share').onclick = () => { $('#share-url').value = location.origin + state.case_url; $('#share-dialog').showModal(); };
$('#reconnect').onclick = async () => {
  try {
    const response = await fetch('/api/reconnect', {method:'POST'});
    if (!response.ok) throw new Error('Could not reconnect; the worker may still be ending.');
    notice('Reconnecting. The last completed views stay available while compute starts.');
  } catch (error) { notice(error.message); }
};
$('#close-share').onclick = () => $('#share-dialog').close();
$('#copy-share').onclick = async () => { try { await navigator.clipboard.writeText($('#share-url').value); $('#share-note').textContent = 'Copied. Recipients need access to this endpoint. The live share is read-only.'; } catch { $('#share-url').select(); $('#share-note').textContent = 'Select and copy this address.'; } };
poll();
