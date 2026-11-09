#!/usr/bin/env python3
"""Hand a case to a helper who paints on their own computer (spec §5.6).

    python tools/share_case.py pack knee-mri [-o FILE]     # on the owner's machine
    python tools/share_case.py unpack FILE [--replace]     # on the helper's machine

The zip holds atlas-share.json, then <case>/meta.json, lut.json, points.json (when
present), labels.nii.gz and every sequence file. Never backups/ or auto/.
Standard library plus requirements.txt only: the helper may be on Windows.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from atlaslib import backup_case, read_index, register_case

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "atlas-share.json"
FORMAT = "anatomy-atlas share"
CASE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class ShareError(Exception):
    pass


def _entry_without_mirror(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k != "mirror"}


def pack(root: Path, case_id: str, out: Path | None = None) -> Path:
    root = Path(root)
    case = root / "data" / case_id
    meta_path = case / "meta.json"
    if not meta_path.is_file():
        raise ShareError(f"no case {case_id}")
    meta = json.loads(meta_path.read_text())
    if meta.get("mirror_of"):
        raise ShareError(f"{case_id} is a mirrored copy; pack {meta['mirror_of']} instead")
    if not meta.get("synthetic") and not meta.get("licence"):
        raise ShareError(f"record the dataset's licence in data/{case_id}/meta.json first")

    names = ["meta.json", "lut.json", "points.json", "labels.nii.gz"]
    names += [s["file"] for s in meta.get("sequences", [])]
    for name in ("labels.nii.gz", *(s["file"] for s in meta.get("sequences", []))):
        if not (case / name).is_file():
            raise ShareError(f"data/{case_id}/{name} is missing")
    names = [n for n in dict.fromkeys(names) if (case / n).is_file()]

    entry = next((c for c in read_index(root) if c["case_id"] == case_id), None)
    if entry is None:
        entry = {"case_id": meta.get("case_id", case_id)}
        entry.update({k: meta[k] for k in ("title", "region", "modality", "side", "synthetic") if k in meta})
    manifest = {"format": FORMAT, "version": 1, "case_id": case_id,
                "made": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "index_entry": _entry_without_mirror(entry)}

    if out is None:
        downloads = Path.home() / "Downloads"
        folder = downloads if downloads.is_dir() else Path.cwd()
        out = folder / f"{case_id}-share-{datetime.now().strftime('%Y%m%d')}.zip"
    out = Path(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST, json.dumps(manifest, indent=2) + "\n")
        for n in names:
            z.write(case / n, f"{case_id}/{n}")
    print(f"Licence: {meta.get('licence', '(synthetic)')}")
    if meta.get("sharing"):
        print(f"Sharing: {meta['sharing']}")
    print(out)
    return out


def _check_member(name: str, case_id: str) -> None:
    bad = (not name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name)
           or any(p in ("", ".", "..") for p in name.rstrip("/").split("/")))
    parts = name.rstrip("/").split("/")
    if bad or len(parts) < 2 or parts[0] != case_id:
        raise ShareError(f"unsafe or unexpected file in the zip: {name!r}")


def unpack(root: Path, zip_path: Path, *, replace: bool = False) -> str:
    root = Path(root)
    try:
        z = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as e:
        raise ShareError(f"{zip_path} is not a readable zip ({e})")
    with z:
        try:
            manifest = json.loads(z.read(MANIFEST))
        except (KeyError, ValueError):
            raise ShareError(f"{zip_path} has no readable {MANIFEST}; was it made by share_case.py pack?")
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
            raise ShareError(f"{MANIFEST} is not an {FORMAT} file")
        if manifest.get("version") != 1:
            raise ShareError(f"{MANIFEST} is version {manifest.get('version')!r}; this tool reads version 1")
        case_id = manifest.get("case_id")
        if not isinstance(case_id, str) or not CASE_ID.match(case_id):
            raise ShareError(f"{MANIFEST} has an invalid case_id {case_id!r}")
        entry = manifest.get("index_entry")
        if not isinstance(entry, dict) or entry.get("case_id") != case_id:
            raise ShareError(f"{MANIFEST} has an index_entry that does not match case {case_id}")

        members = [i for i in z.infolist() if i.filename != MANIFEST and not i.is_dir()]
        for i in z.infolist():
            if i.filename != MANIFEST:
                _check_member(i.filename, case_id)
        if f"{case_id}/meta.json" not in {i.filename for i in members}:
            raise ShareError(f"the zip has no {case_id}/meta.json")

        case = root / "data" / case_id
        if (case / "labels.nii.gz").exists():
            if not replace:
                raise ShareError(f"data/{case_id} already has a label map (your paint?). Download your paint "
                                 "file first, then run unpack again with --replace (it keeps a backup).")
            backup_case(case)

        for i in members:
            dest = root / "data" / PurePosixPath(i.filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            with z.open(i) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.replace(tmp, dest)
    register_case(root, _entry_without_mirror(entry))
    return case_id


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack", help="zip a case for a helper")
    p.add_argument("case")
    p.add_argument("-o", "--out", type=Path)
    u = sub.add_parser("unpack", help="install a case from a zip")
    u.add_argument("file", type=Path)
    u.add_argument("--replace", action="store_true", help="overwrite an existing label map (keeps a backup)")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "pack":
            pack(ROOT, args.case, args.out)
        else:
            cid = unpack(ROOT, args.file, replace=args.replace)
            print(f"Unpacked {cid}. Start the server: python tools/serve.py — then open "
                  f"http://127.0.0.1:8004/viewer/?case={cid}&mode=author")
    except ShareError as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
