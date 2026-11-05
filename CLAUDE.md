# CLAUDE.md — anatomy-atlas

> Self-hosted, MRI-first anatomy atlas for use during reading — e-Anatomy-style scrollable labelled stacks, hover to name.
> Browser viewer (NiiVue) over local NIfTI volumes + label maps. No server needed to read.
> Serves the ARIA `/anatomy` tab and runs standalone. Part of the five-repo ARIA ecosystem.
> Personal + departmental use only. Non-commercial. No patient data.

-----

## Purpose and design philosophy

A locally owned alternative to e-Anatomy for the reading room. Pick the joint, scroll to the level you are reading, hover a structure to see its name.

- **Stacks, not single slices.** Every case is a full volume you scroll through, in any plane.
- **MSK MRI first.** Knee → shoulder → ankle → hip → wrist → elbow. Spine, brain, CT and cardiac later.
- **Curation over volume.** One excellent normal per joint beats ten mediocre ones.
- **Labels are the product.** Auto-segmentation covers the big structures. The clinically useful small ones (ligaments, tendons, nerves) are hand-labelled in the viewer’s author mode.
- **Offline.** Everything, including JS libraries, is served from local files. Works on a PACS workstation with no internet.

**Three viewer modes, one set of files:**

|Mode         |URL                                           |Shows                                                                                                   |
|-------------|----------------------------------------------|--------------------------------------------------------------------------------------------------------|
|ARIA sidebar |`viewer/index.html?case=knee-mri&mode=sidebar`|Structure name on hover only — nothing else                                                             |
|Standalone   |`viewer/index.html?case=knee-mri`             |Hover name + click → panel (name · TA2 · description · normal values · variants/pitfalls · Radiopaedia)|
|Author       |`viewer/index.html?case=knee-mri&mode=author` |Paint / erase / point tools, structure picker, save. Localhost only, via `tools/serve.py`               |

The label JSON always holds full content. What each mode displays is a UI decision, not a data decision.

-----

## Architecture

```
volumes/*.nii.gz  (MRI sequences)  ─┐
labels.nii.gz     (uint16 label map)├─► viewer/index.html (NiiVue, WebGL2)
lut.json          (value → id, rgb) │     hover → LUT lookup / nearest point → name
points.json       (point labels)   ─┘     click → labels/<id>.json → side panel
```

- **Viewer:** NiiVue (BSD-2), vendored at `viewer/vendor/` — never loaded from a CDN.
- **Reading is static files only.** Any static web server works (local, or a departmental web server).
- **`tools/serve.py`:** small local server = static files + a save endpoint for author mode. Binds `127.0.0.1` only.
- **No API layer in v1.** ARIA reads `data/index.json` and embeds the viewer. Add a thin FastAPI wrapper over the same JSON only if a real need appears.

**Two label types:**

|Type  |Stored in                                       |Use for                                                                                                                       |
|------|------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
|Region|`labels.nii.gz` voxel value → `lut.json`        |Anything paintable: bones, cartilage, menisci, ligaments, tendons, muscles, fat pads, large vessels/nerves. Valid in every plane.|
|Point |`points.json` (world mm coordinates)            |Tiny structures and landmarks: genicular arteries, small bursae, Gerdy’s tubercle. Marker + name shown within ±1 slice.         |

-----

## Repo structure

```
anatomy-atlas/
  viewer/
    index.html            # single-file viewer: sidebar / standalone / author modes
    vendor/niivue.umd.js  # vendored, pinned version
  data/                   # volumes + label maps gitignored — see Data storage
    index.json            # [{case_id, region, modality, sequences[], structure_count}]
    knee-mri/
      meta.json           # source, licence, citation, consent ref, side, sequences[], default W/L per sequence
      volumes/
        pd_fs_3d.nii.gz   # labelling reference volume
        pd_3d.nii.gz      # optional, same session
        cor_pd_fs_2d.nii.gz  # optional clinical 2D series, same session
      labels.nii.gz       # uint16 label map, in pd_fs_3d space
      lut.json            # {"1": {"id": "acl", "rgb": [r,g,b]}, ...}
      points.json         # [{"id": "gerdys_tubercle", "xyz_mm": [x,y,z]}]
  labels/
    acl.json              # content — one file per structure, shared across cases
    ...
  checklists/
    knee.md               # structures to label, ticked as done
  tools/
    build_case.py         # DICOM → anonymised NIfTI (dcm2niix), reorient RAS, crop, write meta/lut skeleton
    autoseg.py            # optional base layer (bones, cartilage, menisci) from open models
    serve.py              # local static server + author-mode save endpoint
  subagents/
    case-builder.md
    label-writer.md
```

-----

## Data sources

### Primary: volunteer scans (recommended)

Healthy volunteer (often yourself) on your own scanner with your own protocols. You own the images, and their appearance matches what you read daily. Public normal MSK MRI is scarce, so this is the main path.

**Protocol per joint — one session, no repositioning:**

- 3D isotropic PD-FS, ~0.5–0.6 mm (CUBE / SPACE / VISTA) — the labelling volume
- 3D isotropic PD or T1 without fat sat — anatomy contrast
- Optional: standard clinical 2D TSE series (ax / cor / sag). Same session = same scanner coordinates, so 3D labels carry onto them via the NIfTI affine.

**Before scanning:** written consent, an incidental-findings plan, and confirm whether your institution treats volunteer scans as research (IRB) or protocol development / QA.

**De-identify on conversion:** `dcm2niix -ba y`. No DICOM kept anywhere in the repo.

### Fallback: public datasets (non-commercial research terms)

|Dataset                |Content                                   |Existing labels             |Terms                         |
|-----------------------|------------------------------------------|----------------------------|------------------------------|
|SKM-TEA (Stanford AIMI)|Knee 3D qDESS, 155 scans                  |Cartilage, menisci          |Research use agreement        |
|OAI + OAI-ZIB          |Knee 3D DESS, large cohort incl. controls |Femur, tibia, cartilage     |NIH data use terms; check ZIB |
|TotalSegmentator MR    |Body MRI                                  |Hip/thigh bones and muscles |CC BY 4.0 — useful for hip    |

These terms generally forbid redistribution. Check each agreement before hosting on a departmental server.
Not suitable: fastMRI and MRNet (2D / low resolution, no anatomy labels, pathology-heavy).

### Data storage

- Volumes and label maps **never** go to GitHub (licence terms + volunteer consent). Enforced by `.gitignore`.
- Keep `data/` on local disk or a departmental share, with a separate backup — hand-painted label maps are hours of work.
- Committed: `viewer/`, `tools/`, `labels/`, `checklists/`, and small `data/**/*.json` metadata.

-----

## Viewer (`viewer/index.html`)

- Case (joint) picker + sequence toggle (PD-FS / PD / 2D series)
- Plane: axial / coronal / sagittal; single large view by default, optional 3-up
- Scroll = slice · drag = window/level · zoom / pan · touch-friendly
- Hover → structure name (region LUT lookup, else nearest point label)
- Click → side panel with full label content (not in sidebar mode)
- Overlay: off / outline / filled, opacity slider
- **Find structure:** type a name → jump to its centroid slice and highlight it
- **Author mode:** structure picker (from `labels/` + checklist), paint / erase brush, point tool, undo, save via `serve.py`

**Risk:** NiiVue needs WebGL2. Confirm it runs on the reading-room workstation (and any VDI/Citrix setup) in Phase 0. Fallback if not: pre-rendered PNG stacks + SVG polygon overlay.

MRI has no HU, so there are no fixed window presets. `build_case.py` sets a default W/L per sequence from intensity percentiles, stored in `meta.json`.

-----

## Label content (`labels/`)

One JSON per structure, written or reviewed by you — clinical accuracy is the priority. The `label-writer` subagent drafts; you review before commit.

```json
{
  "id": "patellar_tendon",
  "name": "Patellar Tendon",
  "ta2_name": "Ligamentum patellae",
  "region": "knee",
  "description": "Continuation of the quadriceps mechanism from the inferior patellar pole to the tibial tuberosity. Uniformly low signal.",
  "normal_values": { "insall_salvati_ratio": "0.8–1.2" },
  "variants_pitfalls": ["Magic angle: intermediate signal on short-TE sequences where fibres lie ~55° to B0"],
  "radiopaedia_url": "https://radiopaedia.org/articles/patellar-tendon",
  "related_structures": ["patella", "quadriceps_tendon", "hoffa_fat_pad", "tibial_tuberosity"]
}
```

`normal_values: {}` and `variants_pitfalls: []` when not applicable — never omit the keys.

**Write order:** follow `checklists/knee.md`, then each new joint’s checklist.

-----

## ARIA sidebar UX contract

The ARIA Anatomy tab is a **pure labelled map**. Intentional — do not expand it in the sidebar.

- ARIA lists cases from `data/index.json` and embeds `viewer/index.html?case=<id>&mode=sidebar`.
- **Renders:** joint picker · scrollable image · structure name below the image on hover.
- **Does not render:** TA2 names, descriptions, normal values, pitfalls, Radiopaedia links, click panel.

**Changed from the earlier plan:** there is no `GET /atlas/slice` API. The ARIA repo must be updated to embed the viewer instead.

-----

## Subagents (`subagents/`)

|File              |Purpose                                                                          |
|------------------|---------------------------------------------------------------------------------|
|`case-builder.md` |Runs `build_case.py` for a new scan, checks orientation / anonymisation / W/L    |
|`label-writer.md` |Drafts `labels/<id>.json` from clinical knowledge for your review                |

-----

## Build sequence

```
Phase 0:  Viewer spike    → NiiVue on a sample NIfTI · label hover · confirm WebGL2 on reading-room workstation
Phase A:  Data            → volunteer knee scan (consent / IRB check) · in parallel apply for SKM-TEA / OAI
Phase B:  Case build      → build_case.py · anonymised NIfTI · crop · LUT skeleton
Phase C:  Base labels     → bones (+ cartilage / menisci if a usable open model exists) — else manual
Phase D:  Author mode     → paint + point tools · save via serve.py
Phase E:  Hand labelling  → work through checklists/knee.md
Phase F:  Label content   → labels/*.json for every knee structure (drafted, then reviewed)
Phase G:  ARIA            → sidebar mode · data/index.json · update ARIA repo
Then:     shoulder → ankle → hip → wrist → elbow → spine → brain → CT (TotalSegmentator) → cardiac
```

-----

## Key decisions and rationale

|Decision                          |Rationale                                                                         |
|----------------------------------|----------------------------------------------------------------------------------|
|Scrollable volumes, not one slice |Reading use means matching the level you are on                                   |
|NiiVue over pre-rendered PNGs     |Scroll, any plane, W/L, sequence toggle — far less custom code                    |
|MSK MRI first                     |Main reading need; the most-used part of e-Anatomy                                |
|Volunteer scans as primary source |Full ownership; matches local protocols; public normal MSK MRI is scarce          |
|3D isotropic labelling volume     |Label once, valid in all three planes and on same-session 2D series               |
|Region + point labels             |Paint what is paintable; points for structures too small to paint                 |
|Static files, no API              |Nothing to run at the workstation; ARIA reads the same files                      |
|Imaging data kept out of git      |Dataset licence terms + volunteer consent                                         |
|Non-commercial only               |Allows research-licensed datasets                                                 |
|ARIA sidebar shows name only      |Visual reference during reading, not a teaching resource                          |
