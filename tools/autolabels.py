#!/usr/bin/env python3
"""Automatic labels for a knee case, so painting starts from them instead of from nothing.

    venv/bin/python tools/autolabels.py knee-mri [--no-totalseg]

- DOSMA (iwoai-2019-t6-normalized): the menisci, split medial / lateral and into anterior horn,
  body and posterior horn; and the patellar cartilage.
- TotalSegmentator (appendicular_bones_mr): the patella and fibula, only when a licence is set
  (free academic licence: https://backend.totalsegmentator.com/license-academic/, then
  venv-autoseg/bin/totalseg_set_license -l aca_...).

The models run in venv-autoseg (requirements-autoseg.txt); this file runs in the main venv.
Existing labels always win: only empty voxels are filled, and a structure that is already
labelled without an "auto" mark is never replaced. The case is backed up first, and its
mirrored copy is rebuilt afterwards. Mirrored copies themselves are refused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import date
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

from atlaslib import backup_case, build_lut, clean_header, patch_case, read_index, same_grid
from build_case import checklist_names, colour
from mirror_case import mirror_case

ROOT = Path(__file__).resolve().parents[1]
AUTOSEG_PY = ROOT / "venv-autoseg" / "bin" / "python"
DOSMA_SCRIPT = Path(__file__).resolve().parent / "autoseg" / "dosma_unet.py"
DOSMA_SOURCE = "DOSMA iwoai-2019-t6-normalized"
BONES_SOURCE = "TotalSegmentator appendicular_bones_mr"
LICENCE_FILE = Path("~/.totalsegmentator/config.json")
PARTS = ("anterior_horn", "body", "posterior_horn")

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


def ring_centre(mask: np.ndarray, affine: np.ndarray) -> tuple[float, float]:
    """World (x, y) centre of a meniscus: the middle of its own 1st–99th percentile extent.
    (The tibial cartilage centroid sits several mm behind the ring on knee-mri, which pulls
    the cuts round and puts the lateral body at the posterior corner.)"""
    xy = nib.affines.apply_affine(affine, np.argwhere(mask))[:, :2]
    lo, hi = np.percentile(xy, [1, 99], axis=0)
    return float((lo[0] + hi[0]) / 2), float((lo[1] + hi[1]) / 2)


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


def voxel_print(arr: np.ndarray, value: int) -> str:
    """Fingerprint of the voxels holding `value`, to tell later hand edits from the tool's own output."""
    return hashlib.sha256(np.flatnonzero(arr == value).astype(np.int64).tobytes()).hexdigest()[:16]


def merge_auto(arr: np.ndarray, lut: dict[str, dict], additions: dict[str, np.ndarray], source: str,
               names: dict[str, str], date: str) -> tuple[np.ndarray, dict[str, dict], dict]:
    """Merge automatic masks (id → mask on arr's grid) into a label map and its lut.json dict.

    Existing labels win: only voxels that are 0 are written, and an id already in the lut
    without an "auto" key (ground truth, painted, or checked) is refused. An id this tool added
    before keeps its value; all such ids are cleared first, so a re-run replaces only its own
    voxels — unless they were edited since (they no longer match the fingerprint stored in
    "auto"), in which case the structure is kept as it is. New ids take the next values in the
    order given. Returns copies plus a report: {"written": {id: n}, "blocked": {id: n},
    "refused": [id], "kept": [id]}. Entries get id, name, rgb and "auto": {source, date,
    voxels_sha256}; run build_lut afterwards for voxels, centroids and extents.
    """
    arr = np.array(arr, copy=True)
    lut = {k: dict(v) for k, v in lut.items()}
    by_id = {e["id"]: int(k) for k, e in lut.items()}
    top = max([int(k) for k in lut] + [int(arr.max()) if arr.size else 0])
    report: dict = {"written": {}, "blocked": {}, "refused": [], "kept": []}
    todo = []
    for sid, mask in additions.items():
        if sid in by_id and "auto" not in lut[str(by_id[sid])]:
            report["refused"].append(sid)
            continue
        stored = lut[str(by_id[sid])]["auto"].get("voxels_sha256") if sid in by_id else None
        if stored and stored != voxel_print(arr, by_id[sid]):
            report["kept"].append(sid)  # edited by hand since the last run
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
                           "rgb": colour(sid, value),
                           "auto": {"source": source, "date": date, "voxels_sha256": voxel_print(arr, value)}}
    return arr, lut, report


def has_licence(licence_file: Path) -> bool:
    try:
        return bool(json.loads(Path(licence_file).expanduser().read_text(encoding="utf-8")).get("license_number"))
    except (OSError, ValueError, AttributeError):
        return False


def _replace(write, path: Path) -> None:
    """Write via a temporary file next to path, then swap it in."""
    tmp = path.with_name(f".tmp-{path.name}")
    write(tmp)
    os.replace(tmp, path)


def _prediction(cmd: list[str], out: Path, labels: nib.Nifti1Image, what: str) -> np.ndarray:
    out.unlink(missing_ok=True)
    if subprocess.run(cmd).returncode != 0 or not out.exists():
        raise SystemExit(f"{what} failed (see above); the case is unchanged.")
    img = nib.load(str(out))
    if not same_grid(img, labels):
        raise SystemExit(f"{what} wrote a different grid from labels.nii.gz; the case is unchanged.")
    return np.asanyarray(img.dataobj)


def run(root: Path, case_id: str, *, autoseg_python: Path, totalseg: bool | None = None,
        licence_file: Path = LICENCE_FILE) -> dict:
    """Run the models on data/<case_id>/ and merge their labels in. totalseg None = if licensed."""
    root, autoseg_python = Path(root), Path(autoseg_python)
    case = root / "data" / case_id

    # 1. check everything before anything changes
    if not (case / "meta.json").exists():
        raise SystemExit(f"no case at data/{case_id}")
    meta = json.loads((case / "meta.json").read_text(encoding="utf-8"))
    if meta.get("mirror_of"):
        raise SystemExit(f"{case_id} is a mirrored copy of {meta['mirror_of']}: run this on "
                         f"{meta['mirror_of']}, and its copy is rebuilt afterwards.")
    if not autoseg_python.exists():
        raise SystemExit(f"{autoseg_python} not found. Make the model venv first:\n"
                         "  python3.13 -m venv venv-autoseg && venv-autoseg/bin/pip install -r requirements-autoseg.txt")
    lut = json.loads((case / "lut.json").read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in lut.values()}
    missing = [k for k in ("medial_tibial_cartilage", "lateral_tibial_cartilage") if k not in by_id]
    if missing:
        raise SystemExit(f"{case_id} has no {' or '.join(missing)}: the plateaus are needed to tell medial from lateral.")
    med = by_id["medial_tibial_cartilage"]["centroid_mm"]
    lat = by_id["lateral_tibial_cartilage"]["centroid_mm"]
    mid_x = (med[0] + lat[0]) / 2
    ref = case / "volumes" / f"{meta['reference_sequence']}.nii.gz"
    labels = nib.load(str(case / "labels.nii.gz"))
    use_ts = has_licence(licence_file) if totalseg is None else totalseg

    # 2–3. run the models into data/<case>/auto/ (git-ignored)
    auto = case / "auto"
    auto.mkdir(exist_ok=True)
    pred = _prediction([str(autoseg_python), str(DOSMA_SCRIPT), str(ref), str(auto / "dosma.nii.gz")],
                       auto / "dosma.nii.gz", labels, "DOSMA")
    bones = None
    if use_ts:
        ts = autoseg_python.parent / "TotalSegmentator"
        for device in ("mps", "cpu"):
            cmd = [str(ts), "-i", str(ref), "-o", str(auto / "bones.nii.gz"), "--ml",
                   "--task", "appendicular_bones_mr", "--device", device]
            try:
                bones = _prediction(cmd, auto / "bones.nii.gz", labels, f"TotalSegmentator ({device})")
                break
            except SystemExit as e:
                if device == "cpu":
                    raise SystemExit(f"{e} Run with --no-totalseg to skip the bones.")
                print(f"{e} Trying the CPU.")
    elif totalseg is None:
        print("TotalSegmentator bones (patella, fibula) skipped: no licence. Get the free academic licence at "
              "https://backend.totalsegmentator.com/license-academic/ (task appendicular_bones_mr), then run "
              "venv-autoseg/bin/totalseg_set_license -l aca_...")
    else:
        print("TotalSegmentator bones (patella, fibula) skipped (--no-totalseg).")

    # 4. what to add
    affine = labels.affine
    medial, lateral = split_sides(pred == 4, affine, med[0], lat[0])
    dosma_adds = {}
    for side, mask, plateau in (("medial", medial, med), ("lateral", lateral, lat)):
        centre = ring_centre(mask, affine) if mask.any() else plateau[:2]
        for part, m in zip(PARTS, meniscus_thirds(mask, affine, centre, mid_x)):
            dosma_adds[f"{side}_meniscus_{part}"] = m
    dosma_adds["patellar_cartilage"] = largest_component(pred == 3)
    merges = [(DOSMA_SOURCE, dosma_adds)]
    if bones is not None:
        merges.append((BONES_SOURCE, {"patella": largest_component(bones == 1), "fibula": largest_component(bones == 3)}))

    # 5. write: backup, merge, lut, label map, index, mirror
    names = checklist_names(root, meta.get("region", ""))
    backup = backup_case(case)
    arr = np.asanyarray(labels.dataobj).astype(np.uint16)
    report: dict = {"backup": str(backup), "written": {}, "blocked": {}, "refused": [], "kept": [],
                    "skipped": [] if bones is not None else ["patella", "fibula"], "mirror": None}
    for source, adds in merges:
        arr, lut, r = merge_auto(arr, lut, adds, source, names, date.today().isoformat())
        report["written"].update(r["written"])
        report["blocked"].update(r["blocked"])
        report["refused"] += r["refused"]
        report["kept"] += r["kept"]
        report["skipped"] += [k for k, m in adds.items() if not m.any()]
    lut = build_lut(arr, affine, {int(k): v for k, v in lut.items()})
    out = nib.Nifti1Image(arr, affine)
    clean_header(out)
    out.header.set_intent("label")
    _replace(lambda p: nib.save(out, str(p)), case / "labels.nii.gz")
    _replace(lambda p: p.write_text(json.dumps(lut, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"), case / "lut.json")
    points = json.loads((case / "points.json").read_text(encoding="utf-8")) if (case / "points.json").exists() else []
    if any(c["case_id"] == case_id for c in read_index(root)):
        patch_case(root, case_id, {"structure_count": len(lut) + len(points)})
    if meta.get("side") in ("right", "left"):
        report["mirror"] = mirror_case(root, case_id)
    return report


def print_report(report: dict) -> None:
    print("\nwritten (blocked = voxels already labelled, left alone):")
    for sid, n in report["written"].items():
        print(f"  {sid:<34} {n:>8} vox   blocked {report['blocked'][sid]}")
    if report["refused"]:
        print("refused, already labelled by hand or ground truth: " + ", ".join(report["refused"]))
    if report["kept"]:
        print("kept as they are, edited by hand since the last run: " + ", ".join(report["kept"]))
    if report["skipped"]:
        print("skipped: " + ", ".join(report["skipped"]))
    print(f"backup: {report['backup']}")
    if report["mirror"]:
        print(f"mirrored copy rebuilt: {report['mirror']}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("case_id", help="case under data/, e.g. knee-mri")
    ap.add_argument("--no-totalseg", action="store_true", help="skip the TotalSegmentator bones even if licensed")
    args = ap.parse_args(argv)
    print_report(run(ROOT, args.case_id, autoseg_python=AUTOSEG_PY, totalseg=False if args.no_totalseg else None))


if __name__ == "__main__":
    main()
