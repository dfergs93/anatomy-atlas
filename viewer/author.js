// Author mode (painting, spec §5): the checklist chooses the structure, brush and eraser paint it,
// the wand, fill between slices and grow spread it (§5.3), undo, save. index.html calls
// attachAuthor(ctx) after each loadSequence when ?mode=author; nothing here runs otherwise.
//
// The label map is copied into NiiVue's drawing layer (uint8, x fastest, RAS order = NIfTI order
// because both volumes must have permRAS [1,2,3]). `before` mirrors the accepted drawing: after
// every stroke paint-core's guardChanges puts back anything outside the current structure, and the
// accepted voxels become an undo entry. A save posts the whole bitmap to tools/serve.py's /api/save.
// Unsaved paint is never lost silently: "● Unsaved" shows, leaving the page asks first, and a failed
// save offers the paint as a download.
//
// The wand, fill between and grow write their result straight into nv.drawBitmap and then run the
// same afterEdit() as a stroke, so the guard decides what is kept (NiiVue fires no "draw" for them).
//
// Point structures (checklist type P) are never painted: a click in the main view places the point
// (state.points, saved as points.json), Delete removes it. K marks a model's outline (an `auto` entry
// in lut.json) as checked; the save drops its `auto`. Points and K are on the same undo stack as paint.
"use strict";

const AUTHOR_OPTS = {
  undoDepth: 100,
  sizeMin: 1, sizeMax: 25, sizeStep: 2, sizeDefault: 3, // NiiVue's pen is a square of side 2*floor(n/2)+1
  // wand: seed window = 3x3 median ± tolerance × (cal_max − cal_min); 2D = the current plane.
  // 0.10, not the plan's 0.12: on knee-mri's DESS, clicks along the ACL spilled out of it 14 times in 35 at 0.12,
  // 5 at 0.10 and never at 0.08 (which fills only ~50 voxels a click). ±0.02 with [ ].
  wandTolerance: 0.10, wandTolMin: 0.02, wandTolMax: 0.4, wandTolStep: 0.01, wandTolKeyStep: 0.02, wandMaxDistMM: 40,
  growTolerance: 0.05, growSteps: 12,
  fillSliceType: { sagittal: 2, coronal: 1, axial: 0 }, // interpolateMaskSlices' sliceType (NiiVue SLICE_TYPE)
  drawOpacity: 0.5,
  narrowQuery: "(max-width: 760px)", // same breakpoint as the viewer's single-view layout
  hosts: ["127.0.0.1", "localhost"],
  noCurrent: 256, // a pen value no uint8 voxel can hold: with no current structure every change is put back
};

let authorSession = null;

// Returns the author session, or null (with a banner) when this case can't be painted here.
function attachAuthor(ctx) {
  if (authorSession) return authorSession.reattach(ctx) ? authorSession : null;
  const why = authorRefusal(ctx);
  if (why) {
    authorBanner(ctx, why);
    return null;
  }
  authorSession = makeAuthor(ctx);
  window.atlasAuthor = authorSession; // for the console and browser checks
  return authorSession;
}

// The reason (HTML) painting is refused, or null.
function authorRefusal(ctx, { again = false } = {}) {
  const { nv, state, escapeHTML: esc } = ctx;
  const meta = state.meta;
  if (!again) {
    if (meta.mirror_of) {
      const href = `?case=${encodeURIComponent(meta.mirror_of)}&mode=author`;
      return `This is a mirrored copy, rebuilt from ${esc(meta.mirror_of)} on every save, so it is never painted.
        <a href="${esc(href)}">Paint ${esc(meta.mirror_of)} instead</a>`;
    }
    if (!AUTHOR_OPTS.hosts.includes(location.hostname)) {
      return `Painting works only on the computer running <code>tools/serve.py</code>: open
        <code>http://127.0.0.1:${esc(location.port || "8004")}/viewer/${esc(location.search)}</code> there.`;
    }
    if (matchMedia(AUTHOR_OPTS.narrowQuery).matches) {
      return "Painting needs a wider window (over 760 px). Widen the window and reload.";
    }
  }
  const [img, lab] = nv.volumes;
  if (!img || !lab) return "The image or the label map did not load.";
  for (const [v, what] of [[img, "image"], [lab, "label map"]]) {
    if (Array.from(v.permRAS).join() !== "1,2,3") {
      return `This case's ${what} is not stored in RAS order (permRAS ${esc(Array.from(v.permRAS).join(", "))}),
        so a save would put the paint in the wrong voxels. Rebuild the case with <code>tools/build_case.py</code>.`;
    }
  }
  const di = Array.from(img.dimsRAS).slice(1, 4), dl = Array.from(lab.dimsRAS).slice(1, 4);
  if (di.join() !== dl.join()) {
    return `This sequence (${di.join("×")}) is not on the label map's grid (${dl.join("×")}), so it can't be painted on.
      Choose the case's reference sequence.`;
  }
  if (!again) {
    let max = 0;
    const a = lab.img;
    for (let i = 0; i < a.length; i++) if (a[i] > max) max = a[i];
    const lutMax = Math.max(0, ...Object.keys(state.lut).map(Number));
    if (max > 255 || lutMax > 255) {
      return `This label map uses values up to ${Math.max(max, lutMax)}; the painting layer holds 1–255.`;
    }
  }
  return null;
}

function authorBanner(ctx, html) {
  let el = ctx.$("authorBanner");
  if (!el) {
    authorStyles();
    el = document.createElement("div");
    el.id = "authorBanner";
    el.setAttribute("role", "alert");
    ctx.$("canvasWrap").appendChild(el);
  }
  el.hidden = !html;
  el.innerHTML = html ? `<b>Painting is off.</b> ${html}` : "";
}

function makeAuthor(ctx) {
  const { nv, state, core, paint, $, escapeHTML: esc } = ctx;
  const DRAG = window.niivue.DRAG_MODE;
  const caseId = state.caseId;
  const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  const MOD = IS_MAC ? "⌘" : "Ctrl+";
  const S = {
    rows: [], checklistError: null,
    savedLut: state.lut,     // lut.json as last loaded from disk (value -> entry)
    assigned: new Map(),     // id -> value for structures painted but not yet in lut.json
    current: null, curValue: 0,
    tool: "brush", size: AUTHOR_OPTS.sizeDefault, overwrite: false, paintShown: true,
    wandTol: AUTHOR_OPTS.wandTolerance, wand3D: false,
    lastTool: null,          // {what, ms, added, restored} of the last wand / fill between / grow (for checks)
    undo: [], edits: 0, savedEdits: 0,
    savedPoints: JSON.stringify(state.points), // points.json as last loaded or saved, to tell unsaved points
    checked: new Set(),      // auto outlines marked checked (K) since the last save
    token: null, saving: null, refused: false, filter: "", noteKind: null, lastSaveMs: null, enterAfterStroke: false,
  };
  let before = null;         // the accepted drawing (mirror of nv.drawBitmap)
  let suspended = false;     // drawing switched off for a gesture that started outside the main view
  let stroking = false;      // a left-button gesture that started in the main view with drawing on

  // ---------- drawing ----------
  function loadDrawing() {
    const lab = nv.volumes[1];
    nv.createEmptyDrawing();
    nv.drawBitmap.set(lab.img); // values checked to be 0–255 by authorRefusal
    nv.drawAddUndoBitmap();
    nv.refreshDrawing(true);
    before = nv.drawBitmap.slice();
  }

  function setupView() {
    nv.setOpacity(1, 0); // the label volume stays loaded but hidden: the drawing is what is shown
    nv.setMouseEventConfig({
      leftButton: { primary: DRAG.crosshair, withShift: DRAG.windowing, withCtrl: DRAG.pan },
      rightButton: DRAG.pan,
      centerButton: DRAG.pan,
    });
    nv.setDrawOpacity(S.paintShown ? AUTHOR_OPTS.drawOpacity : 0);
    applyColours();
    applyPen();
    snapToVoxelCentres();
  }

  // The opening cursor sits on a voxel boundary (0.5 on an even axis), so the first click could
  // paint one slice off the one the slider names. Put it on voxel centres.
  function snapToVoxelCentres() {
    const d = Array.from(nv.volumes[0].dimsRAS).slice(1, 4);
    const vox = ctx.frac2vox(nv.scene.crosshairPos);
    nv.scene.crosshairPos = vox.map((v, a) => (v + 0.5) / d[a]);
    nv.drawScene();
    nv.createOnLocationChange();
  }

  function lutIdToValue() {
    const m = {};
    for (const [v, e] of Object.entries(S.savedLut)) m[e.id] = Number(v);
    return m;
  }

  function rowOf(id) {
    return S.rows.find((r) => r.id === id) || null;
  }

  // lut.json + painted-but-unsaved structures + the current one if it is new: names for hover, colours for the drawing.
  function paintLut() {
    const lut = { ...S.savedLut };
    const add = (id, v) => {
      if (!lut[v]) lut[v] = { id, name: (rowOf(id) || { name: id }).name, rgb: paint.colour(id, v) };
    };
    for (const [id, v] of S.assigned) add(id, v);
    if (S.current && !isPoint(S.current)) add(S.current.id, S.curValue);
    return lut;
  }

  function applyColours() {
    state.lut = paintLut();
    nv.setDrawColormap(ctx.buildColormap(state.lut, { expectedFilled: true })); // E structures: filled while painting
  }

  function isPoint(row) {
    return !!row && row.type === "P";
  }

  function pointOf(id) {
    return state.points.find((p) => p.id === id) || null;
  }

  // lut.json's entry for `id` when a model drew it and nobody has checked it yet, else null.
  function autoEntry(id) {
    const e = S.savedLut[lutIdToValue()[id]];
    return e && e.auto ? e : null;
  }

  // Point structures are placed, never painted: with one current, the drawing is off.
  function canPaint() {
    return !!S.current && !isPoint(S.current) && !S.refused && !!nv.drawBitmap;
  }

  // NiiVue's pen is on for the brush and eraser only: with the wand a click must not also lay down a dot.
  function penOn() {
    return canPaint() && (S.tool === "brush" || S.tool === "eraser");
  }

  function applyPen() {
    nv.opts.penSize = S.size;
    if (nv.opts.drawingEnabled !== penOn()) nv.setDrawingEnabled(penOn());
    nv.setPenValue(S.tool === "eraser" || !canPaint() ? 0 : S.curValue, false);
  }

  // NiiVue fires "draw" after each brush or eraser stroke; the wand, fill between and grow call this
  // themselves, naming the tool for the message. Returns the guard's result (or null).
  function afterEdit(what) {
    const bm = nv.drawBitmap;
    if (!bm || !before || bm.length !== before.length) return null;
    const paintable = !!S.current && !isPoint(S.current);
    const cur = paintable ? S.curValue : AUTHOR_OPTS.noCurrent; // a point structure takes no voxels
    const ch = paint.guardChanges(before, bm, cur, S.overwrite && paintable);
    if (ch.restored) nv.refreshDrawing(true);
    if (ch.idx.length) {
      const id = S.current.id;
      if (!(id in lutIdToValue()) && !S.assigned.has(id)) S.assigned.set(id, cur);
      pushUndo({ kind: "paint", idx: ch.idx, old: ch.old });
      edited();
    }
    const name = paintable ? esc(S.current.name) : "the current structure";
    if (ch.restored) {
      note("info", (!what && S.tool === "eraser" ? `The eraser clears only ${name}` : `${what || "The brush"} paints only empty voxels and ${name}`) +
        "; other structures were left as they were. Tick “Paint over other structures” to change them.");
    } else if (ch.idx.length && S.noteKind === "info") {
      clearNote(); // a clean stroke clears an old hint; a repeat call with no changes leaves it
    }
    return ch;
  }

  // ---------- wand, fill between, grow (spec §5.3) ----------
  function volDims() {
    return Array.from(nv.volumes[0].dimsRAS).slice(1, 4);
  }

  function voxMM() {
    const v = nv.volumes[0];
    return Array.from(v.pixDimsRAS || v.hdr.pixDims).slice(1, 4);
  }

  // The sequence's display window from meta.json (not the live one, which Shift-drag changes).
  function calRange() {
    const seq = state.meta.sequences.find((s) => s.id === state.seqId);
    if (seq && Number.isFinite(seq.cal_min) && Number.isFinite(seq.cal_max) && seq.cal_max > seq.cal_min) {
      return [seq.cal_min, seq.cal_max];
    }
    const v = nv.volumes[0];
    return [v.global_min, v.global_max];
  }

  // A tool can run: a structure is chosen and the drawing is open. A stroke still in progress is
  // guarded first, so its voxels never land in the tool's undo entry unchecked.
  function toolReady() {
    if (S.refused || !nv.drawBitmap || !before) return false; // the banner says why
    if (!S.current) {
      note("info", "Choose a structure first: <kbd>Enter</kbd> for the next one, or pick one below.");
      return false;
    }
    if (isPoint(S.current)) {
      note("info", pointHint());
      return false;
    }
    if (stroking) afterEdit();
    return true;
  }

  function pointHint() {
    return `${esc(S.current.name)} is a point label, so it isn't painted: click in the big view to place it.`;
  }

  // ---------- points (spec §5.3 "Point", §5.7) ----------
  function copyPoints() {
    return JSON.parse(JSON.stringify(state.points));
  }

  function pointsChanged() {
    ctx.drawMarkers();
    render();
  }

  // The (0-based) slice of the current plane a stored point sits on.
  function pointSliceHere(p) {
    return ctx.frac2vox(ctx.worldToFrac(p.xyz_mm))[core.PLANE_AXIS[state.plane]];
  }

  // A click in the main view sets the current point structure's point, replacing any earlier one.
  // It goes at the centre of the clicked voxel, so it sits on the slice the slider names.
  function placePoint(frac) {
    if (S.refused || !nv.volumes.length) return;
    const row = S.current;
    const d = volDims();
    const vox = ctx.frac2vox(frac, 0);
    const xyz = ctx.fracToWorld(vox.map((v, a) => (v + 0.5) / d[a])).map((v) => Math.round(v * 100) / 100);
    const old = pointOf(row.id);
    if (old && old.xyz_mm.every((v, a) => v === xyz[a])) return; // the same voxel again
    pushUndo({ kind: "point", before: copyPoints() });
    const p = { id: row.id, name: row.name, xyz_mm: xyz };
    if (old) state.points[state.points.indexOf(old)] = p;
    else state.points.push(p);
    edited();
    pointsChanged();
    note("ok", `${old ? "Moved" : "Placed"} ${esc(row.name)} on ${state.plane} slice ${vox[core.PLANE_AXIS[state.plane]] + 1}.`);
  }

  // P: the current point structure's point goes where the pointer is in the main view (as a click would).
  function pointKey() {
    const c = S.current;
    if (!isPoint(c)) {
      note("info", c ? `<kbd>P</kbd> places point labels; ${esc(c.name)} is painted.`
        : "Choose a point label first: pick one below, then point at the spot and press <kbd>P</kbd>.");
      return;
    }
    const frac = pointerFrac();
    if (!frac) {
      note("info", `Point at the spot in the big view, then press <kbd>P</kbd> (or click there).`);
      return;
    }
    placePoint(frac);
  }

  // Where the pointer is over the main view's image (volume fraction), or null.
  function pointerFrac() {
    const m = state.mouse;
    if (!m || ctx.tileKind(m[0], m[1]) !== "main") return null;
    return ctx.fracAt(m[0], m[1]);
  }

  function deletePoint() {
    const row = S.current;
    const i = state.points.findIndex((p) => p.id === row.id);
    if (i < 0) {
      note("info", `${esc(row.name)} has no point yet: click in the big view to place it.`);
      return;
    }
    pushUndo({ kind: "point", before: copyPoints() });
    state.points.splice(i, 1);
    edited();
    pointsChanged();
    note("ok", `Removed the point for ${esc(row.name)}. <kbd>${MOD}Z</kbd> puts it back.`);
  }

  // The point's slice in the current plane, in the main view.
  function goToPoint() {
    const p = S.current && pointOf(S.current.id);
    if (p) ctx.setSlice(pointSliceHere(p));
  }

  // ---------- K: a model's outline looks right ----------
  // Saved as `checked`: the save drops the structure's `auto`, so the badge and the panel's note go.
  function markChecked() {
    const c = S.current;
    if (!c) {
      note("info", "Choose a structure first: <kbd>Enter</kbd> for the next one, or pick one below.");
      return;
    }
    if (S.checked.has(c.id)) {
      note("info", `${esc(c.name)} is already marked checked; it's kept when you save.`);
      return;
    }
    if (!autoEntry(c.id)) {
      note("info", `${esc(c.name)} wasn't drawn by a model, so there is nothing to check.`);
      return;
    }
    S.checked.add(c.id);
    pushUndo({ kind: "check", id: c.id });
    render();
    note("ok", `${esc(c.name)} marked checked. Save to keep it.`);
  }

  // Paint the current value into `mask`, then let the guard decide what stays.
  function applyMask(mask, what) {
    const bm = nv.drawBitmap;
    const v = S.curValue;
    for (let k = 0; k < mask.length; k++) bm[mask[k]] = v;
    nv.refreshDrawing(true);
    return afterEdit(what);
  }

  // Report a tool's result: a count when it added voxels, a hint when it added none. The guard's own
  // message (other structures left alone) wins.
  function toolDone(what, ch, t0, okText, emptyText) {
    const added = ch ? ch.idx.length : 0;
    S.lastTool = { what, ms: Math.round(performance.now() - t0), added, restored: ch ? ch.restored : 0 };
    if (ch && ch.restored) return;
    if (added) note("ok", okText(added.toLocaleString()));
    else note("info", emptyText);
  }

  function wandAt(frac) {
    if (!toolReady()) return;
    const t0 = performance.now();
    const img = nv.volumes[0].img;
    const dims = volDims();
    const axis = core.PLANE_AXIS[state.plane];
    const seed = ctx.frac2vox(frac, 0);
    const [lo, hi] = paint.seedWindow(img, dims, seed, axis, S.wandTol, calRange());
    const mask = paint.wandMask(img, dims, seed, {
      lo, hi, is2D: !S.wand3D, axis, maxDistMM: AUTHOR_OPTS.wandMaxDistMM, voxMM: voxMM(),
    });
    const ch = mask.length ? applyMask(mask, "The wand") : null;
    toolDone("wand", ch, t0, (n) => `Wand: ${n} voxels added.`,
      "The wand added nothing here: the voxel is unlike its neighbours, or the area is already painted. Try another spot or a higher tolerance.");
  }

  // Interpolate the current structure across the gaps between its painted slices in this plane.
  // NiiVue's interpolateMaskSlices interpolates every label in the drawing (and overwrites others),
  // so it runs on a copy holding only the current structure; what it adds is merged back and guarded.
  function fillBetween() {
    if (!toolReady()) return;
    const t0 = performance.now();
    const cur = S.curValue;
    const name = esc(S.current.name);
    const keys = paint.keySlices(nv.drawBitmap, volDims(), cur, core.PLANE_AXIS[state.plane]);
    if (keys.length < 2) {
      note("info", `Paint at least two slices first (${name} is on ${keys.length} ${state.plane} slice${keys.length === 1 ? "" : "s"}).`);
      return;
    }
    const gaps = [];
    for (let k = 1; k < keys.length; k++) if (keys[k] - keys[k - 1] >= 2) gaps.push([keys[k - 1], keys[k]]);
    if (!gaps.length) {
      note("info", `No gaps to fill: ${name}'s painted ${state.plane} slices are next to each other.`);
      return;
    }
    const bm = nv.drawBitmap;
    const full = bm.slice();
    try {
      for (let i = 0; i < bm.length; i++) if (bm[i] !== cur) bm[i] = 0;
      const sliceType = AUTHOR_OPTS.fillSliceType[state.plane];
      for (const [a, b] of gaps) nv.interpolateMaskSlices(a, b, { sliceType, useIntensityGuided: true });
      const out = nv.drawBitmap;
      for (let i = 0; i < out.length; i++) if (out[i] === cur) full[i] = cur;
    } catch (e) {
      note("error", `Fill between failed: ${esc(e.message)}. Nothing was changed.`);
      return;
    } finally {
      if (nv.drawBitmap !== bm) nv.drawBitmap = bm;
      bm.set(full); // every path: the drawing again holds every structure
      nv.refreshDrawing(true);
    }
    const ch = afterEdit("Fill between");
    const span = `${state.plane} slices ${keys[0] + 1}–${keys[keys.length - 1] + 1}`;
    toolDone("fill", ch, t0, (n) => `Filled ${gaps.length} gap${gaps.length === 1 ? "" : "s"} between ${span}: ${n} voxels added.`,
      `Fill between added nothing between ${span}.`);
  }

  function grow() {
    if (!toolReady()) return;
    const t0 = performance.now();
    const name = esc(S.current.name);
    const mask = paint.growMask(nv.volumes[0].img, volDims(), nv.drawBitmap, S.curValue, {
      tolerance: AUTHOR_OPTS.growTolerance, range: calRange(), steps: AUTHOR_OPTS.growSteps,
    });
    const ch = mask.length ? applyMask(mask, "Grow") : null;
    toolDone("grow", ch, t0, (n) => `Grow: ${n} voxels added. Press G again to keep growing.`,
      before.indexOf(S.curValue) >= 0 ? `${name} can't grow further: no similar signal next to it.`
        : `Paint a few strokes inside ${name} first, then grow.`);
  }

  function pushUndo(entry) {
    S.undo.push(entry);
    if (S.undo.length > AUTHOR_OPTS.undoDepth) S.undo.shift();
  }

  function undoLast() {
    const u = S.undo.pop();
    if (!u) {
      note("info", "Nothing to undo.");
      return;
    }
    if (u.kind === "paint") {
      paint.undoChange(u, nv.drawBitmap, before);
      nv.refreshDrawing(true);
    } else if (u.kind === "point") {
      state.points.splice(0, state.points.length, ...u.before);
      ctx.drawMarkers();
    } else if (u.kind === "check") {
      S.checked.delete(u.id);
    }
    // "Placed …", "… marked checked", tool counts and the guard's hints describe what was just undone;
    // a failed save's message (with its download button) stays
    if (S.noteKind === "ok" || S.noteKind === "info") clearNote();
    edited();
    render();
  }

  function edited() {
    S.edits++;
    renderStatus();
  }

  function unsaved() {
    return S.edits !== S.savedEdits || S.checked.size > 0;
  }

  // ---------- structures ----------
  function done() {
    const ids = new Set(Object.values(S.savedLut).filter((e) => !e.auto).map((e) => e.id));
    for (const p of state.points) ids.add(p.id);
    return ids;
  }

  function nextRow() {
    const d = done();
    if (S.current) d.add(S.current.id); // "next" never means the one being painted
    return core.nextStructure(S.rows, d, S.current ? S.current.id : null);
  }

  // The label value a structure paints with; point structures have none.
  function valueOf(row) {
    return isPoint(row) ? 0 : paint.valueFor(row.id, lutIdToValue(), S.assigned);
  }

  function makeCurrent(row) {
    let v;
    try {
      v = valueOf(row);
    } catch (e) {
      note("error", esc(e.message));
      return;
    }
    S.current = row;
    S.curValue = v;
    applyColours();
    applyPen();
    render();
    ctx.drawMarkers(); // its point, if any, is the lit marker
    if (S.noteKind === "info") clearNote(); // hints were about the previous structure
  }

  async function enterNext() {
    if (stroking) { S.enterAfterStroke = true; return; } // the stroke belongs to this structure: guard it first
    if (S.saving) return;
    if (unsaved() && !(await save())) return; // a failed save keeps you on this structure
    const row = nextRow();
    if (row) makeCurrent(row);
    else note("info", "Every structure on the checklist is labelled.");
  }

  // ---------- save ----------
  async function fetchToken() {
    const r = await fetch(`/api/token?case=${encodeURIComponent(caseId)}`, { cache: "no-store" });
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.token) {
      throw new Error(r.status === 404 && !j.error
        ? "this server has no save endpoint — restart tools/serve.py"
        : `couldn't read the case's version (${j.error || r.status})`);
    }
    return j.token;
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(String(fr.result).slice(String(fr.result).indexOf(",") + 1));
      fr.onerror = () => reject(fr.error);
      fr.readAsDataURL(blob);
    });
  }

  // Resolves true when saved. One save at a time; a second call joins the one in flight.
  function save() {
    if (S.saving) return S.saving;
    const p = runSave().finally(() => {
      if (S.saving === p) S.saving = null;
      renderStatus();
    });
    S.saving = p;
    renderStatus();
    return p;
  }

  async function runSave() {
    const t0 = performance.now();
    // snapshot everything the save sends now: painting may go on while it is in flight
    const seq = S.edits;
    // `before` is the accepted drawing: a stroke still in progress (or never guarded) can't be saved.
    const raw = new Blob([before]); // copies the bytes
    const values = {};
    for (const [v, e] of Object.entries(S.savedLut)) values[v] = e.id;
    for (const [id, v] of S.assigned) values[v] = id;
    const checked = [...S.checked];
    const points = JSON.parse(JSON.stringify(state.points));
    let res;
    try {
      if (!S.token) S.token = await fetchToken();
      const gz = await new Response(raw.stream().pipeThrough(new CompressionStream("gzip"))).blob();
      const body = JSON.stringify({ case_id: caseId, token: S.token, labels_gz_b64: await blobToBase64(gz), values, checked, points });
      const r = await fetch("/api/save", { method: "POST", headers: { "Content-Type": "application/json" }, body });
      res = await r.json().catch(() => ({}));
      if (!r.ok) {
        const err = new Error(res.error || `${r.status} ${r.statusText}`);
        err.status = r.status;
        throw err;
      }
    } catch (e) {
      const extra = pointsOrChecksUnsaved();
      const files = `<code>${esc(caseId)}-unsaved-paint.nii.gz</code> holds the drawing` + (extra
        ? `, and <code>${esc(caseId)}-unsaved-points.json</code> your points and checked marks (the browser may ask to allow two downloads)`
        : "");
      note("error", (e.status === 409
        ? `Not saved: ${esc(e.message)}. Your work is still here — download it before you reload, because reloading discards it.`
        : `Not saved: ${esc(e.message)}. Your work is still here; try again, or download it to keep a copy.`) + ` The download: ${files}.`,
      { download: extra ? "Download my unsaved work" : "Download my unsaved paint" });
      return false;
    }
    // saved: from here on a failure is only about refreshing the panel
    S.token = res.token;
    S.savedEdits = seq;
    S.savedPoints = JSON.stringify(points);
    for (const c of checked) S.checked.delete(c);
    // a saved check can't be undone here (lut.json no longer has the `auto`): drop its undo entries
    S.undo = S.undo.filter((u) => !(u.kind === "check" && checked.includes(u.id)));
    S.lastSaveMs = performance.now() - t0;
    const warn = (res.warnings || []).map(esc);
    try {
      await reloadAfterSave();
    } catch (e) {
      warn.push(`the panel couldn't reload lut.json or the checklist (${esc(e.message)})`);
    }
    if (warn.length) note("warn", `Saved — but ${warn.join("; ")}`);
    else note("ok", `Saved in ${(S.lastSaveMs / 1000).toFixed(1)} s · ${res.structures} structures${res.mirror ? " · left copy rebuilt" : ""}`);
    return true;
  }

  async function reloadAfterSave() {
    const base = `${ctx.DATA}${caseId}/`;
    const [lut, md] = await Promise.all([
      ctx.getJSON(base + "lut.json"),
      fetchChecklist().catch(() => null),
    ]);
    S.savedLut = lut;
    const ids = new Set(Object.values(lut).map((e) => e.id));
    for (const id of [...S.assigned.keys()]) if (ids.has(id)) S.assigned.delete(id);
    if (md !== null) S.rows = core.parseChecklist(md);
    if (S.current) {
      S.current = rowOf(S.current.id) || S.current;
      S.curValue = valueOf(S.current);
    }
    applyColours();
    applyPen();
    render();
  }

  async function fetchChecklist() {
    const r = await fetch(`../checklists/${encodeURIComponent(state.meta.region)}.md`, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${r.status} checklists/${state.meta.region}.md`);
    return r.text();
  }

  function downloadPaint() {
    return nv.saveImage({ filename: `${caseId}-unsaved-paint.nii.gz`, isSaveDrawing: true });
  }

  function pointsOrChecksUnsaved() {
    return S.checked.size > 0 || JSON.stringify(state.points) !== S.savedPoints;
  }

  // The failed save's download: the drawing, and — when points or checked marks are unsaved — a JSON
  // with the same `points` and `checked` a save would send. The drawing goes first: it is the hours of work.
  async function downloadUnsaved() {
    const extra = pointsOrChecksUnsaved() ? { points: copyPoints(), checked: [...S.checked] } : null;
    await downloadPaint();
    if (extra) downloadJSON(`${caseId}-unsaved-points.json`, extra);
  }

  function downloadJSON(filename, obj) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2) + "\n"], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ---------- panel ----------
  const keyHelp = `
    <p><kbd>B</kbd> brush · <kbd>E</kbd> eraser · <kbd>W</kbd> wand (click) · <kbd>[</kbd> <kbd>]</kbd> size or tolerance · <kbd>O</kbd> show/hide paint</p>
    <p><kbd>F</kbd> fill between painted slices · <kbd>G</kbd> grow · <kbd>K</kbd> a model's outline looks right: mark it checked</p>
    <p><b>Ligament:</b> paint 2–3 key slices, press <kbd>F</kbd>, then scroll and touch up. <b>Muscle:</b> paint a little, press <kbd>G</kbd> until full, erase spill.</p>
    <p><b>Point labels:</b> click in the big view, or point and press <kbd>P</kbd>, to place the point · <kbd>Delete</kbd> remove it</p>
    <p><kbd>Enter</kbd> save, then next · <kbd>${MOD}S</kbd> save · <kbd>${MOD}Z</kbd> undo · <kbd>/</kbd> filter</p>
    <p><b>Mouse:</b> drag = paint (big view) · Shift-drag = window/level · right- or Ctrl-drag = pan ·
      wheel or <kbd>↑</kbd><kbd>↓</kbd> = slices · <kbd>1</kbd>–<kbd>3</kbd> plane · click a small view to jump there</p>`;

  function buildPanel() {
    authorStyles();
    $("panelBody").hidden = true;
    const el = document.createElement("div");
    el.id = "authorPanel";
    el.innerHTML = `
      <section class="ap-current">
        <div class="ap-kicker">Painting</div>
        <h2 id="apName"></h2>
        <div id="apMeta" class="muted"></div>
        <div id="apAuto" class="ap-auto" hidden></div>
        <button id="apCheck" class="ap-checkbtn" type="button" title="The outline looks right: mark it checked (K)" hidden>Looks right: mark checked · <kbd>K</kbd></button>
        <button id="apNext" class="ap-next" type="button"></button>
      </section>
      <section id="apPoint" class="ap-point" hidden>
        <p id="apPointText"></p>
        <div class="ap-actions">
          <button id="apPointGo" type="button" title="Show the slice the point is on">Go to it</button>
          <button id="apPointDel" type="button" title="Remove the point (Delete)">Remove point</button>
        </div>
      </section>
      <section id="apTools" class="ap-tools">
        <div class="group" role="group" aria-label="Tool">
          <button type="button" data-tool="brush" title="Brush (B)">Brush</button>
          <button type="button" data-tool="eraser" title="Eraser (E)">Eraser</button>
          <button type="button" data-tool="wand" title="Wand: click a structure to fill similar signal (W)">Wand</button>
        </div>
        <label id="apSizeRow" class="ap-size">Size <input id="apSize" type="range" min="${AUTHOR_OPTS.sizeMin}" max="${AUTHOR_OPTS.sizeMax}"
          step="${AUTHOR_OPTS.sizeStep}" aria-label="Brush size in voxels"> <output id="apSizeOut"></output></label>
        <div id="apWandRow" class="ap-wand">
          <label class="ap-size" title="How far from the clicked signal the fill reaches, as a share of the window width">Tolerance
            <input id="apTol" type="range" min="${AUTHOR_OPTS.wandTolMin}" max="${AUTHOR_OPTS.wandTolMax}" step="${AUTHOR_OPTS.wandTolStep}"
              aria-label="Wand tolerance"> <output id="apTolOut"></output></label>
          <label class="ap-check" title="Off: the wand fills this slice only. On: it also spreads to neighbouring slices"><input id="apWand3D" type="checkbox"> 3D</label>
        </div>
        <div class="ap-actions">
          <button id="apFill" type="button" title="Fill the slices between the painted ones in this plane (F)">Fill between</button>
          <button id="apGrow" type="button" title="Grow the painted strokes into similar signal (G)">Grow</button>
        </div>
        <label class="ap-check"><input id="apOverwrite" type="checkbox"> Paint over other structures</label>
      </section>
      <section class="ap-save">
        <button id="apSave" type="button" title="Save (${MOD}S)">Save</button>
        <button id="apUndo" type="button" title="Undo (${MOD}Z)">Undo</button>
        <span id="apStatus" class="ap-status" aria-live="polite"></span>
      </section>
      <div id="apMsg" class="ap-msg" hidden></div>
      <section class="ap-list">
        <input id="apFilter" type="search" placeholder="Filter structures ( / )" aria-label="Filter structures" autocomplete="off">
        <div id="apRows"></div>
      </section>
      <div class="ap-help">${keyHelp}</div>`;
    $("panel").appendChild(el);

    // header controls that don't apply while painting (the overlay is the paint itself; R | L would
    // open the mirrored copy). Inline style: .group / label.inline set display, which beats [hidden].
    for (const el2 of [$("find"), $("overlayGroup"), $("sideGroup"), $("opacity").closest("label")]) el2.style.display = "none";

    const focusImage = () => $("gl").focus({ preventScroll: true });
    $("apNext").addEventListener("click", () => { enterNext(); focusImage(); });
    $("apCheck").addEventListener("click", () => { markChecked(); focusImage(); });
    $("apPointGo").addEventListener("click", () => { goToPoint(); focusImage(); });
    $("apPointDel").addEventListener("click", () => { deletePoint(); focusImage(); });
    el.querySelector(".ap-tools .group").addEventListener("click", (e) => {
      const t = e.target.closest("[data-tool]");
      if (t) { setTool(t.dataset.tool); focusImage(); }
    });
    $("apSize").addEventListener("input", (e) => setSize(Number(e.target.value)));
    $("apSize").addEventListener("change", focusImage);
    $("apTol").addEventListener("input", (e) => setTolerance(Number(e.target.value)));
    $("apTol").addEventListener("change", focusImage);
    $("apWand3D").addEventListener("change", (e) => { S.wand3D = e.target.checked; focusImage(); });
    $("apFill").addEventListener("click", () => { fillBetween(); focusImage(); });
    $("apGrow").addEventListener("click", () => { grow(); focusImage(); });
    $("apOverwrite").addEventListener("change", (e) => { S.overwrite = e.target.checked; focusImage(); });
    $("apSave").addEventListener("click", () => { save(); focusImage(); });
    $("apUndo").addEventListener("click", () => { undoLast(); focusImage(); });
    $("apFilter").addEventListener("input", (e) => { S.filter = e.target.value; renderRows(); });
    $("apRows").addEventListener("click", (e) => {
      const b = e.target.closest("[data-id]");
      const row = b && rowOf(b.dataset.id);
      if (row) { makeCurrent(row); focusImage(); }
    });
    $("apMsg").addEventListener("click", (e) => {
      if (e.target.closest("[data-download]")) {
        downloadUnsaved().catch((err) => note("error", `The download failed: ${esc(err.message)}.`));
      }
    });
  }

  // `download`: a button label, shown after the message (a failed save's download).
  function note(kind, html, { download = null } = {}) {
    const m = $("apMsg");
    S.noteKind = kind;
    m.hidden = false;
    m.className = `ap-msg ap-${kind}`;
    m.innerHTML = html + (download ? ` <button type="button" data-download>${esc(download)}</button>` : "");
  }

  function clearNote() {
    S.noteKind = null;
    $("apMsg").hidden = true;
    $("apMsg").innerHTML = "";
  }

  function setTool(tool) {
    if (isPoint(S.current)) { note("info", pointHint()); return; }
    // Turning the pen off mid-stroke ends NiiVue's stroke without "draw": guard what it painted so far.
    if (stroking && (tool === "brush" || tool === "eraser") !== (S.tool === "brush" || S.tool === "eraser")) {
      stroking = false;
      afterEdit();
    }
    S.tool = tool;
    applyPen();
    render();
  }

  function setSize(n) {
    S.size = Math.max(AUTHOR_OPTS.sizeMin, Math.min(AUTHOR_OPTS.sizeMax, n));
    applyPen();
    render();
  }

  function setTolerance(t) {
    const r = Math.round(t / AUTHOR_OPTS.wandTolStep) * AUTHOR_OPTS.wandTolStep; // no float drift from [ ]
    S.wandTol = Math.max(AUTHOR_OPTS.wandTolMin, Math.min(AUTHOR_OPTS.wandTolMax, Number(r.toFixed(2))));
    render();
  }

  function typeText(row) {
    return { R: "Region", P: "Point label", E: "Expected location — visible only when distended" }[row.type] || row.type;
  }

  function render() {
    const c = S.current;
    const entry = c && S.savedLut[lutIdToValue()[c.id]];
    $("apName").textContent = c ? c.name : "No structure chosen";
    const auto = !!(entry && entry.auto);
    const marked = auto && S.checked.has(c.id);
    $("apMeta").innerHTML = c
      ? `${esc(typeText(c))}${auto && !marked ? '<span class="badge" title="Drawn by a model, not yet checked">auto</span>' : ""}`
      : S.checklistError ? esc(S.checklistError) : "Press Enter to start on the next structure, or pick one below.";
    $("apAuto").hidden = !auto;
    $("apAuto").textContent = !auto ? "" : marked ? "Marked checked: the auto mark goes when you save."
      : `${core.autoNote(entry)}. Edit it, or if it looks right mark it checked.`;
    $("apCheck").hidden = !auto || marked;
    const pt = isPoint(c);
    $("apTools").hidden = pt;
    $("apPoint").hidden = !pt;
    if (pt) {
      const p = pointOf(c.id);
      $("apPointText").innerHTML = p
        ? `Placed on ${esc(state.plane)} slice ${pointSliceHere(p) + 1}. Click in the big view to move it.`
        : "Not placed yet. Click in the big view to place it.";
      $("apPointGo").disabled = !p;
      $("apPointDel").disabled = !p;
    }
    const nx = nextRow();
    $("apNext").innerHTML = nx ? `Next: <b>${esc(nx.name)}</b> · <kbd>Enter</kbd>`
      : S.rows.length ? "All structures labelled" : S.checklistError ? "No checklist" : "Loading the checklist…";
    $("apNext").disabled = !nx;
    for (const b of document.querySelectorAll("#authorPanel [data-tool]")) b.setAttribute("aria-pressed", String(b.dataset.tool === S.tool));
    $("apSize").value = S.size;
    $("apSizeOut").textContent = `${S.size} vox`;
    $("apTol").value = S.wandTol;
    $("apTolOut").textContent = `${Math.round(S.wandTol * 100)} %`;
    $("apWand3D").checked = S.wand3D;
    // inline style: .ap-size sets display, which beats [hidden]
    $("apSizeRow").style.display = S.tool === "wand" ? "none" : "";
    $("apWandRow").style.display = S.tool === "wand" ? "" : "none";
    $("apOverwrite").checked = S.overwrite;
    renderStatus();
    renderRows();
  }

  function renderStatus() {
    const st = $("apStatus");
    if (!st) return;
    if (S.saving) { st.textContent = "Saving…"; st.className = "ap-status"; }
    else if (unsaved()) { st.textContent = "● Unsaved"; st.className = "ap-status ap-unsaved"; }
    else { st.textContent = "Saved"; st.className = "ap-status muted"; }
    $("apSave").disabled = !!S.saving;
    $("apUndo").disabled = !S.undo.length;
  }

  function renderRows() {
    const q = S.filter.trim().toLowerCase();
    const autoIds = new Set(Object.values(S.savedLut).filter((e) => e.auto).map((e) => e.id));
    const hits = matches(q);
    let html = "", group = null;
    for (const r of hits) {
      if (r.group !== group) {
        group = r.group;
        html += `<div class="ap-group">${esc(group)}</div>`;
      }
      const tag = r.type === "P" ? "point" : r.type === "E" ? "expected" : autoIds.has(r.id) ? "auto" : "";
      html += `<button type="button" class="ap-row" data-id="${esc(r.id)}"${S.current && S.current.id === r.id ? ' aria-current="true"' : ""}>
        <span class="ap-tick">${r.labelled ? "✓" : ""}</span><span class="ap-rname">${esc(r.name)}</span>${tag ? `<span class="ap-tag">${tag}</span>` : ""}</button>`;
    }
    if (!hits.length) html = `<p class="muted">${S.rows.length ? "No structure matches." : esc(S.checklistError || "Loading the checklist…")}</p>`;
    $("apRows").innerHTML = html;
  }

  function matches(q) {
    if (!q) return S.rows;
    return S.rows.filter((r) => r.name.toLowerCase().includes(q) || r.id.includes(q.replace(/\s+/g, "_")));
  }

  // ---------- input ----------
  // Keys: offered first by index.html's keydown handler; true = handled here.
  function onKey(e) {
    const t = e.target;
    if (t && t.id === "apFilter") {
      if (e.key === "Enter") {
        const row = matches(S.filter.trim().toLowerCase())[0];
        if (row) makeCurrent(row);
        t.value = ""; S.filter = ""; renderRows();
        t.blur();
        e.preventDefault();
        return true;
      }
      if (e.key === "Escape") {
        t.value = ""; S.filter = ""; renderRows();
        t.blur();
        return true;
      }
      return false; // typing in the filter: never a tool key
    }
    if (t && (t.tagName === "TEXTAREA" || (t.tagName === "INPUT" && /^(search|text)$/.test(t.type)))) return false;
    const mod = e.metaKey || e.ctrlKey;
    const k = e.key;
    if (mod && !e.altKey && !e.shiftKey && (k === "s" || k === "S")) { e.preventDefault(); save(); return true; }
    if (mod && !e.altKey && !e.shiftKey && (k === "z" || k === "Z")) { e.preventDefault(); undoLast(); return true; }
    if (mod || e.altKey) return false;
    if (k === "Enter") { e.preventDefault(); if (!e.repeat) enterNext(); return true; }
    if (k === "k" || k === "K") { if (!e.repeat) markChecked(); return true; }
    if (k === "p" || k === "P") { if (!e.repeat) pointKey(); return true; }
    if ((k === "Delete" || k === "Backspace") && isPoint(S.current)) { e.preventDefault(); if (!e.repeat) deletePoint(); return true; }
    if (k === "b" || k === "B") { setTool("brush"); return true; }
    if (k === "e" || k === "E") { setTool("eraser"); return true; }
    if (k === "w" || k === "W") { setTool("wand"); return true; }
    if (k === "f" || k === "F") { if (!e.repeat) fillBetween(); return true; }
    if (k === "g" || k === "G") { if (!e.repeat) grow(); return true; }
    if (k === "[" || k === "]") {
      const dir = k === "]" ? 1 : -1;
      if (S.tool === "wand") setTolerance(S.wandTol + dir * AUTHOR_OPTS.wandTolKeyStep);
      else setSize(S.size + dir * AUTHOR_OPTS.sizeStep);
      return true;
    }
    if (k === "/") { e.preventDefault(); $("apFilter").focus(); return true; }
    if (k === "o" || k === "O") {
      S.paintShown = !S.paintShown;
      nv.setDrawOpacity(S.paintShown ? AUTHOR_OPTS.drawOpacity : 0);
      return true;
    }
    return false;
  }

  // A click (no drag) in the main view. Brush and eraser have already painted the dab; the wand fills;
  // with a point structure current (drawing off) it places the point.
  function onClick(frac, _e) {
    if (isPoint(S.current)) placePoint(frac);
    else if (S.tool === "wand") wandAt(frac);
  }

  function beforeUnload(e) {
    if (!unsaved() && !S.saving) return undefined;
    const msg = "You have unsaved paint. Leave and lose it?";
    if (e) { e.preventDefault(); e.returnValue = msg; }
    return msg;
  }

  // Strokes paint in the main view only: a press on a small view (or the gap) keeps its viewer
  // behaviour — the main view jumps there — and paints nothing.
  function onPointerDown(e) {
    if (e.button !== 0 || !nv.opts.drawingEnabled) return;
    if (ctx.tileKind(e.offsetX, e.offsetY) !== "main") {
      nv.opts.drawingEnabled = false;
      suspended = true;
    } else {
      stroking = true;
    }
  }

  function onPointerEnd() {
    stroking = false;
    if (suspended) {
      suspended = false;
      nv.opts.drawingEnabled = penOn();
    }
    if (S.enterAfterStroke) { // after NiiVue's mouseup has fired "draw" for this stroke
      S.enterAfterStroke = false;
      setTimeout(enterNext, 0);
    }
  }

  // A stroke that leaves the canvas: NiiVue's mouseleave ends it without firing "draw" (it only resets
  // the pen), so its voxels would stay unchecked. Registered after NiiVue's listener, so this runs after
  // that reset; coming back in with the button held doesn't resume the stroke.
  function onCanvasLeave() {
    if (!stroking) return;
    stroking = false;
    afterEdit();
  }

  // Case switching reloads the page in author mode, so leaving with unsaved paint is asked about first.
  function onCaseChange(e) {
    if (e.target.id !== "caseSel") return;
    e.stopImmediatePropagation();
    const id = e.target.value;
    e.target.value = caseId;
    location.assign(`?case=${encodeURIComponent(id)}&mode=author`);
  }

  // ---------- after a reload of the volumes (sequence switch) ----------
  function reattach(newCtx) {
    ctx = newCtx;
    if (newCtx.state.caseId !== caseId) { // not reachable from the UI (case changes reload the page)
      S.refused = true;
      authorBanner(newCtx, "The case changed under author mode. Reload the page.");
      return false;
    }
    const why = authorRefusal(newCtx, { again: true });
    S.refused = !!why;
    authorBanner(newCtx, why);
    if (why) {
      nv.setDrawingEnabled(false); // NiiVue's pen throws on a closed drawing
      if (nv.drawBitmap) nv.closeDrawing(); // `before` still holds the paint for when a paintable sequence is back
      return false;
    }
    if (!nv.drawBitmap || nv.drawBitmap.length !== before.length) {
      nv.createEmptyDrawing();
      nv.drawBitmap.set(before);
      nv.drawAddUndoBitmap();
    }
    nv.refreshDrawing(true);
    setupView();
    return true;
  }

  // ---------- start ----------
  loadDrawing();
  buildPanel();
  setupView();
  render();
  nv.onDrawingChanged = (a) => a === "draw" && afterEdit();
  $("gl").addEventListener("pointerdown", onPointerDown);
  $("gl").addEventListener("mouseleave", onCanvasLeave);
  window.addEventListener("pointerup", onPointerEnd);
  window.addEventListener("pointercancel", onPointerEnd);
  document.addEventListener("change", onCaseChange, true);
  window.onbeforeunload = beforeUnload;
  fetchChecklist()
    .then((md) => { S.rows = core.parseChecklist(md); })
    .catch((e) => { S.checklistError = `No checklist for this case (${e.message}).`; })
    .finally(render);
  fetchToken()
    .then((t) => { S.token = t; })
    .catch((e) => note("error", `Saving won't work: ${esc(e.message)}.`));

  return {
    caseId, onKey, onClick, reattach, save, undo: undoLast, afterEdit, beforeUnload, makeCurrent, enterNext,
    unsaved, downloadPaint, downloadUnsaved, wandAt, fillBetween, grow, setTool, placePoint, deletePoint, markChecked,
    get currentId() { return S.current ? S.current.id : null; },
    get state() { return S; },
    get before() { return before; },
  };
}

function authorStyles() {
  if (document.getElementById("authorStyles")) return;
  const st = document.createElement("style");
  st.id = "authorStyles";
  st.textContent = `
  #authorBanner {
    position: absolute; top: 40px; left: 50%; transform: translateX(-50%); z-index: 3; max-width: min(560px, 90%);
    background: var(--warn-bg); color: var(--warn-text); padding: 8px 12px; border-radius: var(--radius);
    font-size: 13px; box-shadow: 0 2px 12px rgba(0,0,0,.5);
  }
  #authorBanner[hidden] { display: none; }
  #authorBanner a { color: #fff; font-weight: 600; }
  #authorPanel { display: flex; flex-direction: column; gap: 12px; height: 100%; min-height: 0; }
  #authorPanel section { display: flex; flex-direction: column; gap: 6px; }
  #authorPanel h2 { margin: 0; font-size: 20px; }
  .ap-kicker { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
  .ap-next { text-align: left; }
  .ap-next kbd, .ap-checkbtn kbd, .ap-help kbd, .ap-msg kbd { font: 11px var(--font); border: 1px solid var(--border); border-radius: 3px; padding: 0 4px; }
  .ap-tools .group { align-self: flex-start; }
  .ap-size, .ap-check { display: flex; align-items: center; gap: 8px; color: var(--muted); }
  .ap-size input { flex: 1; }
  .ap-wand { display: flex; flex-direction: column; gap: 6px; }
  .ap-actions { display: flex; gap: 6px; }
  .ap-size output { min-width: 48px; text-align: right; color: var(--text); font-variant-numeric: tabular-nums; }
  #authorPanel .ap-save { flex-direction: row; align-items: center; }
  #apSave { background: var(--accent); color: var(--accent-ink); font-weight: 600; }
  #apSave:disabled, #apUndo:disabled, .ap-next:disabled, #apPoint button:disabled { opacity: .5; cursor: default; }
  #authorPanel [hidden] { display: none; }
  .ap-auto { font-size: 13px; color: var(--muted); }
  .ap-checkbtn { text-align: left; }
  .ap-point p { margin: 0; }
  .ap-status { margin-left: auto; font-variant-numeric: tabular-nums; }
  .ap-unsaved { color: var(--warn-text); font-weight: 600; }
  .ap-msg { font-size: 13px; padding: 8px 10px; border-radius: var(--radius); background: var(--surface-2); }
  .ap-msg[hidden] { display: none; }
  .ap-msg button { margin-top: 6px; display: block; }
  .ap-error, .ap-warn { background: var(--warn-bg); color: var(--warn-text); }
  .ap-ok { color: var(--muted); }
  .ap-list { flex: 1; min-height: 140px; }
  #apFilter { width: 100%; }
  #apRows { flex: 1; min-height: 0; overflow-y: auto; border: 1px solid var(--border); border-radius: var(--radius); }
  .ap-group { position: sticky; top: 0; background: var(--surface); font-size: 11px; text-transform: uppercase;
    letter-spacing: .05em; color: var(--muted); padding: 6px 8px 3px; }
  .ap-row { display: flex; width: 100%; align-items: center; gap: 6px; border: 0; border-radius: 0; background: none;
    text-align: left; padding: 3px 8px; min-height: 26px; }
  .ap-row[aria-current=true] { background: var(--accent); color: var(--accent-ink); }
  .ap-tick { width: 14px; flex: none; color: #7bd88f; }
  .ap-row[aria-current=true] .ap-tick { color: inherit; }
  .ap-rname { flex: 1; }
  .ap-tag { font-size: 11px; color: var(--muted); }
  .ap-row[aria-current=true] .ap-tag { color: inherit; }
  .ap-help { font-size: 12px; color: var(--muted); }
  .ap-help p { margin: 4px 0; }
  `;
  document.head.appendChild(st);
}
