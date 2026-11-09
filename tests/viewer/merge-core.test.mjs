import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const M = require("../../viewer/merge-core.js");
const P = require("../../viewer/paint-core.js");

const A = [[1,0,0,-2],[0,1,0,-1],[0,0,1,-1],[0,0,0,1]];
const here = { caseId: "k", dims: [4, 2, 2], affine: A };
const rows = ["femur","tibia","acl","pcl"].map((id) => ({ id, name: id.toUpperCase(), type: "R" }))
  .concat([{ id: "trochlea", name: "Trochlea", type: "P" }]);
const L = (o) => Object.fromEntries(Object.entries(o).map(([v, id]) => [v, { id, name: id.toUpperCase() }]));

test("paintLut keeps auto only for unchanged, unchecked outlines", () => {
  const saved = Uint8Array.from([1,1,2,2,3,3,0,0]), now = Uint8Array.from([1,1,2,0,3,3,4,0]);
  const lut = { 1: {id:"femur",name:"Femur",auto:{}}, 2: {id:"tibia",name:"Tibia",auto:{}}, 3: {id:"acl",name:"ACL",auto:{}}, 5: {id:"gone",name:"Gone"} };
  assert.deepEqual(M.paintLut(lut, new Map([["pcl", 4]]), (id) => id.toUpperCase(), new Set(["acl"]), now, saved), {
    1: {id:"femur",name:"Femur",auto:true}, 2: {id:"tibia",name:"Tibia"}, 3: {id:"acl",name:"ACL"}, 4: {id:"pcl",name:"PCL"} });
});

test("sameVoxels: true only when the value sits on exactly the same voxels", () => {
  const a = Uint8Array.from([1,1,2,0]);
  assert.equal(M.sameVoxels(a, Uint8Array.from([1,1,3,0]), 1), true);
  assert.equal(M.sameVoxels(a, Uint8Array.from([1,0,2,0]), 1), false);
  assert.equal(M.sameVoxels(a, Uint8Array.from([1,1,2,2]), 2), false);
});

test("labels survive encode -> decode; a wrong length or junk is refused", async () => {
  const bm = Uint8Array.from({ length: 1000 }, (_, i) => i % 7);
  assert.deepEqual(await M.decodeLabels(await M.encodeLabels(bm), 1000), bm);
  await assert.rejects(M.decodeLabels(await M.encodeLabels(bm), 999), /damaged/);
  await assert.rejects(M.decodeLabels("not base64!", 1000), /damaged/);
  await assert.rejects(M.decodeLabels(btoa("not gzip at all"), 1000), /damaged/);
});

test("checkPaintFile refuses another case, another grid, a moved grid", () => {
  const ok = { format: M.PAINT_FORMAT, version: 1, case_id: "k", dims: [4,2,2], affine: A, lut: L({1: "femur"}), checked: [], points: [], labels_gz_b64: "" };
  assert.equal(M.checkPaintFile(ok, here), null);
  const shifted = A.map((r) => r.slice()); shifted[0][3] += 0.5;
  const flipped = A.map((r) => r.slice()); flipped[0][0] = -1;
  const pt = (id) => ({ id, name: id, xyz_mm: [0, 0, 0] });
  for (const [bad, re] of [[{ case_id: "k-left" }, /for k-left, not k/], [{ dims: [2,4,2] }, /grid \(2×4×2\)/],
      [{ affine: shifted }, /placed differently/], [{ affine: flipped }, /placed differently/], [{ version: 2 }, /version 2/],
      [{ lut: { 300: { id: "x", name: "x" } } }, /damaged/], [{ points: "no" }, /damaged/], [{ checked: [1] }, /damaged/],
      [{ lut: { 1: { id: "femur", name: "a" }, 2: { id: "femur", name: "b" } } }, /damaged/],
      [{ points: [pt("trochlea"), pt("trochlea")] }, /damaged/]])
    assert.match(M.checkPaintFile({ ...ok, ...bad }, here), re);
  assert.match(M.checkPaintFile({ hello: 1 }, here), /isn't an atlas paint file/);
  for (const notAFile of [null, [], 5, "paint"])
    assert.equal(M.checkPaintFile(notAFile, here), "This isn't an atlas paint file.");
});

test("mergeItems: new, changed (added/removed), overlap, same; checklist order; maps by id", () => {
  const own = { bitmap: Uint8Array.from([1,1,2,2,0,0,4,0]), lut: L({1:"femur",2:"tibia",4:"pcl"}), points: [] };
  const inc = { bitmap: Uint8Array.from([0,9,9,6,6,0,7,0]), lut: L({9:"acl",6:"tibia",7:"pcl"}), points: [] };
  const r = M.mergeItems(own, inc, rows);
  assert.deepEqual(r.items.map((i) => [i.id, i.status]), [["tibia","changed"], ["acl","new"]]);
  const [tib, acl] = r.items;
  assert.deepEqual([tib.incValue, tib.ownValue, tib.added, tib.removed, tib.overlapCount], [6, 2, 1, 1, 0]);
  assert.deepEqual([acl.ownValue, acl.added, acl.overlapCount], [0, 2, 2]);
  assert.deepEqual(acl.overlap.map((o) => [o.id, o.count]), [["femur",1], ["tibia",1]]);
  assert.equal(r.same, 1); // pcl: the same voxels under another value
  // femur is absent from the file: never offered for removal
});

test("mergeItems offers an id the owner lacks as new, even on empty voxels only", () => {
  const own = { bitmap: Uint8Array.from([1,0,0,0]), lut: L({1:"femur"}), points: [] };
  const inc = { bitmap: Uint8Array.from([0,3,3,0]), lut: L({3:"acl"}), points: [] };
  const r = M.mergeItems(own, inc, rows);
  assert.equal(r.items.length, 1);
  const [acl] = r.items;
  assert.deepEqual([acl.status, acl.ownValue, acl.incCount, acl.added, acl.removed, acl.overlapCount, acl.key],
    ["new", 0, 2, 2, 0, 0, "region:acl"]);
  assert.equal(r.same, 0);
});

test("mergeItems leaves out incoming auto outlines and names them", () => {
  const own = { bitmap: Uint8Array.from([1,1,0,0]), lut: L({1:"femur"}), points: [] };
  const inc = { bitmap: Uint8Array.from([1,0,0,0]), lut: { 1: { id: "femur", name: "FEMUR", auto: true } }, points: [] };
  assert.deepEqual(M.mergeItems(own, inc, rows), { items: [], same: 0, autoLeft: ["FEMUR"], unknown: [] });
});

test("mergeItems offers a check when the voxels match and only theirs is checked", () => {
  const bm = Uint8Array.from([1,1,0,0]);
  const own = { bitmap: bm, lut: { 1: { id: "femur", name: "FEMUR", auto: true } }, points: [] };
  assert.equal(M.mergeItems(own, { bitmap: bm, lut: L({1:"femur"}), points: [] }, rows).items[0].status, "checked");
});

test("mergeItems: unknown ids and points (new / moved / same)", () => {
  const z = Uint8Array.from([0,0,0,0]);
  const own = { bitmap: z, lut: {}, points: [{ id: "trochlea", name: "Trochlea", xyz_mm: [0,0,0] }] };
  const inc = { bitmap: Uint8Array.from([5,0,0,0]), lut: L({5:"mystery"}),
    points: [{ id: "trochlea", name: "Trochlea", xyz_mm: [0,0,3] }, { id: "zzz", name: "Z", xyz_mm: [1,1,1] }] };
  const r = M.mergeItems(own, inc, rows);
  assert.deepEqual(r.items.map((i) => [i.id, i.status, i.movedMM]), [["trochlea","moved",3]]);
  assert.deepEqual(r.unknown.sort(), ["mystery", "zzz"]);
  inc.points = [{ id: "trochlea", name: "Trochlea", xyz_mm: [0,0,0.005] }];
  assert.equal(M.mergeItems(own, inc, rows).items.length, 0); // within 0.01 mm: the same
});

test("regionChanges: owner wins overlaps unless incomingWins; undo restores", () => {
  const own = Uint8Array.from([1,2,0,3,3]), inc = Uint8Array.from([5,5,5,0,0]);
  const a = M.regionChanges(own, inc, 5, 3, false), b = M.regionChanges(own, inc, 5, 3, true);
  assert.deepEqual([[...a.idx], [...a.val]], [[2,3,4], [3,0,0]]);
  assert.deepEqual([[...b.idx], [...b.val]], [[0,1,2,3,4], [3,3,3,0,0]]);
  // apply b to a copy, keep old values, put them back with paint-core's undoChange: equals `own` again
  const bitmap = own.slice(), before = own.slice();
  const old = Uint8Array.from(b.idx, (i) => bitmap[i]);
  b.idx.forEach((i, k) => { bitmap[i] = b.val[k]; before[i] = b.val[k]; });
  assert.deepEqual(bitmap, Uint8Array.from([3,3,3,0,0]));
  P.undoChange({ idx: b.idx, old }, bitmap, before);
  assert.deepEqual(bitmap, own);
  assert.deepEqual(before, own);
});

test("regionChanges refuses an owner value outside 1-255 (a new structure needs a fresh one)", () => {
  const own = Uint8Array.from([1,2,0]), inc = Uint8Array.from([5,5,5]);
  for (const bad of [0, 256, -1, 1.5, undefined]) assert.throws(() => M.regionChanges(own, inc, 5, bad, true), RangeError);
});

test("focusOf picks the fullest slice and its in-plane centre", () => {
  const bm = new Uint8Array(12); // dims [2,2,3]
  bm[0] = 1; bm[8] = 1; bm[9] = 1; bm[11] = 1; // z=0: (0,0); z=2: (0,0) (1,0) (1,1)
  assert.deepEqual(M.focusOf(bm, [2,2,3], 1, 2), { slice: 2, vox: [1,0,2] });
  assert.equal(M.focusOf(bm, [2,2,3], 4, 2), null);
});

test("itemsLeft: skipped items go; an accept with the owner's overlap kept stays settled until undone", () => {
  const own = { bitmap: Uint8Array.from([1,1,0,0]), lut: L({1:"femur"}), points: [] };
  const inc = { bitmap: Uint8Array.from([0,3,3,0]), lut: L({3:"acl"}), points: [{ id: "trochlea", name: "Trochlea", xyz_mm: [1,2,3] }] };
  const taken = new Map();
  let r = M.mergeItems(own, inc, rows);
  assert.deepEqual(M.itemsLeft(r.items, new Set(["point:trochlea"]), taken).map((i) => i.key), ["region:acl"]);
  // accept the acl, femur kept: voxel 1 stays femur, so theirs still differs from yours by that voxel
  const ch = M.regionChanges(own.bitmap, inc.bitmap, 3, 2, false);
  const old = Uint8Array.from(ch.idx, (i) => own.bitmap[i]);
  ch.idx.forEach((i, k) => { own.bitmap[i] = ch.val[k]; });
  own.lut = L({1:"femur",2:"acl"});
  taken.set("region:acl", null);
  r = M.mergeItems(own, inc, rows);
  assert.equal(r.items.find((i) => i.key === "region:acl").status, "changed");
  assert.deepEqual(M.itemsLeft(r.items, new Set(), taken).map((i) => i.key), ["point:trochlea"]);
  assert.deepEqual(M.itemsLeft(r.items, new Set(), taken).map((i) => i.key), ["point:trochlea"]); // and on every later list
  // undo: the acl is offered again
  ch.idx.forEach((i, k) => { own.bitmap[i] = old[k]; });
  own.lut = L({1:"femur"});
  r = M.mergeItems(own, inc, rows);
  assert.deepEqual(M.itemsLeft(r.items, new Set(), taken).map((i) => i.key), ["region:acl", "point:trochlea"]);
  // an accept that makes it match yours ("" once listed) comes back if it is offered again
  taken.set("point:trochlea", null);
  own.points = inc.points;
  assert.deepEqual(M.itemsLeft(M.mergeItems(own, inc, rows).items, new Set(), taken).map((i) => i.key), ["region:acl"]);
  assert.equal(taken.get("point:trochlea"), "");
  own.points = [];
  assert.deepEqual(M.itemsLeft(M.mergeItems(own, inc, rows).items, new Set(), taken).map((i) => i.key), ["region:acl", "point:trochlea"]);
});

test("nextShown keeps the item shown, else takes the next in list order, wrapping", () => {
  const k = (...keys) => keys.map((key) => ({ key }));
  assert.equal(M.nextShown(k("a","b","c"), k("a","b","c"), "b"), "b");
  assert.equal(M.nextShown(k("a","b","c"), k("a","c"), "b"), "c");
  assert.equal(M.nextShown(k("a","b","c"), k("a","b"), "c"), "a");
  assert.equal(M.nextShown(k("a","b","c"), k("c","x"), "a"), "c");
  assert.equal(M.nextShown(k(), k("x"), null), "x");
  assert.equal(M.nextShown(k("a"), k(), "a"), null);
});
