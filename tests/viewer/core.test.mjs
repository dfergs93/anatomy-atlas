import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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

test("autoNote names the source", () => {
  assert.equal(core.autoNote({ id: "lateral_meniscus_body", auto: { source: "DOSMA iwoai-2019-t6-normalized", date: "2026-11-07" } }),
    "Outline drawn automatically (DOSMA iwoai-2019-t6-normalized) — not yet checked");
});

test("autoNote is null without auto", () => {
  assert.equal(core.autoNote({ id: "femur" }), null);
  assert.equal(core.autoNote(undefined), null);
});

test("parseChecklist matches the Python reader", () => {
  const md = readFileSync(new URL("../../checklists/knee.md", import.meta.url), "utf8");
  const rows = core.parseChecklist(md);
  assert.equal(rows.length, 86);
  assert.equal(rows[0].id, "femur");
  assert.equal(rows[rows.length - 1].id, "pes_anserine_bursa");
  assert.deepEqual(rows.find((r) => r.id === "fibula"), {
    id: "fibula", name: "Fibula", type: "R", labelled: false, group: "Bones and landmarks",
  });
});

test("nextStructure skips done and wraps", () => {
  const rows = [{ id: "a" }, { id: "b" }, { id: "c" }];
  assert.equal(core.nextStructure(rows, new Set(["a"])), rows[1]);
  assert.equal(core.nextStructure(rows, new Set(["c"]), "b"), rows[0]);
  assert.equal(core.nextStructure(rows, new Set(["b"]), "a"), rows[2]);
  assert.equal(core.nextStructure(rows, new Set(["a", "b", "c"])), null);
});

// 7×7 slice with a 5×5 square of value 3 at i, j = 1…5 (row-major: slice[i + j * w]).
function squareSlice(value = 3) {
  const w = 7, h = 7, s = new Uint16Array(w * h);
  for (let j = 1; j <= 5; j++) for (let i = 1; i <= 5; i++) s[i + j * w] = value;
  return { s, w, h };
}
const pairs = (flat) => Array.from({ length: flat.length / 2 }, (_, k) => [flat[2 * k], flat[2 * k + 1]]);

test("boundaryDots outlines a square, skips its inside", () => {
  const { s, w, h } = squareSlice();
  const dots = core.boundaryDots(s, w, h, new Set([3]), 1);
  assert.ok(dots instanceof Int32Array);
  const want = [];
  for (let j = 1; j <= 5; j++) for (let i = 1; i <= 5; i++) if (i === 1 || i === 5 || j === 1 || j === 5) want.push([i, j]);
  assert.deepEqual(pairs(dots), want); // the 16 edge voxels, raster order; none inside, none outside
  assert.equal(core.boundaryDots(s, w, h, new Set([4]), 1).length, 0); // a value not asked for
  // a structure touching the slice's edge is outlined there too
  const e = new Uint16Array(9).fill(2);
  assert.deepEqual(pairs(core.boundaryDots(e, 3, 3, new Set([2]), 1)),
    [[0, 0], [1, 0], [2, 0], [0, 1], [2, 1], [0, 2], [1, 2], [2, 2]]);
});

test("boundaryDots every 2", () => {
  const { s, w, h } = squareSlice();
  const dots = pairs(core.boundaryDots(s, w, h, new Set([3]))); // every = 2 by default
  // every other voxel round the ring, on all four sides (not every other in raster count, which
  // would keep one side of a shape and drop the other)
  assert.deepEqual(dots, [[1, 1], [3, 1], [5, 1], [1, 3], [5, 3], [1, 5], [3, 5], [5, 5]]);
  assert.deepEqual(pairs(core.boundaryDots(s, w, h, new Set([3]), 2)), dots);
  // a disk: both the left and the right side keep dots, never two touching
  const W = 21, d = new Uint8Array(W * W);
  for (let j = 0; j < W; j++) for (let i = 0; i < W; i++) if ((i - 10) ** 2 + (j - 10) ** 2 <= 64) d[i + j * W] = 1;
  const kept = pairs(core.boundaryDots(d, W, W, new Set([1])));
  assert.ok(kept.some(([i]) => i < 5) && kept.some(([i]) => i > 15));
  for (const [a, b] of kept) for (const [c, e] of kept) {
    if (a !== c || b !== e) assert.ok(Math.max(Math.abs(a - c), Math.abs(b - e)) >= 2, `${a},${b} touches ${c},${e}`);
  }
});

test("expectedNote", () => {
  assert.equal(core.expectedNote({ id: "pes_anserine_bursa", expected: true }),
    "Visible only when distended — outlined where it usually lies");
  assert.equal(core.expectedNote({ id: "femur" }), null);
  assert.equal(core.expectedNote(undefined), null);
});

test("rasSlice reads one plane of a volume through NiiVue's img2RAS steps", () => {
  // dims 2×3×4 stored x-fastest (identity): value = x + 10y + 100z
  const dims = [2, 3, 4], img = new Uint16Array(24);
  for (let z = 0; z < 4; z++) for (let y = 0; y < 3; y++) for (let x = 0; x < 2; x++) img[x + y * 2 + z * 6] = x + 10 * y + 100 * z;
  const id = core.rasSlice(img, dims, [1, 2, 6], [0, 0, 0], 1, 2); // coronal slice y = 2: (x, z)
  assert.deepEqual([id.w, id.h], [2, 4]);
  assert.deepEqual(Array.from(id.data), [20, 21, 120, 121, 220, 221, 320, 321]);
  assert.ok(id.data instanceof Uint16Array);
  const sag = core.rasSlice(img, dims, [1, 2, 6], [0, 0, 0], 0, 1); // x = 1: (y, z)
  assert.deepEqual([sag.w, sag.h], [3, 4]);
  assert.deepEqual(Array.from(sag.data).slice(0, 4), [1, 11, 21, 101]);
  // x stored flipped (RAS x = 1 - stored x): step −1, start 1
  const flip = new Uint16Array(24);
  for (let i = 0; i < 24; i++) flip[i] = img[(1 - (i % 2)) + Math.floor(i / 2) * 2];
  assert.deepEqual(Array.from(core.rasSlice(flip, dims, [-1, 2, 6], [1, 0, 0], 2, 0).data), [0, 1, 10, 11, 20, 21]);
});
