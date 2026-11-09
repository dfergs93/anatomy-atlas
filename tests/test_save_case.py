import json
import os

import nibabel as nib
import numpy as np
import pytest

from build_case import build_case, colour
from checklist import read_checklist
from mirror_case import mirror_case
from save_case import SaveError, case_token, save_case

CHECKLIST = """# Knee test

|id|Name|Type|Labelled|Content|
|--|----|----|--------|-------|
|femur|Femur|R|[ ]|[ ]|
|tibia|Tibia|R|[ ]|[ ]|
|patella|Patella|R|[ ]|[ ]|
|trochlea|Trochlea|P|[ ]|[ ]|
|suprapatellar_bursa|Suprapatellar bursa|E|[ ]|[ ]|
|fibula|Fibula|R|[ ]|[ ]|
"""
SHAPE = (24, 12, 10)


def make_case(root, side="right"):
    a = np.eye(4)
    a[:3, 3] = [-12, -6, -5]
    img = np.random.default_rng(1).integers(0, 900, SHAPE).astype(np.int16)
    lab = np.zeros(SHAPE, np.uint8)
    lab[2:6, 2:6, 2:6] = 1
    lab[14:20, 2:6, 2:6] = 2
    nib.save(nib.Nifti1Image(img, a), root / "img.nii.gz")
    nib.save(nib.Nifti1Image(lab, a), root / "lab.nii.gz")
    (root / "checklists").mkdir()
    (root / "checklists" / "knee.md").write_text(CHECKLIST)
    build_case(root, "knee-t", title="Knee T", region="knee", side=side,
               seqs=[("dess_3d", "DESS", root / "img.nii.gz")], labels=root / "lab.nii.gz",
               mapping={1: "femur", 2: "tibia"}, source="test", licence="x")
    return root / "data" / "knee-t"


def painted(case):
    """The case's labels as the browser's bitmap: uint8, x fastest."""
    return np.asanyarray(nib.load(case / "labels.nii.gz").dataobj).astype(np.uint8).ravel(order="F")


def snapshot(case):
    return {p.relative_to(case): p.read_bytes() for p in sorted(case.rglob("*")) if p.is_file()}


def save(root, case, bitmap, values, *, checked=(), points=(), token=None):
    return save_case(root, "knee-t", token=token or case_token(case), labels=bitmap.tobytes(),
                     values=values, checked=list(checked), points=list(points))


def paint_new(case, value=3):
    bm = painted(case).copy()
    arr = bm.reshape(SHAPE, order="F")
    arr[8:11, 7:9, 3:6] = value
    return bm


def test_save_round_trip(tmp_path):
    case = make_case(tmp_path, side="")
    before = json.loads((case / "lut.json").read_text())
    res = save(tmp_path, case, paint_new(case), {1: "femur", 2: "tibia", 3: "patella"})
    lut = json.loads((case / "lut.json").read_text())
    assert lut["3"]["id"] == "patella" and lut["3"]["rgb"] == colour("patella", 3)
    assert lut["3"]["name"] == "Patella"
    assert {k: lut[k] for k in ("1", "2")} == before
    assert len(list((case / "backups").iterdir())) == 1
    assert np.asanyarray(nib.load(case / "labels.nii.gz").dataobj).dtype == np.uint16
    assert nib.load(case / "labels.nii.gz").header.get_intent()[0] == "label"
    ticked = {r.id for r in read_checklist(tmp_path / "checklists" / "knee.md") if r.labelled}
    assert ticked == {"femur", "tibia", "patella"}
    assert res["token"] == case_token(case)
    assert res["structures"] == 3 and res["mirror"] is None
    assert res["labelled"] == ["femur", "patella", "tibia"]


def test_save_refuses_stale_token(tmp_path):
    case = make_case(tmp_path)
    token = case_token(case)
    (case / "points.json").write_text('[{"id": "trochlea", "name": "T", "xyz_mm": [0, 0, 0]}]')
    before = snapshot(case)
    with pytest.raises(SaveError, match="changed on disk") as e:
        save(tmp_path, case, paint_new(case), {1: "femur", 2: "tibia", 3: "patella"}, token=token)
    assert e.value.status == 409
    assert snapshot(case) == before


GOOD = {1: "femur", 2: "tibia", 3: "patella"}


@pytest.mark.parametrize("what", ["length", "unmapped", "duplicate_id", "unknown_id", "bad_point", "mirrored"])
def test_save_rejects_bad_payload_case_untouched(tmp_path, what):
    case = make_case(tmp_path)
    mirror_case(tmp_path, "knee-t")
    target, bm, values, points = "knee-t", paint_new(case), dict(GOOD), []
    if what == "length":
        bm = bm[:-1]
    elif what == "unmapped":
        values.pop(3)
    elif what == "duplicate_id":
        values[3] = "femur"
    elif what == "unknown_id":
        values[3] = "not_a_structure"
    elif what == "bad_point":
        points = [{"id": "trochlea", "name": "Trochlea", "xyz_mm": [1, 2]}]
    elif what == "mirrored":
        target = "knee-t-left"
    tdir = tmp_path / "data" / target
    before = {d: snapshot(tmp_path / "data" / d) for d in ("knee-t", "knee-t-left")}
    checklist = (tmp_path / "checklists" / "knee.md").read_bytes()
    with pytest.raises(SaveError) as e:
        save_case(tmp_path, target, token=case_token(tdir), labels=bm.tobytes(), values=values,
                  checked=[], points=points)
    assert e.value.status == 400
    if what == "mirrored":
        assert "knee-t" in str(e.value)
    assert {d: snapshot(tmp_path / "data" / d) for d in before} == before
    assert (tmp_path / "checklists" / "knee.md").read_bytes() == checklist
    assert not (tdir / "backups").exists()


def test_auto_dropped_only_when_changed_or_checked(tmp_path):
    case = make_case(tmp_path, side="")
    lut = json.loads((case / "lut.json").read_text())
    arr = np.asanyarray(nib.load(case / "labels.nii.gz").dataobj).astype(np.uint16)
    arr[18:22, 8:10, 2:4] = 3  # a third structure
    arr[2:4, 8:10, 7:9] = 4
    nib.save(nib.Nifti1Image(arr, np.asanyarray(nib.load(case / "labels.nii.gz").affine)), case / "labels.nii.gz")
    from atlaslib import build_lut
    base = {int(k): {**v, "auto": {"source": "t"}} for k, v in lut.items()}
    base[3] = {"id": "patella", "name": "Patella", "rgb": [1, 2, 3], "auto": {"source": "t"}}
    base[4] = {"id": "fibula", "name": "Fibula", "rgb": [1, 2, 3], "auto": {"source": "t"}}
    # femur (1) stays untouched; tibia (2) gets edited; patella (3) is checked; fibula (4) untouched too
    (case / "lut.json").write_text(json.dumps(build_lut(arr, nib.load(case / "labels.nii.gz").affine, base)))
    bm = painted(case).copy()
    bm.reshape(SHAPE, order="F")[19, 3, 3] = 0
    save(tmp_path, case, bm, {1: "femur", 2: "tibia", 3: "patella", 4: "fibula"}, checked=["patella"])
    out = json.loads((case / "lut.json").read_text())
    assert {v["id"]: "auto" in v for v in out.values()} == {
        "femur": True, "tibia": False, "patella": False, "fibula": True}
    ticked = {r.id for r in read_checklist(tmp_path / "checklists" / "knee.md") if r.labelled}
    assert ticked == {"tibia", "patella"}


def test_expected_flag_from_checklist_type(tmp_path):
    case = make_case(tmp_path, side="")
    bm = paint_new(case, 3)
    bm.reshape(SHAPE, order="F")[0:2, 9:11, 0:2] = 4
    save(tmp_path, case, bm, {1: "femur", 2: "tibia", 3: "suprapatellar_bursa", 4: "fibula"})
    lut = {v["id"]: v for v in json.loads((case / "lut.json").read_text()).values()}
    assert lut["suprapatellar_bursa"]["expected"] is True
    assert "expected" not in lut["fibula"] and "expected" not in lut["femur"]


def test_points_saved_and_ticked(tmp_path):
    case = make_case(tmp_path, side="")
    pts = [{"id": "trochlea", "name": "Trochlea", "xyz_mm": [1.5, -2, 3]}]
    res = save(tmp_path, case, painted(case), {1: "femur", 2: "tibia"}, points=pts)
    assert json.loads((case / "points.json").read_text()) == pts
    ticked = {r.id for r in read_checklist(tmp_path / "checklists" / "knee.md") if r.labelled}
    assert ticked == {"femur", "tibia", "trochlea"}
    assert "trochlea" in res["labelled"]
    index = json.loads((tmp_path / "data" / "index.json").read_text())
    assert index[0]["structure_count"] == 3


def test_save_rebuilds_mirror_labels_only(tmp_path):
    case = make_case(tmp_path)
    mirror_case(tmp_path, "knee-t")
    vol = tmp_path / "data" / "knee-t-left" / "volumes" / "dess_3d.nii.gz"
    os.utime(vol, (1_000_000, 1_000_000))
    res = save(tmp_path, case, paint_new(case), GOOD)
    assert res["mirror"] == "knee-t-left"
    assert vol.stat().st_mtime == 1_000_000
    mlut = json.loads((tmp_path / "data" / "knee-t-left" / "lut.json").read_text())
    src = json.loads((case / "lut.json").read_text())
    assert mlut["3"]["id"] == "patella"
    assert mlut["3"]["centroid_mm"][0] == pytest.approx(-src["3"]["centroid_mm"][0], abs=0.15)


def test_unrelated_folder_at_mirror_destination_refused_before_any_write(tmp_path):
    case = make_case(tmp_path)
    (tmp_path / "data" / "knee-t-left").mkdir()
    (tmp_path / "data" / "knee-t-left" / "notes.txt").write_text("mine")
    before = snapshot(tmp_path / "data")
    with pytest.raises(SaveError, match="knee-t-left") as e:
        save(tmp_path, case, paint_new(case), GOOD)
    assert e.value.status == 400
    assert snapshot(tmp_path / "data") == before
    assert not (case / "backups").exists()


def test_sided_case_not_in_index_saves_with_warning(tmp_path):
    case = make_case(tmp_path)
    (tmp_path / "data" / "index.json").write_text("[]")
    res = save(tmp_path, case, paint_new(case), GOOD)
    assert res["mirror"] is None and res["token"] == case_token(case)
    assert any("index.json" in w for w in res["warnings"])
    assert not (tmp_path / "data" / "knee-t-left").exists()
    assert json.loads((case / "lut.json").read_text())["3"]["id"] == "patella"


def test_late_failure_becomes_warning_after_files_written(tmp_path, monkeypatch):
    import save_case as sc
    case = make_case(tmp_path)

    def boom(*a, **k):
        raise OSError("disk says no")
    monkeypatch.setattr(sc, "set_labelled", boom)
    monkeypatch.setattr(sc, "mirror_case", boom)
    res = save(tmp_path, case, paint_new(case), GOOD)
    assert res["token"] == case_token(case)
    assert len(res["warnings"]) == 2 and all("disk says no" in w for w in res["warnings"])
    assert json.loads((case / "lut.json").read_text())["3"]["id"] == "patella"


def test_clean_save_has_empty_warnings(tmp_path):
    case = make_case(tmp_path, side="")
    assert save(tmp_path, case, paint_new(case), GOOD)["warnings"] == []


def test_absent_value_with_unknown_id_does_not_block_save(tmp_path):
    # The page keeps an erased structure's id mapped (so an undo back past a save restores it under its
    # own name); while its voxels are gone the id may be on neither the checklist nor lut.json.
    case = make_case(tmp_path, side="")
    res = save(tmp_path, case, paint_new(case), {**GOOD, 7: "not_a_structure"})
    lut = json.loads((case / "lut.json").read_text())
    assert sorted(lut) == ["1", "2", "3"] and lut["3"]["id"] == "patella"
    assert res["structures"] == 3 and res["warnings"] == []


def test_duplicate_id_among_painted_values_still_refused(tmp_path):
    case = make_case(tmp_path, side="")
    bm = paint_new(case)
    bm.reshape(SHAPE, order="F")[0:2, 9:11, 0:2] = 4
    with pytest.raises(SaveError, match="share one structure id"):
        save(tmp_path, case, bm, {**GOOD, 4: "patella"})


def test_synthetic_case_leaves_checklist_untouched(tmp_path):
    # The checklist belongs to the region: a synthetic case of that region must not rewrite it.
    case = make_case(tmp_path, side="")
    meta = json.loads((case / "meta.json").read_text())
    (case / "meta.json").write_text(json.dumps({**meta, "synthetic": True}))
    checklist = (tmp_path / "checklists" / "knee.md").read_bytes()
    res = save(tmp_path, case, paint_new(case), GOOD,
               points=[{"id": "trochlea", "name": "Trochlea", "xyz_mm": [0, 0, 0]}])
    assert (tmp_path / "checklists" / "knee.md").read_bytes() == checklist
    assert res["checklist"] == "skipped (synthetic case)" and res["warnings"] == []
    assert json.loads((case / "lut.json").read_text())["3"]["id"] == "patella"


def test_real_case_reports_checklist_updated(tmp_path):
    case = make_case(tmp_path, side="")
    assert save(tmp_path, case, paint_new(case), GOOD)["checklist"] == "updated"


def test_point_kept_after_its_checklist_row_is_removed(tmp_path):
    # Rows can come off the checklist while painting (spec §5.7); a point saved earlier must not then
    # block every save. A point id on neither the checklist nor points.json is still refused.
    case = make_case(tmp_path, side="")
    pts = [{"id": "trochlea", "name": "Trochlea", "xyz_mm": [1.5, -2, 3]}]
    save(tmp_path, case, painted(case), {1: "femur", 2: "tibia"}, points=pts)
    path = tmp_path / "checklists" / "knee.md"
    path.write_text("".join(l for l in path.read_text().splitlines(keepends=True) if not l.startswith("|trochlea|")))
    save(tmp_path, case, paint_new(case), GOOD, points=pts)
    assert json.loads((case / "points.json").read_text()) == pts
    with pytest.raises(SaveError, match="not in the checklist"):
        save(tmp_path, case, painted(case), GOOD,
             points=pts + [{"id": "gerdy_tubercle", "name": "Gerdy", "xyz_mm": [0, 0, 0]}])
