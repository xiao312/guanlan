// Numerical lookup-table regression, not a mapper/browser/GPU test.
import assert from 'node:assert/strict';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction.js';
import colorMaps from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction/ColorMaps.js';
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData.js';
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray.js';
const lut=vtkColorTransferFunction.newInstance();
const data=vtkPolyData.newInstance();
const values=Float64Array.from({length:101},(_,i)=>100000+i*1000);
data.getCellData().setScalars(vtkDataArray.newInstance({name:'p',values}));
function map(range,bins=0) {
  lut.applyColorMap(colorMaps.getPresetByName('Viridis (matplotlib)'));
  lut.setDiscretize(bins>0);lut.setNumberOfValues(bins||256);
  lut.setMappingRange(...range);lut.updateRange();
  return Array.from(lut.mapScalars(data.getCellData().getScalars(),1,0).getData());
}
const initial=map([100000,200000]);
assert.notDeepEqual(map([0,1]),initial);
assert.deepEqual(map([100000,200000]),initial,'Auto must restore original mapping');
const unique=new Set(Array.from({length:101},(_,i)=>initial.slice(i*4,i*4+3).join(',')));
assert.ok(unique.size>24,`Expected continuous colors, got ${unique.size}`);
const banded=map([100000,200000],12);
const bands=new Set(Array.from({length:101},(_,i)=>banded.slice(i*4,i*4+3).join(',')));
assert.ok(bands.size<=12 && bands.size>2);
console.log(JSON.stringify({continuousColors:unique.size,bands:bands.size,autoRestored:true,gpuTest:false}));
