// Logic-only DOM fixture; not a browser, screenshot, or GPU benchmark.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
class Element {
  constructor(tag = '') { this.tag = tag; this.children = []; this.value = ''; this.pauses = 0; this.classList = {toggle: () => true}; }
  append(...items) {
    this.children.push(...items);
    if (this.tag === 'select' && !this.value) this.value = this.children[0].value;
  }
  setAttribute() {}
  pause() { this.pauses++; }
}
const model = {
  preset: {case_label: 'Synthetic', times: ['1','2'], blocks: [{id: 'slice', title: 'Slice', camera: 'xy', fields: ['p','T'], range: 'data'}]},
  frames: [], images: {}, videos: {'slice|p': 'data:video/mp4;base64,test'}
};
for (const field of ['p','T']) for (const time of ['1','2']) {
  const file = field+time;
  model.frames.push({block: 'slice', field, time, file, range: [0,1], units: '1', plane: null});
  model.images[file] = 'data:image/png;base64,'+file;
}
const nodes = Object.fromEntries(['data','case','timeline','time','blocks','play'].map(id => [id,new Element()]));
nodes.data.textContent = JSON.stringify(model); nodes.timeline.value = '0';
let tick = null;
vm.runInNewContext(readFileSync(new URL('../src/guanlan/media/viewer.js', import.meta.url), 'utf8'), {
  document: {getElementById: id => nodes[id], createElement: tag => new Element(tag)},
  setInterval: fn => {tick = fn; return 1;}, clearInterval: () => {tick = null;}
});
const article = nodes.blocks.children[0];
const select = article.children[0].children[1];
const image = article.children[1].children[0];
const details = article.children[3];
assert.equal(image.src, model.images.p1);
nodes.timeline.value = '1'; nodes.timeline.oninput();
assert.equal(image.src, model.images.p2);
select.value = 'T'; select.onchange();
assert.equal(image.src, model.images.T2); assert.equal(details.hidden, true);
nodes.play.onclick(); tick(); assert.equal(image.src, model.images.T1);
nodes.play.onclick(); assert.equal(tick, null);
assert.match(article.children[2].textContent, /Per-frame auto range/);
console.log(JSON.stringify({ok: true, checks: ['initial frame','time switch','field switch','video visibility','play/pause','range caption'], browser: false}));
