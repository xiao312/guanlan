import { account, record } from './metrics.js';
export const manifest = JSON.parse(document.querySelector('#manifest').textContent);
const resident = new Map();
export async function loadAsset(id) {
  if (resident.has(id)) return resident.get(id);
  const loading = (async () => {
    const start = performance.now();
    const meta = manifest.assets[id];
    const encoded = document.getElementById('asset-' + id).textContent.trim();
    const compressed = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
    const buffer = await new Response(stream).arrayBuffer();
    if (buffer.byteLength !== meta.decoded_bytes) throw new Error('Asset length mismatch: ' + id);
    const constructors = { Float32Array, Uint32Array, Float64Array };
    const values = new constructors[meta.dtype](buffer);
    account('decodedBytes', buffer.byteLength); account('assetDecodes', 1);
    record('asset-decoded', { id, bytes: buffer.byteLength, duration_ms: performance.now()-start });
    return values;
  })();
  resident.set(id, loading);
  try { return await loading; } catch (error) { resident.delete(id); throw error; }
}
