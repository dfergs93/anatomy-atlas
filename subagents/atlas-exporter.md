# Atlas Exporter Subagent

Runs `export/export.py` for a given NIfTI case, then performs quality control on the output.

## Prerequisites

- NIfTI CT volume file (`.nii` or `.nii.gz`)
- TotalSegmentator segmentation label map (`.nii` or `.nii.gz`)
- Python environment with dependencies: `pip install -r requirements.txt`

## Steps

### 1. Run the export

```bash
python export/export.py \
    --volume /path/to/ct_volume.nii.gz \
    --labels /path/to/segmentation.nii.gz \
    --slice-index <z-index> \
    --plane axial \
    --window <preset> \
    --output-dir data/<case-id>/slices/ \
    --labels-dir labels/
```

**Window presets:** `soft_tissue`, `lung`, `bone`, `brain`, `cardiac_cta`

### 2. Verify output files exist

After export, confirm these three files were created:
- `data/<case-id>/slices/<slice_id>.png` — raw CT slice
- `data/<case-id>/slices/<slice_id>_overlay.png` — coloured overlay
- `data/<case-id>/slices/<slice_id>_labels.json` — polygon labels

### 3. Visual QC checklist

Open each file and verify:

- [ ] **Raw PNG:** Anatomy is correctly windowed (not too bright/dark), body outline is clean
- [ ] **Overlay PNG:** Structure colors align with actual anatomy in the raw PNG
- [ ] **Polygons:** Open the labels JSON, check that polygon coordinates trace the correct structure boundaries
- [ ] **Cardiac structures (if applicable):** Extra scrutiny — automated segmentation is unreliable at cardiac resolution. Verify ventricular walls, valves, and coronary arteries manually.

### 4. Regeneration

If polygons misalign:

1. Check the segmentation label map in 3D Slicer for accuracy
2. If the segmentation is wrong, re-run TotalSegmentator or manually correct
3. Re-run `export.py` with the corrected label map
4. Re-verify the QC checklist

### 5. Create metadata files

After QC, create or update:
- `data/<case-id>/meta.json` — case metadata
- `data/<case-id>/index.json` — slice index info

Use existing cases as templates (e.g., `data/ct-chest-axial/meta.json`).
