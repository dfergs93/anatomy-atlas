#!/usr/bin/env python3
"""Generate a SYNTHETIC knee test case for exercising the viewer.

Not anatomy. Simple geometric shapes roughly where knee structures sit, with
PD-FS-like and PD-like intensities, so the viewer (hover, click, find, planes,
sequence toggle, overlay) can be tested before real data is in place.

Writes data/demo-knee-synthetic/ and registers it in data/index.json.

    python tools/make_demo_case.py
"""
from __future__ import annotations

import json
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

from atlaslib import lut_entry, register_case

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "demo-knee-synthetic"
OUT = ROOT / "data" / CASE_ID

VOX = 0.8  # mm, isotropic
X0, X1, Y0, Y1, Z0, Z1 = -60, 60, -60, 60, -75, 75  # mm, RAS, right knee, origin at joint line
rng = np.random.default_rng(7)

xs = np.arange(X0, X1, VOX) + VOX / 2
ys = np.arange(Y0, Y1, VOX) + VOX / 2
zs = np.arange(Z0, Z1, VOX) + VOX / 2
X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
SHAPE = X.shape
AFFINE = np.diag([VOX, VOX, VOX, 1.0])
AFFINE[:3, 3] = [X0 + VOX / 2, Y0 + VOX / 2, Z0 + VOX / 2]


# ---------- primitives (all in mm) ----------
def ellipsoid(c, r):
    return ((X - c[0]) / r[0]) ** 2 + ((Y - c[1]) / r[1]) ** 2 + ((Z - c[2]) / r[2]) ** 2 <= 1


def capsule(p0, p1, r):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    t = ((X - p0[0]) * d[0] + (Y - p0[1]) * d[1] + (Z - p0[2]) * d[2]) / d.dot(d)
    t = np.clip(t, 0, 1)
    return (X - p0[0] - t * d[0]) ** 2 + (Y - p0[1] - t * d[1]) ** 2 + (Z - p0[2] - t * d[2]) ** 2 <= r * r


def band(p0, p1, r, half_width_x):
    """Flat tendon: capsules swept along x."""
    m = np.zeros(SHAPE, bool)
    for dx in np.arange(-half_width_x, half_width_x + 0.01, VOX):
        m |= capsule((p0[0] + dx, p0[1], p0[2]), (p1[0] + dx, p1[1], p1[2]), r)
    return m


def cyl_z(cx, cy, r, z0, z1):
    return ((X - cx) ** 2 + (Y - cy) ** 2 <= r * r) & (Z >= z0) & (Z <= z1)


def dilate(m, mm):
    return ndi.binary_dilation(m, iterations=max(1, round(mm / VOX)))


def erode(m, mm):
    return ndi.binary_erosion(m, iterations=max(1, round(mm / VOX)))


def meniscus(cx, cy, r_in, r_out, z_base, h, opening_deg, midline_deg, parts):
    """C-shaped wedge. parts: list of (id, start_deg, end_deg) measured from midline direction."""
    dx, dy = X - cx, Y - cy
    rr = np.hypot(dx, dy)
    ang = (np.degrees(np.arctan2(dy, dx)) - midline_deg) % 360  # 0 = facing midline
    height = h * np.clip((rr - r_in) / (r_out - r_in), 0, 1)
    ring = (rr >= r_in) & (rr <= r_out) & (Z >= z_base) & (Z <= z_base + height)
    ring &= (ang > opening_deg) & (ang < 360 - opening_deg)
    return {pid: ring & (ang >= a0) & (ang < a1) for pid, a0, a1 in parts}


# ---------- structures ----------
S: dict[str, np.ndarray] = {}

body = ((X / 55) ** 2 + ((Y + 2) / 52) ** 2 <= 1)

# muscles
S["vastus_medialis"] = ellipsoid((-25, 15, 60), (18, 18, 32)) & (Z > 15)
S["vastus_lateralis"] = ellipsoid((28, 8, 70), (16, 18, 32)) & (Z > 30)
S["semimembranosus"] = ellipsoid((-22, -35, 55), (12, 10, 40))
S["biceps_femoris"] = ellipsoid((25, -35, 55), (11, 10, 40))
S["gastrocnemius_medial_head"] = ellipsoid((-18, -38, -40), (16, 12, 50)) & (Z < 15)
S["gastrocnemius_lateral_head"] = ellipsoid((16, -38, -40), (13, 11, 50)) & (Z < 15)
S["popliteus"] = ellipsoid((0, -33, -28), (22, 5, 9))

# fat pads / fluid
S["hoffa_fat_pad"] = ellipsoid((0, 22, 2), (18, 10, 12))
S["suprapatellar_recess"] = ellipsoid((0, 14, 42), (20, 3, 16))
joint_fluid = ellipsoid((0, -5, -4), (40, 28, 5))

# tendons / ligaments
S["patellar_tendon"] = band((0, 36, -2), (0, 22, -32), 2.5, 10)
S["quadriceps_tendon"] = band((0, 38, 40), (0, 24, 75), 2.5, 12)
S["acl"] = capsule((8, -18, 8), (-3, 8, -8), 4)
S["pcl"] = capsule((-8, -2, 10), (0, -25, -14), 4.5)
xm = np.where(Z > -10, -37.5, -37.5 + (Z + 10) * (9.5 / 35))
S["mcl_superficial"] = (np.abs(X - xm) < 1.5) & (Y > -12) & (Y < 6) & (Z > -45) & (Z < 24)
S["lcl"] = capsule((35, -10, 18), (33, -22, -20), 2.5)

# vessels / nerves
S["popliteal_artery"] = capsule((-2, -38, 75), (0, -36, -60), 3.5)
S["popliteal_vein"] = capsule((4, -42, 75), (5, -41, -60), 4.5)
S["tibial_nerve"] = capsule((3, -48, 75), (2, -46, -60), 2.5)
S["common_peroneal_nerve"] = capsule((12, -46, 60), (34, -30, -34), 2)

# bones
femur = (
    cyl_z(0, -5, 14, 25, 80)
    | ellipsoid((0, -6, 27), (32, 22, 14))
    | ellipsoid((-20, -8, 11), (14, 22, 13.5))
    | ellipsoid((20, -8, 11), (14, 22, 13.5))
)
femur &= ~(((np.abs(X) < 7.5) & (Y < 0) & (Z < 22)))  # intercondylar notch
femur &= ~ellipsoid((0, 34, 14), (8, 8, 14))  # trochlear groove
tibia = (
    cyl_z(0, -5, 13, -80, -12)
    | (ellipsoid((0, -5, -22), (38, 26, 16)) & (Z <= -8))
    | (ellipsoid((0, -5, -8), (6, 8, 4)) & (np.abs(X) > 1.5))  # tibial spines
    | ellipsoid((0, 16, -30), (8, 6, 6))  # tuberosity
)
fibula = ellipsoid((30, -22, -24), (8, 8, 9)) | capsule((30, -22, -24), (27, -20, -80), 6)
patella = ellipsoid((0, 38, 18), (20, 9, 22))
S["femur"], S["tibia"], S["fibula"], S["patella"] = femur, tibia, fibula, patella

# cartilage (shells on articular surfaces)
S["femoral_cartilage"] = dilate(femur, 2.4) & ~femur & (Z < 24) & (Y > -32) & ~(Z > 14) | (
    dilate(femur, 2.4) & ~femur & (Y > 24) & (Z < 30) & (np.abs(X) < 20)
)
tib_cart = dilate(tibia, 2.4) & ~tibia & (Z > -9) & (Z < -4) & (np.abs(X) > 6)
S["medial_tibial_cartilage"] = tib_cart & (X < 0)
S["lateral_tibial_cartilage"] = tib_cart & (X > 0)
S["patellar_cartilage"] = dilate(patella, 2.4) & ~patella & (Y < 34)

# menisci (medial = -x for a right knee)
S.update(meniscus(-20, -6, 11, 20, -8, 5.5, 32, 0, [
    ("medial_meniscus_anterior_horn", 32, 110),
    ("medial_meniscus_body", 110, 250),
    ("medial_meniscus_posterior_horn", 250, 328),
]))
S.update(meniscus(20, -6, 9, 17, -8, 5.5, 18, 180, [
    ("lateral_meniscus_posterior_horn", 18, 110),
    ("lateral_meniscus_body", 110, 250),
    ("lateral_meniscus_anterior_horn", 250, 342),
]))

# paint order: later wins
ORDER = [
    "vastus_medialis", "vastus_lateralis", "semimembranosus", "biceps_femoris",
    "gastrocnemius_medial_head", "gastrocnemius_lateral_head", "popliteus",
    "hoffa_fat_pad", "suprapatellar_recess",
    "popliteal_artery", "popliteal_vein", "tibial_nerve", "common_peroneal_nerve",
    "patellar_tendon", "quadriceps_tendon", "mcl_superficial", "lcl", "acl", "pcl",
    "femoral_cartilage", "medial_tibial_cartilage", "lateral_tibial_cartilage", "patellar_cartilage",
    "medial_meniscus_anterior_horn", "medial_meniscus_body", "medial_meniscus_posterior_horn",
    "lateral_meniscus_anterior_horn", "lateral_meniscus_body", "lateral_meniscus_posterior_horn",
    "femur", "tibia", "fibula", "patella",
]

NAMES = {
    "femur": "Femur", "tibia": "Tibia", "fibula": "Fibula", "patella": "Patella",
    "femoral_cartilage": "Femoral cartilage", "medial_tibial_cartilage": "Medial tibial cartilage",
    "lateral_tibial_cartilage": "Lateral tibial cartilage", "patellar_cartilage": "Patellar cartilage",
    "medial_meniscus_anterior_horn": "Medial meniscus — anterior horn",
    "medial_meniscus_body": "Medial meniscus — body",
    "medial_meniscus_posterior_horn": "Medial meniscus — posterior horn",
    "lateral_meniscus_anterior_horn": "Lateral meniscus — anterior horn",
    "lateral_meniscus_body": "Lateral meniscus — body",
    "lateral_meniscus_posterior_horn": "Lateral meniscus — posterior horn",
    "acl": "Anterior cruciate ligament", "pcl": "Posterior cruciate ligament",
    "mcl_superficial": "MCL — superficial", "lcl": "Lateral (fibular) collateral ligament",
    "patellar_tendon": "Patellar tendon", "quadriceps_tendon": "Quadriceps tendon",
    "vastus_medialis": "Vastus medialis", "vastus_lateralis": "Vastus lateralis",
    "semimembranosus": "Semimembranosus", "biceps_femoris": "Biceps femoris",
    "gastrocnemius_medial_head": "Gastrocnemius — medial head",
    "gastrocnemius_lateral_head": "Gastrocnemius — lateral head", "popliteus": "Popliteus",
    "hoffa_fat_pad": "Infrapatellar (Hoffa) fat pad", "suprapatellar_recess": "Suprapatellar recess",
    "popliteal_artery": "Popliteal artery", "popliteal_vein": "Popliteal vein",
    "tibial_nerve": "Tibial nerve", "common_peroneal_nerve": "Common peroneal (fibular) nerve",
}

CLASS = {  # (rgb, PD-FS intensity, PD intensity)
    "bone": ((233, 214, 170), 200, 900),
    "cartilage": ((70, 140, 230), 800, 700),
    "meniscus": ((150, 90, 210), 60, 80),
    "ligament": ((235, 120, 40), 60, 80),
    "tendon": ((240, 200, 40), 60, 80),
    "muscle": ((205, 70, 80), 450, 550),
    "artery": ((220, 30, 30), 50, 50),
    "vein": ((60, 90, 220), 600, 500),
    "nerve": ((120, 210, 60), 700, 500),
    "fat": ((250, 235, 140), 250, 1000),
    "fluid": ((60, 200, 220), 1400, 1100),
}


def klass(sid: str) -> str:
    if sid in ("femur", "tibia", "fibula", "patella"):
        return "bone"
    if "cartilage" in sid:
        return "cartilage"
    if "meniscus" in sid:
        return "meniscus"
    if sid in ("acl", "pcl", "mcl_superficial", "lcl"):
        return "ligament"
    if "tendon" in sid:
        return "tendon"
    if sid.endswith("artery"):
        return "artery"
    if sid.endswith("vein"):
        return "vein"
    if sid.endswith("nerve"):
        return "nerve"
    if "fat_pad" in sid:
        return "fat"
    if "recess" in sid:
        return "fluid"
    return "muscle"


def jitter(rgb, i):
    f = 0.82 + 0.36 * ((i * 0.618) % 1)
    return [int(min(255, max(0, c * f))) for c in rgb]


def main() -> None:
    labels = np.zeros(SHAPE, np.uint16)
    pdfs = np.where(body, 250.0, 0.0)
    pd = np.where(body, 1000.0, 0.0)
    pdfs[joint_fluid & body], pd[joint_fluid & body] = 1400, 1100

    lut = {}
    for i, sid in enumerate(ORDER, start=1):
        m = S[sid] & body
        labels[m] = i
    for i, sid in enumerate(ORDER, start=1):
        m = labels == i
        k = klass(sid)
        rgb, a, b = CLASS[k]
        pdfs[m], pd[m] = a, b
        if k == "bone":  # dark cortex
            cortex = m & ~erode(m, 1.6)
            pdfs[cortex], pd[cortex] = 60, 60
        if m.any():
            lut[str(i)] = {**lut_entry(m, AFFINE, sid, NAMES[sid], jitter(rgb, i)), "class": k}

    # MRI-ish: blur, bias field, noise
    bias = 1 + 0.12 * (Y / 60) - 0.06 * (np.abs(Z) / 75)
    vols = {}
    for name, img in (("pd_fs_3d", pdfs), ("pd_3d", pd)):
        img = ndi.gaussian_filter(img, 0.7) * bias
        img = np.abs(img + rng.normal(0, 22, SHAPE) + 1j * rng.normal(0, 22, SHAPE))
        vols[name] = img.astype(np.int16)

    (OUT / "volumes").mkdir(parents=True, exist_ok=True)
    seqs = []
    for name, label in (("pd_fs_3d", "PD-FS 3D"), ("pd_3d", "PD 3D")):
        img = vols[name]
        nz = img[body]
        wl = [float(np.percentile(nz, 1)), float(np.percentile(nz, 99.5))]
        nii = nib.Nifti1Image(img, AFFINE)
        nii.header.set_xyzt_units("mm")
        nib.save(nii, OUT / "volumes" / f"{name}.nii.gz")
        seqs.append({"id": name, "label": label, "file": f"volumes/{name}.nii.gz",
                     "cal_min": round(wl[0]), "cal_max": round(wl[1])})
    lab = nib.Nifti1Image(labels, AFFINE)
    lab.header.set_xyzt_units("mm")
    lab.header.set_intent("label")  # NIFTI_INTENT_LABEL (1002): NiiVue atlas outline/highlight
    nib.save(lab, OUT / "labels.nii.gz")

    points = [
        {"id": "medial_femoral_condyle", "name": "Medial femoral condyle", "xyz_mm": [-20, -8, 4]},
        {"id": "lateral_femoral_condyle", "name": "Lateral femoral condyle", "xyz_mm": [20, -8, 4]},
        {"id": "intercondylar_notch", "name": "Intercondylar notch", "xyz_mm": [0, -14, 12]},
        {"id": "intercondylar_eminence", "name": "Intercondylar eminence", "xyz_mm": [3, -5, -6]},
        {"id": "tibial_tuberosity", "name": "Tibial tuberosity", "xyz_mm": [0, 21, -30]},
        {"id": "gerdys_tubercle", "name": "Gerdy’s tubercle", "xyz_mm": [27, 13, -16]},
    ]

    meta = {
        "case_id": CASE_ID,
        "title": "Knee — synthetic test case",
        "region": "knee",
        "side": "right",
        "modality": "MR",
        "synthetic": True,
        "source": "Generated by tools/make_demo_case.py — geometric shapes, NOT anatomy",
        "licence": "Same as this repo",
        "citation": "",
        "reference_sequence": "pd_fs_3d",
        "sequences": seqs,
        "default_plane": "sagittal",
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    (OUT / "lut.json").write_text(json.dumps(lut, indent=1, ensure_ascii=False) + "\n")
    (OUT / "points.json").write_text(json.dumps(points, indent=2, ensure_ascii=False) + "\n")

    register_case(ROOT, {"case_id": CASE_ID, "title": meta["title"], "region": "knee", "modality": "MR",
                         "sequences": [s["id"] for s in seqs], "structure_count": len(lut) + len(points),
                         "synthetic": True, "side": "right"})
    print(f"wrote {OUT.relative_to(ROOT)}  shape={SHAPE}  regions={len(lut)}  points={len(points)}")


if __name__ == "__main__":
    main()
