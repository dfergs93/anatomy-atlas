# CLAUDE.md — anatomy-atlas

> Self-hosted, MRI-first anatomy atlas for use during reading — e-Anatomy-style scrollable labelled stacks, hover to name.
> Browser viewer (NiiVue) over local NIfTI volumes + label maps. No server needed to read.
> Built from public datasets. Serves the ARIA `/anatomy` tab and runs standalone. Part of the five-repo ARIA ecosystem.
> Personal use only, on the owner's own Mac and laptop. Non-commercial. No patient data.
>
> **Design (2026-11-05, approved):** `docs/superpowers/specs/2026-11-05-anatomy-atlas-design.md` — wins over this file where they differ. Plans: `docs/superpowers/plans/`.

-----

## Purpose and design philosophy

A locally owned alternative to e-Anatomy for the reading room. Pick the joint, scroll to the level you are reading, hover a structure to see its name.

- **Stacks, not single slices.** Every case is a full volume you scroll through, in any plane.
- **MSK MRI first.** Knee → hip. Shoulder, rectal pelvis, ankle, wrist, elbow, spine, brain, CT and cardiac later.
- **Public datasets first.** Volunteer scans only for joints with no usable public data.
- **Curation over volume.** One excellent normal per joint beats ten mediocre ones.
- **Labels are the product.** Dataset labels + auto-segmentation cover the big structures. The clinically useful small ones (ligaments, tendons, nerves) are hand-labelled in the viewer’s author mode.
- **Offline.** Everything, including JS libraries, is served from local files.
- **Where it runs.** On the owner's own Mac, opened in a browser on that laptop beside the reading workstation. (A departmental server or the hospital workstation is only an optional future idea.)

**Three viewer modes, one set of files:**

|Mode         |URL                                           |Shows                                                                                                   |
|-------------|----------------------------------------------|--------------------------------------------------------------------------------------------------------|
|ARIA sidebar |`viewer/index.html?case=knee-mri&mode=sidebar`|Structure name on hover only — nothing else                                                             |
|Standalone   |`viewer/index.html?case=knee-mri`             |Hover name + click → panel (name · TA2 · description · normal values · variants/pitfalls · Radiopaedia)|
|Author       |`viewer/index.html?case=knee-mri&mode=author` |Painting mode: checklist panel, brush/eraser/wand, fill between, grow, point placement, K to mark checked, save with backups, a helper's paint file merged in structure by structure. Localhost only (127.0.0.1/localhost), via `python tools/serve.py`; refuses mirrored copies. See Painting mode|

The label JSON always holds full content. What each mode displays is a UI decision, not a data decision.

-----

## Running it

```
pip install -r requirements.txt
python tools/make_demo_case.py     # synthetic test case (shapes, not anatomy) → data/demo-knee-synthetic
python tools/serve.py              # http://127.0.0.1:8004/
```

Opening `viewer/index.html` directly from disk does not work (browsers block `fetch` on `file://`). Use `serve.py` or any static web server.

-----

## Architecture

```
volumes/*.nii.gz  (MRI sequences)  ─┐
labels.nii.gz     (uint16 label map)├─► viewer/index.html (NiiVue, WebGL2)
lut.json          (value → id, rgb) │     hover → label value / nearest point → name
points.json       (point labels)   ─┘     click → labels/<id>.json → side panel
```

- **Viewer:** NiiVue 0.69.0 (BSD-2), vendored at `viewer/vendor/niivue.umd.js` — never loaded from a CDN.
- **Reading is static files only.** Served locally by `tools/serve.py`.
- **`tools/serve.py`:** static file server (needs only `requirements.txt`: the save endpoint uses numpy and nibabel), binds `127.0.0.1` only, port **8004** (8000 is protocol_manager's MkDocs). Also `GET /api/token` and `POST /api/save` for painting mode (see Painting mode); static files are unchecked, so the phone can view through the tailnet but not save.
- **No API layer in v1.** ARIA reads `data/index.json` and embeds the viewer. Add a thin FastAPI wrapper over the same JSON only if a real need appears.

**Two label types:**

|Type  |Stored in                                |Use for                                                                                                                          |
|------|-----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
|Region|`labels.nii.gz` voxel value → `lut.json` |Anything paintable: bones, cartilage, menisci, ligaments, tendons, muscles, fat pads, large vessels/nerves. Valid in every plane.|
|Point |`points.json` (world mm coordinates)     |Tiny structures and landmarks: genicular arteries, small bursae, Gerdy’s tubercle. Marker shown within ±1.5 slices; hover radius 4 mm.|

**NiiVue notes (0.69.0):**

- The label map must have NIfTI intent `label` (1002) — this turns on NiiVue’s atlas outline and hover highlight (`opts.atlasOutline`, `opts.atlasActiveIndex`). Both build scripts set it.
- `nv.frac2vox()` throws in this build — the viewer uses its own `frac2vox()` helper.
- **Oblique volumes:** NiiVue draws them in voxel space, and its `frac2mm()` / `mm2frac()` follow a straightened matrix, not the NIfTI affine — on OAI DESS (~4°) that is up to ~1 cm / 7–13 slices out. Stored positions (`lut.json`, `points.json`, mirroring) are true world mm, so the viewer converts with each volume's own `matRAS` (`core.worldToFrac` / `fracToWorld` / `extentSlices`). Never use `nv.frac2mm` / `nv.mm2frac` for stored positions.
- Highlight changes call `updateGLVolume()`. That is ~360 ms in software rendering (SwiftShader), so it is debounced. It should be far faster on a real GPU — check on the Mac.

-----

## Repo structure

```
anatomy-atlas/
  viewer/
    index.html            # single-file viewer: sidebar / standalone (+ author mode via author.js, paint-core.js, merge*.js)
    author.js             # painting mode: panel, checklist, tools, save, paint-file download
    paint-core.js         # pure paint logic (tested): guard, undo, wand, grow, colours
    merge.js              # painting mode's merge screen: a helper's paint file, one structure at a time
    merge-core.js         # pure merge logic (tested): paint-file checks, what differs, the voxels an accept changes
    vendor/niivue.umd.js  # vendored, pinned 0.69.0
  data/                   # volumes + label maps gitignored — see Data storage
    index.json            # [{case_id, title, region, modality, sequences[], structure_count, synthetic}]
    <case_id>/
      meta.json           # title, source, licence, citation, side, sequences[] (file, cal_min/max), default_plane, synthetic
      volumes/<seq>.nii.gz
      labels.nii.gz       # uint16, intent "label", on the reference sequence grid
      lut.json            # {"1": {"id", "name", "rgb", "voxels", "centroid_vox", "centroid_mm", "extent"}, ...}; model outlines add "auto": {source, date}; expected-location structures (bursae) add "expected": true
      points.json         # [{"id", "name", "xyz_mm": [x,y,z]}]
      backups/<UTC time>/ # labels + lut + points before every write; newest 20 kept (gitignored)
      auto/               # raw model predictions from tools/autolabels.py (gitignored)
  labels/
    <id>.json             # content — one file per structure, shared across cases
  checklists/
    knee.md               # structures to label, ticked as done
  tools/
    make_demo_case.py     # synthetic test case (geometric shapes) for viewer testing
    build_case.py         # NIfTI volume(s) + label map → case: RAS, int16/uint16, W/L, LUT, index.json
    serve.py              # local static server (+ /api/token, /api/save)
    save_case.py          # painting-mode save: checks → backup → labels/lut/points → index → mirror → checklist
    checklist.py          # read/tick checklists/<region>.md (Labelled = exactly the saved ids)
    mirror_case.py        # right knee → mirrored left copy (rebuilt, never painted)
    autolabels.py         # model labels merged into a case (main venv): menisci in thirds, patellar cartilage, bones if licensed
    share_case.py         # pack a case for a helper (zip, no backups/auto); unpack it on theirs
    autoseg/dosma_unet.py # DOSMA knee U-Net runner (venv-autoseg; GPL-3.0, this file only)
  subagents/              # not written yet
    case-builder.md
    label-writer.md
  requirements.txt
  requirements-autoseg.txt  # model packages for venv-autoseg only (TensorFlow, TotalSegmentator)
```

-----

## Data sources

### Knee — primary: OAIZIB-CM

|                 |                                                                                                                       |
|-----------------|-----------------------------------------------------------------------------------------------------------------------|
|Where            |huggingface.co/datasets/YongchengYAO/OAIZIB-CM (also Zenodo doi 10.5281/zenodo.14934086). Free HF account, no agreement.|
|Licence          |CC BY-NC 4.0 (from search results — confirm on the HF page). Images derive from the OAI, so OAI terms also apply. Keep internal.|
|Images           |Sagittal 3D DESS-WE, 3T Siemens, ~0.36 × 0.36 × 0.7 mm, NIfTI. Right knees, baseline visit.                            |
|Labels           |Femur, femoral cartilage, tibia, medial + lateral tibial cartilage. **No patella, no menisci.**                          |
|Normals          |103 KL0 knees; 17 are KL0 + age ≤ 55 + BMI 18.5–25 (`tools/oaizib.py list`). **Chosen (owner, 2026-11-06): CMT-ID 036 = OAI 9172581 (M, 49, BMI 24.2), train split** → case `knee-mri`; `knee-mri-left` is its mirrored copy, generated locally with `tools/mirror_case.py knee-mri`.|
|Size             |imagesTr.zip ≈ 10 GB, zip only (no single-subject download).                                                             |

- **Pick the subject yourself.** KL0 is a radiograph grade, not a normal MRI — review for meniscal, marrow and ligament findings before adopting.
- **DESS is not PD-FS:** fluid bright, fat suppressed, cartilage well seen. Fine for anatomy.
- No need to resample to isotropic — NiiVue reslices anisotropic voxels correctly in mm space.
- `build_case.py --preset oaizib-cm` maps values 1–5 to the ids above. **Verify the mapping** against the dataset README — the script prints every value and voxel count.

**Optional add-on:** NIMH Data Archive (NDA) access to the same subject’s full OAI baseline exam: sagittal IW-TSE FS (≈ PD-FS), coronal IW-TSE, coronal 3D FLASH. Same session = same scanner coordinates, so labels carry across. Also confirms whether the subject is in the non-exposed control cohort (n = 122). NDA terms → personal copy only.

### Knee — alternatives

|Dataset                     |Why not primary                                                                 |
|----------------------------|--------------------------------------------------------------------------------|
|Open Knee(s) (simtk.org)    |CC BY 4.0, bones + menisci + cartilage — but **cadaver** knees                  |
|SKM-TEA (Stanford AIMI)     |Has meniscus labels, but ~900 GB, no partial download, no departmental hosting  |
|fastMRI, MRNet, KneeMRI     |2D / low-res / no anatomy labels / pathology-heavy                              |
|SKI10, K2S                  |No longer distributed                                                           |

### Other joints

No open, labelled, normal MRI found for shoulder, ankle, wrist or elbow. Hip: TotalSegmentator MR dataset (femur, hip bone, gluteals; licence unconfirmed — verify before use). For these joints, expect volunteer scans (below) + auto bone labels.

### Base auto-labels (build step 3, done 2026-11-07)

Checked on the owner's M4 Pro with subject 036 (2026-11-06):

|Model                                         |Gives on knee-mri                                             |Licence / status                |
|----------------------------------------------|--------------------------------------------------------------|--------------------------------|
|OAIZIB-CM ground truth                        |Femur, tibia, femoral + medial/lateral tibial cartilage       |CC BY-NC 4.0                    |
|DOSMA `iwoai-2019-t6-normalized` (OAI DESS)   |Menisci (→ medial/lateral × anterior horn / body / posterior horn), patellar cartilage. CPU ~18 s; femoral cartilage Dice 0.756 vs ground truth (not used: ground truth wins)|GPL-3.0 (DOSMA's docs); weights public on Hugging Face `arjundd/dosma-models`|
|TotalSegmentator `appendicular_bones_mr`      |Patella, fibula (tibia not used). MPS ~15 s; works at 1.5 mm, so outlines are blocky|Free academic licence — **owner declined 2026-11-07** ("not worth it for two bones"): patella and fibula are painted|
|TotalSegmentator `total_mr` (open)            |Only the femur on this knee. Covers gluteals, iliopsoas, hip bone → useful for the hip|Open                            |
|Knee muscles (gastrocnemius, popliteus …)     |No model covers them → **painted**                            |—                               |

- **Setup, once:** `python3.13 -m venv venv-autoseg && venv-autoseg/bin/pip install -r requirements-autoseg.txt` (~3.5 GB). The main `venv` stays light for a helper who only paints (spec §5.6).
- **Run:** `venv/bin/python tools/autolabels.py knee-mri` (`--no-totalseg` to skip the bones).
  - It backs up the case, fills only empty voxels, never replaces a structure without an `"auto"` key in `lut.json`, and rebuilds `knee-mri-left`. Mirrored copies are refused.
  - A re-run replaces a structure's earlier auto voxels only if they are unchanged: `"auto"` stores a fingerprint (`voxels_sha256`), and a structure edited since is kept and reported.
  - **Checked = no `"auto"` key.** Removing it marks the outline as checked: the panel note goes and re-runs leave it alone. Painting mode drops `"auto"` from any structure it paints, or marks with K, on save.
  - DOSMA's package breaks on NumPy 2, so `tools/autoseg/dosma_unet.py` rebuilds its U-Net with tf_keras. Weights download once to `~/.cache/anatomy-atlas/dosma/`, checked against a pinned sha256.
  - Meniscus thirds are cut by angle round each meniscus's own ring centre, with the opening facing the notch. On knee-mri: medial 26 / 19 / 55 % (the posterior horn is the widest part), lateral 31 / 33 / 36 %.
  - The viewer's panel says "Outline drawn automatically (…) — not yet checked" for any structure with `"auto"`.
- **Patella and fibula are painted** (owner declined the licence 2026-11-07). If that ever changes: fill the form at https://backend.totalsegmentator.com/license-academic/ (name, email, institution; internal non-commercial use) asking for `appendicular_bones_mr`, then `venv-autoseg/bin/totalseg_set_license -l aca_…` and re-run `tools/autolabels.py knee-mri`. The key lives in `~/.totalsegmentator/config.json`, never in the repo.
- **Usage stats:** the owner's `~/.totalsegmentator/config.json` has `send_usage_stats: true` — each run sends the task name, platform and an install id, never images. Set it to `false` to stop that.
- `thigh_shoulder_muscles_mr` gives compartments only, and its licence is by email. SegmentAnyBone (CC BY-NC 4.0) remains an option for other joints' bones.

### Fallback: volunteer scans

Only for joints with no public data. One session, no repositioning: 3D isotropic PD-FS ~0.5–0.6 mm (CUBE / SPACE / VISTA) as the labelling volume, optional 3D PD / T1 and clinical 2D series. Before scanning: written consent, incidental-findings plan, and confirm whether your institution treats it as research (IRB) or protocol development / QA. Convert with `dcm2niix -ba y -z y`.

### Data storage

- Volumes and label maps **never** go to GitHub (dataset terms). Enforced by `.gitignore` (`*.nii*`, `*.dcm`, and everything under `data/` except JSON).
- Keep `data/` on local disk or a departmental share, with a separate backup — hand-painted label maps are hours of work.
- Committed: `viewer/`, `tools/`, `labels/`, `checklists/`, and per-case `meta.json` / `lut.json` / `points.json` (points are hand-placed — worth versioning). `data/index.json` and the synthetic demo are generated locally.

-----

## Viewer (`viewer/index.html`)

Built:

- Case picker (grouped: cases, then any "Candidates — pick one") · sequence toggle · plane (sagittal / coronal / axial, keys `1`–`3`)
- **Main view + two small reference views** (standalone, window wider than 760 px): the main plane large on the left, the other two planes stacked on the right. Each small view draws a reference line where the main slice cuts it; pointing in the main view puts a ring at that spot in both small views (they do not move on hover). Click in the main view → small views move through that point (+ details if a structure is there; empty space keeps the selection). Click a small view → the main view jumps there. Wheel over a small view does nothing; over the main view it steps the main slice (handled by the viewer, so the small views stay put). Sidebar mode and narrow windows keep a single view.
- **Follow a structure**: selecting (click, find `/`, related chips) keeps it lit — hover only names others — and marks its slice range on a bar under the slider, with Start / Widest / End jumps. Find and chips land on its widest slice with the small views through it. Ranges come from per-plane `extent` (mm) in `lut.json`; cases without it just hide the follow controls. `Esc` clears.
- **Right / left**: a case and its mirrored copy (`tools/mirror_case.py`, world x → −x) are linked in `data/index.json` (`mirror` / `mirror_of`); the R | L switch opens the other at the mirrored spot with the same plane and structure. A banner marks mirrored copies.
- Display conventions: radiological (patient right on screen left); sagittal anterior on screen left
- ↑/↓ = slice · slider = slice (touch) · left-drag = window/level · right-drag = pan · +/− zoom · R reset
- Click → side panel with full label content; “Draft — not reviewed” badge until `reviewed: true`
- Overlay: off / outline / fill, opacity slider
- Point labels drawn as markers on nearby slices (main view only)
- WebGL2 check with a clear message if unavailable; GPU name shown at the bottom
- `?mode=sidebar`: image, slider, case/sequence/plane, hover name — no panel, find, overlay or follow controls
- Pure helpers live in `viewer/core.js` (tested: `node --test "tests/viewer/*.test.mjs"`); NiiVue glue stays in `index.html`

To do: keyboard focus polish.

**Checked:** NiiVue (WebGL2) runs on the owner's M4 Pro Mac (ANGLE Metal). OAI DESS volumes are ~4° oblique; NiiVue warns and shows them in voxel space.

-----

## Painting mode

Open: `python tools/serve.py`, then `http://127.0.0.1:8004/viewer/?case=knee-mri&mode=author` (or the "Paint" link in the standalone header, shown on 127.0.0.1/localhost for a case that isn't a mirrored copy). Code: `viewer/author.js` + `viewer/paint-core.js` (merging: `viewer/merge.js` + `viewer/merge-core.js`); saving: `tools/save_case.py`, `tools/checklist.py`, `tools/serve.py`.

**Panel:** current structure (with an "auto" badge), "Next: … · Enter", filter box over the checklist (groups, ✓ = labelled; click a row to make it current), tools, "Paint over other structures" (off), Save, status ("Saved" / "● Unsaved"), "Download paint file", "Merge in a paint file…", key help.

|Key                 |Does                                                                                      |
|--------------------|------------------------------------------------------------------------------------------|
|B / E               |brush / eraser                                                                            |
|W                   |wand: click; Tolerance 10 % default, 3D off, 40 mm cap                                    |
|F                   |fill between: paint two or more slices in the current plane, F fills the gaps pair by pair|
|G                   |grow: each press spreads 12 layers into similar signal. On DESS it doesn't stop at fascia by itself: press until the muscle is full, erase any spill|
|P / click           |place the point for a point-type structure at the pointer; Delete removes it              |
|K                   |"Looks right: mark checked" for an automatic outline                                      |
|[ ]                 |brush size (odd, 1–25); wand tolerance when the wand is active                            |
|Enter               |save, then next structure                                                                 |
|⌘/Ctrl+S, ⌘/Ctrl+Z  |save, undo                                                                                |
|O                   |show/hide the paint                                                                       |
|Shift-drag, Ctrl- or right-drag|windowing, pan                                                         |

Ligament workflow: paint 2–3 key slices, F, then scroll through and touch up.

**Rules**
- Painting is restricted to the current structure: other structures never change unless "Paint over other structures" is on. Strokes paint in the main view only. Point-type structures are never brushed.
- **Auto hand-off:** painting a structure, or K, drops its `"auto"` key on save (= checked: the panel note goes, `autolabels.py` re-runs leave it alone).
- **Expected-location (type E) structures** (the four bursae) are painted where they usually lie. In standalone/sidebar they show as a dotted outline, never filled, with "Visible only when distended — outlined where it usually lies". `lut.json` carries `"expected": true`.
- NiiVue's own hotkeys that change layout, drag mode or open a dialog are silenced in every mode.

**Save** (`POST /api/save`): checks first (nothing written if one fails) → backup to `data/<case>/backups/<UTC time>/` (newest 20) → labels + lut (with the auto contract) + points → `data/index.json` → rebuild the left mirror (only if the case is in the index) → tick `checklists/<region>.md` (Labelled = exactly the saved ids; skipped for a synthetic case, because the checklist belongs to the region). Late steps failing become `warnings`, not errors.
- The server requires: Host `127.0.0.1:<port>` / `localhost:<port>`, Origin matching when present, `Content-Type: application/json`, body ≤ 64 MB, one save at a time, and the token from `GET /api/token`.
- Only painted values are checked: a structure a save erased keeps its value in the page, so ⌘/Ctrl+Z back past that save restores it under its own name. A point already in `points.json` stays valid after its checklist row is removed.
- If the case changed on disk since the page opened (another tab, `tools/autolabels.py`) the save is refused (409): the page reads the token before the case's files. "Download my unsaved work" saves one file, `<case>-unsaved-<time>.atlaspaint` (paint, points and K marks); reload, then "Merge in a paint file…" brings it back. Closing the tab with unsaved work warns.

**Author mode refuses** (banner): a mirrored copy (links to the source), a host other than 127.0.0.1/localhost, a narrow window, a non-RAS-identity volume, a label value over 255, a label grid different from the image grid.

**Sharing and merging** (spec §5.6): a helper paints a copy on their own computer and sends back one file; the owner merges it in.
- **Owner → helper:** `python tools/share_case.py pack knee-mri` writes `knee-mri-share-<date>.zip` to `~/Downloads` (`-o FILE` for elsewhere): meta, lut, points, the label map and the sequences, never `backups/` or `auto/`. It refuses a mirrored copy, and a real case whose `meta.json` has no licence. Hand it over directly, never via git. The helper runs `python tools/share_case.py unpack <zip>`, which registers the case in their `data/index.json` (no mirror link) and refuses to overwrite their own paint unless `--replace` (which backs it up first); then `tools/serve.py`. Their saves tick their copy of `checklists/knee.md` and change the case's tracked JSON, so they have nothing to commit.
- **Helper → owner:** "Download paint file" writes one `<case>-paint-<time>.atlaspaint`: JSON with the grid (dims, affine), the structure list (`auto` kept only for model outlines that are unchanged and unchecked), the K marks, the points and the gzipped label map. `*.atlaspaint` and `*-share-*.zip` are git-ignored.
- **Merging:** "Merge in a paint file…" (painting mode). A file for another case, another grid or a moved grid (rebuilt, mirrored) is refused before anything changes. The merge screen takes the panel's place and goes through what differs one item at a time in checklist order, with their structure outlined in yellow dots on the main view and red dots where it covers another of your structures.
  - Matched by id, never by label value. An item is new, changed ("Theirs adds … removes … of yours"), checked (their K on the same voxels), a new point or a moved point.
  - Accepting a structure makes its voxels theirs; your other structures win any overlap unless you pick "Accept — theirs wins the overlap". "Accept all the rest" takes every item left, yours winning every overlap, and ends where accepting them one at a time would (an item kept out of a voxel that a later accept frees is taken again). On a helper's file it leaves the "changed" structures on the list for you to look at one at a time (see the next point); on a refused save's own file it takes everything.
  - A structure or point you have and the file lacks is never removed. Their model outlines they never checked (`auto`) are left out and named. The merge has no pack-time base, so a structure you have changed since packing shows as "changed", and accepting it brings back the helper's (packed) version; that is why "Accept all the rest" on a helper's file skips "changed" structures. A stale copy can undo your later fixes only through an accept you chose. Ids not on your checklist are left out and named.
  - Each accept is one ordinary undo step (⌘/Ctrl+Z offers the item again), and nothing is written until Save. A structure taken with yours winning an overlap still differs from theirs: it stays off the list while accepting it again would change nothing, and opening the file again offers it again.
  - Keys while merging: Enter accept, N skip, Esc stop merging (accepted edits stay, unsaved); ⌘/Ctrl+S, ⌘/Ctrl+Z, O, the arrows and the wheel work as usual. The tools and their keys are off and a click only moves the cursor. A sequence change ends the merge.
- **A refused save (409):** download the unsaved work, reload, then "Merge in a paint file…" and accept what you want back.

**Not built:** AI click-to-outline (§5.4, deferred).

-----

## Label content (`labels/`)

One JSON per structure, written or reviewed by you — clinical accuracy is the priority. The `label-writer` subagent drafts with `"reviewed": false`; you flip it to `true` after checking.

```json
{
  "id": "patellar_tendon",
  "name": "Patellar Tendon",
  "ta2_name": "Ligamentum patellae",
  "region": "knee",
  "reviewed": false,
  "description": "Continuation of the quadriceps mechanism from the inferior patellar pole to the tibial tuberosity. Uniformly low signal.",
  "normal_values": { "insall_salvati_ratio": "0.8–1.2" },
  "variants_pitfalls": ["Magic angle: intermediate signal on short-TE sequences where fibres lie ~55° to B0"],
  "radiopaedia_url": "https://radiopaedia.org/articles/patellar-tendon",
  "related_structures": ["patella", "quadriceps_tendon", "hoffa_fat_pad", "tibial_tuberosity"]
}
```

`normal_values: {}` and `variants_pitfalls: []` when not applicable — never omit the keys. `id` must match the checklist / `lut.json` id.

**Write order:** follow `checklists/knee.md`, then each new joint’s checklist.

-----

## ARIA sidebar UX contract

The ARIA Anatomy tab is a **pure labelled map**. Intentional — do not expand it in the sidebar.

- ARIA lists cases from `data/index.json` and embeds `viewer/index.html?case=<id>&mode=sidebar`.
- **Renders:** case picker · sequence + plane toggle · scrollable image · structure name below the image on hover.
- **Does not render:** TA2 names, descriptions, normal values, pitfalls, Radiopaedia links, click panel.

**Changed from the earlier plan:** there is no `GET /atlas/slice` API. The ARIA repo must be updated to embed the viewer instead.

-----

## Subagents (`subagents/`)

|File              |Purpose                                                                          |
|------------------|---------------------------------------------------------------------------------|
|`case-builder.md` |Runs `build_case.py` for a new dataset subject, checks orientation / label mapping / W/L|
|`label-writer.md` |Drafts `labels/<id>.json` (`reviewed: false`) from clinical knowledge for your review|

-----

## Build sequence

From the design (spec §9). Phase 0 (viewer spike) is done; its workstation test is dropped.

```
1. Real knee       → download OAIZIB-CM · owner reviews the 17 candidates and picks one · build + verify mapping/orientation · mirrored left copy   ✓ done 2026-11-06 (subject 036)
2. Getting oriented→ reference lines + shared cursor · follow a structure (spec §4)   ✓ done 2026-11-06
3. Auto-labels     → big structures: DOSMA menisci (thirds) + patellar cartilage   ✓ done 2026-11-07 · patella/fibula: painted (owner declined the TotalSegmentator licence) · muscles: none available for the knee — painted
4. Painting mode   → checklist-driven, smart fill, fill between slices, grow, points, expected locations, save + backups, helper merge (spec §5)   ✓ done 2026-11-08, helper merge included; AI click-to-outline (§5.4) stays deferred
5. Core knee set   → owner paints; Claude drafts labels/*.json, owner reviews
6. Hip             → find data or volunteer scan · checklists/hip.md · two linked cases (spec §7.2)
Then:              ARIA sidebar embed (unchanged contract) · shoulder · rectal pelvis · others
```

-----

## Key decisions and rationale

|Decision                          |Rationale                                                                          |
|----------------------------------|-----------------------------------------------------------------------------------|
|Scrollable volumes, not one slice |Reading use means matching the level you are on                                    |
|NiiVue over pre-rendered PNGs     |Scroll, any plane, W/L, sequence toggle — far less custom code                     |
|MSK MRI first                     |Main reading need; the most-used part of e-Anatomy                                 |
|Public datasets first             |No scanning, consent or IRB overhead; OAIZIB-CM gives normal knees with base labels|
|Region + point labels             |Paint what is paintable; points for structures too small to paint                  |
|Static files, no API              |Nothing to deploy; ARIA reads the same files                                       |
|Imaging data kept out of git      |Dataset licence terms                                                              |
|Non-commercial only               |Allows CC BY-NC and research-licensed datasets and models                          |
|`reviewed` flag on label content  |Drafts are visibly marked until a radiologist signs off                            |
|ARIA sidebar shows name only      |A quick visual reference inside ARIA; the teaching lives in the standalone panel   |
