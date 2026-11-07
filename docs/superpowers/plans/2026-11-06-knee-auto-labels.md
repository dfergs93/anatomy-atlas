# Knee auto-labels: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic labels to `knee-mri` for the structures a model can find on OAI DESS, so painting starts from them instead of from nothing:
- the menisci, each split into anterior horn, body and posterior horn;
- the patellar cartilage;
- the patella and fibula, when the owner has a TotalSegmentator licence.

**Architecture:**
- **Models run in their own venv**, `venv-autoseg/` (TensorFlow + TotalSegmentator). The main `venv/` and `requirements.txt` stay light, so the helper's painting path is unchanged (spec §5.6).
- **`tools/autoseg/dosma_unet.py`** runs DOSMA's `iwoai-2019-t6-normalized` 2D U-Net on one NIfTI and writes its raw prediction on the same grid. It imports TensorFlow lazily, so its orientation and download helpers can be tested from the main venv.
- **TotalSegmentator** runs through its own CLI (`appendicular_bones_mr`) only when a licence is set.
- **`tools/autolabels.py`** runs in the main venv. It does the post-processing:
  - split medial from lateral;
  - split each meniscus into thirds;
  - keep the largest piece;
  - merge into the case without overwriting any existing voxel;
  - back up first, then rebuild the mirrored left copy.
- **The viewer** marks automatic outlines as "not yet checked" in the details panel.

**Tech stack:**
- Main venv: Python 3.13 (`venv/`), nibabel, numpy, scipy, pytest. Node 25 `node --test` for `core.js`.
- `venv-autoseg/` (Python 3.13): TensorFlow 2.21.0 with tf_keras 2.21.0 (CPU), TotalSegmentator 2.18.0 (torch, MPS).

**Spec:** `docs/superpowers/specs/2026-11-05-anatomy-atlas-design.md`, sections 3, 5.5 (backups), 5.6 (helper path stays light), 7.1 (auto-labels, left copy rebuilt after every save) and 9 (step 3).

**Feasibility facts (checked 2026-11-06 on the owner's M4 Pro, subject 036; scripts and outputs are in this session's scratchpad):**
- **DOSMA runs.**
  - DOSMA's own package breaks on NumPy 2, so the runner rebuilds its U-Net with `tf_keras` and loads the weights directly. All 39 layers were checked against the weights file.
  - Speed: CPU, about 18 s per knee.
  - Accuracy on femoral cartilage: Dice 0.756 against ground truth.
  - Menisci and patellar cartilage look right: triangles on sagittal, C-shapes on axial.
  - Weights: public, from Hugging Face `arjundd/dosma-models`, file `iwoai-2019-t6-normalized/iwoai-2019-unet2d-normalized_fc-tc-pc-men_weights.h5`, 138,536,872 bytes, sha256 `a175bf63f22c9c2308a0fc7d0fdb8b5ecf6cd2f875dde1de8f385dc4e0e91fd1`. DOSMA's docs say GPL-3.0.
  - Model input: sagittal slices, rows superior→inferior, columns anterior→posterior, whole volume `(x − mean) / std`.
  - Model output: 4 sigmoid channels (femoral cartilage, tibial cartilage, patellar cartilage, menisci), thresholded at 0.5. A flipped input breaks it.
- **TotalSegmentator runs**, on MPS in about 15 s.
  - The open `total_mr` model finds only the femur on this knee.
  - `appendicular_bones_mr` (patella 1, tibia 2, fibula 3) needs a free academic licence, which only the owner can request. Without one it exits with code 1.
  - Output is on the input grid, but the model works at 1.5 mm, so outlines are blocky.
  - No TotalSegmentator task covers the knee muscles (gastrocnemius, popliteus and the rest).

## Global constraints

- **No imaging in git.** No `.nii`/`.nii.gz`/`.dcm`/`.h5` is ever committed. Stage files by name; never `git add -A` or `git add .`.
- **Ignored by name.** `venv-autoseg/`, `data/*/backups/` and `data/*/auto/` are git-ignored. Backups hold `lut.json` copies, which the `data/**/*.json` rule would otherwise let in.
- **Two venvs.**
  - The main `venv/` keeps `requirements.txt` unchanged.
  - Model packages go only in `requirements-autoseg.txt`, pinned to the versions above.
  - Tests run in the main venv. Tests that need `venv-autoseg/`, the weights or the dataset skip themselves when those are missing.
- **Licences.**
  - `tools/autoseg/dosma_unet.py` starts with `# SPDX-License-Identifier: GPL-3.0-or-later` and a line saying the network is adapted from DOSMA (ad12/DOSMA, `dosma/models/oaiunet2d.py`).
  - Weights download at run time to `~/.cache/anatomy-atlas/dosma/` and are checked against the pinned sha256.
  - The TotalSegmentator licence key is never written into the repo.
- **Existing labels win.** Auto-labels only fill voxels that are 0. An id already in the LUT without an `auto` key is never replaced.
- **Mirrored copies are never labelled** (spec §7.1). The tool refuses a case with `mirror_of` and rebuilds the copy after every merge.
- **Backups** (spec §5.5): before writing, copy `labels.nii.gz`, `lut.json` and `points.json` to `data/<case>/backups/<UTC timestamp>/`. Keep the newest 20.
- **Python and tests.** `venv/bin/python -m pytest` and `node --test "tests/viewer/*.test.mjs"`.
- **Commit messages** end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018rxg1P1FJjBGEHBhNbSmQY
  ```
- **Branch:** `auto-labels`, made from `main` at 8d2ece3. It holds this plan.

## Review focus

1. **Menisci joined across the middle**, or a fragment on the wrong side. Each voxel goes to the nearer plateau, then each side keeps its largest piece. Task 2 `test_split_sides_breaks_a_bridge`.
2. **The lateral meniscus is nearly a full ring.** The angle cut must sit in its gap, facing the notch, so the horns don't swap or wrap. Task 2 `test_thirds_on_a_near_ring`.
3. **Re-running after painting.** Painted voxels and non-auto ids are never overwritten. Re-running replaces only the tool's own earlier auto voxels. Task 3 `test_merge_never_overwrites`, `test_rerun_replaces_own_auto_only` and `test_refuses_non_auto_id_clash`.
4. **Missing pieces** (no `venv-autoseg/`, no weights or network, no licence, a mirrored case). The tool gives a clear message, and the case files are byte-identical afterwards. Task 4 `test_refuses_mirror_case`, `test_missing_venv_leaves_case_untouched`, and the licence-skip test.
5. **Wrong model orientation on an oblique RAS volume.** Round trip plus a real Dice check. Task 1 `test_orientation_round_trip` and `test_dosma_real_dice` (skips when unavailable).

---

### Task 1: Model environment and the DOSMA runner

**Files:**
- Create: `requirements-autoseg.txt`:
  - `tensorflow==2.21.0`, `tf_keras==2.21.0`, `h5py==3.14.0`
  - `TotalSegmentator==2.18.0`
  - `nibabel>=5`, `numpy>=1.24,<2.6`, `scipy>=1.10`
- Modify: `.gitignore`. Add `venv-autoseg/`, `data/*/backups/` and `data/*/auto/` after the `data/**` rules, each with its comment on its own line.
- Create: `tools/autoseg/__init__.py` (empty) and `tools/autoseg/dosma_unet.py`.
- Test: `tests/test_dosma_unet.py`

**Interfaces:**
- Produces, in `dosma_unet.py`:
  - `WEIGHTS_URL: str`, `WEIGHTS_SHA256: str`, `WEIGHTS_SIZE = 138536872`
  - `weights_path(cache: Path = Path("~/.cache/anatomy-atlas/dosma")) -> Path`: downloads to `<name>.part` with `urllib`, checks size and sha256, then renames. If the file is already present and valid, it is reused. A mismatch raises `ValueError`.
  - `to_model(arr, affine) -> np.ndarray`: shape (slices, SI, AP), rows superior→inferior, columns anterior→posterior. Uses `nib.orientations`, as in the scratchpad runner.
  - `from_model(arr_model, affine) -> np.ndarray`: the exact inverse, back to the input array's axes.
  - `normalise(x) -> float32`: whole volume `(x − mean) / std`.
  - `predict(img: Nifti1Image, weights: Path) -> np.ndarray[uint8]`: 1 femoral cartilage, 2 tibial cartilage, 3 patellar cartilage, 4 menisci. A voxel over 0.5 in two channels goes to the higher one. TensorFlow and `tf_keras` are imported inside this function, with `TF_USE_LEGACY_KERAS=1`. The network matches DOSMA's `IWOAIOAIUnet2D`: features 32…1024, two 3×3 ReLU convs plus BN (momentum 0.95, ε 0.001) per level, transpose-conv up, 1×1 sigmoid with 4 channels.
  - CLI: `python dosma_unet.py <in.nii.gz> <out.nii.gz>`. It writes uint8 on the input affine.

- [ ] **Step 1: Make the venv.**
  Run: `python3.13 -m venv venv-autoseg && venv-autoseg/bin/pip install -r requirements-autoseg.txt && venv-autoseg/bin/python -c "import tensorflow, tf_keras, totalsegmentator, nibabel; print('ok')"`
  Expected: `ok`. If TensorFlow and TotalSegmentator can't share one venv, split it into `venv-dosma/` and `venv-totalseg/` and ledger a ruling.
- [ ] **Step 2: Write the failing tests** in `tests/test_dosma_unet.py` (main venv):
  - `test_orientation_round_trip`: a random (4, 5, 6) array with an oblique RAS affine (the cand-049 matrix from `tests/viewer/core.test.mjs`). `from_model(to_model(a))` equals `a`. On a RAS input, `to_model(a)[i]` equals `a[i, ::-1, ::-1].T`: rows run from superior, columns from anterior.
  - `test_normalise_zero_mean_unit_std`.
  - `test_weights_path_rejects_bad_hash`: a pre-placed file of the right size with the wrong bytes in a tmp cache raises `ValueError`, and the file isn't left looking valid.
  - `test_dosma_real_dice`: skips unless `venv-autoseg/bin/python`, a valid cached weights file and `~/datasets/OAIZIB-CM/candidates/oaizib_036_0000.nii.gz` all exist. It runs the CLI through that venv into `tmp_path`, then checks the Dice of class 1 against label 2 of `oaizib_036.nii.gz` is ≥ 0.70.
- [ ] **Step 3: Run them.** `venv/bin/python -m pytest tests/test_dosma_unet.py -v`. Expected: FAIL (`dosma_unet` doesn't exist yet).
- [ ] **Step 4: Implement `dosma_unet.py`** with the interface above and the GPL header. To seed the cache without downloading again, copy this session's scratchpad weights file into `~/.cache/anatomy-atlas/dosma/`; `weights_path` still checks it.
- [ ] **Step 5: Run them.** Expected: PASS, with `test_dosma_real_dice` running, not skipping, and Dice about 0.75.
- [ ] **Step 6: Commit** `requirements-autoseg.txt .gitignore tools/autoseg/__init__.py tools/autoseg/dosma_unet.py tests/test_dosma_unet.py` with the message "DOSMA knee model runner in its own venv".

### Task 2: Medial / lateral and meniscus thirds

**Files:**
- Create: `tools/autolabels.py` (post-processing part)
- Test: `tests/test_autolabels.py`

**Interfaces:**
- Produces, in `autolabels.py`:
  - `largest_component(mask) -> mask`: 3D, 26-connected.
  - `split_sides(mask, affine, medial_x: float, lateral_x: float) -> (medial, lateral)`: each voxel goes to the nearer of the two world x positions, then each side keeps its largest component.
  - `meniscus_thirds(mask, affine, centre_xy, mid_x) -> (anterior_horn, body, posterior_horn)`:
    - The angle is `atan2(y − cy, (x − cx) · outward)` in world mm, where `outward = sign(cx − mid_x)`. The periphery is near 0°, anterior is positive, and the opening toward the notch is at ±180°.
    - Cut points sit at ⅓ and ⅔ of the span between the 0.5th and 99.5th percentile angles.
    - Every voxel of `mask` lands in exactly one part.

- [ ] **Step 1: Write the failing tests.**
  - `test_largest_component_drops_fragments`
  - `test_split_sides_assigns_by_nearer_plateau`
  - `test_split_sides_breaks_a_bridge`: two blobs joined by a thin bar across the midline.
  - `test_thirds_on_a_c_shape`: a synthetic C, 1 mm voxels, open toward `mid_x`. Its anterior part has the highest mean y and its posterior part the lowest. Each part holds 20–45 % of the voxels, and the parts don't overlap and cover the whole mask.
  - `test_thirds_on_a_near_ring`: a 330° ring whose gap faces the midline. Same assertions; neither horn touches both ends.
  - `test_thirds_mirror_side`: the same C on the other side of `mid_x` (outward −1). Anterior and posterior are unchanged.
- [ ] **Step 2: Run them.** `venv/bin/python -m pytest tests/test_autolabels.py -v`. Expected: FAIL (import error).
- [ ] **Step 3: Implement the three functions.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** `tools/autolabels.py tests/test_autolabels.py` with the message "Auto-labels: medial/lateral split and meniscus thirds".

### Task 3: Merging into a case, with backups

**Files:**
- Modify: `tools/atlaslib.py`. Add `backup_case(case_dir: Path, keep: int = 20) -> Path`.
- Modify: `tools/autolabels.py` (merge part).
- Test: `tests/test_atlaslib.py`, `tests/test_autolabels.py`

**Interfaces:**
- `backup_case(case_dir, keep=20) -> Path`:
  - copies `labels.nii.gz`, `lut.json` and `points.json`, whichever exist, to `case_dir/backups/<YYYYmmddTHHMMSSffffffZ>/`;
  - deletes the oldest folders beyond `keep`;
  - returns the new folder.
- `merge_auto(arr, lut, additions: dict[str, np.ndarray], source: str, names: dict[str, str], date: str) -> (arr, lut, report)`:
  - `additions` is id → mask, all on `arr`'s grid.
  - **Value choice.** An id already in `lut` with an `auto` key keeps its value. Its old voxels are cleared first, then it is re-added. A new id gets `max(existing values) + 1`, in the order given.
  - **Refusal.** An id already in `lut` without `auto` is refused: it goes in `report["refused"]` and the array is untouched for it.
  - **No overwriting.** Only voxels that are 0 after clearing are written. Voxels held by other structures are counted in `report["blocked"][id]`.
  - **LUT entries** get `{"id", "name": names.get(id, …), "rgb": build_case.colour(id, value), "auto": {"source": source, "date": date}}`. The caller then recomputes the full LUT with `build_lut`, which keeps extra keys.

- [ ] **Step 1: Write the failing tests.**
  - `test_backup_case_keeps_newest_20`: make 22 backups in `tmp_path`, check 20 remain and the newest is the last.
  - `test_merge_never_overwrites`: base label 1 covers half a mask. Only the other half is written; `blocked` gives the count.
  - `test_rerun_replaces_own_auto_only`: merge, then merge a shifted mask with the same id. The old voxels are gone, the value is unchanged, and label 1 is untouched.
  - `test_refuses_non_auto_id_clash`: a lut with `femur` and no `auto`, plus an addition `femur`. It is refused and the array is unchanged.
  - `test_new_ids_get_next_values_and_auto_key`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement both functions.**
- [ ] **Step 4: Run them.** Expected: PASS. The full suite stays green.
- [ ] **Step 5: Commit** `tools/atlaslib.py tools/autolabels.py tests/test_atlaslib.py tests/test_autolabels.py` with the message "Auto-labels: merge without overwriting; backups before writing".

### Task 4: The `autolabels` command, run on knee-mri

**Files:**
- Modify: `tools/autolabels.py` (CLI)
- Test: `tests/test_autolabels.py`

**Interfaces:**
- `run(root: Path, case_id: str, *, autoseg_python: Path, totalseg: bool | None = None, licence_file: Path = Path("~/.totalsegmentator/config.json")) -> dict`: returns a report.
- CLI: `venv/bin/python tools/autolabels.py <case_id> [--no-totalseg]`.
- Order:
  1. **Check everything first.** `meta.json` has no `mirror_of`. `autoseg_python` exists. The LUT has `medial_tibial_cartilage` and `lateral_tibial_cartilage`, whose centroids give `medial_x`, `lateral_x`, each plateau's `centre_xy` and `mid_x`.
  2. **Run DOSMA** through `autoseg_python` on `volumes/<reference_sequence>.nii.gz` into `data/<case>/auto/dosma.nii.gz`.
  3. **Run TotalSegmentator, if allowed.** `totalseg` is None means "if `licence_file` has a `license_number`". The command is `TotalSegmentator -i … -o auto/bones.nii.gz --ml --task appendicular_bones_mr --device mps`, falling back to `cpu` if MPS fails. Otherwise print one line saying it was skipped and how to get the licence.
  4. **Additions:**
     - DOSMA class 4 → `split_sides` → `meniscus_thirds` on each side → `{medial,lateral}_meniscus_{anterior_horn,body,posterior_horn}`.
     - DOSMA class 3 → `largest_component` → `patellar_cartilage`.
     - If bones ran: class 1 → `patella` and class 3 → `fibula`, each through `largest_component`.
     - DOSMA classes 1–2 and TotalSegmentator's tibia are not used, because ground truth exists.
  5. **Write.** `backup_case` → `merge_auto` (source `"DOSMA iwoai-2019-t6-normalized"` or `"TotalSegmentator appendicular_bones_mr"`, names from `build_case.checklist_names`) → `build_lut` → write `labels.nii.gz` (intent label, `clean_header`) and `lut.json` → `patch_case(structure_count)` → `mirror_case.mirror_case(root, case_id)` if `meta.side` is set.
  6. **Report** per id: voxels written, blocked, refused, skipped.
- Any failure in steps 1–3 raises `SystemExit` with a message before anything in the case changes.

- [ ] **Step 1: Write the failing tests.** These use a tiny synthetic case in `tmp_path`, built with `build_case`, plus a fake `autoseg_python` script that writes a fixed prediction:
  - `test_refuses_mirror_case`
  - `test_missing_venv_leaves_case_untouched`: the bytes of `labels.nii.gz` and `lut.json` are unchanged.
  - `test_totalseg_skipped_without_licence`: no `license_number` → no bones in the report, and the skip message is printed.
  - `test_run_end_to_end_on_fake_prediction`: six meniscus ids and `patellar_cartilage` are in the LUT with `auto`, ground-truth voxels are unchanged, a backup folder exists, and the mirror is rebuilt.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement `run` and the CLI.**
- [ ] **Step 4: Run them.** Expected: PASS. The full suite stays green.
- [ ] **Step 5: Run it for real.**
  Run: `venv/bin/python tools/autolabels.py knee-mri`
  Expected:
  - Six meniscus parts, each non-empty. Each part holds 15–50 % of its meniscus. Medial parts have lower x than lateral ones. Anterior horns have higher y than posterior horns.
  - `patellar_cartilage` at about 33,000 voxels, anterior to the femur.
  - Patella and fibula only if the owner has set the licence by then; otherwise the skip line.
  - Ground-truth voxel counts unchanged.
  - `knee-mri-left` rebuilt, with the meniscus x signs reversed.
- [ ] **Step 6: Look at it.** In Playwright on `?case=knee-mri`:
  - **Sagittal, medial plateau:** medial anterior and posterior horn triangles.
  - **Sagittal, far lateral:** the lateral body.
  - **Axial at the plateau:** three colours per C, in anterior / body / posterior order.
  - Follow `Lateral meniscus — posterior horn`.
  - Switch to L.
  - The console shows only the expected `labels/*.json` 404s.
- [ ] **Step 7: Commit** `tools/autolabels.py tests/test_autolabels.py data/knee-mri/lut.json` with the message "Auto-labels: menisci (thirds) and patellar cartilage on knee-mri".

### Task 5: "Not yet checked" in the panel, and the docs

**Files:**
- Modify: `viewer/core.js`. Add `autoNote(lutEntry) -> string | null`.
- Modify: `viewer/index.html` (`showPanel`, both branches)
- Modify: `CLAUDE.md`, `README.md`
- Test: `tests/viewer/core.test.mjs`

**Interfaces:**
- `autoNote({auto: {source: "DOSMA iwoai-2019-t6-normalized"}})` returns `"Outline drawn automatically (DOSMA iwoai-2019-t6-normalized) — not yet checked"`. With no `auto` key it returns `null`.
- The panel shows the note as a muted line under the heading. For regions it is looked up from `state.lut[t.value]`. Points never have one.

- [ ] **Step 1: Write the failing tests** `autoNote names the source` and `autoNote is null without auto`.
- [ ] **Step 2: Run them.** `node --test "tests/viewer/*.test.mjs"`. Expected: FAIL.
- [ ] **Step 3: Implement it,** and wire the panel.
- [ ] **Step 4: Run them.** Expected: PASS. Browser check: click a meniscus and the note shows; click the femur and there is no note; the sidebar mode is unchanged.
- [ ] **Step 5: Update the docs.**
  - **CLAUDE.md:**
    - Replace the "Base auto-labels" table with the feasibility facts above, plus how to run it: `venv-autoseg` setup, `tools/autolabels.py <case>`, and the licence steps.
    - The owner fills the form at https://backend.totalsegmentator.com/license-academic/ asking for `appendicular_bones_mr`, then runs `venv-autoseg/bin/totalseg_set_license -l aca_…`.
    - Note that the owner's TotalSegmentator config has `send_usage_stats: true`. It sends task name, platform and install id, never images.
    - Repo structure gets `tools/autolabels.py` and `tools/autoseg/`.
    - Build sequence step 3 is marked done, with "muscles: none available for the knee — painted".
  - **README:** a short "Auto-labels" section.
- [ ] **Step 6: Commit** `viewer/core.js viewer/index.html tests/viewer/core.test.mjs CLAUDE.md README.md` with the message "Viewer marks automatic outlines; docs for auto-labels".
