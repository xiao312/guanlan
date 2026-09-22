const selector = document.querySelector('#view');
const preview = document.querySelector('#preview');
const status = document.querySelector('#status');
const caption = document.querySelector('#caption');
const snapshot = document.querySelector('#snapshot');
const share = document.querySelector('#share');
const notice = document.querySelector('#notice');
let generation = 0;
let timer;
let currentBlobUrl;

async function getJson(url) {
  const response = await fetch(url, {signal: AbortSignal.timeout(10000)});
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function refresh(version) {
  let interval = 2;
  try {
    const view = selector.value;
    const envelope = await getJson(`/api/preview?view=${encodeURIComponent(view)}`);
    interval = envelope.poll_interval_seconds;
    const response = await fetch(envelope.image_url, {signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error(`Image failed: ${response.status}`);
    const blobUrl = URL.createObjectURL(await response.blob());
    const candidate = new Image();
    candidate.src = blobUrl;
    try { await candidate.decode(); } catch (error) { URL.revokeObjectURL(blobUrl); throw error; }
    if (version !== generation) { URL.revokeObjectURL(blobUrl); return; }
    const oldUrl = currentBlobUrl;
    currentBlobUrl = blobUrl;
    preview.src = blobUrl;
    if (oldUrl) URL.revokeObjectURL(oldUrl);
    caption.textContent = `${envelope.case_id} · t = ${envelope.simulation_time.toFixed(3)} s · frame ${envelope.frame_id}`;
    snapshot.href = `/snapshot?view=${encodeURIComponent(view)}&frame=${envelope.frame_id}`;
    snapshot.setAttribute('aria-disabled', 'false');
    status.textContent = '● Following latest';
    if (notice.textContent.startsWith('Keeping the last displayed')) {
      notice.textContent = 'Local development fixture. These images are synthetic, not results from your simulations.';
    }
    share.disabled = false;
  } catch (error) {
    if (version !== generation) return;
    status.textContent = 'Connection unavailable · retrying';
    notice.textContent = 'Keeping the last displayed preview. Check that the local demo server is running.';
  } finally {
    if (version === generation) timer = setTimeout(() => refresh(version), interval * 1000);
  }
}

function changeView() {
  clearTimeout(timer);
  generation += 1;
  history.replaceState(null, '', `/?view=${encodeURIComponent(selector.value)}`);
  snapshot.removeAttribute('href');
  snapshot.setAttribute('aria-disabled', 'true');
  share.disabled = true;
  status.textContent = 'Loading saved view…';
  refresh(generation);
}

selector.addEventListener('change', changeView);
share.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(location.href);
    notice.textContent = 'Local live link copied. It is only usable where this development server is reachable.';
  } catch {
    notice.textContent = `Copy the address from your browser: ${location.href}`;
  }
});

async function start() {
  try {
    const recipes = await getJson('/api/views');
    for (const recipe of recipes) {
      const option = document.createElement('option');
      option.value = recipe.id;
      option.textContent = recipe.panels.map(panel => panel.field === 'U' ? 'Velocity magnitude' : 'Pressure').join(' + ');
      selector.append(option);
    }
    const requested = new URLSearchParams(location.search).get('view');
    selector.value = recipes.some(recipe => recipe.id === requested) ? requested : recipes[0].id;
    changeView();
  } catch {
    status.textContent = 'Cannot load saved views';
    notice.textContent = 'Start the demo server, then reload this page.';
  }
}
start();
