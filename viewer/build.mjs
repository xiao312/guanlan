import { build } from 'esbuild';
import path from 'node:path';
import fs from 'node:fs';
const vtkLicense=fs.readFileSync('node_modules/@kitware/vtk.js/LICENSE','utf8');
await build({entryPoints:['../src/guanlan/portable/viewer.js'],bundle:true,minify:true,
  format:'iife',legalComments:'inline',nodePaths:[path.resolve('node_modules')],
  footer:{js:'/* vtk.js BSD-3-Clause license\n'+vtkLicense+'\n*/'},
  outfile:'../state/portable/viewer.js',logLevel:'info'});
await build({entryPoints:['../src/guanlan/portable/glance_controls.js'],bundle:true,minify:true,
  format:'iife',legalComments:'inline',outfile:'../state/portable/glance-controls.js',logLevel:'info'});
