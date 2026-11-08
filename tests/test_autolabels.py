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
