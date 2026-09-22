"use strict";
const model = JSON.parse(document.getElementById("data").textContent);
const preset = model.preset;
const timeline = document.getElementById("timeline");
timeline.max = preset.times.length - 1;
document.getElementById("case").textContent = preset.case_label;
const blocks = preset.blocks.map(block => {
  const article = document.createElement("article");
  const head = document.createElement("div"); head.className = "block-head";
  const title = document.createElement("h2"); title.textContent = block.title; head.append(title);
  const select = document.createElement("select"); select.setAttribute("aria-label", block.title + " field");
  for (const field of block.fields || [""]) {
    const option = document.createElement("option"); option.value = field; option.textContent = field || block.kind;
    select.append(option);
  }
  head.append(select);
  const viewport = document.createElement("div"); viewport.className = "viewport";
  const image = document.createElement("img"); image.alt = block.title; image.loading = "lazy";
  viewport.append(image);
  const zoom = document.createElement("button"); zoom.type = "button"; zoom.textContent = "1:1 / fit";
  zoom.setAttribute("aria-label", block.title + " image zoom"); head.append(zoom);
  const toggle = () => viewport.classList.toggle("zoom"); zoom.onclick = toggle; viewport.onclick = toggle;
  const caption = document.createElement("div"); caption.className = "caption";
  const details = document.createElement("details");
  const summary = document.createElement("summary"); summary.textContent = "Prepared video · independent playback";
  const video = document.createElement("video"); video.controls = true; video.preload = "none"; video.muted = true; video.playsInline = true;
  details.append(summary, video);
  details.ontoggle = () => { if (!details.open) video.pause(); };
  article.append(head, viewport, caption, details); document.getElementById("blocks").append(article);
  select.onchange = update;
  return {block, select, image, caption, video, details, clipKey: null};
});
function update() {
  const time = preset.times[Number(timeline.value)];
  document.getElementById("time").textContent = "t = " + time;
  for (const item of blocks) {
    const frame = model.frames.find(f => f.block === item.block.id && f.field === item.select.value && f.time === time);
    item.image.src = model.images[frame.file];
    const clipKey = item.block.id + "|" + item.select.value;
    const clip = model.videos?.[clipKey]; item.details.hidden = !clip;
    if (clip && item.clipKey !== clipKey) {
      item.video.pause(); item.video.src = clip; item.clipKey = clipKey;
    }
    const summary = ["t=" + time, item.block.camera + " camera"];
    if (frame.field) {
      summary.push(frame.field + " [" + frame.units + "] · cell values");
      summary.push((item.block.range === "data" ? "Per-frame auto range " : "Fixed range ") + frame.range.map(v => Number(v).toPrecision(5)).join(" … "));
    } else summary.push("Physical boundaries; processor interfaces excluded");
    if (frame.plane) summary.push("Plane origin (m): " + frame.plane.origin.map(v => Number(v).toPrecision(5)).join(", "));
    item.caption.textContent = summary.join("\n");
  }
}
let timer = null;
const play = document.getElementById("play"); play.disabled = preset.times.length < 2;
play.onclick = () => {
  if (timer) { clearInterval(timer); timer = null; play.textContent = "Play sequence"; }
  else {
    timer = setInterval(() => { timeline.value = (Number(timeline.value)+1) % preset.times.length; update(); }, 500);
    play.textContent = "Pause";
  }
};
timeline.oninput = update;
update();
