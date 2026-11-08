#!/usr/bin/env python3
"""Automatic labels for a knee case: the menisci (in thirds) and patellar cartilage from DOSMA.

The models run in venv-autoseg (requirements-autoseg.txt); this file runs in the main venv and
does the post-processing: medial / lateral split, meniscus thirds, keeping the largest piece.
"""
from __future__ import annotations

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

from build_case import colour

CONNECT_26 = np.ones((3, 3, 3), bool)


def _mask_of(shape, idx: np.ndarray) -> np.ndarray:
    m = np.zeros(shape, bool)
    m[tuple(idx.T)] = True
    return m


def largest_component(mask: np.ndarray) -> np.ndarray:
    """The largest 26-connected piece of mask (empty if mask is empty)."""
    lab, n = ndi.label(mask, structure=CONNECT_26)
    if n == 0:
        return np.zeros(mask.shape, bool)
    sizes = np.bincount(lab.ravel())[1:]
    return lab == (int(np.argmax(sizes)) + 1)


def split_sides(mask: np.ndarray, affine: np.ndarray, medial_x: float,
                lateral_x: float) -> tuple[np.ndarray, np.ndarray]:
    """(medial, lateral): each voxel goes to the nearer of the two world x positions, then each
    side keeps its largest piece (drops a bridge's far end or a stray fragment)."""
    idx = np.argwhere(mask)
    x = nib.affines.apply_affine(affine, idx)[:, 0]
    to_medial = np.abs(x - medial_x) <= np.abs(x - lateral_x)
    medial = _mask_of(mask.shape, idx[to_medial])
    lateral = _mask_of(mask.shape, idx[~to_medial])
    return largest_component(medial), largest_component(lateral)


def meniscus_thirds(mask: np.ndarray, affine: np.ndarray, centre_xy, mid_x: float
                    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(anterior_horn, body, posterior_horn) of one meniscus, by angle round its plateau centre.

    The angle is atan2(y - cy, (x - cx) * outward) in world mm, outward = sign(cx - mid_x): the
    periphery is near 0°, anterior is positive and the opening toward the notch is at ±180°, so
    even a near-ring lateral meniscus is cut in its gap. Cuts sit at ⅓ and ⅔ of the span between
    the 0.5th and 99.5th percentile angles; every voxel lands in exactly one part.
    """
    idx = np.argwhere(mask)
    if len(idx) == 0:
        return tuple(np.zeros(mask.shape, bool) for _ in range(3))
    xyz = nib.affines.apply_affine(affine, idx)
    cx, cy = centre_xy
    outward = 1.0 if cx >= mid_x else -1.0
    ang = np.degrees(np.arctan2(xyz[:, 1] - cy, (xyz[:, 0] - cx) * outward))
    lo, hi = np.percentile(ang, [0.5, 99.5])
    c1, c2 = lo + (hi - lo) / 3, lo + 2 * (hi - lo) / 3
    return (_mask_of(mask.shape, idx[ang >= c2]),
            _mask_of(mask.shape, idx[(ang >= c1) & (ang < c2)]),
            _mask_of(mask.shape, idx[ang < c1]))


def merge_auto(arr: np.ndarray, lut: dict[str, dict], additions: dict[str, np.ndarray], source: str,
               names: dict[str, str], date: str) -> tuple[np.ndarray, dict[str, dict], dict]:
    """Merge automatic masks (id → mask on arr's grid) into a label map and its lut.json dict.

    Existing labels win: only voxels that are 0 are written, and an id already in the lut
    without an "auto" key (ground truth, or painted) is refused. An id this tool added before
    keeps its value; all such ids are cleared first, so a re-run replaces only its own voxels.
    New ids take the next values in the order given. Returns copies plus a report:
    {"written": {id: n}, "blocked": {id: n}, "refused": [id]}. Entries get id, name, rgb and
    "auto": {source, date}; run build_lut afterwards for voxels, centroids and extents.
    """
    arr = np.array(arr, copy=True)
    lut = {k: dict(v) for k, v in lut.items()}
    by_id = {e["id"]: int(k) for k, e in lut.items()}
    top = max([int(k) for k in lut] + [int(arr.max()) if arr.size else 0])
    report: dict = {"written": {}, "blocked": {}, "refused": []}
    todo = []
    for sid, mask in additions.items():
        if sid in by_id and "auto" not in lut[str(by_id[sid])]:
            report["refused"].append(sid)
            continue
        if sid in by_id:
            value = by_id[sid]
        else:
            top += 1
            value = top
        todo.append((sid, value, np.asarray(mask, bool)))
    for _, value, _ in todo:
        arr[arr == value] = 0
    for sid, value, mask in todo:
        free = mask & (arr == 0)
        arr[free] = value
        report["written"][sid] = int(free.sum())
        report["blocked"][sid] = int((mask & ~free).sum())
        lut[str(value)] = {**lut.get(str(value), {}), "id": sid,
                           "name": names.get(sid, sid.replace("_", " ").capitalize()),
                           "rgb": colour(sid, value), "auto": {"source": source, "date": date}}
    return arr, lut, report
