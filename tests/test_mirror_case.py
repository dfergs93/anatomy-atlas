import json

import nibabel as nib
import numpy as np
import pytest

from build_case import build_case
from mirror_case import mirror_affine, mirror_case, mirror_image

MX = np.diag([-1.0, 1.0, 1.0, 1.0])


def dess_affine():
    a = np.diag([0.36, 0.36, 0.7, 1.0])
    a[:3, 3] = [-30, -40, -20]
    return a


def test_mirror_affine_maps_voxel_to_mirrored_world():
    a = dess_affine()
    m = mirror_affine(a, 50)
    for j in (0, 7, 49):
        assert np.allclose(m @ [j, 3, 4, 1], MX @ a @ [49 - j, 3, 4, 1])


def test_mirror_keeps_ras_and_handedness():
    a = dess_affine()
    img = nib.Nifti1Image(np.zeros((50, 10, 10), np.int16), a)
    out = mirror_image(img)
    assert nib.aff2axcodes(out.affine) == ("R", "A", "S")
    assert np.sign(np.linalg.det(out.affine)) == np.sign(np.linalg.det(a))


def value_at(img, xyz):
    ijk = np.round(np.linalg.inv(img.affine) @ np.r_[xyz, 1])[:3].astype(int)
    return np.asanyarray(img.dataobj)[tuple(ijk)]


def test_mirror_oblique_affine():
    t = np.radians(10)
    rot = np.array([[np.cos(t), -np.sin(t), 0, 0], [np.sin(t), np.cos(t), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
    a = rot @ dess_affine()
    data = np.zeros((40, 40, 20), np.uint16)
    voxels = [(3, 5, 2), (10, 30, 7), (20, 20, 10), (35, 4, 15), (39, 39, 19)]
    for n, v in enumerate(voxels, start=1):
        data[v] = n
    src = nib.Nifti1Image(data, a)
    dst = mirror_image(src)
    for n, v in enumerate(voxels, start=1):
        p = (a @ np.r_[v, 1])[:3]
        assert value_at(dst, [-p[0], p[1], p[2]]) == n


def make_right_knee(root):
    """Image + labels: medial cartilage at x < 0, lateral at x > 0 (right knee, RAS)."""
    a = np.eye(4)
    a[:3, 3] = [-20, -10, -10]
    img = np.random.default_rng(3).integers(0, 900, (40, 20, 20)).astype(np.int16)
    lab = np.zeros((40, 20, 20), np.uint8)
    lab[4:10, 5:10, 5:10] = 1     # x -16 … -11
    lab[25:33, 5:10, 5:10] = 2    # x 5 … 12
    nib.save(nib.Nifti1Image(img, a), root / "img.nii.gz")
    nib.save(nib.Nifti1Image(lab, a), root / "lab.nii.gz")
    build_case(root, "knee-t", title="Knee T", region="knee", side="right",
               seqs=[("dess_3d", "DESS 3D", root / "img.nii.gz")], labels=root / "lab.nii.gz",
               mapping={1: "medial_tibial_cartilage", 2: "lateral_tibial_cartilage"},
               source="test", licence="CC BY-NC 4.0")
    (root / "data" / "knee-t" / "points.json").write_text(json.dumps(
        [{"id": "gerdys_tubercle", "name": "Gerdy’s tubercle", "xyz_mm": [8.5, 2, -3]}]))


def load(root, case_id, name):
    return json.loads((root / "data" / case_id / name).read_text())


def test_mirror_case_swaps_sides(tmp_path):
    make_right_knee(tmp_path)
    assert mirror_case(tmp_path, "knee-t") == "knee-t-left"
    src, dst = load(tmp_path, "knee-t", "lut.json"), load(tmp_path, "knee-t-left", "lut.json")
    assert dst["2"]["id"] == "lateral_tibial_cartilage"
    assert dst["2"]["centroid_mm"][0] < dst["1"]["centroid_mm"][0]
    assert dst["2"]["extent"]["sagittal"]["start_mm"] == pytest.approx(-src["2"]["extent"]["sagittal"]["end_mm"], abs=0.01)
    mirrored = nib.load(tmp_path / "data" / "knee-t-left" / "labels.nii.gz")
    assert mirrored.header.get_intent()[0] == "label"


def test_mirror_case_points_and_index(tmp_path):
    make_right_knee(tmp_path)
    mirror_case(tmp_path, "knee-t")
    assert load(tmp_path, "knee-t-left", "points.json")[0]["xyz_mm"] == [-8.5, 2, -3]
    meta = load(tmp_path, "knee-t-left", "meta.json")
    assert (meta["side"], meta["mirror_of"], meta["case_id"]) == ("left", "knee-t", "knee-t-left")
    assert meta["title"] == "Knee T · left (mirrored)"
    index = {c["case_id"]: c for c in json.loads((tmp_path / "data" / "index.json").read_text())}
    assert index["knee-t"]["mirror"] == "knee-t-left"
    assert index["knee-t-left"]["mirror_of"] == "knee-t"
    assert index["knee-t-left"]["side"] == "left"


def test_refuses_to_mirror_a_mirror(tmp_path):
    make_right_knee(tmp_path)
    mirror_case(tmp_path, "knee-t")
    with pytest.raises(ValueError):
        mirror_case(tmp_path, "knee-t-left")
