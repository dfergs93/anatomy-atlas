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

const ident = (mm) => Math.round(mm);

test("sliceRange is null without an extent (old lut.json)", () => {
  assert.equal(core.sliceRange(undefined, ident, 100), null);
  assert.equal(core.sliceRange(null, ident, 100), null);
});

test("sliceRange converts mm to slices and sorts a reversed range", () => {
  assert.deepEqual(core.sliceRange({ start_mm: 10, end_mm: 20, widest_mm: 14 }, ident, 100), { start: 10, end: 20, widest: 14 });
  assert.deepEqual(core.sliceRange({ start_mm: 20, end_mm: 10, widest_mm: 14 }, ident, 100), { start: 10, end: 20, widest: 14 });
});

test("sliceRange clamps to the volume", () => {
  assert.deepEqual(core.sliceRange({ start_mm: -3, end_mm: 120, widest_mm: 130 }, ident, 100), { start: 0, end: 99, widest: 99 });
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
