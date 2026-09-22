import { account, record } from './metrics.js';
export const manifest = JSON.parse(document.querySelector('#manifest').textContent);
if(!Array.isArray(manifest.blocks) || manifest.blocks.length<1 || manifest.blocks.length>8)throw new Error('Block budget exceeded');
const resident = new Map();
const limit = 64*1024*1024;
const constructors = { Float32Array, Uint32Array, Float64Array };
let queue = Promise.resolve();
let budget = 0;
for(const [id,meta] of Object.entries(manifest.assets)) {
  if(!/^[a-f0-9]{64}$/.test(id) || !constructors[meta.dtype]
    || (meta.codec && meta.codec!=='gzip')
    || !Number.isSafeInteger(meta.decoded_bytes) || meta.decoded_bytes<=0
    || !Number.isSafeInteger(meta.compressed_bytes) || meta.compressed_bytes<=0
    || meta.compressed_bytes>limit || meta.decoded_bytes % constructors[meta.dtype].BYTES_PER_ELEMENT) {
    throw new Error('Invalid prepared asset metadata');
  }
  budget+=meta.decoded_bytes;
}
// Frozen selected manifests have a finite lifetime; reject oversized working sets.
// No frame accumulation. Serial decoding bounds temporary decompression work.
if(budget>limit)throw new Error('Selected arrays exceed the 64 MiB decoded budget');

async function boundedBytes(stream, maximum) {
  const reader=stream.getReader(), chunks=[]; let total=0;
  try {
    while(true) {
      const {done,value}=await reader.read(); if(done)break;
      total+=value.byteLength;
      if(total>maximum)throw new Error('Asset stream exceeds declared size');
      chunks.push(value);
    }
  } catch(error) {await reader.cancel();throw error;}
  const result=new Uint8Array(total);let at=0;
  for(const chunk of chunks){result.set(chunk,at);at+=chunk.length;}
  return result;
}

export async function loadAsset(id) {
  if(resident.has(id))return resident.get(id);
  if(!Object.hasOwn(manifest.assets,id))throw new Error('Unselected asset');
  const loading=queue.then(async()=>{
    const start=performance.now(), meta=manifest.assets[id];
    let compressed;
    const embedded=document.getElementById('asset-'+id);
    if(embedded) {
      compressed=Uint8Array.from(atob(embedded.textContent.trim()),c=>c.charCodeAt(0));
    } else {
      if(manifest.asset_base!=='assets/')throw new Error('Missing embedded asset');
      const response=await fetch(new URL('assets/'+id+'.bin.gz',location.href),{credentials:'same-origin'});
      if(!response.ok)throw new Error('Prepared asset unavailable: '+response.status);
      // Server sends a gzip file, NOT Content-Encoding:gzip. Decode exactly once.
      if(response.headers.has('Content-Encoding'))throw new Error('Unexpected HTTP decompression boundary');
      compressed=await boundedBytes(response.body,meta.compressed_bytes);
      record('asset-retrieved',{id,compressed_bytes:compressed.length});
    }
    if(compressed.length!==meta.compressed_bytes)throw new Error('Compressed length mismatch');
    const bytes=await boundedBytes(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip')),meta.decoded_bytes);
    if(bytes.length!==meta.decoded_bytes)throw new Error('Decoded length mismatch');
    const prefix=new TextEncoder().encode(meta.dtype+'\0');
    const canonical=new Uint8Array(prefix.length+bytes.length);canonical.set(prefix);canonical.set(bytes,prefix.length);
    const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',canonical)),b=>b.toString(16).padStart(2,'0')).join('');
    if(hash!==id)throw new Error('Asset content hash mismatch');
    const values=new constructors[meta.dtype](bytes.buffer);
    account('decodedBytes',bytes.length);account('assetDecodes',1);
    record('asset-decoded',{id,bytes:bytes.length,duration_ms:performance.now()-start});
    return values;
  });
  queue=loading.catch(()=>{});
  resident.set(id,loading);
  try{return await loading;}catch(error){resident.delete(id);throw error;}
}
