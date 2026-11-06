#!/usr/bin/env python3
"""OAIZIB-CM knee dataset: find the candidate normal knees, extract them, build them for review.

    python tools/oaizib.py list                # the 17 candidates (KL0, age ≤ 55, BMI 18.5–25)
    python tools/oaizib.py extract             # their images + labels → <root>/candidates/
    python tools/oaizib.py build-candidates    # image-only cases data/cand-<id>/ to scroll in the viewer
    python tools/oaizib.py remove-candidates   # delete those cases once one has been picked

--root defaults to ~/datasets/OAIZIB-CM (info.zip, imagesTr/Ts.zip, labelsTr/Ts.zip).
Licence: CC BY-NC 4.0 (dataset card + info/license). The citation below is required.
"""
from __future__ import annotations

import argparse
import io
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from atlaslib import read_index, write_index
from build_case import build_case

ROOT = Path(__file__).resolve().parents[1]
CITATION = ("Yao Y et al. CartiMorph: a framework for automated knee articular cartilage morphometrics. "
            "Med Image Anal 2024;91:103035. Data from the Osteoarthritis Initiative.")
LICENCE = "CC BY-NC 4.0"
SEX = {1: "M", 2: "F"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass(frozen=True)
class Subject:
    cmt_id: str
    subject_id: int
    split: str
    kl: int
    sex: str
    age: int
    bmi: float


def _col_index(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_rows(data: bytes) -> list[list[str]]:
    """Rows of the first sheet as text. Cells Excel leaves out (blanks) come back as ""."""
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = ["".join(si.itertext()) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
    rows = []
    for r in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).findall(".//m:sheetData/m:row", NS):
        out: list[str] = []
        for c in r.findall("m:c", NS):
            i = _col_index(c.get("r")) if c.get("r") else len(out)
            if c.get("t") == "inlineStr":
                val = "".join(c.find("m:is", NS).itertext())
            else:
                v = c.find("m:v", NS)
                val = (v.text or "") if v is not None else ""
                if c.get("t") == "s" and val:
                    val = shared[int(val)]
            out.extend([""] * (i - len(out) + 1))
            out[i] = val
        rows.append(out)
    return rows


def read_subjects(info_zip: Path) -> list[Subject]:
    subjects = []
    with zipfile.ZipFile(info_zip) as z:
        members = {Path(n).name: n for n in z.namelist()}
        for split in ("train", "test"):
            rows = xlsx_rows(z.read(members[f"subInfo_{split}.xlsx"]))
            header = rows[0]
            for r in rows[1:]:
                d = dict(zip(header, r))
                try:
                    subjects.append(Subject(
                        cmt_id=str(int(float(d["CMT-ID"]))).zfill(3), subject_id=int(float(d["SubjectID"])),
                        split=split, kl=int(float(d["KLGrade"])), sex=SEX[int(float(d["Gender"]))],
                        age=int(float(d["Age"])), bmi=float(d["BMI"])))
                except (KeyError, ValueError):
                    continue  # blank or odd cell: not a usable row
    return subjects


def candidates(subjects, max_age: int = 55, bmi_min: float = 18.5, bmi_max: float = 25.0) -> list[Subject]:
    keep = [s for s in subjects if s.kl == 0 and s.age <= max_age and bmi_min <= s.bmi <= bmi_max]
    return sorted(keep, key=lambda s: s.cmt_id)


def image_name(cmt_id: str) -> str:
    return f"oaizib_{cmt_id}_0000.nii.gz"


def label_name(cmt_id: str) -> str:
    return f"oaizib_{cmt_id}.nii.gz"


def candidate_case_id(cmt_id: str) -> str:
    return f"cand-{cmt_id}"


def candidate_title(s: Subject) -> str:
    return f"Candidate {s.cmt_id} · {s.sex} {s.age} · BMI {s.bmi:.1f}"


def extract(zip_path: Path, names: set[str], out_dir: Path) -> list[Path]:
    """Copy the members whose basename is in `names` (any folder) into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        found = {Path(i.filename).name: i for i in z.infolist() if not i.is_dir() and Path(i.filename).name in names}
        missing = sorted(set(names) - set(found))
        if missing:
            raise FileNotFoundError(f"{zip_path.name} has no {', '.join(missing)}")
        paths = []
        for name, info in sorted(found.items()):
            target = out_dir / name
            if not (target.exists() and target.stat().st_size == info.file_size):
                tmp = target.with_suffix(".part")
                with z.open(info) as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                tmp.rename(target)
            paths.append(target)
    return paths


def remove_candidates(root: Path) -> list[str]:
    """Delete data/cand-* cases registered as candidates. Returns the ids removed."""
    cases = read_index(root)
    gone = [c["case_id"] for c in cases if c.get("candidate") and c["case_id"].startswith("cand-")]
    for cid in gone:
        shutil.rmtree(Path(root) / "data" / cid, ignore_errors=True)
    write_index(root, [c for c in cases if c["case_id"] not in gone])
    return gone


def _candidates_at(dataset: Path) -> list[Subject]:
    return candidates(read_subjects(dataset / "info.zip"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["list", "extract", "build-candidates", "remove-candidates"])
    ap.add_argument("--root", type=Path, default=Path("~/datasets/OAIZIB-CM"), help="dataset folder")
    args = ap.parse_args()
    dataset = args.root.expanduser()
    cand_dir = dataset / "candidates"

    if args.command == "list":
        subs = _candidates_at(dataset)
        for s in subs:
            print(f"{s.cmt_id}  {s.split:<5}  {s.sex} {s.age}  BMI {s.bmi:.1f}  (OAI {s.subject_id})")
        print(f"{len(subs)} candidates")
    elif args.command == "extract":
        subs = _candidates_at(dataset)
        for split, img_zip, lab_zip in (("train", "imagesTr.zip", "labelsTr.zip"), ("test", "imagesTs.zip", "labelsTs.zip")):
            ids = [s.cmt_id for s in subs if s.split == split]
            if ids:
                extract(dataset / img_zip, {image_name(i) for i in ids}, cand_dir)
                extract(dataset / lab_zip, {label_name(i) for i in ids}, cand_dir)
        print(f"{len(list(cand_dir.glob('*.nii.gz')))} files in {cand_dir}")
    elif args.command == "build-candidates":
        for s in _candidates_at(dataset):
            build_case(ROOT, candidate_case_id(s.cmt_id), title=candidate_title(s), region="knee", side="right",
                       seqs=[("dess_3d", "DESS 3D", cand_dir / image_name(s.cmt_id))],
                       source=f"OAIZIB-CM candidate {s.cmt_id} (OAI baseline, KL0)", licence=LICENCE,
                       citation=CITATION, index_extra={"candidate": True})
    else:
        print("removed:", " ".join(remove_candidates(ROOT)) or "nothing")


if __name__ == "__main__":
    main()
