import json

import nibabel as nib
import numpy as np

from build_case import build_case


def write_nifti(path, data, affine=None):
    nib.save(nib.Nifti1Image(data, np.eye(4) if affine is None else affine), path)
    return path


def synthetic_inputs(tmp_path):
    rng = np.random.default_rng(1)
    img = write_nifti(tmp_path / "img.nii.gz", rng.integers(0, 1000, (20, 20, 20)).astype(np.int16))
    lab = np.zeros((20, 20, 20), np.uint8)
    lab[2:8, 2:8, 2:8] = 1
    lab[10:15, 10:15, 10:15] = 3
    labels = write_nifti(tmp_path / "lab.nii.gz", lab)
    return img, labels


def test_build_case_writes_case(tmp_path):
    img, labels = synthetic_inputs(tmp_path)
    meta = build_case(tmp_path, "knee-test", title="Knee test", region="knee",
                      seqs=[("dess_3d", "DESS 3D", img)], labels=labels,
                      mapping={1: "femur", 3: "tibia"}, side="right",
                      source="test", licence="CC BY-NC 4.0")
    out = tmp_path / "data" / "knee-test"
    on_disk = json.loads((out / "meta.json").read_text())
    assert on_disk == meta
    assert (meta["side"], meta["licence"], meta["reference_sequence"]) == ("right", "CC BY-NC 4.0", "dess_3d")
    lut = json.loads((out / "lut.json").read_text())
    assert sorted(lut) == ["1", "3"]
    assert lut["1"]["id"] == "femur" and lut["3"]["id"] == "tibia"
    assert lut["3"]["extent"]["sagittal"]["start_mm"] == 10
    assert nib.load(out / "labels.nii.gz").header.get_intent()[0] == "label"
    entry = json.loads((tmp_path / "data" / "index.json").read_text())[0]
    assert (entry["case_id"], entry["side"]) == ("knee-test", "right")


def test_build_case_without_labels_writes_empty_map(tmp_path):
    img, _ = synthetic_inputs(tmp_path)
    build_case(tmp_path, "cand-001", title="Candidate", region="knee",
               seqs=[("dess_3d", "DESS 3D", img)], source="test", licence="CC BY-NC 4.0",
               index_extra={"candidate": True})
    out = tmp_path / "data" / "cand-001"
    assert json.loads((out / "lut.json").read_text()) == {}
    lab = nib.load(out / "labels.nii.gz")
    assert lab.shape == (20, 20, 20) and not np.asanyarray(lab.dataobj).any()
    entry = json.loads((tmp_path / "data" / "index.json").read_text())[0]
    assert entry["candidate"] is True


def test_meniscus_parts_have_distinct_colours():
    from build_case import colour

    parts = ("anterior_horn", "body", "posterior_horn")
    for side, values in (("medial", (6, 7, 8)), ("lateral", (9, 10, 11))):
        rgb = [np.array(colour(f"{side}_meniscus_{p}", v), float) for p, v in zip(parts, values)]
        for i in range(3):
            for j in range(i + 1, 3):
                assert np.linalg.norm(rgb[i] - rgb[j]) >= 80, (side, parts[i], parts[j], rgb[i], rgb[j])
    # still distinct from the cartilage next to them
    cart = np.array(colour("medial_tibial_cartilage", 4), float)
    assert all(np.linalg.norm(np.array(colour(f"medial_meniscus_{p}", 7), float) - cart) >= 80 for p in parts)
