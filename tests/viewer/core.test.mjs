import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const core = require("../../viewer/core.js");

const TYPES = { sagittal: 2, coronal: 1, axial: 0 };

test("layoutFor puts the main plane large on the left and the other two stacked on the right", () => {
  const tiles = core.layoutFor("sagittal", TYPES);
  assert.deepEqual(tiles, [
    { sliceType: 2, position: [0, 0, 0.7, 1] },
    { sliceType: 1, position: [0.7, 0, 0.3, 0.5] },
    { sliceType: 0, position: [0.7, 0.5, 0.3, 0.5] },
  ]);
  assert.deepEqual(core.layoutFor("coronal", TYPES).map((t) => t.sliceType), [1, 2, 0]);
  assert.deepEqual(core.layoutFor("axial", TYPES).map((t) => t.sliceType), [0, 2, 1]);
});

test("layoutFor tiles never overlap", () => {
  for (const main of core.PLANES) {
    const r = core.layoutFor(main, TYPES).map((t) => t.position);
    for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) {
      const [a, b] = [r[i], r[j]];
      const overlapX = a[0] < b[0] + b[2] - 1e-9 && b[0] < a[0] + a[2] - 1e-9;
      const overlapY = a[1] < b[1] + b[3] - 1e-9 && b[1] < a[1] + a[3] - 1e-9;
      assert.ok(!(overlapX && overlapY), `${main}: tiles ${i} and ${j} overlap`);
    }
  }
});

test("refLineOrientation for every main/small pair", () => {
  const want = [
    ["sagittal", "coronal", "vertical"], ["sagittal", "axial", "vertical"],
    ["coronal", "sagittal", "vertical"], ["coronal", "axial", "horizontal"],
    ["axial", "sagittal", "horizontal"], ["axial", "coronal", "horizontal"],
  ];
  for (const [main, small, o] of want) assert.equal(core.refLineOrientation(main, small), o, `${main}/${small}`);
});

test("tileAt finds the tile under a point, -1 in gaps and off-canvas", () => {
  const tiles = [{ leftTopWidthHeight: [0, 0, 700, 900] }, { leftTopWidthHeight: [704, 0, 296, 448] }];
  assert.equal(core.tileAt(tiles, 350, 450), 0);
  assert.equal(core.tileAt(tiles, 800, 100), 1);
  assert.equal(core.tileAt(tiles, 702, 100), -1);
  assert.equal(core.tileAt(tiles, 800, 600), -1);
  assert.equal(core.tileAt(tiles, -5, 10), -1);
});

test("tileAt handles a tile drawn flipped (negative width or height)", () => {
  const tiles = [{ leftTopWidthHeight: [700, 0, -700, 900] }, { leftTopWidthHeight: [704, 448, 296, -448] }];
  assert.equal(core.tileAt(tiles, 350, 450), 0);
  assert.equal(core.tileAt(tiles, 800, 100), 1);
  assert.equal(core.tileAt(tiles, 800, 600), -1);
});

// cand-049 (OAI DESS): RAS affine, ~4° oblique — row-major, as NiiVue's volume.matRAS.
const CAND = [0.6982881426811218, 0.025432050228118896, 0.0, 8.507220268249512,
  -0.04882906749844551, 0.3636952340602875, 8.095376441806596e-17, -70.65251922607422,
  1.084223100155002e-17, 0.0, 0.3645833432674408, -85.64833068847656, 0, 0, 0, 1];
const CAND_DIMS = [160, 384, 384];
const mul = (m, v) => [0, 1, 2].map((r) => m[r * 4] * v[0] + m[r * 4 + 1] * v[1] + m[r * 4 + 2] * v[2] + m[r * 4 + 3]);
const frac = (vox, dims) => vox.map((v, a) => (v + 0.5) / dims[a]);
const close = (a, b, tol) => a.forEach((v, i) => assert.ok(Math.abs(v - b[i]) <= tol, `${a} vs ${b}`));

test("fracToWorld uses the volume's own (oblique) affine", () => {
  close(core.fracToWorld(CAND, CAND_DIMS, frac([80, 370, 370], CAND_DIMS)), [73.7801, 60.0084, 49.2475], 1e-3);
  close(core.fracToWorld(CAND, CAND_DIMS, frac([0, 0, 0], CAND_DIMS)), [8.5072, -70.6525, -85.6483], 1e-3);
});

test("worldToFrac puts a world point back on its own voxel on an oblique grid", () => {
  for (const vox of [[0, 0, 0], [80, 370, 370], [159, 383, 383]]) {
    const f = core.worldToFrac(CAND, CAND_DIMS, mul(CAND, vox));
    close(f.map((x, a) => x * CAND_DIMS[a] - 0.5), vox, 1e-6);
  }
});

// lut.json extent for one plane, built the way tools/atlaslib.py does: slice coordinate =
// world coordinate along the axis of voxel (slice, anchor's other indices).
function extentFor(m, axis, anchorVox, start, end, widest) {
  const at = (s) => { const v = [...anchorVox]; v[axis] = s; return mul(m, v)[axis]; };
  return { start_mm: at(start), end_mm: at(end), widest_mm: at(widest), anchor_mm: mul(m, anchorVox) };
}

test("extentSlices recovers the exact slices on an oblique grid, whatever the cursor", () => {
  const sag = extentFor(CAND, 0, [70, 200, 190], 60, 85, 70);
  assert.deepEqual(core.extentSlices(sag, 0, CAND, CAND, CAND_DIMS), { start: 60, end: 85, widest: 70 });
  const cor = extentFor(CAND, 1, [70, 200, 190], 150, 260, 200);
  assert.deepEqual(core.extentSlices(cor, 1, CAND, CAND, CAND_DIMS), { start: 150, end: 260, widest: 200 });
});

test("extentSlices maps onto a different sequence grid through world space", () => {
  const coarse = [...CAND];
  for (const r of [0, 1, 2]) for (const c of [0, 1, 2]) coarse[r * 4 + c] *= 2; // same origin, 2× voxels
  const sag = extentFor(CAND, 0, [70, 200, 190], 60, 84, 70);
  assert.deepEqual(core.extentSlices(sag, 0, CAND, coarse, [80, 192, 192]), { start: 30, end: 42, widest: 35 });
});

const IDENT = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

test("extentSlices is null without an extent (old lut.json) or with a missing value", () => {
  assert.equal(core.extentSlices(undefined, 0, IDENT, IDENT, [100, 100, 100]), null);
  assert.equal(core.extentSlices({ start_mm: 1, widest_mm: 2, anchor_mm: [2, 5, 5] }, 0, IDENT, IDENT, [100, 100, 100]), null);
});

test("extentSlices sorts a reversed range and clamps to the volume", () => {
  const ext = { start_mm: 120, end_mm: -3, widest_mm: 130, anchor_mm: [50, 50, 50] };
  assert.deepEqual(core.extentSlices(ext, 0, IDENT, IDENT, [100, 100, 100]), { start: 0, end: 99, widest: 99 });
});

test("pointRange clamps at both ends", () => {
  assert.deepEqual(core.pointRange(0, 2, 100), { start: 0, end: 2, widest: 0 });
  assert.deepEqual(core.pointRange(99, 2, 100), { start: 97, end: 99, widest: 99 });
  assert.deepEqual(core.pointRange(50, 2, 100), { start: 48, end: 52, widest: 50 });
});

test("trackGradient marks the range on the slider track", () => {
  const g = core.trackGradient(10, 20, 101, "orange", "grey");
  assert.match(g, /^linear-gradient\(to right,/);
  assert.match(g, /grey 10%, orange 10%/);
  assert.match(g, /orange 20%, grey 20%/);
});

test("mirrorMM negates x only", () => {
  assert.deepEqual(core.mirrorMM([12.5, -3, 4]), [-12.5, -3, 4]);
});

test("counterpart links a case and its mirrored copy both ways", () => {
  const cases = [
    { case_id: "knee", mirror: "knee-left" },
    { case_id: "knee-left", mirror_of: "knee" },
    { case_id: "hip" },
  ];
  assert.equal(core.counterpart(cases, "knee"), "knee-left");
  assert.equal(core.counterpart(cases, "knee-left"), "knee");
  assert.equal(core.counterpart(cases, "hip"), null);
  assert.equal(core.counterpart(cases, "nope"), null);
});

test("counterpart still finds the copy when the source was rebuilt and lost its mirror key", () => {
  const cases = [{ case_id: "knee" }, { case_id: "knee-left", mirror_of: "knee" }];
  assert.equal(core.counterpart(cases, "knee"), "knee-left");
});

test("pickerGroups separates candidates; mirrored copies stay with the cases", () => {
  const cases = [
    { case_id: "knee" }, { case_id: "knee-left", mirror_of: "knee" },
    { case_id: "cand-049", candidate: true }, { case_id: "cand-414", candidate: true },
  ];
  const g = core.pickerGroups(cases);
  assert.deepEqual(g.cases.map((c) => c.case_id), ["knee", "knee-left"]);
  assert.deepEqual(g.candidates.map((c) => c.case_id), ["cand-049", "cand-414"]);
});
