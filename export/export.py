#!/usr/bin/env python3
"""NIfTI → PNG slice exporter + polygon extractor for the anatomy atlas.

Takes a NIfTI CT volume and its TotalSegmentator multi-label map, extracts a
slice at a given index, applies windowing, renders structure overlays, and
exports:
  1. Raw CT slice as grayscale PNG
  2. Semi-transparent coloured structure overlay PNG
  3. JSON file with each structure's pixel polygon for that slice

Usage:
    python export.py \\
        --volume /path/to/ct_volume.nii.gz \\
        --labels /path/to/segmentation.nii.gz \\
        --slice-index 50 \\
        --plane axial \\
        --window soft_tissue \\
        --output-dir /path/to/output \\
        --structure-map /path/to/structure_map.json

Dependencies:
    pip install nibabel numpy matplotlib scikit-image Pillow
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
from PIL import Image
from skimage import measure

# ---------------------------------------------------------------------------
# Windowing presets (hardcoded per CLAUDE.md spec)
# ---------------------------------------------------------------------------

WINDOW_PRESETS = {
    "soft_tissue": {"width": 400, "level": 40},
    "lung":        {"width": 1500, "level": -600},
    "bone":        {"width": 1500, "level": 300},
    "brain":       {"width": 80, "level": 40},
    "cardiac_cta": {"width": 700, "level": 100},
}

# Default TotalSegmentator label map (subset — extend as needed)
DEFAULT_STRUCTURE_MAP = {
    1: {"id": "spleen", "name": "Spleen", "ta2": "Splen"},
    2: {"id": "right_kidney", "name": "Right Kidney", "ta2": "Ren dexter"},
    3: {"id": "left_kidney", "name": "Left Kidney", "ta2": "Ren sinister"},
    4: {"id": "gallbladder", "name": "Gallbladder", "ta2": "Vesica biliaris"},
    5: {"id": "liver", "name": "Liver", "ta2": "Hepar"},
    6: {"id": "stomach", "name": "Stomach", "ta2": "Gaster"},
    7: {"id": "pancreas", "name": "Pancreas", "ta2": "Pancreas"},
    8: {"id": "adrenal_glands", "name": "Right Adrenal Gland", "ta2": "Glandula suprarenalis dextra"},
    9: {"id": "adrenal_glands", "name": "Left Adrenal Gland", "ta2": "Glandula suprarenalis sinistra"},
    10: {"id": "right_lung", "name": "Right Upper Lung Lobe", "ta2": "Lobus superior pulmonis dextri"},
    11: {"id": "right_lung", "name": "Right Middle Lung Lobe", "ta2": "Lobus medius pulmonis dextri"},
    12: {"id": "right_lung", "name": "Right Lower Lung Lobe", "ta2": "Lobus inferior pulmonis dextri"},
    13: {"id": "left_lung", "name": "Left Upper Lung Lobe", "ta2": "Lobus superior pulmonis sinistri"},
    14: {"id": "left_lung", "name": "Left Lower Lung Lobe", "ta2": "Lobus inferior pulmonis sinistri"},
    15: {"id": "esophagus", "name": "Esophagus", "ta2": "Oesophagus"},
    16: {"id": "trachea", "name": "Trachea", "ta2": "Trachea"},
    17: {"id": "thymus", "name": "Thymus", "ta2": "Thymus"},
    18: {"id": "small_bowel", "name": "Small Bowel", "ta2": "Intestinum tenue"},
    19: {"id": "colon", "name": "Colon", "ta2": "Intestinum crassum"},
    20: {"id": "aorta", "name": "Aorta", "ta2": "Aorta"},
    21: {"id": "inferior_vena_cava", "name": "Inferior Vena Cava", "ta2": "Vena cava inferior"},
    22: {"id": "portal_vein", "name": "Portal Vein", "ta2": "Vena portae hepatis"},
    23: {"id": "pulmonary_trunk", "name": "Pulmonary Trunk", "ta2": "Truncus pulmonalis"},
}


def apply_window(image, width, level):
    """Apply HU windowing to a CT slice.

    Args:
        image: 2D numpy array of HU values.
        width: Window width in HU.
        level: Window level (center) in HU.

    Returns:
        2D numpy array normalized to [0, 255] uint8.
    """
    lower = level - width / 2
    upper = level + width / 2
    windowed = np.clip(image, lower, upper)
    normalized = ((windowed - lower) / (upper - lower) * 255).astype(np.uint8)
    return normalized


def extract_slice(volume, index, plane="axial"):
    """Extract a 2D slice from a 3D volume.

    Args:
        volume: 3D numpy array.
        index: Slice index along the chosen axis.
        plane: One of 'axial', 'coronal', 'sagittal'.

    Returns:
        2D numpy array.
    """
    if plane == "axial":
        return volume[:, :, index].T
    elif plane == "coronal":
        return volume[:, index, :].T
    elif plane == "sagittal":
        return volume[index, :, :].T
    else:
        raise ValueError(f"Unknown plane: {plane}")


def extract_polygons(label_slice, structure_map):
    """Extract contour polygons for each structure in the label slice.

    Args:
        label_slice: 2D numpy array of integer labels.
        structure_map: dict mapping label int → {id, name, ta2}.

    Returns:
        List of dicts with polygon coordinates per structure.
    """
    polygons = []
    unique_labels = np.unique(label_slice)

    for label_val in unique_labels:
        if label_val == 0:  # background
            continue
        if label_val not in structure_map:
            continue

        mask = (label_slice == label_val).astype(np.uint8)
        contours = measure.find_contours(mask, 0.5)

        if not contours:
            continue

        # Use the longest contour
        contour = max(contours, key=len)

        # Simplify: reduce number of points (keep every Nth point)
        n_points = len(contour)
        step = max(1, n_points // 50)  # Target ~50 points max
        simplified = contour[::step].tolist()

        # Convert to [x, y] format (contour is [row, col] = [y, x])
        polygon = [[round(pt[1], 1), round(pt[0], 1)] for pt in simplified]

        struct_info = structure_map[label_val]
        polygons.append({
            "id": struct_info["id"],
            "name": struct_info["name"],
            "ta2": struct_info["ta2"],
            "polygon": polygon,
        })

    return polygons


def generate_overlay(ct_slice_windowed, label_slice, structure_map):
    """Generate a semi-transparent coloured overlay image.

    Args:
        ct_slice_windowed: 2D uint8 array (windowed CT slice).
        label_slice: 2D integer array of structure labels.
        structure_map: dict mapping label int → structure info.

    Returns:
        RGBA PIL Image.
    """
    h, w = label_slice.shape
    overlay = np.zeros((h, w, 4), dtype=np.uint8)

    unique_labels = np.unique(label_slice)
    # Generate distinct colors using a colormap
    n_structures = len([l for l in unique_labels if l > 0 and l in structure_map])
    colormap = cm.get_cmap("tab20", max(n_structures, 1))

    color_idx = 0
    for label_val in unique_labels:
        if label_val == 0 or label_val not in structure_map:
            continue

        mask = label_slice == label_val
        color = colormap(color_idx / max(n_structures, 1))
        overlay[mask, 0] = int(color[0] * 255)
        overlay[mask, 1] = int(color[1] * 255)
        overlay[mask, 2] = int(color[2] * 255)
        overlay[mask, 3] = 100  # semi-transparent
        color_idx += 1

    return Image.fromarray(overlay, "RGBA")


def load_structure_map(path):
    """Load structure map from a JSON file.

    Expected format: {"1": {"id": "spleen", "name": "Spleen", "ta2": "Splen"}, ...}
    """
    with open(path) as f:
        data = json.load(f)
    return {int(k): v for k, v in data.items()}


def enrich_labels(polygons, labels_dir):
    """Enrich polygon data with full label information from labels/ directory.

    Args:
        polygons: List of polygon dicts from extract_polygons.
        labels_dir: Path to labels/ directory.

    Returns:
        Enriched list of polygon dicts.
    """
    labels_path = Path(labels_dir)
    for poly in polygons:
        label_file = labels_path / f"{poly['id']}.json"
        if label_file.exists():
            with open(label_file) as f:
                full_label = json.load(f)
            poly["description"] = full_label.get("description", "")
            poly["normal_values"] = full_label.get("normal_values", {})
            poly["radiopaedia_url"] = full_label.get("radiopaedia_url", "")
        else:
            poly["description"] = ""
            poly["normal_values"] = {}
            poly["radiopaedia_url"] = ""

    return polygons


def export_slice(volume_path, labels_path, slice_index, output_dir,
                 plane="axial", window_preset="soft_tissue",
                 structure_map_path=None, labels_dir=None):
    """Main export function: volume + labels → PNG + overlay + JSON.

    Args:
        volume_path: Path to NIfTI CT volume.
        labels_path: Path to NIfTI segmentation label map.
        slice_index: Integer slice index.
        output_dir: Output directory path.
        plane: 'axial', 'coronal', or 'sagittal'.
        window_preset: Key from WINDOW_PRESETS.
        structure_map_path: Optional path to custom structure map JSON.
        labels_dir: Optional path to labels/ directory for enrichment.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load volumes
    print(f"Loading CT volume: {volume_path}")
    ct_img = nib.load(volume_path)
    ct_data = ct_img.get_fdata()

    print(f"Loading label map: {labels_path}")
    label_img = nib.load(labels_path)
    label_data = label_img.get_fdata().astype(int)

    # Load structure map
    if structure_map_path:
        structure_map = load_structure_map(structure_map_path)
    else:
        structure_map = DEFAULT_STRUCTURE_MAP

    # Get windowing preset
    if window_preset not in WINDOW_PRESETS:
        print(f"Unknown window preset: {window_preset}")
        print(f"Available: {list(WINDOW_PRESETS.keys())}")
        sys.exit(1)

    window = WINDOW_PRESETS[window_preset]
    print(f"Window: {window_preset} (W:{window['width']} L:{window['level']})")

    # Extract slices
    print(f"Extracting {plane} slice at index {slice_index}")
    ct_slice = extract_slice(ct_data, slice_index, plane)
    label_slice = extract_slice(label_data, slice_index, plane)

    # Apply windowing
    ct_windowed = apply_window(ct_slice, window["width"], window["level"])

    # Pad slice ID to 3 digits
    slice_id = f"{slice_index:03d}"

    # 1. Save raw CT slice as grayscale PNG
    raw_path = output_dir / f"{slice_id}.png"
    raw_img = Image.fromarray(ct_windowed, "L")
    raw_img.save(raw_path)
    print(f"  Saved: {raw_path}")

    # 2. Save overlay PNG
    overlay_path = output_dir / f"{slice_id}_overlay.png"
    overlay_img = generate_overlay(ct_windowed, label_slice, structure_map)
    overlay_img.save(overlay_path)
    print(f"  Saved: {overlay_path}")

    # 3. Save labels JSON
    polygons = extract_polygons(label_slice, structure_map)

    # Enrich with full label data if labels_dir is provided
    if labels_dir:
        polygons = enrich_labels(polygons, labels_dir)

    labels_json_path = output_dir / f"{slice_id}_labels.json"
    with open(labels_json_path, "w") as f:
        json.dump(polygons, f, indent=2)
    print(f"  Saved: {labels_json_path} ({len(polygons)} structures)")


def main():
    parser = argparse.ArgumentParser(
        description="Export NIfTI CT slices with structure overlays and polygon labels."
    )
    parser.add_argument("--volume", required=True,
                        help="Path to NIfTI CT volume (.nii or .nii.gz)")
    parser.add_argument("--labels", required=True,
                        help="Path to NIfTI segmentation label map (.nii or .nii.gz)")
    parser.add_argument("--slice-index", type=int, required=True,
                        help="Slice index to extract")
    parser.add_argument("--plane", default="axial",
                        choices=["axial", "coronal", "sagittal"],
                        help="Slice plane (default: axial)")
    parser.add_argument("--window", default="soft_tissue",
                        choices=list(WINDOW_PRESETS.keys()),
                        help="Windowing preset (default: soft_tissue)")
    parser.add_argument("--output-dir", required=True,
                        help="Output directory for exported files")
    parser.add_argument("--structure-map",
                        help="Path to custom structure map JSON (optional)")
    parser.add_argument("--labels-dir",
                        help="Path to labels/ directory for label enrichment (optional)")

    args = parser.parse_args()

    export_slice(
        volume_path=args.volume,
        labels_path=args.labels,
        slice_index=args.slice_index,
        output_dir=args.output_dir,
        plane=args.plane,
        window_preset=args.window,
        structure_map_path=args.structure_map,
        labels_dir=args.labels_dir,
    )

    print("\nExport complete. Perform visual QC before committing:")
    print("  1. Open the raw PNG — verify anatomy is correctly windowed")
    print("  2. Open the overlay PNG — verify structure colors align with anatomy")
    print("  3. Check the labels JSON — verify polygon coordinates are reasonable")


if __name__ == "__main__":
    main()
