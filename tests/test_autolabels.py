import numpy as np

import autolabels

EYE = np.eye(4)


def world_x(idx, affine):
    return (affine @ np.c_[idx, np.ones(len(idx))].T)[0]


# ---- largest component / medial–lateral split ----

def test_largest_component_drops_fragments():
    m = np.zeros((20, 20, 20), bool)
    m[2:8, 2:8, 2:8] = True        # big
    m[8, 8, 8] = True              # touches the big one only at a corner: 26-connected, kept
    m[15:17, 15:17, 15:17] = True  # separate fragment
    out = autolabels.largest_component(m)
    assert out.sum() == 6 ** 3 + 1
    assert out[8, 8, 8] and not out[15:17, 15:17, 15:17].any()
    assert not autolabels.largest_component(np.zeros((3, 3, 3), bool)).any()


def test_split_sides_assigns_by_nearer_plateau():
    a = np.diag([0.5, 0.5, 0.5, 1.0])
    a[:3, 3] = [10, -5, 3]  # voxel i is at world x = 10 + i/2
    m = np.zeros((120, 10, 10), bool)
    m[10:30, 2:8, 2:8] = True   # world x 15 … 24.5
    m[90:110, 2:8, 2:8] = True  # world x 55 … 64.5
    medial, lateral = autolabels.split_sides(m, a, medial_x=20.0, lateral_x=60.0)
    assert (medial == m & (np.arange(120) < 60)[:, None, None]).all()
    assert (lateral == m & (np.arange(120) >= 60)[:, None, None]).all()
    # a left knee has medial at higher x: the same call with the sides swapped
    medial, lateral = autolabels.split_sides(m, a, medial_x=60.0, lateral_x=20.0)
    assert medial[90:110, 2:8, 2:8].all() and lateral[10:30, 2:8, 2:8].all()


def test_split_sides_breaks_a_bridge():
    m = np.zeros((100, 20, 10), bool)
    m[10:35, 5:15, 3:7] = True   # medial meniscus
    m[65:90, 5:15, 3:7] = True   # lateral meniscus
    m[35:65, 9:11, 4:6] = True   # thin bar joining them across the midline (x = 50)
    m[56:58, 1:3, 1:3] = True    # stray fragment on the lateral side
    medial, lateral = autolabels.split_sides(m, EYE, medial_x=22.0, lateral_x=78.0)
    xm, xl = np.argwhere(medial)[:, 0], np.argwhere(lateral)[:, 0]
    assert xm.max() <= 50 and xl.min() >= 50
    assert not (medial & lateral).any()
    assert medial[10:35, 5:15, 3:7].all() and lateral[65:90, 5:15, 3:7].all()
    assert not lateral[56:58, 1:3, 1:3].any()  # the fragment is dropped


# ---- meniscus thirds ----

def c_shape(centre, mid_x, arc_deg, shape=(140, 100, 6), r=(14, 22)):
    """A flat C (1 mm voxels) round `centre`, its opening facing mid_x."""
    cx, cy = centre
    x, y, z = np.meshgrid(*[np.arange(n) for n in shape], indexing="ij")
    outward = np.sign(cx - mid_x)
    ang = np.degrees(np.arctan2(y - cy, (x - cx) * outward))
    rad = np.hypot(x - cx, y - cy)
    return (rad >= r[0]) & (rad <= r[1]) & (np.abs(ang) <= arc_deg / 2) & (z >= 2) & (z <= 4)


def check_thirds(mask, centre, mid_x):
    ant, body, post = autolabels.meniscus_thirds(mask, EYE, centre, mid_x)
    total = mask.sum()
    assert ((ant.astype(int) + body + post) == mask).all()  # no overlap, nothing left out
    for part in (ant, body, post):
        assert 0.20 <= part.sum() / total <= 0.45
    mean_y = [np.argwhere(p)[:, 1].mean() for p in (ant, body, post)]
    assert mean_y[0] > mean_y[1] > mean_y[2]  # anterior highest y, posterior lowest
    return ant, body, post


def test_thirds_on_a_c_shape():
    check_thirds(c_shape((100, 50), mid_x=70, arc_deg=280), (100, 50), 70)


def test_thirds_on_a_near_ring():
    ring = c_shape((100, 50), mid_x=70, arc_deg=330)
    ant, body, post = check_thirds(ring, (100, 50), 70)
    # neither horn wraps round to the other end: anterior stays in front of the centre, posterior behind
    assert np.argwhere(ant)[:, 1].min() > 50 and np.argwhere(post)[:, 1].max() < 50
    # the body sits on the periphery (away from the notch)
    assert np.argwhere(body)[:, 0].min() > 100


def test_thirds_mirror_side():
    c = c_shape((40, 50), mid_x=70, arc_deg=280)  # medial side of a right knee: opening faces +x
    ant, body, post = check_thirds(c, (40, 50), 70)
    assert np.argwhere(body)[:, 0].max() < 40


def test_thirds_of_nothing_is_nothing():
    parts = autolabels.meniscus_thirds(np.zeros((5, 5, 5), bool), EYE, (2, 2), 0)
    assert len(parts) == 3 and not any(p.any() for p in parts)


# ---- merging into a case ----

def base_lut():
    return {"1": {"id": "femur", "name": "Femur", "rgb": [1, 2, 3]}}


def merge(arr, lut, additions):
    return autolabels.merge_auto(arr, lut, additions, source="DOSMA test", names={"patellar_cartilage": "Patellar cartilage"},
                                 date="2026-11-07")


def test_merge_never_overwrites():
    arr = np.zeros((10, 10, 10), np.uint16)
    arr[:5] = 1
    add = np.zeros(arr.shape, bool)
    add[3:7, 2:4, 2:4] = True  # half on the femur
    out, lut, report = merge(arr, base_lut(), {"patellar_cartilage": add})
    assert (out[:5] == 1).all()
    assert (out[5:7, 2:4, 2:4] == 2).all() and (out == 2).sum() == 8
    assert report["written"]["patellar_cartilage"] == 8 and report["blocked"]["patellar_cartilage"] == 8
    assert (arr[5:] == 0).all()  # the caller's array is not changed in place


def test_rerun_replaces_own_auto_only():
    arr = np.zeros((10, 10, 10), np.uint16)
    arr[0] = 1
    add = np.zeros(arr.shape, bool)
    add[2:4, 2:4, 2:4] = True
    out, lut, _ = merge(arr, base_lut(), {"patellar_cartilage": add})
    moved = np.roll(add, 4, axis=0)
    out2, lut2, _ = merge(out, lut, {"patellar_cartilage": moved})
    assert ((out2 == 2) == moved).all()  # old voxels gone, same value
    assert (out2[0] == 1).all()
    assert lut2["2"]["id"] == "patellar_cartilage"


def test_rerun_moved_boundaries_not_blocked_by_own_old_voxels():
    arr = np.zeros((10, 10, 10), np.uint16)
    a = np.zeros(arr.shape, bool)
    a[:5] = True
    out, lut, _ = merge(arr, {}, {"medial_meniscus_body": a, "medial_meniscus_anterior_horn": ~a})
    out2, lut2, report = merge(out, lut, {"medial_meniscus_body": ~a, "medial_meniscus_anterior_horn": a})
    assert report["blocked"] == {"medial_meniscus_body": 0, "medial_meniscus_anterior_horn": 0}
    assert (out2[5:] == 1).all() and (out2[:5] == 2).all()


def test_refuses_non_auto_id_clash():
    arr = np.zeros((10, 10, 10), np.uint16)
    arr[:3] = 1
    add = np.ones(arr.shape, bool)
    out, lut, report = merge(arr, base_lut(), {"femur": add})
    assert report["refused"] == ["femur"]
    assert np.array_equal(out, arr) and lut == base_lut()


def test_new_ids_get_next_values_and_auto_key():
    from build_case import colour

    arr = np.zeros((10, 10, 10), np.uint16)
    arr[0] = 1
    arr[1] = 5
    lut = {**base_lut(), "5": {"id": "tibia", "name": "Tibia", "rgb": [4, 5, 6]}}
    a, b = np.zeros(arr.shape, bool), np.zeros(arr.shape, bool)
    a[3], b[4] = True, True
    out, lut2, _ = merge(arr, lut, {"patellar_cartilage": a, "lateral_meniscus_body": b})
    assert (out[3] == 6).all() and (out[4] == 7).all()
    assert lut2["6"] == {"id": "patellar_cartilage", "name": "Patellar cartilage", "rgb": colour("patellar_cartilage", 6),
                         "auto": {"source": "DOSMA test", "date": "2026-11-07"}}
    assert lut2["7"]["name"] == "Lateral meniscus body" and lut2["7"]["auto"]["source"] == "DOSMA test"
    assert lut2["1"] == lut["1"] and lut2["5"] == lut["5"]


# ---- the command, on a synthetic case with a fake model venv ----

import json
import sys

import nibabel as nib
import pytest

from build_case import build_case
from mirror_case import mirror_case

SHAPE = (100, 80, 20)
MED, LAT = (30, 40), (70, 40)  # plateau centres (1 mm voxels, world = voxel)


def fake_prediction():
    pred = np.zeros(SHAPE, np.uint8)
    big = (100, 80, 20)
    for centre in (MED, LAT):
        c = c_shape(centre, mid_x=50, arc_deg=290, shape=big, r=(7, 11))
        pred[c] = 4
    pred[40:60, 70:76, 10:16] = 3  # patellar cartilage
    pred[90:92, 2:4, 17:19] = 3    # a stray fragment: dropped
    return pred


def make_case(root, plateau_dy=0):
    """Right knee: femur (1) overlaps some meniscus voxels; tibial cartilage gives the plateaus
    (moved plateau_dy voxels along y from the meniscus rings)."""
    rng = np.random.default_rng(3)
    img = root / "img.nii.gz"
    nib.save(nib.Nifti1Image(rng.integers(0, 1000, SHAPE).astype(np.int16), np.eye(4)), img)
    lab = np.zeros(SHAPE, np.uint8)
    lab[20:40, 25:35, 3] = 1                 # femur: covers part of the medial C on slice 3
    y0 = 35 + plateau_dy
    lab[25:36, y0:y0 + 11, 8] = 4            # medial tibial cartilage, centroid (30, 40 + plateau_dy)
    lab[65:76, y0:y0 + 11, 8] = 5            # lateral tibial cartilage, centroid (70, 40 + plateau_dy)
    labels = root / "lab.nii.gz"
    nib.save(nib.Nifti1Image(lab, np.eye(4)), labels)
    build_case(root, "knee-t", title="Knee T", region="knee", side="right",
               seqs=[("dess_3d", "DESS 3D", img)], labels=labels,
               mapping={1: "femur", 4: "medial_tibial_cartilage", 5: "lateral_tibial_cartilage"},
               source="test", licence="test")
    return root / "data" / "knee-t"


def fake_venv(root, *, dosma_exit=0, bones=True):
    """venv-autoseg stand-in: 'python' copies a fixed DOSMA prediction to its last argument;
    'TotalSegmentator' copies a fixed bone map to its -o and leaves a marker that it ran."""
    bin_ = root / "fake-venv" / "bin"
    bin_.mkdir(parents=True)
    nib.save(nib.Nifti1Image(fake_prediction(), np.eye(4)), bin_ / "pred.nii.gz")
    b = np.zeros(SHAPE, np.uint8)
    b[45:55, 60:70, 14:18] = 1   # patella
    b[80:84, 20:24, 0:3] = 3     # fibula
    nib.save(nib.Nifti1Image(b, np.eye(4)), bin_ / "bones.nii.gz")
    py = bin_ / "python"
    py.write_text(f"#!{sys.executable}\nimport shutil, sys\nif {dosma_exit}: sys.exit({dosma_exit})\n"
                  f"shutil.copy({str(bin_ / 'pred.nii.gz')!r}, sys.argv[-1])\n")
    ts = bin_ / "TotalSegmentator"
    ts.write_text(f"#!{sys.executable}\nimport pathlib, shutil, sys\n"
                  f"pathlib.Path({str(bin_ / 'ts-ran')!r}).write_text(' '.join(sys.argv))\n"
                  f"shutil.copy({str(bin_ / 'bones.nii.gz')!r}, sys.argv[sys.argv.index('-o') + 1])\n")
    py.chmod(0o755)
    ts.chmod(0o755)
    return py


def licence(root, number):
    p = root / "config.json"
    p.write_text(json.dumps({"license_number": number} if number else {"send_usage_stats": True}))
    return p


def case_bytes(case):
    return {n: (case / n).read_bytes() for n in ("labels.nii.gz", "lut.json", "points.json", "meta.json")}


def test_refuses_mirror_case(tmp_path):
    make_case(tmp_path)
    mirror_case(tmp_path, "knee-t")
    left = tmp_path / "data" / "knee-t-left"
    before = case_bytes(left)
    with pytest.raises(SystemExit, match="mirrored copy"):
        autolabels.run(tmp_path, "knee-t-left", autoseg_python=fake_venv(tmp_path), totalseg=False)
    assert case_bytes(left) == before


def test_missing_venv_leaves_case_untouched(tmp_path):
    case = make_case(tmp_path)
    before = case_bytes(case)
    with pytest.raises(SystemExit, match="requirements-autoseg.txt"):
        autolabels.run(tmp_path, "knee-t", autoseg_python=tmp_path / "nope" / "python", totalseg=False)
    assert case_bytes(case) == before and not (case / "backups").exists()


def test_dosma_failure_leaves_case_untouched(tmp_path):
    case = make_case(tmp_path)
    before = case_bytes(case)
    with pytest.raises(SystemExit, match="DOSMA"):
        autolabels.run(tmp_path, "knee-t", autoseg_python=fake_venv(tmp_path, dosma_exit=1), totalseg=False)
    assert case_bytes(case) == before and not (case / "backups").exists()


def test_totalseg_skipped_without_licence(tmp_path, capsys):
    case = make_case(tmp_path)
    py = fake_venv(tmp_path)
    report = autolabels.run(tmp_path, "knee-t", autoseg_python=py, licence_file=licence(tmp_path, None))
    ids = {e["id"] for e in json.loads((case / "lut.json").read_text()).values()}
    assert not {"patella", "fibula"} & ids
    assert not (py.parent / "ts-ran").exists()
    assert "license-academic" in capsys.readouterr().out
    assert set(report["skipped"]) >= {"patella", "fibula"}


def test_totalseg_runs_with_licence(tmp_path):
    case = make_case(tmp_path)
    py = fake_venv(tmp_path)
    autolabels.run(tmp_path, "knee-t", autoseg_python=py, licence_file=licence(tmp_path, "aca_TEST"))
    lut = {e["id"]: e for e in json.loads((case / "lut.json").read_text()).values()}
    assert lut["patella"]["auto"]["source"] == "TotalSegmentator appendicular_bones_mr"
    assert lut["fibula"]["voxels"] == 4 * 4 * 3
    assert "--task appendicular_bones_mr" in (py.parent / "ts-ran").read_text()


def test_run_end_to_end_on_fake_prediction(tmp_path):
    case = make_case(tmp_path)
    gt_before = {v: int((np.asanyarray(nib.load(case / "labels.nii.gz").dataobj) == v).sum()) for v in (1, 4, 5)}
    report = autolabels.run(tmp_path, "knee-t", autoseg_python=fake_venv(tmp_path), totalseg=False)
    lut = json.loads((case / "lut.json").read_text())
    by_id = {e["id"]: (int(k), e) for k, e in lut.items()}
    parts = [f"{s}_meniscus_{p}" for s in ("medial", "lateral") for p in ("anterior_horn", "body", "posterior_horn")]
    for sid in parts + ["patellar_cartilage"]:
        assert by_id[sid][1]["auto"] == {"source": "DOSMA iwoai-2019-t6-normalized",
                                         "date": by_id[sid][1]["auto"]["date"]}
    arr = np.asanyarray(nib.load(case / "labels.nii.gz").dataobj)
    assert {v: int((arr == v).sum()) for v in (1, 4, 5)} == gt_before
    assert report["blocked"]["medial_meniscus_body"] + report["blocked"]["medial_meniscus_anterior_horn"] \
        + report["blocked"]["medial_meniscus_posterior_horn"] > 0  # the femur kept its voxels
    x = {sid: np.argwhere(arr == by_id[sid][0])[:, 0].mean() for sid in parts}
    y = {sid: np.argwhere(arr == by_id[sid][0])[:, 1].mean() for sid in parts}
    assert max(x[p] for p in parts[:3]) < 50 < min(x[p] for p in parts[3:])
    for s in ("medial", "lateral"):
        assert y[f"{s}_meniscus_anterior_horn"] > y[f"{s}_meniscus_body"] > y[f"{s}_meniscus_posterior_horn"]
    assert by_id["patellar_cartilage"][1]["voxels"] == 20 * 6 * 6  # the fragment is gone
    assert len(list((case / "backups").iterdir())) == 1
    assert nib.load(case / "labels.nii.gz").header.get_intent()[0] == "label"
    left = json.loads((tmp_path / "data" / "knee-t-left" / "lut.json").read_text())
    left_x = {e["id"]: e["centroid_mm"][0] for e in left.values()}
    assert left_x["medial_meniscus_body"] == -lut[str(by_id["medial_meniscus_body"][0])]["centroid_mm"][0]
    index = {c["case_id"]: c for c in json.loads((tmp_path / "data" / "index.json").read_text())}
    assert index["knee-t"]["structure_count"] == len(lut)


def test_body_sits_on_the_periphery_when_the_plateau_centre_is_off(tmp_path):
    # on knee-mri the tibial cartilage centroids sit ~7 mm behind the meniscal rings; the thirds
    # must still put each body at the side of its ring, not at the posterior corner
    case = make_case(tmp_path, plateau_dy=-7)
    autolabels.run(tmp_path, "knee-t", autoseg_python=fake_venv(tmp_path), totalseg=False)
    arr = np.asanyarray(nib.load(case / "labels.nii.gz").dataobj)
    by_id = {e["id"]: int(k) for k, e in json.loads((case / "lut.json").read_text()).items()}
    for s in ("medial", "lateral"):
        body_y = np.argwhere(arr == by_id[f"{s}_meniscus_body"])[:, 1].mean()
        assert abs(body_y - 40) < 2, (s, body_y)


def test_ring_centre_of_a_c():
    c = c_shape((100, 50), mid_x=70, arc_deg=280)
    cx, cy = autolabels.ring_centre(c, EYE)
    # y is centred; x leans ~2.6 mm outward, since the open side stops at the horn tips (x ≈ 83)
    assert abs(cy - 50) < 1 and 101 <= cx <= 104


def test_rerun_gives_the_same_labels(tmp_path):
    case = make_case(tmp_path)
    py = fake_venv(tmp_path)
    autolabels.run(tmp_path, "knee-t", autoseg_python=py, totalseg=False)
    first = (np.asanyarray(nib.load(case / "labels.nii.gz").dataobj).copy(), json.loads((case / "lut.json").read_text()))
    autolabels.run(tmp_path, "knee-t", autoseg_python=py, totalseg=False)
    assert np.array_equal(np.asanyarray(nib.load(case / "labels.nii.gz").dataobj), first[0])
    assert json.loads((case / "lut.json").read_text()) == first[1]
    assert len(list((case / "backups").iterdir())) == 2
