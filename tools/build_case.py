#!/usr/bin/env python3
"""Build a viewer case from NIfTI volume(s) + an optional label map.

Example (OAIZIB-CM subject — see CLAUDE.md "Data sources"):

    python tools/build_case.py knee-mri \
        --title "Knee — OAI 3D DESS" --region knee --side right \
        --seq dess_3d "DESS 3D" ~/datasets/OAIZIB-CM/imagesTr/oaizib_001_0000.nii.gz \
        --labels ~/datasets/OAIZIB-CM/labelsTr/oaizib_001.nii.gz --preset oaizib-cm \
        --source "OAIZIB-CM (OAI baseline, KL0)" --licence "CC BY-NC 4.0" \
        --citation "Yao et al., OAIZIB-CM; Osteoarthritis Initiative"

What it does:
  - reorients every volume to RAS (closest canonical) and strips free-text header fields
  - stores volumes as int16, label map as uint16 with NIfTI intent "label"
  - checks label map and volumes share the same grid (same session / same space)
  - sets a default window/level per sequence from intensity percentiles
  - writes meta.json, lut.json (value → id, name, colour, centroid), points.json (kept if present)
  - registers the case in data/index.json
  - prints every label value found, so the preset mapping can be checked

DICOM input: convert first with `dcm2niix -ba y -z y -o OUT DICOM_DIR` (anonymises the sidecar).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

from atlaslib import build_lut, clean_header, load_ras, register_case, same_grid

ROOT = Path(__file__).resolve().parents[1]

# value → structure id. VERIFY against the dataset's own README before trusting a preset:
# the script prints the values present and their voxel counts.
PRESETS = {
    "oaizib-cm": {
        1: "femur",
        2: "femoral_cartilage",
        3: "tibia",
        4: "medial_tibial_cartilage",
        5: "lateral_tibial_cartilage",
    },
}

PALETTE = [  # (keyword in id, rgb)
    ("cartilage", (70, 140, 230)), ("meniscus", (150, 90, 210)), ("tendon", (240, 200, 40)),
    ("ligament", (235, 120, 40)), ("acl", (235, 120, 40)), ("pcl", (235, 120, 40)),
    ("mcl", (235, 120, 40)), ("lcl", (235, 120, 40)), ("mpfl", (235, 120, 40)),
    ("artery", (220, 30, 30)), ("vein", (60, 90, 220)), ("nerve", (120, 210, 60)),
    ("fat_pad", (250, 235, 140)), ("bursa", (60, 200, 220)), ("recess", (60, 200, 220)),
    ("femur", (233, 214, 170)), ("tibia", (233, 214, 170)), ("fibula", (233, 214, 170)),
    ("patella", (233, 214, 170)),
]
MUSCLE = (205, 70, 80)


# Meniscus thirds sit side by side, so each part gets its own hue (unshaded): the cuts show in Fill.
MENISCUS_PARTS = [("meniscus_anterior_horn", (165, 95, 230)), ("meniscus_body", (235, 95, 160)),
                  ("meniscus_posterior_horn", (100, 60, 180))]


def colour(sid: str, i: int) -> list[int]:
    part = next((c for k, c in MENISCUS_PARTS if sid.endswith(k)), None)
    if part:
        return list(part)
    rgb = next((c for k, c in PALETTE if k in sid), MUSCLE)
    f = 0.82 + 0.36 * ((i * 0.618) % 1)  # vary shade so neighbours differ
    return [int(min(255, c * f)) for c in rgb]


def checklist_names(root: Path, region: str) -> dict[str, str]:
    """id → display name from checklists/<region>.md tables."""
    path = Path(root) / "checklists" / f"{region}.md"
    names: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and re.fullmatch(r"[a-z0-9_]+", cells[0]) and cells[0] != "id":
                names[cells[0]] = cells[1]
    return names


def build_case(root: Path, case_id: str, *, title: str, region: str,
               seqs: list[tuple[str, str, Path]], labels: Path | None = None,
               mapping: dict[int, str] | None = None, side: str = "", plane: str = "sagittal",
               source: str, licence: str, citation: str = "",
               index_extra: dict | None = None) -> dict:
    """Write data/<case_id>/ (volumes, labels, meta, lut, points) and register it. Returns meta."""
    root = Path(root)
    out = root / "data" / case_id
    (out / "volumes").mkdir(parents=True, exist_ok=True)

    # ---- volumes ----
    seq_meta, ref = [], None
    for sid, label, path in seqs:
        img = load_ras(Path(path).expanduser())
        if ref is None:
            ref = img
        elif not same_grid(img, ref):
            print(f"note: {sid} is on a different grid from {seqs[0][0]} — "
                  "fine if same session (scanner coordinates); labels follow the reference grid")
        data = np.asanyarray(img.dataobj).astype(np.float32)
        body = data[data > np.percentile(data, 5)]
        lo, hi = np.percentile(body, [1, 99.5])
        if data.max() > 32767 or data.min() < -32768 or (data.max() - data.min()) < 100:
            scale = 4000.0 / max(hi - lo, 1e-6)  # rescale floats / tiny ranges into int16
            data, lo, hi = (data - lo) * scale, 0.0, (hi - lo) * scale
        vol = nib.Nifti1Image(np.round(data).astype(np.int16), img.affine)
        clean_header(vol)
        nib.save(vol, out / "volumes" / f"{sid}.nii.gz")
        seq_meta.append({"id": sid, "label": label, "file": f"volumes/{sid}.nii.gz",
                         "cal_min": round(float(lo)), "cal_max": round(float(hi))})
        print(f"{sid}: shape={img.shape} voxel={tuple(round(float(z), 3) for z in img.header.get_zooms())} W/L {lo:.0f}–{hi:.0f}")

    # ---- labels ----
    mapping = dict(mapping or {})
    names = checklist_names(root, region)
    lut = {}
    if labels:
        lab = load_ras(Path(labels).expanduser())
        if not same_grid(lab, ref):
            sys.exit("label map grid does not match the reference sequence — resample it first")
        arr = np.asanyarray(lab.dataobj)
        if not np.allclose(arr, np.round(arr)):
            sys.exit("label map has non-integer values")
        arr = np.round(arr).astype(np.uint16)
        values, counts = np.unique(arr[arr > 0], return_counts=True)
        base = {}
        print("label values found:")
        for v, n in zip(values.tolist(), counts.tolist()):
            sid = mapping.get(v, f"label_{v}")
            base[v] = {"id": sid, "name": names.get(sid, sid.replace("_", " ").capitalize()), "rgb": colour(sid, v)}
            flag = "" if v in mapping else "   <-- unmapped: add to --label-names"
            print(f"  {v:>4}  {n:>9} vox  {sid}{flag}")
        lut = build_lut(arr, lab.affine, base)
        out_lab = nib.Nifti1Image(arr, lab.affine)
    else:
        # empty label map on the reference grid, ready for painting mode
        out_lab = nib.Nifti1Image(np.zeros(ref.shape, np.uint16), ref.affine)
    clean_header(out_lab)
    out_lab.header.set_intent("label")
    nib.save(out_lab, out / "labels.nii.gz")

    meta = {
        "case_id": case_id, "title": title, "region": region, "side": side,
        "modality": "MR", "synthetic": False, "source": source, "licence": licence,
        "citation": citation, "reference_sequence": seq_meta[0]["id"], "sequences": seq_meta,
        "default_plane": plane,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "lut.json").write_text(json.dumps(lut, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if not (out / "points.json").exists():
        (out / "points.json").write_text("[]\n", encoding="utf-8")
    points = json.loads((out / "points.json").read_text(encoding="utf-8"))

    register_case(root, {"case_id": case_id, "title": title, "region": region, "modality": "MR",
                         "sequences": [s["id"] for s in seq_meta], "structure_count": len(lut) + len(points),
                         "synthetic": False, "side": side, **(index_extra or {})})
    print(f"wrote {out}  ({len(lut)} labelled structures)")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser(description="Build an atlas case from NIfTI files.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("case_id", help="folder name under data/, e.g. knee-mri")
    ap.add_argument("--seq", nargs=3, action="append", required=True, metavar=("ID", "LABEL", "PATH"),
                    help="sequence id, display label, NIfTI path (repeat; first = reference)")
    ap.add_argument("--labels", type=Path, help="label map NIfTI (integer values)")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="label value → id mapping")
    ap.add_argument("--label-names", type=Path, help='JSON {"1": "femur", ...} (overrides preset)')
    ap.add_argument("--title", required=True)
    ap.add_argument("--region", required=True, help="checklist name, e.g. knee")
    ap.add_argument("--side", default="")
    ap.add_argument("--plane", default="sagittal", choices=["sagittal", "coronal", "axial"])
    ap.add_argument("--source", required=True)
    ap.add_argument("--licence", required=True)
    ap.add_argument("--citation", default="")
    args = ap.parse_args()

    mapping: dict[int, str] = dict(PRESETS.get(args.preset, {}))
    if args.label_names:
        mapping = {int(k): v for k, v in json.loads(args.label_names.read_text(encoding="utf-8")).items()}
    build_case(ROOT, args.case_id, title=args.title, region=args.region,
               seqs=[(sid, label, Path(path)) for sid, label, path in args.seq],
               labels=args.labels, mapping=mapping, side=args.side, plane=args.plane,
               source=args.source, licence=args.licence, citation=args.citation)


if __name__ == "__main__":
    main()
