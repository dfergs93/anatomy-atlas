"""Write a painted label map back to its case, safely (the browser's painting mode posts here).

Every check runs before anything is written; a refused save leaves the case byte-identical
and makes no backup. Then: backup, label map, lut.json, points.json, index, mirror, checklist.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import nibabel as nib
import numpy as np

from atlaslib import backup_case, build_lut, clean_header, patch_case, read_index
from autolabels import _replace, voxel_print
from build_case import colour
from checklist import read_checklist, set_labelled
from mirror_case import mirror_case, mirror_id


class SaveError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def case_token(case_dir) -> str:
    """Fingerprint of the files a save replaces; changes whenever any of them does."""
    h = hashlib.sha256()
    for name in ("labels.nii.gz", "lut.json", "points.json"):
        p = Path(case_dir) / name
        h.update(p.read_bytes() if p.exists() else b"")
    return h.hexdigest()[:16]


def _check_points(points, checklist_ids) -> list[dict]:
    if not isinstance(points, list):
        raise SaveError("points must be a list")
    out, seen = [], set()
    for p in points:
        if not (isinstance(p, dict) and isinstance(p.get("id"), str) and isinstance(p.get("name"), str)):
            raise SaveError("each point needs a string id and name")
        xyz = p.get("xyz_mm")
        if not (isinstance(xyz, list) and len(xyz) == 3
                and all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in xyz)):
            raise SaveError(f"point {p['id']}: xyz_mm must be 3 finite numbers")
        if p["id"] in seen:
            raise SaveError(f"point {p['id']} appears twice")
        if p["id"] not in checklist_ids:
            raise SaveError(f"point {p['id']} is not in the checklist")
        seen.add(p["id"])
        out.append({"id": p["id"], "name": p["name"], "xyz_mm": list(xyz)})
    return out


def save_case(root, case_id: str, *, token: str, labels: bytes, values: dict[int, str],
              checked: list[str], points: list[dict]) -> dict:
    root = Path(root)
    case = root / "data" / case_id

    # ---- checks: nothing is written until all have passed ----
    if not (case / "meta.json").exists():
        raise SaveError(f"no case {case_id}")
    meta = json.loads((case / "meta.json").read_text())
    if meta.get("mirror_of"):
        raise SaveError(f"{case_id} is a mirrored copy of {meta['mirror_of']}; paint {meta['mirror_of']} instead")
    if token != case_token(case):
        raise SaveError(f"{case_id} changed on disk since you opened it; reload before saving", 409)
    old_img = nib.load(str(case / "labels.nii.gz"))
    shape = old_img.shape
    if len(labels) != int(np.prod(shape)):
        raise SaveError(f"bitmap has {len(labels)} voxels, the case has {int(np.prod(shape))}")
    bitmap = np.frombuffer(labels, np.uint8)
    try:
        values = {int(k): str(v) for k, v in values.items()}
    except (TypeError, ValueError, AttributeError):
        raise SaveError("values must map integers to ids") from None
    unmapped = sorted(set(np.unique(bitmap).tolist()) - {0} - set(values))
    if unmapped:
        raise SaveError(f"painted values with no structure id: {unmapped}")
    if len(set(values.values())) != len(values):
        raise SaveError("two values share one structure id")
    if not isinstance(checked, list) or not all(isinstance(c, str) for c in checked):
        raise SaveError("checked must be a list of ids")
    old_lut = json.loads((case / "lut.json").read_text()) if (case / "lut.json").exists() else {}
    checklist_path = root / "checklists" / f"{meta['region']}.md"
    rows = {r.id: r for r in read_checklist(checklist_path)} if checklist_path.exists() else {}
    known = set(rows) | {e["id"] for e in old_lut.values()}
    for sid in values.values():
        if sid not in known:
            raise SaveError(f"{sid} is not in the {meta['region']} checklist or the case")
    points = _check_points(points, set(rows))
    mirror_dir = (root / "data" / mirror_id(meta, case_id)) if mirror_id(meta, case_id) else None
    if mirror_dir and mirror_dir.exists():
        theirs = json.loads((mirror_dir / "meta.json").read_text()) if (mirror_dir / "meta.json").exists() else {}
        if theirs.get("mirror_of") != case_id:
            raise SaveError(f"data/{mirror_dir.name} exists and is not the mirror of {case_id}; move it aside")

    # ---- write ----
    backup_case(case)
    affine = old_img.affine
    old_arr = np.asanyarray(old_img.dataobj)
    arr = bitmap.reshape(shape, order="F").astype(np.uint16)
    base = {}
    for v in np.unique(arr[arr > 0]).tolist():
        sid = values[v]
        old = old_lut.get(str(v))
        if old and old["id"] == sid:
            entry = dict(old)
        else:
            entry = {"id": sid, "name": rows[sid].name if sid in rows else sid, "rgb": colour(sid, v)}
        if sid in checked or voxel_print(old_arr, v) != voxel_print(arr, v):
            entry.pop("auto", None)
        if sid in rows and rows[sid].type == "E":
            entry["expected"] = True
        else:
            entry.pop("expected", None)
        base[v] = entry
    lut = build_lut(arr, affine, base)
    out = nib.Nifti1Image(arr, affine)
    clean_header(out)
    out.header.set_intent("label")
    _replace(lambda p: nib.save(out, str(p)), case / "labels.nii.gz")
    _replace(lambda p: p.write_text(json.dumps(lut, indent=1, ensure_ascii=False) + "\n"), case / "lut.json")
    _replace(lambda p: p.write_text(json.dumps(points, indent=2, ensure_ascii=False) + "\n"), case / "points.json")
    warnings, mirror = [], None
    indexed = any(c["case_id"] == case_id for c in read_index(root))
    try:
        if indexed:
            patch_case(root, case_id, {"structure_count": len(lut) + len(points)})
    except Exception as e:
        warnings.append(f"index not updated: {e}")
    try:
        if mirror_dir and indexed:
            mirror = mirror_case(root, case_id, volumes=False)
        elif mirror_dir:
            warnings.append("not in data/index.json: left copy not rebuilt")
    except Exception as e:
        warnings.append(f"mirror not rebuilt: {e}")
    labelled = sorted({e["id"] for e in lut.values() if not e.get("auto")} | {p["id"] for p in points})
    try:
        if checklist_path.exists():
            set_labelled(checklist_path, set(labelled))
    except Exception as e:
        warnings.append(f"checklist not updated: {e}")
    return {"token": case_token(case), "structures": len(lut), "labelled": labelled, "mirror": mirror,
            "warnings": warnings}
