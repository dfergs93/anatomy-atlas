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
