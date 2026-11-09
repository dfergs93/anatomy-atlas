import json
import zipfile

import pytest

from atlaslib import read_index
from mirror_case import mirror_case
from share_case import ShareError, pack, unpack
from test_save_case import make_case


def zipped(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


def manifest(**over):
    m = {"format": "anatomy-atlas share", "version": 1, "case_id": "knee-t",
         "made": "2026-11-08T00:00:00+00:00", "index_entry": {"case_id": "knee-t"}}
    m.update(over)
    return json.dumps(m)


def roots(tmp_path):
    owner, helper = tmp_path / "o", tmp_path / "h"
    owner.mkdir()
    helper.mkdir()
    return owner, helper


def files_under(root):
    return [p for p in root.rglob("*") if p.is_file()]


def test_pack_unpack_round_trip(tmp_path):
    owner, helper = roots(tmp_path)
    case = make_case(owner)
    mirror_case(owner, "knee-t")  # the owner's index entry now has "mirror"
    (case / "backups" / "x").mkdir(parents=True)
    (case / "backups" / "x" / "labels.nii.gz").write_bytes(b"old")
    z = pack(owner, "knee-t", tmp_path / "s.zip")
    names = set(zipfile.ZipFile(z).namelist())
    assert {"atlas-share.json", "knee-t/labels.nii.gz", "knee-t/volumes/dess_3d.nii.gz"} <= names
    assert not any("/backups/" in n or "/auto/" in n for n in names)
    assert unpack(helper, z) == "knee-t"
    for f in ("labels.nii.gz", "lut.json", "meta.json", "volumes/dess_3d.nii.gz"):
        assert (helper / "data/knee-t" / f).read_bytes() == (case / f).read_bytes()
    entry = next(c for c in read_index(helper) if c["case_id"] == "knee-t")
    assert "mirror" not in entry  # the helper's first save rebuilds the left copy and adds it back


def test_pack_refuses_a_mirror_and_an_unlicensed_case(tmp_path):
    owner, _ = roots(tmp_path)
    case = make_case(owner)
    mirror_case(owner, "knee-t")
    with pytest.raises(ShareError, match="knee-t"):
        pack(owner, "knee-t-left", tmp_path / "m.zip")
    with pytest.raises(ShareError, match="no case"):
        pack(owner, "nope", tmp_path / "n.zip")
    meta = json.loads((case / "meta.json").read_text())
    meta.pop("licence")
    meta["synthetic"] = False
    (case / "meta.json").write_text(json.dumps(meta))
    with pytest.raises(ShareError, match="licence"):
        pack(owner, "knee-t", tmp_path / "u.zip")
    assert not (tmp_path / "u.zip").exists()


@pytest.mark.parametrize("bad", ["../evil", "/abs", "knee-t/../../evil", "other/x", "knee-t\\..\\x"])
def test_unpack_refuses_paths_outside_the_case(tmp_path, bad):
    _, helper = roots(tmp_path)
    z = zipped(tmp_path / "bad.zip", {"atlas-share.json": manifest(), "knee-t/meta.json": "{}", bad: "x"})
    with pytest.raises(ShareError):
        unpack(helper, z)
    assert files_under(helper) == []


def test_unpack_refuses_over_paint_unless_replace(tmp_path):
    owner, helper = roots(tmp_path)
    case = make_case(owner)
    z = pack(owner, "knee-t", tmp_path / "s.zip")
    unpack(helper, z)
    mine = helper / "data/knee-t/labels.nii.gz"
    mine.write_bytes(b"my paint")
    with pytest.raises(ShareError, match="--replace"):
        unpack(helper, z)
    assert mine.read_bytes() == b"my paint"
    unpack(helper, z, replace=True)
    backups = list((helper / "data/knee-t/backups").iterdir())
    assert len(backups) == 1 and (backups[0] / "labels.nii.gz").read_bytes() == b"my paint"
    assert mine.read_bytes() == (case / "labels.nii.gz").read_bytes()


def test_unpack_fills_a_folder_holding_only_tracked_json(tmp_path):
    owner, helper = roots(tmp_path)
    case = make_case(owner)
    z = pack(owner, "knee-t", tmp_path / "s.zip")
    folder = helper / "data/knee-t"
    folder.mkdir(parents=True)
    for f in ("lut.json", "meta.json", "points.json"):
        (folder / f).write_text("[]")
    assert unpack(helper, z) == "knee-t"
    assert (folder / "labels.nii.gz").read_bytes() == (case / "labels.nii.gz").read_bytes()
    assert (folder / "meta.json").read_bytes() == (case / "meta.json").read_bytes()


@pytest.mark.parametrize("members", [
    {"knee-t/meta.json": "{}"},
    {"atlas-share.json": manifest(format="other"), "knee-t/meta.json": "{}"},
    {"atlas-share.json": manifest(version=2), "knee-t/meta.json": "{}"},
    {"atlas-share.json": manifest(case_id="../x"), "knee-t/meta.json": "{}"},
    {"atlas-share.json": manifest(index_entry=["knee-t"]), "knee-t/meta.json": "{}"},
    {"atlas-share.json": manifest(index_entry={"case_id": "other"}), "knee-t/meta.json": "{}"},
])
def test_unpack_refuses_a_bad_manifest(tmp_path, members):
    _, helper = roots(tmp_path)
    with pytest.raises(ShareError):
        unpack(helper, zipped(tmp_path / "bad.zip", members))
    assert files_under(helper) == []
