// User-run headed smoke/measurement trace. No personal browser profile or server.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from 'playwright-core';
const input = process.argv.slice(2).find(arg => !arg.startsWith('--'));
if (!input) throw new Error('Usage: node benchmark.mjs <local Guanlan HTML> [--check]');
const html = path.resolve(input);
await fs.access(html);
if (process.argv.includes('--check')) { console.log(JSON.stringify({html, launch:false})); process.exit(0); }
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = path.join(root, 'state/portable/browser-runs', new Date().toISOString().replace(/[:.]/g,'-'));
await fs.mkdir(output, {recursive:true});
const browser = await chromium.launch({channel:'msedge', headless:false});
const errors = [], counters = [];
try {
  const context = await browser.newContext({viewport:{width:1280,height:900}, acceptDownloads:true});
  await context.route(/^https?:/, route=>route.abort());
  const page = await context.newPage();
  page.on('pageerror', error=>errors.push(String(error)));
  page.on('console', message=>{if(message.type()==='error')errors.push(message.text());});
  const cdp = await context.newCDPSession(page);
  await cdp.send('Performance.enable');
  await page.goto(pathToFileURL(html).href);
  const geometry = page.locator('#block-0');
  await geometry.getByRole('button',{name:'Reset',exact:true}).waitFor();
  await page.waitForFunction(()=>!document.querySelector('#block-0 button')?.disabled);
  await page.locator('#measure').click();
  async function drag(block, button) {
    const viewport = block.locator('.viewport'); await viewport.scrollIntoViewIfNeeded();
    const box = await viewport.boundingBox();
    await page.mouse.move(box.x+box.width*.45,box.y+box.height*.5);
    await page.mouse.down({button});
    for(let step=1;step<=30;step++) {
      await page.mouse.move(box.x+box.width*.45+step*3,box.y+box.height*.5+step);
      await page.waitForTimeout(16);
    }
    await page.mouse.up({button});
  }
  await drag(geometry,'middle');
  await page.screenshot({path:path.join(output,'middle-pan.png')});
  await drag(geometry,'left'); await page.mouse.wheel(0,-240);
  const slice = page.locator('#block-2'); await slice.scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>!document.querySelector('#block-2 button')?.disabled);
  const field = slice.locator('label').filter({hasText:/^Field /}).locator('select');
  for(const name of ['T','p']) {
    await field.selectOption(name);
    await page.waitForTimeout(300);
  }
  const numbers = slice.locator('input[type=number]');
  await numbers.nth(0).fill('0'); await numbers.nth(1).fill('1');
  await slice.getByRole('button',{name:'Apply range',exact:true}).click();
  await slice.getByRole('button',{name:'Auto',exact:true}).click();
  await page.screenshot({path:path.join(output,'slice-auto.png')});
  counters.push(await cdp.send('Performance.getMetrics'));
  await page.locator('#layout').click();
  await drag(geometry,'middle');
  await page.screenshot({path:path.join(output,'multi-block.png')});
  await page.locator('#measure').click();
  const download = page.waitForEvent('download'); await page.locator('#report').click();
  await (await download).saveAs(path.join(output,'measurements.json'));
  counters.push(await cdp.send('Performance.getMetrics'));
} catch(error) { errors.push(String(error)); process.exitCode=1; }
finally {
  await fs.writeFile(path.join(output,'run.json'),JSON.stringify({html,errors,counters,
    qualification:'EXPLORATORY_REQUIRES_SCREENSHOT_REVIEW',browser:browser.version()},null,2));
  await browser.close(); console.log(output);
}
