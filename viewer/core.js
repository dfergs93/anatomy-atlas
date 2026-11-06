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

  // Index of the tile (nv.screenSlices) containing canvas point x, y; -1 when none.
  function tileAt(tiles, x, y) {
    for (let i = 0; i < tiles.length; i++) {
      const [l, t, w, h] = tiles[i].leftTopWidthHeight;
      if (x > l && y > t && x < l + w && y < t + h) return i;
    }
    return -1;
  }

  const clamp = (v, n) => Math.max(0, Math.min(n - 1, v));

  // A structure's extent on one plane (mm, from lut.json) → slice numbers on the current grid.
  function sliceRange(planeExtent, mmToIndex, n) {
    if (!planeExtent) return null;
    const s = clamp(mmToIndex(planeExtent.start_mm), n);
    const e = clamp(mmToIndex(planeExtent.end_mm), n);
    return { start: Math.min(s, e), end: Math.max(s, e), widest: clamp(mmToIndex(planeExtent.widest_mm), n) };
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

  function pickerGroups(cases) {
    return { cases: cases.filter((c) => !c.candidate), candidates: cases.filter((c) => c.candidate) };
  }

  return {
    PLANES, PLANE_AXIS, HERO_FRACTION, otherPlanes, layoutFor, refLineOrientation, tileAt,
    sliceRange, pointRange, trackGradient, mirrorMM, counterpart, pickerGroups,
  };
});
