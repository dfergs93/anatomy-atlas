#!/usr/bin/env python3
"""Generate demo/placeholder data for the anatomy atlas.

Creates sample PNG slices, overlay PNGs, and label JSON files for all v1 CT cases.
The generated images are simple gradients/noise patterns — they serve as placeholder
data so the API and viewer work end-to-end without real medical imaging data.

Usage:
    python generate_demo_data.py
"""

import json
import math
import os
import struct
import zlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent / "data"
LABELS_DIR = Path(__file__).parent / "labels"
IMG_SIZE = 512

# Structure polygon definitions per body region (approximate anatomical positions)
# Coordinates are in pixel space relative to 512x512 image

CARDIAC_STRUCTURES = {
    "left_ventricle": {
        "name": "Left Ventricle",
        "ta2": "Ventriculus sinister",
        "color": [220, 50, 50],
        "polygon": [[280, 240], [310, 260], [320, 300], [310, 340], [280, 360],
                     [250, 340], [240, 300], [250, 260]],
    },
    "right_ventricle": {
        "name": "Right Ventricle",
        "ta2": "Ventriculus dexter",
        "color": [50, 100, 220],
        "polygon": [[200, 230], [240, 240], [250, 280], [250, 320], [240, 350],
                     [200, 360], [170, 340], [160, 300], [170, 260]],
    },
    "left_atrium": {
        "name": "Left Atrium",
        "ta2": "Atrium sinistrum",
        "color": [220, 100, 100],
        "polygon": [[300, 180], [340, 190], [350, 220], [340, 240], [300, 245],
                     [270, 235], [260, 210], [270, 190]],
    },
    "right_atrium": {
        "name": "Right Atrium",
        "ta2": "Atrium dextrum",
        "color": [100, 100, 220],
        "polygon": [[180, 180], [220, 175], [240, 195], [240, 225], [220, 240],
                     [180, 235], [160, 215], [160, 195]],
    },
    "aorta": {
        "name": "Ascending Aorta",
        "ta2": "Aorta ascendens",
        "color": [255, 80, 80],
        "polygon": [[250, 150], [270, 150], [275, 170], [270, 185], [250, 185],
                     [245, 170]],
    },
    "pulmonary_trunk": {
        "name": "Pulmonary Trunk",
        "ta2": "Truncus pulmonalis",
        "color": [80, 80, 255],
        "polygon": [[215, 145], [235, 145], [240, 165], [235, 180], [215, 180],
                     [210, 165]],
    },
    "interventricular_septum": {
        "name": "Interventricular Septum",
        "ta2": "Septum interventriculare",
        "color": [200, 150, 50],
        "polygon": [[248, 255], [255, 255], [258, 300], [255, 345], [248, 345],
                     [245, 300]],
    },
    "pericardium": {
        "name": "Pericardium",
        "ta2": "Pericardium",
        "color": [180, 180, 80],
        "polygon": [[150, 150], [350, 150], [380, 200], [390, 300], [380, 380],
                     [300, 400], [200, 400], [130, 380], [120, 300], [130, 200]],
    },
}

CHEST_STRUCTURES = {
    "right_lung": {
        "name": "Right Lung",
        "ta2": "Pulmo dexter",
        "color": [150, 200, 255],
        "polygon": [[80, 100], [200, 80], [220, 120], [230, 200], [230, 350],
                     [200, 420], [100, 430], [60, 380], [50, 250], [60, 150]],
    },
    "left_lung": {
        "name": "Left Lung",
        "ta2": "Pulmo sinister",
        "color": [150, 200, 255],
        "polygon": [[290, 120], [320, 80], [430, 100], [450, 150], [460, 250],
                     [450, 380], [410, 430], [310, 420], [280, 350], [280, 200]],
    },
    "aorta": {
        "name": "Descending Aorta",
        "ta2": "Aorta descendens",
        "color": [255, 80, 80],
        "polygon": [[240, 270], [260, 270], [265, 290], [260, 310], [240, 310],
                     [235, 290]],
    },
    "trachea": {
        "name": "Trachea",
        "ta2": "Trachea",
        "color": [50, 50, 50],
        "polygon": [[245, 80], [265, 80], [268, 100], [265, 120], [245, 120],
                     [242, 100]],
    },
    "esophagus": {
        "name": "Esophagus",
        "ta2": "Oesophagus",
        "color": [200, 150, 100],
        "polygon": [[250, 130], [262, 130], [264, 150], [262, 165], [250, 165],
                     [248, 150]],
    },
    "thoracic_vertebra": {
        "name": "Thoracic Vertebra",
        "ta2": "Vertebra thoracica",
        "color": [240, 240, 220],
        "polygon": [[230, 350], [280, 350], [290, 370], [290, 410], [280, 430],
                     [230, 430], [220, 410], [220, 370]],
    },
    "sternum": {
        "name": "Sternum",
        "ta2": "Sternum",
        "color": [240, 230, 200],
        "polygon": [[248, 40], [264, 40], [268, 60], [268, 80], [264, 90],
                     [248, 90], [244, 80], [244, 60]],
    },
    "diaphragm": {
        "name": "Diaphragm",
        "ta2": "Diaphragma",
        "color": [180, 120, 80],
        "polygon": [[60, 430], [200, 450], [256, 460], [310, 450], [450, 430],
                     [460, 445], [310, 465], [256, 475], [200, 465], [50, 445]],
    },
}

ABDOMEN_STRUCTURES = {
    "liver": {
        "name": "Liver",
        "ta2": "Hepar",
        "color": [160, 80, 50],
        "polygon": [[250, 80], [400, 90], [440, 130], [450, 200], [420, 280],
                     [350, 300], [280, 290], [250, 250], [240, 180], [240, 120]],
    },
    "spleen": {
        "name": "Spleen",
        "ta2": "Splen",
        "color": [120, 50, 80],
        "polygon": [[60, 150], [120, 130], [150, 150], [160, 200], [150, 260],
                     [110, 280], [70, 260], [50, 220], [50, 180]],
    },
    "right_kidney": {
        "name": "Right Kidney",
        "ta2": "Ren dexter",
        "color": [180, 100, 60],
        "polygon": [[370, 280], [400, 270], [420, 290], [425, 340], [420, 380],
                     [400, 400], [370, 395], [360, 360], [360, 310]],
    },
    "left_kidney": {
        "name": "Left Kidney",
        "ta2": "Ren sinister",
        "color": [180, 100, 60],
        "polygon": [[90, 280], [120, 270], [140, 290], [145, 340], [140, 380],
                     [120, 400], [90, 395], [80, 360], [80, 310]],
    },
    "pancreas": {
        "name": "Pancreas",
        "ta2": "Pancreas",
        "color": [220, 180, 120],
        "polygon": [[150, 260], [200, 250], [280, 240], [340, 250], [360, 265],
                     [340, 280], [280, 275], [200, 280], [150, 285]],
    },
    "stomach": {
        "name": "Stomach",
        "ta2": "Gaster",
        "color": [200, 160, 160],
        "polygon": [[150, 130], [220, 110], [250, 130], [260, 180], [250, 230],
                     [210, 250], [160, 240], [140, 200], [140, 160]],
    },
    "gallbladder": {
        "name": "Gallbladder",
        "ta2": "Vesica biliaris",
        "color": [80, 160, 80],
        "polygon": [[300, 250], [320, 240], [330, 255], [330, 285], [320, 300],
                     [300, 295], [295, 275]],
    },
    "abdominal_aorta": {
        "name": "Abdominal Aorta",
        "ta2": "Aorta abdominalis",
        "color": [255, 60, 60],
        "polygon": [[248, 310], [268, 310], [272, 340], [268, 370], [248, 370],
                     [244, 340]],
    },
    "portal_vein": {
        "name": "Portal Vein",
        "ta2": "Vena portae hepatis",
        "color": [100, 60, 180],
        "polygon": [[270, 200], [290, 195], [295, 215], [290, 235], [270, 240],
                     [265, 220]],
    },
    "psoas_muscle": {
        "name": "Psoas Muscle",
        "ta2": "Musculus psoas major",
        "color": [160, 100, 100],
        "polygon": [[210, 340], [240, 330], [245, 380], [240, 430], [210, 435],
                     [205, 390]],
    },
}

# Case configurations
CASES = {
    "cardiac-cta-axial": {
        "modality": "CT",
        "body_part": "cardiac",
        "plane": "axial",
        "source": "TCIA MM-WHS (demo placeholder)",
        "licence": "CC BY 4.0",
        "window": {"width": 700, "level": 100},
        "level_desc": "Mid-ventricular level",
        "structures": CARDIAC_STRUCTURES,
    },
    "ct-chest-axial": {
        "modality": "CT",
        "body_part": "chest",
        "plane": "axial",
        "source": "TotalSegmentator (demo placeholder)",
        "licence": "CC BY 4.0",
        "window": {"width": 400, "level": 40},
        "level_desc": "T4 vertebral body — carina level",
        "structures": CHEST_STRUCTURES,
    },
    "ct-abdomen-axial": {
        "modality": "CT",
        "body_part": "abdomen",
        "plane": "axial",
        "source": "TotalSegmentator (demo placeholder)",
        "licence": "CC BY 4.0",
        "window": {"width": 400, "level": 40},
        "level_desc": "L1 vertebral body — portal venous phase",
        "structures": ABDOMEN_STRUCTURES,
    },
    "ct-head-axial": {
        "modality": "CT",
        "body_part": "head",
        "plane": "axial",
        "source": "TotalSegmentator (demo placeholder)",
        "licence": "CC BY 4.0",
        "window": {"width": 80, "level": 40},
        "level_desc": "Basal ganglia level",
        "structures": {},
    },
    "ct-spine-sagittal": {
        "modality": "CT",
        "body_part": "spine",
        "plane": "sagittal",
        "source": "TotalSegmentator (demo placeholder)",
        "licence": "CC BY 4.0",
        "window": {"width": 1500, "level": 300},
        "level_desc": "Midline sagittal",
        "structures": {},
    },
    "ct-neck-axial": {
        "modality": "CT",
        "body_part": "neck",
        "plane": "axial",
        "source": "TotalSegmentator (demo placeholder)",
        "licence": "CC BY 4.0",
        "window": {"width": 400, "level": 40},
        "level_desc": "C4 vertebral body — hyoid level",
        "structures": {},
    },
}


# ---------------------------------------------------------------------------
# Minimal PNG writer (no external dependencies)
# ---------------------------------------------------------------------------

def _make_png(width, height, pixels_rgb):
    """Create a PNG file as bytes from an RGB pixel array.

    pixels_rgb: list of rows, each row is list of (r, g, b) tuples.
    """
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

    raw = b""
    for row in pixels_rgb:
        raw += b"\x00"  # filter byte
        for r, g, b in row:
            raw += struct.pack("BBB", r, g, b)

    idat = chunk(b"IDAT", zlib.compress(raw, 6))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


def _make_png_rgba(width, height, pixels_rgba):
    """Create a PNG file as bytes from an RGBA pixel array."""
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))

    raw = b""
    for row in pixels_rgba:
        raw += b"\x00"
        for r, g, b, a in row:
            raw += struct.pack("BBBB", r, g, b, a)

    idat = chunk(b"IDAT", zlib.compress(raw, 6))
    iend = chunk(b"IEND", b"")
    return header + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Image generation helpers
# ---------------------------------------------------------------------------

def _point_in_polygon(x, y, polygon):
    """Ray-casting algorithm for point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def generate_ct_slice(size, window, seed=42):
    """Generate a synthetic CT-like grayscale image.

    Creates a gradient background with some circular features to vaguely
    resemble a CT cross-section.
    """
    pixels = []
    cx, cy = size // 2, size // 2
    radius = size * 0.42

    for y in range(size):
        row = []
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > radius:
                v = 10  # background (air)
            else:
                # Radial gradient simulating body
                norm = dist / radius
                base = 160 - int(60 * norm)

                # Add some circular features
                angle = math.atan2(dy, dx)
                feature = int(15 * math.sin(angle * 3 + seed) * (1 - norm))
                v = max(0, min(255, base + feature))

                # Brighter ring near edge (simulating subcutaneous fat/skin)
                if 0.85 < norm < 0.95:
                    v = min(255, v + 40)

            row.append((v, v, v))
        pixels.append(row)

    return pixels


def generate_overlay(size, structures):
    """Generate a colored overlay PNG with semi-transparent structure regions."""
    pixels = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]

    for struct_id, struct_data in structures.items():
        color = struct_data["color"]
        polygon = struct_data["polygon"]

        # Find bounding box
        min_x = max(0, min(p[0] for p in polygon) - 1)
        max_x = min(size - 1, max(p[0] for p in polygon) + 1)
        min_y = max(0, min(p[1] for p in polygon) - 1)
        max_y = min(size - 1, max(p[1] for p in polygon) + 1)

        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                if _point_in_polygon(x, y, polygon):
                    pixels[y][x] = (color[0], color[1], color[2], 100)

    return pixels


def generate_labels_json(structures):
    """Generate the labels JSON for a slice."""
    labels = []
    for struct_id, struct_data in structures.items():
        # Load full label data from labels/ directory if available
        label_file = LABELS_DIR / f"{struct_id}.json"
        description = ""
        normal_values = {}
        radiopaedia_url = ""

        if label_file.exists():
            with open(label_file) as f:
                full_label = json.load(f)
                description = full_label.get("description", "")
                normal_values = full_label.get("normal_values", {})
                radiopaedia_url = full_label.get("radiopaedia_url", "")

        labels.append({
            "id": struct_id,
            "name": struct_data["name"],
            "ta2": struct_data["ta2"],
            "polygon": struct_data["polygon"],
            "description": description,
            "normal_values": normal_values,
            "radiopaedia_url": radiopaedia_url,
        })

    return labels


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_case(case_id, config):
    """Generate all files for a single atlas case."""
    case_dir = BASE_DIR / case_id
    slices_dir = case_dir / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)

    # meta.json
    meta = {
        "modality": config["modality"],
        "body_part": config["body_part"],
        "plane": config["plane"],
        "source": config["source"],
        "licence": config["licence"],
        "structures": list(config["structures"].keys()),
    }
    with open(case_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    # index.json
    index = {
        "canonical_slice": "050",
        "slice_range": [1, 100],
        "level": config["level_desc"],
    }
    with open(case_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2)

    # Generate slice PNG
    seed = hash(case_id) % 1000
    pixels = generate_ct_slice(IMG_SIZE, config["window"], seed=seed)
    png_data = _make_png(IMG_SIZE, IMG_SIZE, pixels)
    with open(slices_dir / "050.png", "wb") as f:
        f.write(png_data)

    # Generate overlay PNG
    if config["structures"]:
        overlay_pixels = generate_overlay(IMG_SIZE, config["structures"])
        overlay_data = _make_png_rgba(IMG_SIZE, IMG_SIZE, overlay_pixels)
        with open(slices_dir / "050_overlay.png", "wb") as f:
            f.write(overlay_data)

        # Generate labels JSON
        labels = generate_labels_json(config["structures"])
        with open(slices_dir / "050_labels.json", "w") as f:
            json.dump(labels, f, indent=2)
    else:
        # Empty overlay and labels for cases without structures yet
        empty_pixels = [[(0, 0, 0, 0) for _ in range(IMG_SIZE)] for _ in range(IMG_SIZE)]
        overlay_data = _make_png_rgba(IMG_SIZE, IMG_SIZE, empty_pixels)
        with open(slices_dir / "050_overlay.png", "wb") as f:
            f.write(overlay_data)
        with open(slices_dir / "050_labels.json", "w") as f:
            json.dump([], f, indent=2)

    print(f"  Generated: {case_id} ({len(config['structures'])} structures)")


def main():
    print("Generating demo data for anatomy atlas...")
    print(f"  Image size: {IMG_SIZE}x{IMG_SIZE}")
    print(f"  Output directory: {BASE_DIR}")
    print()

    for case_id, config in CASES.items():
        generate_case(case_id, config)

    print()
    print("Done! Demo data generated successfully.")
    print(f"Total cases: {len(CASES)}")
    total_structures = sum(len(c["structures"]) for c in CASES.values())
    print(f"Total structures with polygons: {total_structures}")


if __name__ == "__main__":
    main()
