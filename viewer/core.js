// Pure viewer helpers (no NiiVue, no DOM) — loaded by index.html, tested with `node --test`.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.atlasCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const PLANES = ["sagittal", "coronal", "axial"];
  const PLANE_AXIS = { sagittal: 0, coronal: 1, axial: 2 };
  const HERO_FRACTION = 0.7;
  const SIDE_FRACTION = 0.3; // 1 - HERO_FRACTION, written out to avoid 0.30000000000000004

  function otherPlanes(main) {
    return PLANES.filter((p) => p !== main);
  }

  // NiiVue custom layout: main plane large on the left, the other two stacked on the right.
  function layoutFor(main, sliceTypes) {
    const [a, b] = otherPlanes(main);
    return [
      { sliceType: sliceTypes[main], position: [0, 0, HERO_FRACTION, 1] },
      { sliceType: sliceTypes[a], position: [HERO_FRACTION, 0, SIDE_FRACTION, 0.5] },
      { sliceType: sliceTypes[b], position: [HERO_FRACTION, 0.5, SIDE_FRACTION, 0.5] },
    ];
  }

  // Where the main plane's slice cuts a small view: a line across that view.
  // Screen axes: sagittal = (y, z), coronal = (x, z), axial = (x, y).
  function refLineOrientation(main, small) {
    const screenX = { sagittal: 1, coronal: 0, axial: 0 }[small];
    return PLANE_AXIS[main] === screenX ? "vertical" : "horizontal";
  }

  // A tile rectangle [left, top, width, height] with positive width and height (NiiVue flips some).
  function tileRect(ltwh) {
    let [l, t, w, h] = ltwh;
    if (w < 0) { l += w; w = -w; }
    if (h < 0) { t += h; h = -h; }
    return [l, t, w, h];
  }

  // Index of the tile (nv.screenSlices) containing canvas point x, y; -1 when none.
  function tileAt(tiles, x, y) {
    for (let i = 0; i < tiles.length; i++) {
      const [l, t, w, h] = tileRect(tiles[i].leftTopWidthHeight);
      if (x > l && y > t && x < l + w && y < t + h) return i;
    }
    return -1;
  }

  const clamp = (v, n) => Math.max(0, Math.min(n - 1, v));

  // ---- world (scanner mm) ↔ volume, using the volume's own affine ----
  // NiiVue shows oblique volumes (OAI DESS is ~4°) in voxel space, and its frac2mm / mm2frac follow
  // a straightened matrix, not the NIfTI affine — up to ~1 cm out. Stored positions (lut.json,
  // points.json, mirroring) are true world mm, so convert with the volume's matRAS (row-major 4×4).
  function applyAffine(m, v) {
    return [0, 1, 2].map((r) => m[r * 4] * v[0] + m[r * 4 + 1] * v[1] + m[r * 4 + 2] * v[2] + m[r * 4 + 3]);
  }

  function invertAffine(m) {
    const [a, b, c, d, e, f, g, h, i] = [m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]];
    const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
    const det = a * A + b * B + c * C;
    const inv3 = [A, -(b * i - c * h), b * f - c * e, B, a * i - c * g, -(a * f - c * d), C, -(a * h - b * g), a * e - b * d]
      .map((x) => x / det);
    const t = [m[3], m[7], m[11]];
    const out = [];
    for (let r = 0; r < 3; r++) {
      const row = inv3.slice(r * 3, r * 3 + 3);
      out.push(...row, -(row[0] * t[0] + row[1] * t[1] + row[2] * t[2]));
    }
    return [...out, 0, 0, 0, 1];
  }

  function worldToVox(m, mm) {
    return applyAffine(invertAffine(m), mm);
  }

  // NiiVue frac = (voxel + 0.5) / dim on each axis.
  function worldToFrac(m, dims, mm) {
    return worldToVox(m, mm).map((v, a) => (v + 0.5) / dims[a]);
  }

  function fracToWorld(m, dims, frac) {
    return applyAffine(m, frac.map((f, a) => f * dims[a] - 0.5));
  }

  // A structure's extent on one plane (lut.json, world mm on the label grid) → slice numbers on the
  // reference grid. start/end/widest_mm are world coordinates along the axis of voxel
  // (slice, anchor's other indices), so solve for that slice exactly on the label grid, then carry
  // the voxel through world space onto the reference grid. Independent of where the cursor is.
  function extentSlices(planeExt, axis, labelM, refM, refDims) {
    const keys = ["start_mm", "end_mm", "widest_mm"];
    if (!planeExt || !keys.every((k) => Number.isFinite(planeExt[k])) ||
        !Array.isArray(planeExt.anchor_mm) || !planeExt.anchor_mm.every(Number.isFinite)) return null;
    const anchor = worldToVox(labelM, planeExt.anchor_mm).map(Math.round);
    const refInv = invertAffine(refM);
    const n = refDims[axis];
    const [s, e, w] = keys.map((k) => {
      let rest = labelM[axis * 4 + 3];
      for (let b = 0; b < 3; b++) if (b !== axis) rest += labelM[axis * 4 + b] * anchor[b];
      const vox = [...anchor];
      vox[axis] = (planeExt[k] - rest) / labelM[axis * 4 + axis];
      return clamp(Math.round(applyAffine(refInv, applyAffine(labelM, vox))[axis]), n);
    });
    return { start: Math.min(s, e), end: Math.max(s, e), widest: w };
  }

  // Slices on which a point label's marker shows.
  function pointRange(index, halfWidth, n) {
    return { start: clamp(index - halfWidth, n), end: clamp(index + halfWidth, n), widest: clamp(index, n) };
  }

  // Slider track background marking slices start…end.
  function trackGradient(start, end, n, on, off) {
    const pct = (i) => `${n > 1 ? +((i / (n - 1)) * 100).toFixed(3) : 0}%`;
    const a = pct(start), b = pct(end);
    return `linear-gradient(to right, ${off} 0%, ${off} ${a}, ${on} ${a}, ${on} ${b}, ${off} ${b}, ${off} 100%)`;
  }

  // Mirrored copies are built with world x → −x (tools/mirror_case.py).
  function mirrorMM(mm) {
    return [-mm[0], mm[1], mm[2]];
  }

  // The case's mirrored copy, or the case it was mirrored from.
  function counterpart(cases, caseId) {
    const ids = new Set(cases.map((c) => c.case_id));
    const me = cases.find((c) => c.case_id === caseId);
    if (!me) return null;
    if (me.mirror && ids.has(me.mirror)) return me.mirror;
    if (me.mirror_of && ids.has(me.mirror_of)) return me.mirror_of;
    const copy = cases.find((c) => c.mirror_of === caseId);
    return copy ? copy.case_id : null;
  }

  // Panel line for a structure drawn by tools/autolabels.py and not yet checked by hand.
  function autoNote(entry) {
    return entry && entry.auto ? `Outline drawn automatically (${entry.auto.source}) — not yet checked` : null;
  }

  function pickerGroups(cases) {
    return { cases: cases.filter((c) => !c.candidate), candidates: cases.filter((c) => c.candidate) };
  }

  return {
    PLANES, PLANE_AXIS, HERO_FRACTION, otherPlanes, layoutFor, refLineOrientation, tileRect, tileAt,
    applyAffine, invertAffine, worldToVox, worldToFrac, fracToWorld, extentSlices,
    pointRange, trackGradient, mirrorMM, counterpart, pickerGroups, autoNote,
  };
});
