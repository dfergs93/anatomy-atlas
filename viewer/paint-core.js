// Pure painting helpers (no NiiVue, no DOM): the guard, undo, colours and the growing tools.
// Loaded by index.html, tested with `node --test`.
// Layout: dims = [nx, ny, nz]; flat index = x + y*nx + z*nx*ny; axis = the axis held constant in a slice.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.atlasPaint = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Port of tools/build_case.py colour(); tests/fixtures/colours.json checks both.
  const PALETTE = [
    ["cartilage", [70, 140, 230]], ["meniscus", [150, 90, 210]], ["tendon", [240, 200, 40]],
    ["ligament", [235, 120, 40]], ["acl", [235, 120, 40]], ["pcl", [235, 120, 40]],
    ["mcl", [235, 120, 40]], ["lcl", [235, 120, 40]], ["mpfl", [235, 120, 40]],
    ["artery", [220, 30, 30]], ["vein", [60, 90, 220]], ["nerve", [120, 210, 60]],
    ["fat_pad", [250, 235, 140]], ["bursa", [60, 200, 220]], ["recess", [60, 200, 220]],
    ["femur", [233, 214, 170]], ["tibia", [233, 214, 170]], ["fibula", [233, 214, 170]],
    ["patella", [233, 214, 170]],
  ];
  const MUSCLE = [205, 70, 80];
  const MENISCUS_PARTS = [
    ["meniscus_anterior_horn", [165, 95, 230]], ["meniscus_body", [235, 95, 160]],
    ["meniscus_posterior_horn", [100, 60, 180]],
  ];

  function colour(id, value) {
    const part = MENISCUS_PARTS.find(([k]) => id.endsWith(k));
    if (part) return part[1].slice();
    const hit = PALETTE.find(([k]) => id.includes(k));
    const rgb = hit ? hit[1] : MUSCLE;
    const f = 0.82 + 0.36 * ((value * 0.618) % 1);
    return rgb.map((c) => Math.trunc(Math.min(255, c * f)));
  }

  // The LUT value for an id; else its value in `assigned`; else max(all) + 1.
  function valueFor(id, lut, assigned) {
    if (Object.prototype.hasOwnProperty.call(lut, id)) return lut[id];
    if (assigned.has(id)) return assigned.get(id);
    let max = 0;
    for (const v of Object.values(lut)) if (v > max) max = v;
    for (const v of assigned.values()) if (v > max) max = v;
    if (max + 1 > 255) throw new RangeError("no free label values left (255 is the maximum)");
    return max + 1;
  }

  // `assigned` after a save, given lut.json's id -> value before (oldIds) and after (newIds) it. A saved id
  // leaves `assigned` (lut.json holds its value now). An id the save dropped (every voxel erased) goes into
  // `assigned` with its old value, unless lut.json gave that value to another id: an undo back past the
  // save then restores its voxels under its own id, and a new structure never takes the value.
  function carryDropped(oldIds, newIds, assigned) {
    const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
    for (const id of [...assigned.keys()]) if (has(newIds, id)) assigned.delete(id);
    const taken = new Set([...Object.values(newIds), ...assigned.values()]);
    for (const [id, v] of Object.entries(oldIds)) {
      if (has(newIds, id) || assigned.has(id) || taken.has(v)) continue;
      assigned.set(id, v);
      taken.add(v);
    }
    return assigned;
  }

  // A voxel may change o -> n only if (n === cur && (o === 0 || overwrite)) or (n === 0 && (o === cur || overwrite)).
  // Everything else is put back into `after`. Allowed changes are copied into `before` (the mirror of the
  // accepted state) and returned with their old values for undo.
  function guardChanges(before, after, cur, overwrite) {
    const len = after.length;
    let cap = 4096;
    let idx = new Uint32Array(cap);
    let old = new Uint8Array(cap);
    let count = 0;
    let restored = 0;
    for (let i = 0; i < len; i++) {
      const n = after[i];
      const o = before[i];
      if (n === o) continue;
      if ((n === cur && (o === 0 || overwrite)) || (n === 0 && (o === cur || overwrite))) {
        if (count === cap) {
          cap *= 2;
          const ni = new Uint32Array(cap); ni.set(idx); idx = ni;
          const no = new Uint8Array(cap); no.set(old); old = no;
        }
        idx[count] = i;
        old[count] = o;
        count++;
        before[i] = n;
      } else {
        after[i] = o;
        restored++;
      }
    }
    return { idx: idx.slice(0, count), old: old.slice(0, count), restored };
  }

  function undoChange(change, bitmap, before) {
    const { idx, old } = change;
    for (let k = 0; k < idx.length; k++) {
      bitmap[idx[k]] = old[k];
      before[idx[k]] = old[k];
    }
  }

  function inPlane(axis) {
    return [0, 1, 2].filter((a) => a !== axis);
  }

  // Median of the 3x3 in-plane neighbourhood (clipped at the edge) +- tolerance * (range[1] - range[0]).
  function seedWindow(img, dims, seed, axis, tolerance, range) {
    const [a, b] = inPlane(axis);
    const stride = [1, dims[0], dims[0] * dims[1]];
    const vals = [];
    for (let da = -1; da <= 1; da++) {
      const pa = seed[a] + da;
      if (pa < 0 || pa >= dims[a]) continue;
      for (let db = -1; db <= 1; db++) {
        const pb = seed[b] + db;
        if (pb < 0 || pb >= dims[b]) continue;
        vals.push(img[seed[axis] * stride[axis] + pa * stride[a] + pb * stride[b]]);
      }
    }
    vals.sort((x, y) => x - y);
    const m = vals.length >> 1;
    const med = vals.length % 2 ? vals[m] : (vals[m - 1] + vals[m]) / 2;
    const t = tolerance * (range[1] - range[0]);
    return [med - t, med + t];
  }

  function pushTo(state, v) {
    if (state.n === state.a.length) {
      const bigger = new Uint32Array(state.a.length * 2);
      bigger.set(state.a);
      state.a = bigger;
    }
    state.a[state.n++] = v;
  }

  // Breadth-first fill from the seed through lo <= value <= hi; 4-connected in the seed's plane when is2D,
  // else 6-connected; within maxDistMM (Euclidean, voxMM) of the seed.
  function wandMask(img, dims, seed, opts) {
    const { lo, hi, is2D, axis, maxDistMM, voxMM } = opts;
    const [nx, ny, nz] = dims;
    const nxy = nx * ny;
    const visited = new Uint8Array(nx * ny * nz);
    const s = seed[0] + seed[1] * nx + seed[2] * nxy;
    const out = { a: new Uint32Array(1024), n: 0 };
    const max2 = maxDistMM * maxDistMM;
    const sx = voxMM[0] * voxMM[0], sy = voxMM[1] * voxMM[1], sz = voxMM[2] * voxMM[2];
    const v0 = img[s];
    if (!(v0 >= lo && v0 <= hi)) return new Uint32Array(0);
    visited[s] = 1;
    pushTo(out, s);
    // directions: [dx, dy, dz]
    const dirs = [];
    for (const [dx, dy, dz] of [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]) {
      if (is2D && [dx, dy, dz][axis] !== 0) continue;
      dirs.push([dx, dy, dz]);
    }
    for (let head = 0; head < out.n; head++) {
      const i = out.a[head];
      const x = i % nx;
      const y = ((i / nx) | 0) % ny;
      const z = (i / nxy) | 0;
      for (let d = 0; d < dirs.length; d++) {
        const px = x + dirs[d][0], py = y + dirs[d][1], pz = z + dirs[d][2];
        if (px < 0 || px >= nx || py < 0 || py >= ny || pz < 0 || pz >= nz) continue;
        const j = px + py * nx + pz * nxy;
        if (visited[j]) continue;
        const v = img[j];
        if (!(v >= lo && v <= hi)) continue;
        const ex = px - seed[0], ey = py - seed[1], ez = pz - seed[2];
        if (ex * ex * sx + ey * ey * sy + ez * ez * sz > max2) continue;
        visited[j] = 1;
        pushTo(out, j);
      }
    }
    return out.a.slice(0, out.n);
  }

  // Spread from all voxels equal to `cur` into empty (0) voxels, 6-connected, at most `steps` layers,
  // accepting intensities within [p5 - t*span, p95 + t*span] of the structure's own voxels.
  function growMask(img, dims, bitmap, cur, opts) {
    const { tolerance, range, steps } = opts;
    const [nx, ny, nz] = dims;
    const nxy = nx * ny;
    const len = bitmap.length;
    let count = 0;
    for (let i = 0; i < len; i++) if (bitmap[i] === cur) count++;
    if (count === 0) return new Uint32Array(0);
    const own = new Float32Array(count);
    let frontier = new Uint32Array(count);
    for (let i = 0, k = 0; i < len; i++) {
      if (bitmap[i] === cur) { own[k] = img[i]; frontier[k++] = i; }
    }
    own.sort();
    const p5 = own[Math.floor(0.05 * (count - 1))];
    const p95 = own[Math.ceil(0.95 * (count - 1))];
    const t = tolerance * (range[1] - range[0]);
    const lo = p5 - t, hi = p95 + t;
    const taken = new Uint8Array(len);
    const out = { a: new Uint32Array(1024), n: 0 };
    const tryAdd = (j, next) => {
      if (taken[j] || bitmap[j] !== 0) return;
      const v = img[j];
      if (!(v >= lo && v <= hi)) return;
      taken[j] = 1;
      pushTo(out, j);
      pushTo(next, j);
    };
    let fn = frontier.length;
    for (let layer = 0; layer < steps && fn > 0; layer++) {
      const next = { a: new Uint32Array(1024), n: 0 };
      for (let f = 0; f < fn; f++) {
        const i = frontier[f];
        const x = i % nx;
        const y = ((i / nx) | 0) % ny;
        const z = (i / nxy) | 0;
        if (x > 0) tryAdd(i - 1, next);
        if (x < nx - 1) tryAdd(i + 1, next);
        if (y > 0) tryAdd(i - nx, next);
        if (y < ny - 1) tryAdd(i + nx, next);
        if (z > 0) tryAdd(i - nxy, next);
        if (z < nz - 1) tryAdd(i + nxy, next);
      }
      frontier = next.a;
      fn = next.n;
    }
    return out.a.slice(0, out.n);
  }

  // Sorted distinct coordinates along `axis` of the voxels equal to `value`.
  function keySlices(bitmap, dims, value, axis) {
    const [nx, ny] = dims;
    const nxy = nx * ny;
    const seen = new Uint8Array(dims[axis]);
    for (let i = 0; i < bitmap.length; i++) {
      if (bitmap[i] !== value) continue;
      const c = axis === 0 ? i % nx : axis === 1 ? ((i / nx) | 0) % ny : (i / nxy) | 0;
      seen[c] = 1;
    }
    const res = [];
    for (let c = 0; c < seen.length; c++) if (seen[c]) res.push(c);
    return res;
  }

  return { colour, valueFor, carryDropped, guardChanges, undoChange, seedWindow, wandMask, growMask, keySlices };
});
