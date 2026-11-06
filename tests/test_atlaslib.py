import json

import numpy as np

import atlaslib


def box_mask(shape=(30, 40, 20)):
    m = np.zeros(shape, bool)
    m[10:15, 20:30, 5:8] = True
    return m


def test_extents_box():
    ext = atlaslib.structure_extents(box_mask(), np.eye(4))
    assert (ext["sagittal"]["start_mm"], ext["sagittal"]["end_mm"]) == (10, 14)
    assert (ext["coronal"]["start_mm"], ext["coronal"]["end_mm"]) == (20, 29)
    assert (ext["axial"]["start_mm"], ext["axial"]["end_mm"]) == (5, 7)


def test_widest_slice_and_anchor_inside():
    m = np.zeros((30, 30, 30), bool)
    m[10:15, 10:12, 10:12] = True       # thin rod along x
    m[12, 5:20, 5:20] = True            # big plate on the x = 12 slice
    m[12, 12, 12] = False               # hole at the plate's centre: anchor must still be inside
    ext = atlaslib.structure_extents(m, np.eye(4))
    sag = ext["sagittal"]
    assert sag["widest_mm"] == 12
    assert sag["anchor_mm"][0] == 12
    i, j, k = (int(round(v)) for v in sag["anchor_mm"])
    assert m[i, j, k]


def test_extents_use_affine():
    aff = np.diag([0.5, 0.5, 0.5, 1.0])
    aff[:3, 3] = [-10, 0, 0]
    m = np.zeros((40, 10, 10), bool)
    m[10:20, 2:4, 2:4] = True
    ext = atlaslib.structure_extents(m, aff)
    assert ext["sagittal"]["start_mm"] == -5.0
    assert ext["sagittal"]["end_mm"] == -0.5


def test_build_lut_keeps_base_fields_and_skips_absent():
    arr = np.zeros((20, 20, 20), np.uint16)
    arr[2:6, 2:6, 2:6] = 1
    base = {
        1: {"id": "femur", "name": "Femur", "rgb": [1, 2, 3], "class": "bone"},
        2: {"id": "tibia", "name": "Tibia", "rgb": [4, 5, 6]},
    }
    lut = atlaslib.build_lut(arr, np.eye(4), base)
    assert list(lut) == ["1"]
    e = lut["1"]
    assert (e["id"], e["name"], e["rgb"], e["class"]) == ("femur", "Femur", [1, 2, 3], "bone")
    assert e["voxels"] == 64
    assert set(e["extent"]) == {"sagittal", "coronal", "axial"}
    assert e["extent"]["axial"]["start_mm"] == 2 and e["extent"]["axial"]["end_mm"] == 5


def test_register_case_replaces_and_patch_merges(tmp_path):
    atlaslib.register_case(tmp_path, {"case_id": "a", "title": "A"})
    atlaslib.register_case(tmp_path, {"case_id": "b", "title": "B"})
    atlaslib.register_case(tmp_path, {"case_id": "a", "title": "A2"})
    atlaslib.patch_case(tmp_path, "a", {"mirror": "a-left"})
    cases = json.loads((tmp_path / "data" / "index.json").read_text())
    assert [c["case_id"] for c in cases] == ["b", "a"]
    a = atlaslib.read_index(tmp_path)[1]
    assert a == {"case_id": "a", "title": "A2", "mirror": "a-left"}
