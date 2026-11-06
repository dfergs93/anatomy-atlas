"""Shared helpers for building atlas cases: NIfTI I/O, lut.json entries, data/index.json.

Every volume is stored RAS-canonical, so array axes 0, 1, 2 are the sagittal,
coronal and axial slice directions. Structure extents are stored in world mm so
the viewer can turn them into slice numbers on any sequence's grid.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

PLANES = ("sagittal", "coronal", "axial")  # array axis 0, 1, 2 of a RAS-canonical volume


def load_ras(path: Path) -> nib.Nifti1Image:
    img = nib.as_closest_canonical(nib.load(str(path)))
    if img.ndim != 3:
        sys.exit(f"{path}: expected a 3D volume, got shape {img.shape}")
    return img


def clean_header(img: nib.Nifti1Image) -> None:
    h = img.header
    for field in ("descrip", "aux_file", "db_name", "intent_name"):
        if field in h:
            h[field] = b""
    h.set_xyzt_units("mm")


def same_grid(a: nib.Nifti1Image, b: nib.Nifti1Image) -> bool:
    return a.shape == b.shape and np.allclose(a.affine, b.affine, atol=1e-3)


def _world(affine: np.ndarray, ijk) -> np.ndarray:
    return (affine @ np.r_[np.asarray(ijk, float), 1.0])[:3]


def _nearest(idx: np.ndarray) -> np.ndarray:
    """The row of idx (N×d voxel indices) nearest their mean — a voxel inside the structure."""
    return idx[np.argmin(((idx - idx.mean(0)) ** 2).sum(1))]


def structure_extents(mask: np.ndarray, affine: np.ndarray, offset=(0, 0, 0)) -> dict[str, dict]:
    """Per plane: first, last and widest slice of the structure (world mm along that axis),
    plus an anchor voxel inside the structure on its widest slice.

    `offset` is the index of mask[0, 0, 0] in the full volume (for cropped masks).
    """
    off = np.asarray(offset, int)
    out = {}
    for axis, plane in enumerate(PLANES):
        others = tuple(a for a in range(3) if a != axis)
        counts = mask.sum(axis=others)
        present = np.flatnonzero(counts)
        start, end = int(present[0]), int(present[-1])
        widest = int(np.argmax(counts))  # first maximum = lowest index on ties
        in_slice = np.argwhere(np.take(mask, widest, axis=axis))
        pick = _nearest(in_slice)
        anchor = np.insert(pick, axis, widest) + off

        def coord(s: int) -> float:  # world mm along this axis of slice s, at the anchor's other indices
            ijk = anchor.copy()
            ijk[axis] = s + off[axis]
            return round(float(_world(affine, ijk)[axis]), 2)

        out[plane] = {
            "start_mm": coord(start), "end_mm": coord(end), "widest_mm": coord(widest),
            "anchor_mm": [round(float(v), 2) for v in _world(affine, anchor)],
        }
    return out


def lut_entry(mask: np.ndarray, affine: np.ndarray, sid: str, name: str, rgb: list[int],
              offset=(0, 0, 0)) -> dict:
    idx = np.argwhere(mask)
    c = _nearest(idx) + np.asarray(offset, int)
    return {
        "id": sid, "name": name, "rgb": list(rgb), "voxels": int(len(idx)),
        "centroid_vox": [int(x) for x in c],
        "centroid_mm": [round(float(x), 1) for x in _world(affine, c)],
        "extent": structure_extents(mask, affine, offset),
    }


def build_lut(arr: np.ndarray, affine: np.ndarray, base: dict[int, dict]) -> dict[str, dict]:
    """lut.json for label map `arr`. base[value] holds at least id, name, rgb; extra keys are kept.
    Values in base but absent from arr are skipped."""
    arr = np.asarray(arr)
    present = set(np.unique(arr[arr > 0]).tolist())
    boxes = ndi.find_objects(arr.astype(np.int64, copy=False)) if present else []
    lut = {}
    for value in sorted(v for v in base if v in present):
        box = boxes[value - 1]
        sub = arr[box] == value
        offset = [s.start for s in box]
        b = base[value]
        lut[str(value)] = {**b, **lut_entry(sub, affine, b["id"], b["name"], b["rgb"], offset)}
    return lut


def index_path(root: Path) -> Path:
    return Path(root) / "data" / "index.json"


def read_index(root: Path) -> list[dict]:
    p = index_path(root)
    return json.loads(p.read_text()) if p.exists() else []


def _write_index(root: Path, cases: list[dict]) -> None:
    p = index_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n")


def register_case(root: Path, entry: dict) -> None:
    """Add entry to data/index.json, replacing any entry with the same case_id."""
    cases = [c for c in read_index(root) if c["case_id"] != entry["case_id"]]
    cases.append(entry)
    _write_index(root, cases)


def patch_case(root: Path, case_id: str, fields: dict) -> None:
    cases = read_index(root)
    for c in cases:
        if c["case_id"] == case_id:
            c.update(fields)
            break
    else:
        raise KeyError(f"{case_id} is not in data/index.json")
    _write_index(root, cases)
