# CLAUDE.md — anatomy-atlas

> Self-hosted cross-sectional anatomy atlas — pre-rendered PNG slices · SVG label overlays · FastAPI
> Serves the ARIA `/anatomy` tab and operates as a standalone web tool.
> Part of the five-repo ARIA ecosystem. No patient data. No DICOM served.

-----

## Purpose and design philosophy

One canonical “best normal” scan per body region + modality + plane. Quality and curation over volume. Expand iteratively.

**The atlas has two consumers with different UX contracts:**

|Consumer                     |What it needs                        |Label detail shown                                                                       |
|-----------------------------|-------------------------------------|-----------------------------------------------------------------------------------------|
|ARIA sidebar (`/anatomy` tab)|Slice PNG + SVG polygon overlay      |Structure name on hover only — nothing else                                              |
|Standalone web viewer        |Slice PNG + SVG overlay + label panel|Full label content on click (name · TA2 · description · normal values · Radiopaedia link)|

The API serves both. The label JSON always contains full content — what each consumer chooses to display is a UI decision, not a data decision.

**Reference UX:** xrayhead.com — one image, hover reveals labels. Keep v1 this simple.

-----

## Repo structure

```
anatomy-atlas/
  data/
    cardiac-cta-axial/
      meta.json          # {modality, body_part, plane, source, licence, structures[]}
      index.json         # {canonical_slice, slice_range, level}
      slices/
        050.png          # raw CT slice — grayscale, windowed
        050_overlay.png  # coloured structure overlay (toggleable in viewer)
        050_labels.json  # [{id, name, ta2, polygon, description, normal_values, radiopaedia_url}]
    ct-chest-axial/
    ct-abdomen-axial/
    ct-head-axial/
    ct-spine-sagittal/
    ct-neck-axial/
    mri-brain-t1-axial/    # v2
    mri-cardiac-sax/       # v2
    mri-spine-t2-sagittal/ # v2
  export/
    export.py        # NIfTI → PNG slice exporter + polygon extractor
  api/
    server.py        # FastAPI: four endpoints (see below)
  viewer/
    index.html       # Standalone single-file web viewer
  labels/
    left_ventricle.json
    right_ventricle.json
    ...              # One JSON per structure — you write these
  subagents/
    atlas-exporter.md
    label-writer.md
```

-----

## v1 atlas cases (CT — build first)

|Slot               |Source                            |Window          |Notes                                           |
|-------------------|----------------------------------|----------------|------------------------------------------------|
|`cardiac-cta-axial`|TCIA MM-WHS or de-id institutional|700 HU / 100 HU |**Manual QC required** — your clinical expertise|
|`ct-chest-axial`   |TotalSegmentator (Zenodo)         |400 HU / 40 HU  |Auto-seg acceptable                             |
|`ct-abdomen-axial` |TotalSegmentator (Zenodo)         |400 HU / 40 HU  |Portal venous phase                             |
|`ct-head-axial`    |TotalSegmentator (Zenodo)         |80 HU / 40 HU   |Non-contrast                                    |
|`ct-spine-sagittal`|TotalSegmentator (Zenodo)         |1500 HU / 300 HU|Bone window                                     |
|`ct-neck-axial`    |TotalSegmentator (Zenodo)         |400 HU / 40 HU  |Soft tissue window                              |

## v2 atlas cases (MRI — after CT atlas is live)

|Slot                   |Source                                    |
|-----------------------|------------------------------------------|
|`mri-brain-t1-axial`   |TotalSegmentator MR dataset (298 subjects)|
|`mri-cardiac-sax`      |TotalSegmentator MR dataset               |
|`mri-spine-t2-sagittal`|TotalSegmentator MR dataset               |

-----

## Windowing presets — hardcode in `export.py`

|Modality      |Window (HU)|Level (HU)|
|--------------|-----------|----------|
|CT soft tissue|400        |40        |
|CT lung       |1500       |−600      |
|CT bone       |1500       |300       |
|CT brain      |80         |40        |
|Cardiac CTA   |700        |100       |

-----

## Data sources and licences

|Dataset                  |Coverage                            |Modality |Licence        |URL                         |
|-------------------------|------------------------------------|---------|---------------|----------------------------|
|TotalSegmentator (Zenodo)|117 CT structures · 50 MR structures|CT + MRI |CC BY 4.0      |zenodo.org/records/10047292 |
|TCIA MM-WHS              |Whole heart                         |CT + MRI |CC BY 4.0      |cancerimagingarchive.net    |
|TCIA CT-ORG              |6 organs                            |CT       |TCIA Data Usage|cancerimagingarchive.net    |
|NLM Visible Human        |Whole body                          |CT + cryo|Public domain  |nlm.nih.gov/research/visible|

**IRB:** Institutional cases (cardiac CTA) require IRB sign-off before inclusion. Confirm with your institution before sourcing. All TotalSegmentator and TCIA data is pre-de-identified — no PHI enters this pipeline.

-----

## Export pipeline (`export/export.py`)

Takes a NIfTI volume + TotalSegmentator label map and produces the three files needed per slice.

**Outputs per slice:**

1. `{slice_id}.png` — raw CT slice, grayscale, windowed
1. `{slice_id}_overlay.png` — semi-transparent coloured structure overlay
1. `{slice_id}_labels.json` — per-structure polygon array for that slice

**Label JSON schema (per structure per slice):**

```json
{
  "id": "left_ventricle",
  "name": "Left Ventricle",
  "ta2": "Ventriculus sinister",
  "polygon": [[x1,y1],[x2,y2],...],
  "description": "Main pumping chamber...",
  "normal_values": { "wall_thickness_mm": "6–10", "EF_pct": "55–70" },
  "radiopaedia_url": "https://radiopaedia.org/articles/left-ventricle"
}
```

**Polygon extraction:** contour tracing per structure from the NIfTI label mask. Coordinates are pixel-space relative to the exported PNG dimensions.

**QC step:** after export, visually confirm every label polygon aligns with anatomy in the PNG before committing. Cardiac structures especially — automated segmentation is imprecise at cardiac resolution.

**Claude Code prompt to write `export.py`:**

```
Write a Python script using nibabel and matplotlib that takes a NIfTI CT volume
and its TotalSegmentator multi-label map, extracts the axial slice at a given
z-index, applies a soft-tissue window (W:400 L:40), renders each structure as
a semi-transparent coloured overlay, and exports: (1) raw CT slice as PNG,
(2) overlay PNG, and (3) a JSON file with each structure's pixel polygon for that slice.
```

-----

## FastAPI (`api/server.py`)

Four endpoints. CORS enabled for browser extension and standalone viewer.

```
GET /atlas/slice?body_part=chest&modality=CT&plane=axial
  → { slice_png_url, overlay_png_url, labels_json_url, level, source_citation }

GET /atlas/label?slice_id=ct-chest-axial&label_id=42
  → { name, ta2_name, description, normal_values, radiopaedia_url, related_structures[] }

GET /atlas/search?q=left+ventricle
  → [{ slice_id, label_id, name, modality, plane }]

GET /atlas/list
  → [{ body_part, modality, plane, canonical_level, structure_count }]
```

Mount `data/` as a static file server — PNGs are served directly by URL, not proxied through the API.

**ARIA sidebar calls `GET /atlas/slice` only.** The response gives the sidebar everything it needs: the PNG URL for the image and the labels JSON URL for the SVG polygon overlay. The sidebar renders name-on-hover and nothing else. The `/atlas/label` endpoint is used by the standalone viewer when a user clicks a structure — it is not called by the ARIA sidebar.

-----

## ARIA sidebar UX contract

The ARIA Anatomy tab is a **pure labelled map**. This is intentional and should not be expanded in the sidebar context.

**What the sidebar renders:**

- Region picker (Cardiac CTA · CT Chest · CT Abdomen · CT Head) — manual for now, PACS-parsed in future
- Full-width slice PNG with SVG polygon overlay
- On hover: structure name displayed below the image — no tooltip panel, no click state, no normal values

**What the sidebar does not render:**

- TA2 names
- Descriptions
- Normal values
- Radiopaedia links

Those live in the label JSON and are available via `/atlas/label` — the standalone viewer uses them. The sidebar deliberately does not, to keep the anatomy tab a fast visual reference during case reading.

-----

## Standalone web viewer (`viewer/index.html`)

Single HTML file. Used independently and embedded in the ARIA sidebar for the full-detail experience when needed.

**Viewer renders:**

- Slice PNG with toggleable coloured overlay
- SVG polygon overlay — hover highlights structure + shows name tooltip
- Click on structure → right panel with full label content (name · TA2 · description · normal values · Radiopaedia link)
- Region + modality selector
- Window preset toggle (soft tissue / lung / bone for CT)
- Mobile-responsive for whiteboard or conference use

-----

## Label content (`labels/`)

One JSON file per structure. These are written by you — clinical accuracy is the priority, not automated generation.

**Template:**

```json
{
  "id": "left_ventricle",
  "name": "Left Ventricle",
  "ta2_name": "Ventriculus sinister",
  "description": "Main pumping chamber. Normal wall thickness 6–10 mm. On cardiac CTA: assess wall motion, trabeculations, thrombus, LVEF.",
  "normal_values": {
    "wall_thickness_mm": "6–10",
    "ejection_fraction_pct": "55–70",
    "EDV_ml": "90–180"
  },
  "radiopaedia_url": "https://radiopaedia.org/articles/left-ventricle",
  "related_structures": ["mitral_valve", "aortic_valve", "interventricular_septum", "papillary_muscles"]
}
```

**Write order:**

1. Cardiac structures — your domain, do these first
1. Chest structures
1. Abdominal structures — use TotalSegmentator label list as checklist
1. Brain + head/neck structures

Add `normal_values` wherever clinically relevant. Leave it as `{}` where not applicable rather than omitting the key.

-----

## Subagents (`subagents/`)

|File               |Purpose                                             |
|-------------------|----------------------------------------------------|
|`atlas-exporter.md`|Runs `export.py` for a given NIfTI case, QCs output |
|`label-writer.md`  |Drafts label JSON from clinical knowledge for review|

-----

## Build sequence

```
Phase A:  Data sourcing     → download TotalSegmentator · select canonical cases · IRB for cardiac
Phase B:  Segmentation QC   → run TotalSegmentator · 3D Slicer QC · manual cardiac correction
Phase C:  Export pipeline   → export.py · PNG + polygon JSON for all v1 CT cases · visual QC
Phase D:  Atlas API         → FastAPI server · four endpoints · static file mount · CORS
Phase E:  Web viewer        → index.html · SVG overlay · click panel · region selector
Phase F:  Label content     → cardiac first · chest · abdomen · brain (ongoing)
```

**Critical dependency for ARIA:** The API (`Phase D`) must be running before the ARIA browser interface can be built. The `/anatomy` tab calls `GET /atlas/slice` — ARIA cannot be tested end-to-end without it.

-----

## Key decisions and rationale

|Decision                             |Rationale                                                                                |
|-------------------------------------|-----------------------------------------------------------------------------------------|
|Pre-rendered PNGs, no DICOM          |Browser-native · no viewer complexity · no PHI risk                                      |
|Polygon overlay in SVG, not canvas   |Scalable · CSS hover states · easy to maintain                                           |
|ARIA sidebar shows name only         |Anatomy tab is a visual reference during reading, not a teaching resource                |
|Full label content in JSON regardless|Viewer and future consumers get everything; sidebar selects what it shows                |
|One canonical case per slot          |Curation over volume — one excellent normal beats ten mediocre ones                      |
|Cardiac requires manual QC           |Automated segmentation is unreliable at cardiac resolution — clinical expertise needed   |
|Self-hosted, no external dependency  |Works offline at PACS workstation · no rate-limit risk · no third-party uptime dependency|
