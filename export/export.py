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

# Default TotalSegmentator v2 label map (subset — extend as needed)
# Label IDs match TotalSegmentator v2 class_map['total'] exactly.
DEFAULT_STRUCTURE_MAP = {
    # Abdominal organs
    1:  {"id": "spleen", "name": "Spleen", "ta2": "Splen"},
    2:  {"id": "right_kidney", "name": "Right Kidney", "ta2": "Ren dexter"},
    3:  {"id": "left_kidney", "name": "Left Kidney", "ta2": "Ren sinister"},
    4:  {"id": "gallbladder", "name": "Gallbladder", "ta2": "Vesica biliaris"},
    5:  {"id": "liver", "name": "Liver", "ta2": "Hepar"},
    6:  {"id": "stomach", "name": "Stomach", "ta2": "Gaster"},
    7:  {"id": "pancreas", "name": "Pancreas", "ta2": "Pancreas"},
    8:  {"id": "adrenal_glands", "name": "Right Adrenal Gland", "ta2": "Glandula suprarenalis dextra"},
    9:  {"id": "adrenal_glands", "name": "Left Adrenal Gland", "ta2": "Glandula suprarenalis sinistra"},
    # Lung lobes (TotalSegmentator v2: left lobes are 10–11, right lobes are 12–14)
    10: {"id": "left_lung", "name": "Left Upper Lobe", "ta2": "Lobus superior pulmonis sinistri"},
    11: {"id": "left_lung", "name": "Left Lower Lobe", "ta2": "Lobus inferior pulmonis sinistri"},
    12: {"id": "right_lung", "name": "Right Upper Lobe", "ta2": "Lobus superior pulmonis dextri"},
    13: {"id": "right_lung", "name": "Right Middle Lobe", "ta2": "Lobus medius pulmonis dextri"},
    14: {"id": "right_lung", "name": "Right Lower Lobe", "ta2": "Lobus inferior pulmonis dextri"},
    # Mediastinal airways
    15: {"id": "esophagus", "name": "Esophagus", "ta2": "Oesophagus"},
    16: {"id": "trachea", "name": "Trachea", "ta2": "Trachea"},
    17: {"id": "thyroid_gland", "name": "Thyroid Gland", "ta2": "Glandula thyroidea"},
    # Cardiovascular
    51: {"id": "heart", "name": "Heart", "ta2": "Cor"},
    52: {"id": "aorta", "name": "Aorta", "ta2": "Aorta"},
    53: {"id": "pulmonary_vein", "name": "Pulmonary Vein", "ta2": "Vena pulmonalis"},
    62: {"id": "superior_vena_cava", "name": "Superior Vena Cava", "ta2": "Vena cava superior"},
    63: {"id": "inferior_vena_cava", "name": "Inferior Vena Cava", "ta2": "Vena cava inferior"},
    64: {"id": "portal_vein", "name": "Portal Vein", "ta2": "Vena portae hepatis"},
    # Thoracic vertebrae
    36: {"id": "thoracic_vertebra", "name": "T8 Vertebra", "ta2": "Vertebra thoracica VIII"},
    37: {"id": "thoracic_vertebra", "name": "T7 Vertebra", "ta2": "Vertebra thoracica VII"},
    38: {"id": "thoracic_vertebra", "name": "T6 Vertebra", "ta2": "Vertebra thoracica VI"},
    39: {"id": "thoracic_vertebra", "name": "T5 Vertebra", "ta2": "Vertebra thoracica V"},
    40: {"id": "thoracic_vertebra", "name": "T4 Vertebra", "ta2": "Vertebra thoracica IV"},
    41: {"id": "thoracic_vertebra", "name": "T3 Vertebra", "ta2": "Vertebra thoracica III"},
    # Ribs and sternum
    92:  {"id": "rib", "name": "Left 1st Rib", "ta2": "Costa I sinistra"},
    93:  {"id": "rib", "name": "Left 2nd Rib", "ta2": "Costa II sinistra"},
    94:  {"id": "rib", "name": "Left 3rd Rib", "ta2": "Costa III sinistra"},
    95:  {"id": "rib", "name": "Left 4th Rib", "ta2": "Costa IV sinistra"},
    96:  {"id": "rib", "name": "Left 5th Rib", "ta2": "Costa V sinistra"},
    97:  {"id": "rib", "name": "Left 6th Rib", "ta2": "Costa VI sinistra"},
    98:  {"id": "rib", "name": "Left 7th Rib", "ta2": "Costa VII sinistra"},
    99:  {"id": "rib", "name": "Left 8th Rib", "ta2": "Costa VIII sinistra"},
    100: {"id": "rib", "name": "Left 9th Rib", "ta2": "Costa IX sinistra"},
    101: {"id": "rib", "name": "Left 10th Rib", "ta2": "Costa X sinistra"},
    102: {"id": "rib", "name": "Left 11th Rib", "ta2": "Costa XI sinistra"},
    103: {"id": "rib", "name": "Left 12th Rib", "ta2": "Costa XII sinistra"},
    104: {"id": "rib", "name": "Right 1st Rib", "ta2": "Costa I dextra"},
    105: {"id": "rib", "name": "Right 2nd Rib", "ta2": "Costa II dextra"},
    106: {"id": "rib", "name": "Right 3rd Rib", "ta2": "Costa III dextra"},
    107: {"id": "rib", "name": "Right 4th Rib", "ta2": "Costa IV dextra"},
    108: {"id": "rib", "name": "Right 5th Rib", "ta2": "Costa V dextra"},
    109: {"id": "rib", "name": "Right 6th Rib", "ta2": "Costa VI dextra"},
    110: {"id": "rib", "name": "Right 7th Rib", "ta2": "Costa VII dextra"},
    111: {"id": "rib", "name": "Right 8th Rib", "ta2": "Costa VIII dextra"},
    112: {"id": "rib", "name": "Right 9th Rib", "ta2": "Costa IX dextra"},
    113: {"id": "rib", "name": "Right 10th Rib", "ta2": "Costa X dextra"},
    114: {"id": "rib", "name": "Right 11th Rib", "ta2": "Costa XI dextra"},
    115: {"id": "rib", "name": "Right 12th Rib", "ta2": "Costa XII dextra"},
    116: {"id": "sternum", "name": "Sternum", "ta2": "Sternum"},
    # Spine (lumbar and lower thoracic for abdomen slices)
    29: {"id": "lumbar_vertebra", "name": "L3 Vertebra", "ta2": "Vertebra lumbalis III"},
    30: {"id": "lumbar_vertebra", "name": "L2 Vertebra", "ta2": "Vertebra lumbalis II"},
    31: {"id": "lumbar_vertebra", "name": "L1 Vertebra", "ta2": "Vertebra lumbalis I"},
    32: {"id": "thoracic_vertebra", "name": "T12 Vertebra", "ta2": "Vertebra thoracica XII"},
    33: {"id": "thoracic_vertebra", "name": "T11 Vertebra", "ta2": "Vertebra thoracica XI"},
    34: {"id": "thoracic_vertebra", "name": "T10 Vertebra", "ta2": "Vertebra thoracica X"},
    35: {"id": "thoracic_vertebra", "name": "T9 Vertebra", "ta2": "Vertebra thoracica IX"},
    # Great vessels (additional)
    54: {"id": "aorta", "name": "Brachiocephalic Trunk", "ta2": "Truncus brachiocephalicus"},
    55: {"id": "aorta", "name": "Right Subclavian Artery", "ta2": "Arteria subclavia dextra"},
    56: {"id": "aorta", "name": "Left Subclavian Artery", "ta2": "Arteria subclavia sinistra"},
    59: {"id": "superior_vena_cava", "name": "Left Brachiocephalic Vein", "ta2": "Vena brachiocephalica sinistra"},
    60: {"id": "superior_vena_cava", "name": "Right Brachiocephalic Vein", "ta2": "Vena brachiocephalica dextra"},
    # Musculoskeletal
    71: {"id": "rib", "name": "Left Scapula", "ta2": "Scapula sinistra"},
    72: {"id": "rib", "name": "Right Scapula", "ta2": "Scapula dextra"},
    79: {"id": "thoracic_vertebra", "name": "Spinal Cord", "ta2": "Medulla spinalis"},
    86: {"id": "thoracic_vertebra", "name": "Left Paraspinal Muscles", "ta2": "Musculi autochthones dorsi sinister"},
    87: {"id": "thoracic_vertebra", "name": "Right Paraspinal Muscles", "ta2": "Musculi autochthones dorsi dexter"},
    117: {"id": "sternum", "name": "Costal Cartilages", "ta2": "Cartilagines costales"},
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
    colormap = matplotlib.colormaps.get_cmap("tab20").resampled(max(n_structures, 1))

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
