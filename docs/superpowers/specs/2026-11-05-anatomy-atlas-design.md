# Anatomy atlas — knee then hip: design

Date: 2026-11-05. Agreed with the owner in conversation. Builds on the existing plan in `CLAUDE.md` and the Phase 0 viewer on `main` (6b74e54). Where this document and `CLAUDE.md` disagree, this document wins, and `CLAUDE.md` is updated to match (see "Changes to CLAUDE.md").

Marks used below: **(owner)** = decided by the owner. **(my call)** = settled while writing this design; the owner can overturn it. Everything else is carried over from the existing plan.

---

## 1. Intent and why

The owner is a radiologist (MSK reading, cardiac fellowship) who is frustrated with how rigid e-Anatomy and similar resources are. They want an anatomy reference they design and control themselves, used mainly to **troubleshoot MSK anatomy in the middle of a case**.

The real problem isn't missing labels. **It's hard to get to the spot you want and stay oriented there.** With e-Anatomy it was hard to scroll to the right level, follow a structure from slice to slice, and match what's on screen to their own patient's images. **(owner)**

These recent cases are the ones the atlas has to handle:
- **Knee:** the posterolateral corner; the meniscofemoral ligaments (Wrisberg, and Humphry); whether the lateral meniscus can reach that far medial.
- **Hip:** edema by the greater trochanter, where the question was bursa or strain; which of the muscles near the pelvic floor the edema was in.
- **Shoulder:** the MGHL and the labrum, for possible tears (later).
- **Rectal staging MR anatomy** (later; this is pelvic MRI, not MSK).

It is a reading aid first, but it **teaches as you use it**: clicking a structure gives what it is, normal values, variants and pitfalls. **(owner)**

## 2. Goals

1. **One excellent normal knee, then the hip** (two linked hip cases, §7). **(owner)**
2. **Getting oriented** (§4): reference lines with a shared cursor across planes, and following one structure through the stack. **(owner: mockups A and B)**
3. **A painting mode that is easy to use** (§5), for the owner and for a helper they recruit. It has three named pains to remove: tracing outlines, typing full structure names, and going image by image. **(owner)**
4. **A teaching panel** (§6) in which written variant descriptions answer "could it?" questions. **(owner: "descriptor of variants may be enough")**

## 3. Non-goals, anti-goals, constraints

**Non-goals for now**
- **Other regions:** shoulder, rectal pelvis, ankle, wrist, elbow, spine and the rest. These come after the hip.
- **Named-level ladder** (mockup C). **(owner: not chosen)**
- **Oblique reslicing to match the clinical plane** (mockup D). Not chosen. My call: it probably comes back with the shoulder, where oblique planes matter most.
- **A gallery of variant scans.** Text descriptions are enough. **(owner)**
- **Hosting, remote access, or running on the hospital workstation.** The owner uses it on their own laptop. **(owner)**
- **AI click-to-outline** (nnInteractive and similar) is deferred (§5.4). **(my call, from research)**
- **The OAI's extra knee sequences via NDA** (TSE fat-sat). DESS is acceptable. **(owner)**
- **Phone.** Keep the existing phone layout working, but it isn't a target. **(my call: the owner said "computer screen")**

**Anti-goals.** These make it a failure even if it technically works. **(owner)**
- **A UI that's awkward to use in the middle of a case.** It must be quick to open, quick to get oriented, and must not need fiddly controls.
- **Barriers to labelling:** typing names, tracing contours, working slice by slice, or setup hassle before painting can start.

**Constraints**
- **Where it runs.** The owner's own Mac (Apple M4 Pro, 48 GB, ~420 GB free), in a browser on that laptop, next to the reading workstation. **(owner)**
- **Server.** It is served by `tools/serve.py`, a standard-library server bound to 127.0.0.1. The default port moves from 8000 to **8004**. **(my call:** 8000 is taken by protocol_manager's MkDocs in the owner's port map; 8004 was free on 2026-11-05.**)**
- **Offline.** All JS is vendored. NiiVue 0.69.0 is pinned at `viewer/vendor/niivue.umd.js`.
- **Dataset terms.**
  - Personal, non-commercial use only.
  - Imaging and label maps never go to git (already enforced by `.gitignore`).
  - Nothing is published.
- **Knee data.** The sequence is OAIZIB-CM **sagittal 3D DESS**. The owner is fine with how it differs from PD fat-sat. **(owner)**
- **Python.** The repo `venv` is 3.13.5. The owner's system Python is 3.14, so new venvs use `python3.13`.

## 4. Getting oriented (viewer, standalone mode)

### 4.1 Reference lines and a shared cursor (mockup A)

- **Layout.** The main view is a large image in the chosen plane. Two small views of the other two planes sit beside it. **(owner)**
- **Reference lines.** Each small view draws a line where the main view's current slice sits. The line moves as you scroll. **(owner)**
- **Shared cursor.** Pointing at a spot in the main view marks the same millimetre point in both small views. **(owner)**
- **Small views stay put on hover.** Moving the pointer over the main view doesn't re-slice the small views. It only moves a marker along their reference line to show where the pointer sits. **(owner: chose this over live PACS-style re-slicing)**
- **Clicking in the main view** does two things at once:
  - it opens the clicked structure's details (as now);
  - it moves both small views to slices that pass through that point. **(owner)**
- **Jumping.** Clicking a small view moves the main view to that point. The main view's slice changes to pass through it. **(owner)**
- **Small-view interaction** (my call):
  - Hovering in a small view also names the structure under the cursor, as it does in the main view.
  - Scrolling over a small view does nothing.
  - Swapping planes takes one key (the existing `1`–`3`), and the small views update to match.
- **Replaces "3-up".** This layout replaces the existing equal "3-up" mode as the standalone default. **(my call)** Sidebar mode is unchanged (§8).
- **Builder notes.**
  - NiiVue 0.69.0 has `heroImageFraction`, `multiplanarLayout` / `setMultiplanarLayout`, and `syncWith` / `broadcastTo` for linked instances.
  - Either one instance in a multiplanar hero layout or three synced instances may be the cleaner route. Builder's choice.
  - Hover highlighting and the name readout must keep working in every view.

### 4.2 Follow one structure (mockup B)

1. **Pick a structure** in any of these ways:
   - click it in the image;
   - use find (`/`), which already exists;
   - pick it from the painting-mode list.
2. **Stays highlighted.** Once picked, it stays highlighted, even when the cursor is elsewhere, until you clear it (Esc). **(owner)**
3. **Slice range on the slider.** The slider shows the range of slices the structure appears on in the current plane. Stepping (wheel, ↑/↓) moves through the stack as normal. **(owner)**
4. **Jumps.** Three jumps are available: **Start**, **Widest** (the slice with the most voxels of it) and **End**. **(owner)**
5. **Small views highlight it too**, so you can see where it runs in the other planes. **(my call: "the two should work together")**
   - When a structure is picked, the small views move to pass through it, at a voxel on its widest slice. That way they can't miss it.
   - They show its **cross-section** on that slice, using NiiVue's own highlight.
   - A projected "whole course" footprint is **not** built now. Thin oblique ligaments show only as a dot in a cross-section, so the footprint may be worth adding after the owner has used the cross-section version. **(my call, from the builder check)**
6. **Point labels.** For a point label, the range is the slices where its marker shows. Start, Widest and End collapse to the one slice the point is on.

**Per-plane slice extents and voxel counts.** These can be computed in the browser from the label map when it loads, or precomputed into `lut.json` by `build_case.py`. Either way they must refresh after painting. Builder's choice.

## 5. Painting mode (author mode)

This replaces "Phase D: author mode" in the existing plan. **The bar is "easy to use"** for the owner and for a helper who has never seen it. **(owner)**

### 5.1 Getting started

- **One command, no extra installs.** `python tools/serve.py` (the existing requirements only), then open `viewer/?case=<id>&mode=author`.
- **A link from the standalone view.** **(my call)** The standalone view links to author mode when it's served from localhost. One screen of help, the existing `?` panel, covers the tools and keys.

### 5.2 No typing names (owner pain)

- **Structures come from the region's checklist** (`checklists/knee.md`, later `hip.md`), in checklist order.
- **The next one is shown.** The UI shows the next structure not yet labelled ("Next: ligament of Wrisberg"). One key accepts it and moves on. **(my call, agreed in conversation)**
- **Choosing a different structure.** Pick from a list, or type a few letters to filter it. A full name is never typed.
- **Checklist columns.** Each structure's type (region or point) comes from the checklist's existing Type column. Its "Labelled" status updates automatically when you save. Builder's choice whether status lives in the Markdown or in a small JSON file the checklist is generated from. The owner edits the list itself freely.
- **Adding a structure.** A structure that isn't on the checklist is added by editing the checklist. Rare, so there's no UI for it. **(my call)**

### 5.3 No tracing, not image by image (owner pains)

All of these are built into the vendored NiiVue. They were verified by name in `viewer/vendor/niivue.umd.js` and the NiiVue demos.

| Tool | NiiVue | Use |
|---|---|---|
| Brush, with size control | `setPenValue`, pen | Paint *inside* a structure. No outline tracing |
| Smart fill / magic wand | `clickToSegment*` options, `drawFloodFill` (intensity window, max distance mm, 2D or 3D) | Click a structure and it fills similar signal, stopping at edges. Ligaments and tendons are dark on DESS, so dark mode matters |
| Fill between slices | `interpolateMaskSlices(lo, hi, {useIntensityGuided: true, …})` | Paint every 3rd–5th slice, then fill the gaps guided by image signal. It only adds voxels, and only between the first and last painted slices of each label |
| Grow | `drawGrowCut()` | Spread a few strokes through a large muscle (hip rotators, pelvic floor) |
| Eraser, undo | pen value 0, `drawUndo()` | Correct mistakes |
| Point | — (`points.json`) | Place a marker for a structure too small to paint |

- **The ligament workflow** (my call, from research): paint 2–3 key slices → fill between → scroll through and touch up, with the reference lines (§4.1) showing the structure's course in the other planes.
- **Defaults** are tuned so the common case needs no settings. This means a sensible intensity window and distance cap for the magic wand on DESS.
- **Painting is restricted to the current structure.** It must not overwrite other structures unless asked to (`drawFillOverwrites` exists).

### 5.4 AI click-to-outline: deferred (my call, from research 2026-11-05)

- **No Mac support.** nnInteractive needs an NVIDIA GPU. Its napari plugin calls it "prohibitively slow" on Apple Silicon. One report gives about 120 s per click on CPU. A pull request adding Mac (MPS) support to the 3D Slicer extension was closed unmerged in May 2026.
- **Other models are a poor fit.** MedSAM2, SAM-Med3D, VISTA3D and SegVol are CT-focused, slice-by-slice, or have unproven Mac support.
- **None has been shown to work on ligaments or tendons.**
- **Route if NiiVue's tools prove too slow:** nnInteractive's torch-free client (`nninteractive-client`) inside `serve.py`, talking to a GPU rented only for painting sessions. Code is Apache-2.0; weights are CC BY-NC-SA 4.0.
- **Not to be built now.**

### 5.5 Saving

- **What gets saved.** A save endpoint in `serve.py` writes the label map (`labels.nii.gz`), `lut.json` and `points.json` into the case folder.
- **Backups.** Hand-painted maps are hours of work. Every save first keeps the previous files as a timestamped backup inside the case folder, and the last 20 are kept. **(my call)**
- **Nothing is lost on reload.** An unsaved change survives a page reload. Builder's choice: autosave or a clear unsaved marker plus a warning on leaving.
- **Bound to 127.0.0.1 only.** The existing behaviour stays.

### 5.6 A helper paints too (owner: "or recruit someone to help me")

- **Getting the case to the helper.** The owner gives the helper a copy of the case folder by direct file transfer, never via git. The repo code is shared as usual.
  - The dataset's licence allows this non-commercial sharing.
  - The builder confirms the OAIZIB-CM terms on the Hugging Face page and notes them in `meta.json`.
- **Painting.** The helper runs the same `serve.py` and painting mode on their own machine. Their saves go to their own copy.
- **Merging back** (my call):
  - A merge tool (CLI or author-mode screen) brings the helper's label map into the owner's, **structure by structure**.
  - The owner sees each incoming structure overlaid on their case and accepts or skips it.
  - Accepting replaces that structure's voxels in the owner's map.
  - Voxels where an incoming structure overlaps a different structure in the owner's map are shown, and the owner's map wins unless they say otherwise.
  - Points merge the same way.
- **Helper's machine.** The helper may not be on a Mac, so the helper path uses only the standard library plus `requirements.txt`.

### 5.7 Structures that don't show on a normal scan

- **Bursae (and recesses):** collapsed on a normal scan, so they can't be painted as seen. **(my call, agreed in conversation)**
  - They are painted as **expected location** regions: a flag in `lut.json`, drawn with a dashed outline and never a fill.
  - The panel notes that the structure is only visible when distended.
  - This applies to the knee bursae now, and to the trochanteric, gluteal and iliopsoas bursae on the hip.
- **Too small or faint on DESS** (e.g. arcuate ligament, anterolateral ligament, genicular arteries): these become **point labels**, or come off the checklist. That is decided per structure while painting. The checklist's Type column is the record.

## 6. Teaching panel (standalone mode)

- **Existing panel and schema unchanged.** The panel and the `labels/<id>.json` schema stay as they are: name, TA2, description, normal values, variants and pitfalls, Radiopaedia link, related structures, `reviewed` flag, with a "Draft — not reviewed" badge.
- **Variant writing.** Variants and pitfalls carry the "could it?" answers. They should be written as answers a reader can use mid-case, with prevalence where it is known. Examples:
  - how often each meniscofemoral ligament is present;
  - how close they come to mimicking a posterior horn tear;
  - the lateral meniscus root and how far its posterior horn can sit medially.
- **Who writes it.** Claude drafts with `reviewed: false`, and the owner reviews. Clinical accuracy comes first.
- **Expected-location structures** (§5.7) show the "visible only when distended" note.

## 7. Data and cases

### 7.1 Knee (first)

- **Dataset.** OAIZIB-CM, as in the existing plan. Download with a free Hugging Face account:
  - `imagesTr.zip` (~10 GB);
  - `imagesTs.zip` (~2.5 GB): 3 of the 17 candidates (cases 414, 420 and 422) are in the test split;
  - `info.zip`, which holds the KL grade, age and BMI to rebuild the candidate list exactly. The earlier candidate, OAI 9208055, is `oaizib_049`.
- **Picking the normal.** It must be a knee the owner has actually looked at.
  - The builder makes the **17 candidate normals** (KL0, age ≤ 55, BMI 18.5–25) viewable in the existing viewer as quick image-only cases.
  - The owner scrolls each for meniscal, marrow and ligament findings, then picks one.
  - The rest are deleted afterwards. **(my call)**
- **Building the case.** Build the chosen knee with `build_case.py --preset oaizib-cm` and verify the label mapping against the dataset README.
- **Auto-labels** for the big structures (existing Phase C):
  - dataset ground truth: femur, tibia, cartilage;
  - DOSMA: menisci, patellar cartilage;
  - TotalSegmentator MR: patella, fibula, muscles.
  - **Risk:** DOSMA (TensorFlow) and TotalSegmentator may not run cleanly on Apple Silicon. Check each one early. Anything that won't run gets painted instead: the menisci are dark triangles and suit the magic wand.
- **Left knee: a flipped copy.** **(owner)**
  - **Why.** All OAIZIB-CM knees are right knees. A generated **left-knee case** is made by mirroring the right knee left to right: volumes, label map, points and centroids.
  - **Viewer.** It appears as its own case in the viewer.
  - **Rebuild rules.**
    - The right knee is the only one ever painted.
    - The left copy is rebuilt from it after every save, so it never drifts.
    - It is never painted directly. Author mode refuses it.
  - **Labelling.** Its `meta.json` says it is a mirrored copy of the right knee.
  - **Switching sides** (my call): a right/left switch moves between the two and lands on the mirrored millimetre point.
- **The core knee set**, painted first, is the minimum for "it works". **(agreed in conversation)**

  | Group | Structures |
  |---|---|
  | Bones | Femur, tibia, fibula, patella |
  | Menisci | Horns and bodies, plus the posterior roots |
  | Cruciates | ACL, PCL |
  | Collaterals | MCL superficial and deep, LCL |
  | Posterolateral corner | Popliteus tendon and muscle, popliteofibular ligament, biceps femoris tendon, arcuate ligament if visible |
  | Meniscofemoral ligaments | Humphry, Wrisberg |

  The rest of `checklists/knee.md` gets filled in over time.

### 7.2 Hip (second): two linked cases

The owner wants both kinds of view. **(owner: "Yes both")**

- **Hip — around the joint** (larger field of view, both hips and pelvic floor if possible):
  - gluteus medius, minimus and maximus muscles and tendons, and the greater trochanter facets they insert on;
  - TFL and IT band;
  - trochanteric, subgluteus medius, subgluteus minimus and iliopsoas bursae, as expected locations;
  - deep rotators: piriformis, the gemelli, obturator internus and externus, quadratus femoris;
  - ischiofemoral space, hamstring origin, iliopsoas, adductors, sciatic nerve;
  - pelvic floor: levator ani parts and coccygeus.
- **Hip — the joint** (small field of view): acetabular labrum, cartilage, ligamentum teres, transverse acetabular ligament, capsule and its ligaments (iliofemoral, ischiofemoral, pubofemoral), zona orbicularis.
- **Linking** (my call): a switch in the viewer moves between the two cases. Because they come from one session, they share scanner coordinates, so the switch lands on the same millimetre point.
- **Data source: still open.** No free, labelled, normal hip MRI is known at either field of view. The TotalSegmentator MR dataset has some hip bones and muscles, but its licence is unconfirmed.
  - The likely route is a **volunteer scan**. One session would give one 3D isotropic sequence per field of view: a large-field 3D fluid-sensitive pelvis and a small-field 3D PD fat-sat hip. The consent, incidental-findings and IRB/QA steps already in `CLAUDE.md` apply.
  - **Search for public hip data first** when the hip starts. The knee work never waits on this.
- **Checklist.** `checklists/hip.md` is drafted by Claude from the lists above, for the owner to edit.

## 8. ARIA sidebar

Unchanged from the existing plan. It is a name-on-hover-only embed and comes after the knee. It gets the new layout only if the builder finds it costs nothing; otherwise it keeps its current single view. **(my call)**

## 9. Build order (proposed by Claude, accepted by the owner: "That's good")

1. **Real knee.**
   - Download OAIZIB-CM.
   - Make the 17 candidates viewable.
   - The owner picks one.
   - Build the case and verify the mapping and orientation.
   - Generate the mirrored left-knee copy.
2. **Getting oriented** (§4): reference lines, the shared cursor, and following a structure.
3. **Auto-labels for the big structures** (§7.1).
4. **Painting mode** (§5): checklist-driven, smart fill, fill between, grow, points, expected locations, saving with backups, and the helper merge.
5. **Paint the core knee set and draft its text.** The owner paints; Claude drafts the `labels/*.json` files and the owner reviews them.
6. **Hip.** Search for data or set up a volunteer scan, draft the checklist, then build the two linked cases.

**Phase 0's "open on the reading-room workstation" step is dropped.** It isn't used there. **(owner)**

## 10. Changes to CLAUDE.md (do these with step 1)

- **Region order:** knee → hip → (shoulder, others later). Not knee → shoulder → ankle → hip.
- **Where it runs:** on the owner's own Mac and laptop. Remove the workstation WebGL2 test and the departmental-server framing as the target. They can stay as an optional future note.
- **Port:** default 8004.
- **Key decisions table:** "ARIA sidebar shows name only" stays. The rationale should no longer say the atlas isn't a teaching resource, because the standalone view does teach.
- **Build sequence:** replace it with §9. Phase D becomes the painting mode described here.
- **Mockups:** add `.superpowers/` (brainstorm mockups) to `.gitignore`.

## 11. Left to the builder

- How the reference lines are implemented (one NiiVue instance in a hero layout, or synced instances).
- Where per-structure slice extents are computed.
- How checklist "Labelled" status is stored and updated.
- Save format details, autosave or not, and backup naming.
- The merge tool's form: CLI or a screen.
- Magic wand and interpolation defaults for DESS.
- Exact key bindings, beyond keeping the existing ones.
- How the 17 candidates are presented for review.
- Tests:
  - Python tools get unit tests.
  - Viewer behaviour gets checked in a real browser on the owner's Mac. The earlier spike used headless Chrome with software rendering.
