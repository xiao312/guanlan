// This is a numerical reader check, not a browser or GPU performance benchmark.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import vtkXMLPolyDataReader from '@kitware/vtk.js/IO/XML/XMLPolyDataReader.js';

const [scenePath, comparisonPath]=process.argv.slice(2);
if(!scenePath||!comparisonPath)throw new Error('Usage: node check-fixture.mjs scene.json comparison-directory');
const scene=JSON.parse(fs.readFileSync(scenePath,'utf8'));
function bytes(array){return Buffer.from(array.buffer,array.byteOffset,array.byteLength);}
const results=[];
for(const [name,source] of Object.entries(scene.datasets)) {
  const input=fs.readFileSync(path.join(comparisonPath,name+'.vtp'));
  const reader=vtkXMLPolyDataReader.newInstance();
  reader.parseAsArrayBuffer(input.buffer.slice(input.byteOffset,input.byteOffset+input.byteLength));
  const data=reader.getOutputData();
  assert.equal(data.getNumberOfPoints(),source.point_count);
  assert.equal(data.getNumberOfCells(),source.cell_count);
  assert.deepEqual(bytes(data.getPoints().getData()),Buffer.from(source.points,'base64'));
  assert.deepEqual(bytes(data.getPolys().getData()),Buffer.from(source.polys,'base64'));
  for(const [field,values] of Object.entries(source.fields)) {
    assert.deepEqual(bytes(data.getCellData().getArrayByName(field).getData()),Buffer.from(values.values,'base64'));
  }
  results.push({dataset:name,points:data.getNumberOfPoints(),cells:data.getNumberOfCells(),fields:Object.keys(source.fields),exact_bytes:true});
}
const edgeInput=fs.readFileSync(path.join(comparisonPath,'surface-edges.vtp'));
const edgeReader=vtkXMLPolyDataReader.newInstance();
edgeReader.parseAsArrayBuffer(edgeInput.buffer.slice(edgeInput.byteOffset,edgeInput.byteOffset+edgeInput.byteLength));
const edgeData=edgeReader.getOutputData();
const topology=new Uint32Array(Uint8Array.from(Buffer.from(scene.datasets.surface.polys,'base64')).buffer);
const expected=new Set();
for(let at=0;at<topology.length;){const n=topology[at++];for(let j=0;j<n;j++){const a=topology[at+j],b=topology[at+(j+1)%n];if(a!==b)expected.add(Math.min(a,b)+':'+Math.max(a,b));}at+=n;}
const edges=edgeData.getLines().getData();
assert.equal(edgeData.getNumberOfLines(),expected.size);
for(let at=0;at<edges.length;at+=3){assert.equal(edges[at],2);assert(expected.delete(edges[at+1]+':'+edges[at+2]));}
assert.equal(expected.size,0);
console.log(JSON.stringify({vtkjs:'37.1.1',datasets:results,original_edges:edgeData.getNumberOfLines(),gpu_test:false},null,2));
