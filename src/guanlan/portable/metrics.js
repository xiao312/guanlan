// User-run real-device observations; these are not GPU-completion measurements.
const events = [];
const frames = [];
let measuring = false;
let activeCount = 0;
let previousFrame = null;
let frameRequest = null;
const resources = { decodedBytes: 0, assetDecodes: 0, topologyBuilds: 0, fieldSelections: 0 };
const environment = { browser: navigator.userAgent, devicePixelRatio: devicePixelRatio,
  hardwareConcurrency: navigator.hardwareConcurrency, gpu: null };
export function record(name, detail = {}) {
  const event = { name, at_ms: performance.now(), ...detail };
  events.push(event);
  if (events.length > 10000) events.shift();
  performance.mark('guanlan:' + name, { detail });
  return event.at_ms;
}
export function account(key, value) { resources[key] += value; }
export function captureGPU(canvas) {
  const gl = canvas.getContext('webgl2');
  if (!gl) return;
  const ext = gl.getExtension('WEBGL_debug_renderer_info');
  environment.gpu = { vendor: gl.getParameter(ext ? ext.UNMASKED_VENDOR_WEBGL : gl.VENDOR),
    renderer: gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER), version: gl.getParameter(gl.VERSION) };
}
function tick(at) {
  if (measuring && activeCount > 0 && previousFrame !== null && frames.length < 20000) frames.push(at - previousFrame);
  previousFrame = at;
  if (measuring && activeCount > 0) frameRequest = requestAnimationFrame(tick);
  else { previousFrame = null; frameRequest = null; }
}
export function interaction(active) {
  activeCount = Math.max(0, activeCount + (active ? 1 : -1));
  record(active ? 'interaction-start' : 'interaction-end');
  if (active && measuring && frameRequest === null) frameRequest = requestAnimationFrame(tick);
}
function percentile(values, p) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a-b);
  return sorted[Math.min(sorted.length-1, Math.ceil(p*sorted.length)-1)];
}
export function measurementControls(manifest) {
  document.querySelector('#measure').onclick = () => {
    measuring = !measuring;
    if (measuring) { frames.length = 0; record('measurement-start'); }
    else record('measurement-end');
    document.querySelector('#measure').textContent = measuring ? 'Stop measurement' : 'Start measurement';
    document.querySelector('#measurement-state').textContent = measuring ? 'Rotate, zoom, change a field; then stop and download' : 'Not measuring';
  };
  document.querySelector('#report').onclick = () => {
    const result = { schema_version: 1, fixture_sha256: manifest.fixture_sha256,
      viewer_sha256: manifest.viewer_sha256, wrapper_sha256: manifest.wrapper_sha256 ?? null, measured_at: new Date().toISOString(),
      environment: { ...environment, viewport: [innerWidth, innerHeight], layout: document.querySelector('#blocks').className },
      canvases: [...document.querySelectorAll('canvas')].map(canvas=>({buffer:[canvas.width,canvas.height],
        css:[canvas.getBoundingClientRect().width,canvas.getBoundingClientRect().height]})),
      cache_condition:'USER_MUST_RECORD', network_profile:location.protocol==='file:'?'offline-file':'USER_MUST_RECORD',
      resources, browser_process_bytes: null, gpu_memory_bytes: null, gpu_time_ms: null,
      js_heap_bytes: performance.memory?.usedJSHeapSize ?? null,
      active_raf: { samples: frames.length, p50_ms: percentile(frames,.5), p95_ms: percentile(frames,.95),
        max_ms: frames.length ? Math.max(...frames) : null, intervals_ms: frames },
      events, caveats: ['rAF intervals during interaction are scheduling proxies, not physical presentation or GPU completion.',
        'First render marks are CPU submission; visual correctness and first-useful-view require observation.',
        'Decoded bytes exclude JS bookkeeping, temporary decoding memory and per-context GPU duplication.',
        'A manual trace is exploratory; report sample count/cache conditions, not a qualified p95 SLA.',
        'Active interval sampling retains the first 20,000 samples per measurement.'] };
    const url = URL.createObjectURL(new Blob([JSON.stringify(result,null,2)], { type:'application/json' }));
    const link = document.createElement('a'); link.href=url; link.download='guanlan-measurements.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url),1000);
  };
}
