import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const P = require("../../viewer/paint-core.js");

const sorted = (a) => Array.from(a).sort((x, y) => x - y);

test("guard keeps other structures (pen and eraser, cur = 2)", () => {
  const before = Uint8Array.from([0, 2, 3, 0, 2, 3]);
  // pen: 0->2 ok, 3->2 refused; eraser: 2->0 ok, 3->0 refused, 0->3 refused
  const after = Uint8Array.from([2, 2, 2, 3, 0, 0]);
  const r = P.guardChanges(before, after, 2, false);
  assert.deepEqual(Array.from(after), [2, 2, 3, 0, 0, 3]);
  assert.equal(r.restored, 3);
  assert.deepEqual(sorted(r.idx), [0, 4]);
  assert.deepEqual(Array.from(before), [2, 2, 3, 0, 0, 3]);
  assert.deepEqual(Array.from(r.old), [0, 2]);
});

test("guard with overwrite", () => {
  const before = Uint8Array.from([3, 3, 2, 0]);
  const after = Uint8Array.from([2, 0, 5, 7]);
  const r = P.guardChanges(before, after, 2, true);
  assert.deepEqual(Array.from(after), [2, 0, 2, 0]);
  assert.equal(r.idx.length, 2);
  assert.equal(r.restored, 2);
});

test("undo restores exactly", () => {
  const orig = Uint8Array.from([0, 2, 3, 0, 2, 3, 0]);
  const before = Uint8Array.from(orig);
  const bitmap = Uint8Array.from([2, 0, 3, 2, 2, 3, 9]);
  const ch = P.guardChanges(before, bitmap, 2, false);
  P.undoChange(ch, bitmap, before);
  assert.deepEqual(Array.from(bitmap), Array.from(orig));
  assert.deepEqual(Array.from(before), Array.from(orig));
});

test("valueFor reuses, assigns next, refuses 256", () => {
  const lut = { femur: 1, tibia: 2 };
  const assigned = new Map();
  assert.equal(P.valueFor("tibia", lut, assigned), 2);
  assert.equal(P.valueFor("new_a", lut, assigned), 3);
  assigned.set("new_a", 3);
  assert.equal(P.valueFor("new_a", lut, assigned), 3);
  assigned.set("new_b", 9);
  assert.equal(P.valueFor("new_c", lut, assigned), 10);
  assigned.set("z", 255);
  assert.throws(() => P.valueFor("w", lut, assigned), RangeError);
});

test("colour matches the Python fixture", () => {
  const fx = JSON.parse(readFileSync(new URL("../fixtures/colours.json", import.meta.url)));
  assert.ok(fx.length >= 20);
  for (const [id, v, rgb] of fx) assert.deepEqual(P.colour(id, v), rgb, id);
});

// 10x10x1 slab helper: x fastest
function slab(nx, ny, nz, f) {
  const a = new Int16Array(nx * ny * nz);
  for (let z = 0; z < nz; z++) for (let y = 0; y < ny; y++) for (let x = 0; x < nx; x++) a[x + y * nx + z * nx * ny] = f(x, y, z);
  return a;
}

test("wand stops at an edge and at maxDistMM", () => {
  const dims = [10, 10, 1];
  const img = slab(10, 10, 1, (x) => (x < 5 ? 100 : 500));
  const m = P.wandMask(img, dims, [2, 5, 0], { lo: 90, hi: 110, is2D: true, axis: 2, maxDistMM: 1000, voxMM: [1, 1, 1] });
  assert.equal(m.length, 50);
  assert.ok(Array.from(m).every((i) => i % 10 < 5));
  const near = P.wandMask(img, dims, [2, 5, 0], { lo: 90, hi: 110, is2D: true, axis: 2, maxDistMM: 2, voxMM: [1, 1, 1] });
  // disc of radius 2 around (2,5): 13 voxels
  assert.equal(near.length, 13);
  const aniso = P.wandMask(img, dims, [2, 5, 0], { lo: 90, hi: 110, is2D: true, axis: 2, maxDistMM: 2, voxMM: [2, 1, 1] });
  // x step is 2mm: (2±1,5) ok at 2mm, y steps ±1, ±2 ok => (2,3..7)=5 + (1,5),(3,5) + (1,4),(1,6)? dist sqrt(4+1)>2 no
  assert.equal(aniso.length, 7);
});

test("wand 2D stays on its slice", () => {
  const dims = [4, 4, 3];
  const img = slab(4, 4, 3, () => 100);
  const opts = { lo: 0, hi: 200, axis: 2, maxDistMM: 1000, voxMM: [1, 1, 1] };
  const m2 = P.wandMask(img, dims, [1, 1, 1], { ...opts, is2D: true });
  assert.equal(m2.length, 16);
  assert.ok(Array.from(m2).every((i) => Math.floor(i / 16) === 1));
  const m3 = P.wandMask(img, dims, [1, 1, 1], { ...opts, is2D: false });
  assert.equal(m3.length, 48);
  const mx = P.wandMask(img, dims, [1, 1, 1], { ...opts, is2D: true, axis: 0 });
  assert.equal(mx.length, 12);
  assert.ok(Array.from(mx).every((i) => i % 4 === 1));
});

test("grow fills a matching region only into empty voxels", () => {
  const dims = [9, 1, 1];
  const img = Int16Array.from([500, 100, 100, 100, 100, 100, 100, 100, 500]);
  const bitmap = Uint8Array.from([0, 0, 2, 2, 0, 0, 0, 0, 0]);
  const range = [0, 1000];
  const m = P.growMask(img, dims, bitmap, 2, { tolerance: 0.01, range, steps: 2 });
  assert.deepEqual(sorted(m), [1, 4, 5]);
  const all = P.growMask(img, dims, bitmap, 2, { tolerance: 0.01, range, steps: 50 });
  assert.deepEqual(sorted(all), [1, 4, 5, 6, 7]);
  // occupied voxels of another structure are not taken
  const b2 = Uint8Array.from([0, 0, 2, 2, 3, 0, 0, 0, 0]);
  const m2 = P.growMask(img, dims, b2, 2, { tolerance: 0.01, range, steps: 50 });
  assert.deepEqual(sorted(m2), [1]);
});

test("grow with nothing painted does nothing", () => {
  const img = new Int16Array(8).fill(100);
  const m = P.growMask(img, [2, 2, 2], new Uint8Array(8), 2, { tolerance: 0.5, range: [0, 100], steps: 5 });
  assert.equal(m.length, 0);
});

test("seedWindow takes the in-plane 3x3 median, clipped at the edge", () => {
  const dims = [5, 5, 2];
  const img = slab(5, 5, 2, (x, y, z) => (z === 1 ? 9999 : x === 2 && y === 2 ? 1000 : 100 + x));
  const [lo, hi] = P.seedWindow(img, dims, [2, 2, 0], 2, 0.1, [0, 1000]);
  assert.equal(lo, 102 - 100);
  assert.equal(hi, 102 + 100);
  const [lo2, hi2] = P.seedWindow(img, dims, [0, 0, 0], 2, 0, [0, 1000]); // 4 voxels: 100,101,100,101
  assert.equal(lo2, hi2);
  assert.equal(lo2, 100.5);
});

test("keySlices", () => {
  const dims = [3, 3, 3];
  const b = new Uint8Array(27);
  b[0 + 0 * 3 + 2 * 9] = 4;
  b[1 + 2 * 3 + 0 * 9] = 4;
  b[2 + 2 * 3 + 2 * 9] = 4;
  b[1 + 1 * 3 + 1 * 9] = 5;
  assert.deepEqual(P.keySlices(b, dims, 4, 2), [0, 2]);
  assert.deepEqual(P.keySlices(b, dims, 4, 1), [0, 2]);
  assert.deepEqual(P.keySlices(b, dims, 4, 0), [0, 1, 2]);
  assert.deepEqual(P.keySlices(b, dims, 9, 0), []);
});

test("guardChanges timing on 160x384x384", () => {
  const n = 160 * 384 * 384;
  const before = new Uint8Array(n);
  for (let i = 0; i < n; i += 7) before[i] = 3;
  const after = Uint8Array.from(before);
  for (let i = 1000; i < 200000; i += 3) after[i] = 2;
  const t0 = performance.now();
  const r = P.guardChanges(before, after, 2, false);
  const ms = performance.now() - t0;
  console.log(`guardChanges 160x384x384: ${ms.toFixed(1)} ms (${r.idx.length} allowed, ${r.restored} restored)`);
  assert.ok(r.idx.length > 0);
});

test("carryDropped: saved ids leave assigned, erased ids keep their old value", () => {
  const assigned = new Map([["patella", 3], ["ghost", 9]]);
  P.carryDropped({ femur: 1, fibula: 2 }, { femur: 1, patella: 3 }, assigned);
  // patella is in lut.json now; fibula (erased) keeps 2; an unsaved new structure stays
  assert.deepEqual([...assigned].sort(), [["fibula", 2], ["ghost", 9]]);
  // a value lut.json gave another id is never carried
  const a2 = new Map();
  P.carryDropped({ femur: 1, fibula: 2 }, { femur: 1, tibia: 2 }, a2);
  assert.deepEqual([...a2], []);
});

// author.js's bookkeeping round a save, with save_case.py's rules (only painted values are kept/checked).
function authorSim(lut, bitmap) {
  const s = { savedLut: lut, assigned: new Map(), before: Uint8Array.from(bitmap), undo: [] };
  s.ids = () => Object.fromEntries(Object.entries(s.savedLut).map(([v, e]) => [e.id, Number(v)]));
  s.choose = (id) => { s.cur = id; s.val = P.valueFor(id, s.ids(), s.assigned); };
  s.stroke = (idx, v) => { // a brush (v = cur) or eraser (v = 0) stroke, then afterEdit
    const bm = Uint8Array.from(s.before);
    for (const i of idx) bm[i] = v;
    const ch = P.guardChanges(s.before, bm, s.val, false);
    if (ch.idx.length) {
      if (!(s.cur in s.ids()) && !s.assigned.has(s.cur)) s.assigned.set(s.cur, s.val);
      s.undo.push(ch);
    }
  };
  s.undoLast = () => P.undoChange(s.undo.pop(), Uint8Array.from(s.before), s.before);
  s.save = () => { // runSave's values -> save_case -> reloadAfterSave
    const values = {};
    for (const [v, e] of Object.entries(s.savedLut)) values[v] = e.id;
    for (const [id, v] of s.assigned) values[v] = id;
    const present = [...new Set(s.before)].filter((v) => v);
    const unmapped = present.filter((v) => !(v in values));
    if (unmapped.length) return `400 painted values with no structure id: ${unmapped}`;
    const lut = {};
    for (const v of present) lut[v] = { id: values[v] };
    const old = s.ids();
    s.savedLut = lut;
    P.carryDropped(old, s.ids(), s.assigned);
    return Object.fromEntries(Object.entries(lut).map(([v, e]) => [v, e.id]));
  };
  return s;
}

test("undo back past a save that erased a structure restores it under its own id", () => {
  const s = authorSim({ 1: { id: "femur" }, 2: { id: "fibula" } }, [1, 1, 2, 2, 0, 0, 0, 0]);
  s.choose("fibula");
  s.stroke([2, 3], 0);                                   // erase all of fibula (the highest value)
  assert.deepEqual(s.save(), { 1: "femur" });
  s.choose("patella");
  assert.equal(s.val, 3, "a new structure must not take the erased fibula's value");
  s.stroke([5], s.val);
  s.undoLast();                                          // the patella stroke
  s.undoLast();                                          // the fibula erase, from before the save
  assert.deepEqual(Array.from(s.before), [1, 1, 2, 2, 0, 0, 0, 0]);
  assert.deepEqual(s.save(), { 1: "femur", 2: "fibula" });
  s.choose("patella");
  s.stroke([6], s.val);
  assert.deepEqual(s.save(), { 1: "femur", 2: "fibula", 3: "patella" });
});
