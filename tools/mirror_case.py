#!/usr/bin/env python3
"""Make a mirrored copy of a case: a right knee shown as a left knee (or the reverse).

    python tools/mirror_case.py knee-mri            # → data/knee-mri-left/

The mirror is world x → −x. Volumes, label map, points, centroids and extents
are all mirrored; ids, names and colours carry over. The copy is generated:
never paint it — rebuild it from the source instead (re-running replaces it).
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np

from atlaslib import build_lut, clean_header, patch_case, read_index, register_case

ROOT = Path(__file__).resolve().parents[1]
OTHER_SIDE = {"right": "left", "left": "right"}


def mirror_affine(affine: np.ndarray, nx: int) -> np.ndarray:
    """Affine for data flipped along array axis 0 whose world is mirrored x → −x."""
    flip = np.array([[-1, 0, 0, nx - 1], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], float)
    return np.diag([-1.0, 1.0, 1.0, 1.0]) @ affine @ flip


def mirror_image(img: nib.Nifti1Image) -> nib.Nifti1Image:
    data = np.asanyarray(img.dataobj)[::-1].astype(img.get_data_dtype())
    out = nib.Nifti1Image(np.ascontiguousarray(data), mirror_affine(img.affine, img.shape[0]))
    clean_header(out)
    intent = img.header.get_intent()[0]
    if intent != "none":
        out.header.set_intent(intent)
    return out


def mirror_case(root: Path, src_id: str, dst_id: str | None = None, *, volumes: bool = True) -> str:
    """volumes=False: when the copy already exists, keep its volumes and rewrite only the label files."""
    root = Path(root)
    src = root / "data" / src_id
    meta = json.loads((src / "meta.json").read_text())
    if meta.get("mirror_of"):
        raise ValueError(f"{src_id} is already a mirrored copy of {meta['mirror_of']}")
    side = OTHER_SIDE.get(meta.get("side", ""))
    if not side:
        raise ValueError(f"{src_id} has side {meta.get('side')!r}; need 'right' or 'left' to mirror")
    dst_id = dst_id or f"{src_id}-{side}"
    out = root / "data" / dst_id
    if out.exists():
        old = json.loads((out / "meta.json").read_text()) if (out / "meta.json").exists() else {}
        if old.get("mirror_of") != src_id:
            raise ValueError(f"data/{dst_id} exists and is not a mirror of {src_id}; not overwriting it")
        if volumes:
            shutil.rmtree(out)
    else:
        volumes = True
    (out / "volumes").mkdir(parents=True, exist_ok=True)

    if volumes:
        for seq in meta["sequences"]:
            nib.save(mirror_image(nib.load(src / seq["file"])), out / seq["file"])
    labels = mirror_image(nib.load(src / "labels.nii.gz"))
    nib.save(labels, out / "labels.nii.gz")

    src_lut = json.loads((src / "lut.json").read_text())
    lut = build_lut(np.asanyarray(labels.dataobj), labels.affine, {int(k): v for k, v in src_lut.items()})
    points = json.loads((src / "points.json").read_text()) if (src / "points.json").exists() else []
    points = [{**p, "xyz_mm": [-p["xyz_mm"][0], *p["xyz_mm"][1:]]} for p in points]

    title = f"{meta['title']} · {side} (mirrored)"
    new_meta = {**meta, "case_id": dst_id, "title": title, "side": side, "mirror_of": src_id}
    (out / "meta.json").write_text(json.dumps(new_meta, indent=2, ensure_ascii=False) + "\n")
    (out / "lut.json").write_text(json.dumps(lut, indent=1, ensure_ascii=False) + "\n")
    (out / "points.json").write_text(json.dumps(points, indent=2, ensure_ascii=False) + "\n")

    entry = next((c for c in read_index(root) if c["case_id"] == src_id), {"case_id": src_id})
    entry = {k: v for k, v in entry.items() if k != "mirror"}
    register_case(root, {**entry, "case_id": dst_id, "title": title, "side": side, "mirror_of": src_id})
    patch_case(root, src_id, {"mirror": dst_id})
    print(dst_id)
    return dst_id


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src_id", help="case to mirror, e.g. knee-mri")
    ap.add_argument("--dst", help="id of the copy (default: <src>-left or <src>-right)")
    args = ap.parse_args()
    mirror_case(ROOT, args.src_id, args.dst)


if __name__ == "__main__":
    main()
