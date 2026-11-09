// The merge screen (spec §5.6): a helper's .atlaspaint file, gone through one structure at a time in
// painting mode. The item shown is drawn on the main view (yellow dots round their structure, red dots
// where it covers another of yours) and is accepted, skipped, or accepted with theirs winning the overlap.
// Each accept is an ordinary undoable edit made through `api` (author.js builds it); nothing is written
// until Save. What differs, and the voxels an accept changes, come from merge-core.js; this file is the panel.
"use strict";

function makeMerge(api) {
  const { $, esc, M } = api;
  let file = null;       // {name, made, why, inc: {bitmap, lut, points}} while merging, else null
  let own = null;        // api.own() at the last refresh; own.bitmap is the live drawing
  let items = [], same = 0, autoLeft = [], unknown = [];
  let shown = null;      // key of the item shown
  let wired = false;     // #apMerge's click handler (the section is author.js's)
  const skipped = new Set();
  const taken = new Map(); // accepted keys (merge-core's itemsLeft): out of the list until an undo brings them back

  mergeStyles();

  const fmt = (n) => n.toLocaleString();
  const current = () => items.find((it) => it.key === shown) || null;

  async function open(f) {
    let obj;
    try {
      obj = JSON.parse(await f.text());
    } catch (e) {
      api.note("error", e instanceof SyntaxError ? "This isn't an atlas paint file."
        : `Couldn't read ${esc(f.name)}: ${esc(e.message)}.`);
      return;
    }
    const here = api.here();
    const why = M.checkPaintFile(obj, here);
    if (why) {
      api.note("error", esc(why));
      return;
    }
    let bitmap;
    try {
      bitmap = await M.decodeLabels(obj.labels_gz_b64, here.dims[0] * here.dims[1] * here.dims[2]);
    } catch (e) {
      api.note("error", esc(e.message));
      return;
    }
    if (file) close();
    file = { name: f.name, made: obj.made, why: obj.why, inc: { bitmap, lut: obj.lut, points: obj.points } };
    api.clearNote();
    refresh();
    api.renderAuthor();
  }

  function close() {
    if (!file) return;
    file = own = null;
    items = []; autoLeft = []; unknown = []; same = 0;
    shown = null;
    skipped.clear();
    taken.clear();
    api.setPreview(null);
    $("apMerge").hidden = true;
    $("apMerge").innerHTML = "";
    api.renderAuthor();
  }

  const active = () => !!file;

  // What the file offers now, against the owner's current drawing, lut and points.
  function refresh() {
    if (!file) return;
    own = api.own();
    const r = M.mergeItems(own, file.inc, api.rows());
    same = r.same; autoLeft = r.autoLeft; unknown = r.unknown;
    list(M.itemsLeft(r.items, skipped, taken));
  }

  // Replace the list; the item shown stays if it is still there, else the next one in list order.
  function list(next) {
    const prev = items;
    items = next;
    show(M.nextShown(prev, items, shown));
  }

  // Show an item: preview it, and move the cursor to it only when it isn't the one already shown.
  function show(key) {
    const moved = key !== shown;
    shown = key;
    const it = current();
    if (!it || it.kind === "point") api.setPreview(null);
    else api.setPreview({ inc: file.inc.bitmap, value: it.incValue, own: own.bitmap, ownValue: it.ownValue });
    if (it && moved) {
      if (it.kind === "point") api.goToMM(it.xyz_mm);
      else {
        const f = M.focusOf(file.inc.bitmap, api.here().dims, it.incValue, api.mainAxis());
        if (f) api.goToVox(f.vox);
      }
    }
    render();
  }

  // Take one item into the owner's state (one undo entry). Returns an error message (HTML) or null.
  function take(it, wins) {
    if (it.kind === "point") api.setPoint({ id: it.id, name: it.name, xyz_mm: it.xyz_mm });
    else if (it.status === "checked") api.markChecked(it.id);
    else {
      let value;
      try {
        value = api.valueFor(it.id);
      } catch (e) {
        if (e instanceof RangeError) return `${esc(it.name)} wasn't merged: ${esc(e.message)}.`;
        throw e;
      }
      api.applyChanges(it.id, value, M.regionChanges(own.bitmap, file.inc.bitmap, it.incValue, value, wins));
    }
    taken.set(it.key, null);
    return null;
  }

  function accept(wins = false) {
    const it = current();
    if (!it) return;
    const err = take(it, wins);
    if (err) { api.note("error", err); return; }
    refresh();
  }

  function skip() {
    const it = current();
    if (!it) return;
    skipped.add(it.key);
    list(items.filter((x) => x !== it));
  }

  // Every item left, in list order, the owner's map winning every overlap.
  function acceptAll() {
    let n = 0, err = null;
    for (const it of items) {
      err = take(it, false);
      if (err) break;
      n++;
    }
    refresh();
    if (err) api.note("error", `Accepted ${n}, then stopped: ${err}`);
    else api.note("ok", `Accepted ${n}. Save to keep them.`);
  }

  // ---------- panel ----------
  function statusText(it) {
    if (it.kind === "point") return it.status === "moved" ? `Moved ${it.movedMM} mm from yours` : "New point";
    if (it.status === "new") return `New — you haven't painted it · ${fmt(it.incCount)} voxels`;
    if (it.status === "checked") return "They marked the model's outline checked; the voxels are the same as yours";
    return `Theirs adds ${fmt(it.added)} voxels and removes ${fmt(it.removed)} of yours`;
  }

  function tagText(it) {
    return it.kind === "point" ? (it.status === "moved" ? "moved point" : "new point") : it.status;
  }

  function madeText() {
    const d = new Date(file.made);
    return Number.isNaN(d.getTime()) ? "an unknown date" : d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  }

  function render() {
    const el = $("apMerge");
    if (!el || !file) return;
    if (!wired) { el.addEventListener("click", onPanelClick); wired = true; }
    const it = current();
    let body;
    if (it) {
      const overlap = it.kind === "region" && it.overlapCount > 0;
      body = `
        <h2>${it.kind === "region" ? '<span class="am-swatch am-yellow"></span>' : ""}${esc(it.name)}</h2>
        <p class="am-status">${esc(statusText(it))}</p>
        ${overlap ? `<p class="am-overlap"><span class="am-swatch am-red"></span>${fmt(it.overlapCount)} of its voxels are your
          ${esc(it.overlap.map((o) => o.name).join(", "))} (red dots): yours are kept</p>` : ""}
        <div class="am-actions">
          <button type="button" class="am-accept" data-act="accept">Accept · <kbd>Enter</kbd></button>
          ${overlap ? '<button type="button" data-act="wins">Accept — theirs wins the overlap</button>' : ""}
          <button type="button" data-act="skip">Skip · <kbd>N</kbd></button>
          <button type="button" data-act="all" title="Accepts every item left; where one overlaps your other structures, yours are kept">Accept all the rest</button>
          <button type="button" data-act="stop">Stop merging · <kbd>Esc</kbd></button>
        </div>`;
    } else {
      const done = taken.size > 0 && api.unsaved() ? "Save to keep what you accepted."
        : !taken.size && !skipped.size ? "Nothing in this file differs from yours." : "";
      body = `
        <p class="am-status">Nothing left to merge.${done ? ` ${done}` : ""}</p>
        <div class="am-actions"><button type="button" data-act="stop">Stop merging · <kbd>Esc</kbd></button></div>`;
    }
    const leftOut = [
      autoLeft.length ? `Left out — model outlines they didn't check: ${esc(autoLeft.join(", "))}` : "",
      unknown.length ? `Left out — not on your checklist (add them to checklists/${esc(api.region)}.md to merge): ${esc(unknown.join(", "))}` : "",
    ].filter(Boolean).map((t) => `<p class="muted">${t}</p>`).join("");
    const rows = items.map((x) => `<button type="button" class="ap-row" data-key="${esc(x.key)}"${x.key === shown ? ' aria-current="true"' : ""}>
      <span class="ap-rname">${esc(x.name)}</span><span class="ap-tag">${esc(tagText(x))}</span></button>`).join("");
    el.innerHTML = `
      <div class="am-head">Merging <b>${esc(file.name)}</b>
        <div class="muted">${file.why === "unsaved" ? "unsaved work" : "paint"} from ${esc(madeText())}</div></div>
      <div class="am-item">${body}</div>
      <div class="am-summary"><p class="muted">${items.length} to review · ${same} the same as yours</p>${leftOut}</div>
      ${rows ? `<div class="am-list">${rows}</div>` : ""}`;
    el.hidden = false;
  }

  function onPanelClick(e) {
    const b = e.target.closest("button");
    if (!b || !file) return;
    if (b.dataset.key) show(b.dataset.key);
    else if (b.dataset.act === "accept") accept(false);
    else if (b.dataset.act === "wins") accept(true);
    else if (b.dataset.act === "skip") skip();
    else if (b.dataset.act === "all") acceptAll();
    else if (b.dataset.act === "stop") close();
    $("gl").focus({ preventScroll: true }); // keys go on working
  }

  // Enter, N and Esc while merging; true = handled.
  function onKey(e) {
    if (!file) return false;
    const k = e.key;
    if (k === "Enter") { e.preventDefault(); if (!e.repeat) accept(false); return true; }
    if (k === "n" || k === "N") { if (!e.repeat) skip(); return true; }
    if (k === "Escape") { close(); return true; }
    return false;
  }

  return { open, close, active, onKey, refresh };
}

function mergeStyles() {
  if (document.getElementById("mergeStyles")) return;
  const st = document.createElement("style");
  st.id = "mergeStyles";
  st.textContent = `
  .am-head b { word-break: break-all; }
  .am-item { display: flex; flex-direction: column; gap: 6px; padding: 10px; border: 1px solid var(--border); border-radius: var(--radius); }
  .am-item p, .am-summary p { margin: 0; }
  .am-status { font-variant-numeric: tabular-nums; }
  .am-overlap { font-size: 13px; color: var(--muted); }
  .am-swatch { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
  .am-yellow { background: #ffd60a; }
  .am-red { background: #ff453a; }
  .am-actions { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
  .am-actions button { text-align: left; }
  .am-actions kbd { font: 11px var(--font); border: 1px solid var(--border); border-radius: 3px; padding: 0 4px; }
  .am-accept { background: var(--accent); color: var(--accent-ink); font-weight: 600; }
  .am-accept kbd { border-color: currentColor; }
  .am-summary { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
  .am-list { max-height: 40vh; overflow-y: auto; border: 1px solid var(--border); border-radius: var(--radius); }
  `;
  document.head.appendChild(st);
}
