// Pure helper-merge logic (no NiiVue, no DOM): paint-file checks, the file's structure list, one-pass
// comparison of two label maps, per-structure voxel changes, where to put the cursor.
// Loaded by index.html, tested with `node --test`. Runs in node and in browsers (gzip via Compression Streams).
// Layout: dims = [nx, ny, nz]; flat index = x + y*nx + z*nx*ny (uint8 bitmaps, 0 = empty).
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.atlasMerge = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const PAINT_FORMAT = "anatomy-atlas paint";
  const POINT_SAME_MM = 0.01;
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

  // True when `value` sits on exactly the same voxels in a and b.
  function sameVoxels(a, b, value) {
    for (let i = 0; i < a.length; i++) if ((a[i] === value) !== (b[i] === value)) return false;
    return true;
  }

  // The lut written into a paint file: only values present in `bitmap`. Id and name come from `savedLut[v]`, else
  // from the id `assigned` maps to v. "auto" survives only for an unchanged, unchecked outline. One pass over
  // both bitmaps: a value changed when some voxel holds it in exactly one of them.
  function paintLut(savedLut, assigned, nameOf, checked, bitmap, savedBitmap) {
    const present = new Uint8Array(256), changed = new Uint8Array(256);
    for (let i = 0; i < bitmap.length; i++) {
      const n = bitmap[i], o = savedBitmap[i];
      present[n] = 1;
      if (n !== o) { changed[n] = 1; changed[o] = 1; }
    }
    const idOfAssigned = new Map();
    for (const [id, v] of assigned) idOfAssigned.set(v, id);
    const lut = {};
    for (let v = 1; v < 256; v++) {
      if (!present[v]) continue;
      const saved = has(savedLut, v) ? savedLut[v] : null;
      let id, name;
      if (saved) { id = saved.id; name = saved.name; }
      else if (idOfAssigned.has(v)) { id = idOfAssigned.get(v); name = nameOf(id); }
      else continue;
      const entry = { id, name };
      if (saved && saved.auto && !checked.has(id) && !changed[v]) entry.auto = true;
      lut[v] = entry;
    }
    return lut;
  }

  const damagedLabels = () => new Error("This paint file's label map is damaged.");

  async function pipeBytes(bytes, stream) {
    const out = new Blob([bytes]).stream().pipeThrough(stream);
    return new Uint8Array(await new Response(out).arrayBuffer());
  }

  // gzip, then base64. Built in chunks (a multiple of 3 bytes, so each piece is valid base64 on its own):
  // String.fromCharCode(...bytes) overflows the stack on a real ~24 MB bitmap.
  async function encodeLabels(bitmap) {
    const zipped = await pipeBytes(bitmap, new CompressionStream("gzip"));
    const CHUNK = 3 * 8192;
    const parts = [];
    for (let i = 0; i < zipped.length; i += CHUNK)
      parts.push(btoa(String.fromCharCode.apply(null, zipped.subarray(i, i + CHUNK))));
    return parts.join("");
  }

  // The bitmap in a paint file; rejects unless it decodes to exactly n bytes.
  async function decodeLabels(b64, n) {
    let out;
    try {
      const bin = atob(b64);
      const zipped = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) zipped[i] = bin.charCodeAt(i);
      out = await pipeBytes(zipped, new DecompressionStream("gzip"));
    } catch (e) {
      throw damagedLabels();
    }
    if (out.length !== n) throw damagedLabels();
    return out;
  }

  const isNum = (x) => typeof x === "number" && Number.isFinite(x);

  // First problem with a paint file as a message for the owner, or null if it can be merged into `here`.
  function checkPaintFile(obj, here) {
    if (obj === null || typeof obj !== "object" || Array.isArray(obj) || obj.format !== PAINT_FORMAT)
      return "This isn't an atlas paint file.";
    if (obj.version !== 1) return `This paint file is version ${obj.version}; this atlas reads version 1.`;
    if (obj.case_id !== here.caseId)
      return `This paint file is for ${obj.case_id}, not ${here.caseId}. Open ${obj.case_id} in painting mode to merge it.`;
    const damaged = "This paint file's structure list is damaged.";
    const { dims, affine } = obj;
    if (!Array.isArray(dims) || dims.length !== 3 || !dims.every(isNum)) return damaged;
    if (dims.some((d, k) => d !== here.dims[k]))
      return `This paint file's grid (${dims.join("×")}) doesn't match this case's (${here.dims.join("×")}), so its paint would land in the wrong voxels.`;
    if (!Array.isArray(affine) || affine.length !== 4 || !affine.every((r) => Array.isArray(r) && r.length === 4 && r.every(isNum)))
      return damaged;
    if (affine.some((r, i) => r.some((x, j) => Math.abs(x - here.affine[i][j]) > 1e-3)))
      return "This paint file's grid is placed differently from this case's (rebuilt or mirrored?), so its paint would land in the wrong voxels.";
    if (obj.lut === null || typeof obj.lut !== "object" || Array.isArray(obj.lut)) return damaged;
    const lutIds = new Set();
    for (const [k, e] of Object.entries(obj.lut)) {
      const v = Number(k);
      if (!(Number.isInteger(v) && v >= 1 && v <= 255 && String(v) === k)) return damaged;
      if (e === null || typeof e !== "object" || typeof e.id !== "string" || lutIds.has(e.id)) return damaged;
      lutIds.add(e.id);
    }
    if (!Array.isArray(obj.points)) return damaged;
    const pointIds = new Set();
    for (const p of obj.points) {
      if (p === null || typeof p !== "object" || typeof p.id !== "string" || typeof p.name !== "string" ||
          !Array.isArray(p.xyz_mm) || p.xyz_mm.length !== 3 || !p.xyz_mm.every(isNum) || pointIds.has(p.id)) return damaged;
      pointIds.add(p.id);
    }
    if (!Array.isArray(obj.checked) || !obj.checked.every((c) => typeof c === "string")) return damaged;
    if (typeof obj.labels_gz_b64 !== "string") return damaged;
    return null;
  }

  // What the incoming paint file offers, structure by structure, against the owner's current state.
  // `own` / `inc`: {bitmap, lut: {value: {id, name, auto?}}, points}. `rows`: checklist rows {id, name, type}.
  // Two bitmaps, one pass: per-value counters, plus a 256x256 table of (incoming, owner) overlaps.
  function mergeItems(own, inc, rows) {
    const idsToValue = (lut) => {
      const m = new Map();
      for (const [v, e] of Object.entries(lut)) m.set(e.id, Number(v));
      return m;
    };
    const ownById = idsToValue(own.lut), incById = idsToValue(inc.lut);
    const toOwn = new Uint8Array(256); // incoming value -> the owner's value for the same id (0 = none)
    for (const [id, v] of incById) toOwn[v] = ownById.get(id) || 0;

    const incCount = new Uint32Array(256), ownCount = new Uint32Array(256), same = new Uint32Array(256);
    const pairs = new Uint32Array(65536); // incValue * 256 + ownValue
    const a = inc.bitmap, b = own.bitmap;
    for (let i = 0; i < a.length; i++) {
      const x = a[i], y = b[i];
      if (x === 0 && y === 0) continue;
      ownCount[y]++;
      if (x === 0) continue;
      incCount[x]++;
      const m = toOwn[x];
      if (y !== 0 && y === m) same[x]++; // "same" needs a value the owner has (m > 0)
      else if (y !== 0) pairs[x * 256 + y]++;
    }

    const rowIndex = new Map(rows.map((r, k) => [r.id, k]));
    const order = (id) => (rowIndex.has(id) ? rowIndex.get(id) : Infinity);
    const known = new Set(rows.map((r) => r.id));
    for (const e of Object.values(own.lut)) known.add(e.id);
    const ownPointIds = new Map(own.points.map((p) => [p.id, p]));
    const knownPoint = (id) => rowIndex.has(id) || ownPointIds.has(id);

    const items = [], autoLeft = [], unknown = [];
    let sameTotal = 0;

    for (const [id, v] of incById) {
      if (incCount[v] === 0) continue; // listed but not painted
      const e = inc.lut[v];
      const m = toOwn[v];
      const added = incCount[v] - same[v];
      const removed = (m ? ownCount[m] : 0) - same[v];
      if (e.auto) {
        if (added || removed) autoLeft.push(e.name);
        continue;
      }
      if (!known.has(id)) { if (!unknown.includes(id)) unknown.push(id); continue; }
      const identical = m > 0 && added === 0 && removed === 0;
      if (identical && !own.lut[m].auto) { sameTotal++; continue; }
      const overlap = [];
      for (let o = 1; o < 256; o++) {
        const count = pairs[v * 256 + o];
        if (count && o !== m) overlap.push({ id: own.lut[o] ? own.lut[o].id : `#${o}`, name: own.lut[o] ? own.lut[o].name : `#${o}`, count });
      }
      overlap.sort((p, q) => q.count - p.count || order(p.id) - order(q.id));
      items.push({
        key: `region:${id}`, kind: "region", status: identical ? "checked" : m ? "changed" : "new", id, name: e.name || id,
        incValue: v, ownValue: m, incCount: incCount[v], ownCount: m ? ownCount[m] : 0, added, removed,
        overlap, overlapCount: overlap.reduce((s, o) => s + o.count, 0),
      });
    }

    for (const p of inc.points) {
      if (!knownPoint(p.id)) { if (!unknown.includes(p.id)) unknown.push(p.id); continue; }
      const mine = ownPointIds.get(p.id);
      let status = "new", movedMM = 0;
      if (mine) {
        const d = Math.hypot(...p.xyz_mm.map((c, k) => c - mine.xyz_mm[k]));
        if (p.xyz_mm.some((c, k) => Math.abs(c - mine.xyz_mm[k]) > POINT_SAME_MM)) { status = "moved"; movedMM = Math.round(d * 10) / 10; }
        else { sameTotal++; continue; }
      }
      items.push({ key: `point:${p.id}`, kind: "point", status, id: p.id, name: p.name, xyz_mm: p.xyz_mm, movedMM });
    }

    items.sort((p, q) => order(p.id) - order(q.id)); // stable: unlisted ids keep their file order, last
    return { items, same: sameTotal, autoLeft, unknown };
  }

  // The voxels to change to take one incoming structure into the owner's map: where theirs is painted, the
  // owner's voxel becomes ownValue (if empty, or if incomingWins); where it isn't, an ownValue voxel is cleared.
  // The caller passes the value the structure will be painted with (a fresh one for a new structure, never
  // mergeItems' ownValue 0): anything but an integer 1-255 throws, so a mistake changes nothing.
  function regionChanges(own, inc, incValue, ownValue, incomingWins) {
    if (!Number.isInteger(ownValue) || ownValue < 1 || ownValue > 255)
      throw new RangeError(`regionChanges needs an owner value from 1 to 255, got ${ownValue}`);
    let cap = 4096, count = 0;
    let idx = new Uint32Array(cap), val = new Uint8Array(cap);
    for (let i = 0; i < own.length; i++) {
      const o = own[i];
      let n = o;
      if (inc[i] === incValue) { if (o === 0 || incomingWins) n = ownValue; }
      else if (o === ownValue) n = 0;
      if (n === o) continue;
      if (count === cap) {
        cap *= 2;
        const ni = new Uint32Array(cap); ni.set(idx); idx = ni;
        const nv = new Uint8Array(cap); nv.set(val); val = nv;
      }
      idx[count] = i;
      val[count] = n;
      count++;
    }
    return { idx: idx.slice(0, count), val: val.slice(0, count) };
  }

  // The slice along `axis` holding most voxels of `value` (lowest on a tie), with that slice's centroid
  // rounded to a voxel; null when the value is absent.
  function focusOf(bitmap, dims, value, axis) {
    const [nx, ny] = dims, nxy = nx * ny;
    const [p, q] = [0, 1, 2].filter((k) => k !== axis);
    const count = new Float64Array(dims[axis]), sp = new Float64Array(dims[axis]), sq = new Float64Array(dims[axis]);
    for (let i = 0; i < bitmap.length; i++) {
      if (bitmap[i] !== value) continue;
      const c = [i % nx, ((i / nx) | 0) % ny, (i / nxy) | 0];
      const s = c[axis];
      count[s]++; sp[s] += c[p]; sq[s] += c[q];
    }
    let best = -1;
    for (let s = 0; s < count.length; s++) if (count[s] > 0 && (best < 0 || count[s] > count[best])) best = s;
    if (best < 0) return null;
    const vox = [0, 0, 0];
    vox[axis] = best;
    vox[p] = Math.round(sp[best] / count[best]);
    vox[q] = Math.round(sq[best] / count[best]);
    return { slice: best, vox };
  }

  return { PAINT_FORMAT, paintLut, sameVoxels, encodeLabels, decodeLabels, checkPaintFile, mergeItems, regionChanges, focusOf };
});
