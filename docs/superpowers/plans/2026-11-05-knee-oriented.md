# Real knee you can get oriented in: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put one normal OAIZIB-CM knee, and a mirrored left copy, into the viewer, with reference lines, a shared cursor, and following a structure through the stack.

**Architecture:**
- **Python tools build the cases.** They share one module, `tools/atlaslib.py`. Each structure's per-plane slice range (its "extent") is precomputed into `lut.json` in millimetres, so the viewer can convert it to slice numbers on any grid.
- **The viewer stays a single static page.** Pure logic moves into `viewer/core.js`, which can be tested with Node. All NiiVue code stays in `viewer/index.html`.
- **The main view and two small views** come from one NiiVue instance using `setCustomLayout`. The reference lines and the hover marker are DOM overlays, drawn the same way as the existing point markers.

**Tech stack:**
- Python 3.13 (repo `venv/`), nibabel, numpy, scipy, pytest.
- NiiVue 0.69.0, vendored.
- Plain browser JS.
- Node 25 `node --test` for `core.js`.

**Spec:** `docs/superpowers/specs/2026-11-05-anatomy-atlas-design.md`, sections 3, 4, 7.1, 8, 9 (steps 1–2) and 10. This plan covers build steps 1–2. Painting, auto-labels and the hip come in later plans.

## Global constraints

- **Offline, no CDN.** NiiVue 0.69.0 is vendored at `viewer/vendor/niivue.umd.js`. Nothing is loaded from a CDN.
- **No imaging in git.** No `.nii`/`.nii.gz`/`.dcm` is ever committed.
  - Stage files by name. Never use `git add -A` or `git add .`, because `data/**/*.json` is not ignored. Generated and temporary cases are ignored by name: `data/demo-*/`, `data/knee-mri-left/`, `data/cand-*/`.
- **Python.** Use `venv/bin/python` (3.13.5). There are no new runtime dependencies: the helper path is the standard library plus `requirements.txt`.
- **Server.** `tools/serve.py` binds to 127.0.0.1, with the default **port 8004**.
- **Display conventions are unchanged.** Radiological (patient right on screen left). Sagittal has anterior on screen left.
- **Sidebar mode** (`?mode=sidebar`) stays a single view showing the name on hover, as now.
- **Narrow screens.** Windows 760 px wide or less (the existing phone breakpoint) keep a single view.
- **Dataset strings.**
  - Licence: `CC BY-NC 4.0`. It is confirmed by the Hugging Face tag and the `info/license` file in `info.zip`.
  - Citation (required by the dataset): `Yao Y et al. CartiMorph: a framework for automated knee articular cartilage morphometrics. Med Image Anal 2024;91:103035. Data from the Osteoarthritis Initiative.`
- **Commit messages** end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018rxg1P1FJjBGEHBhNbSmQY
  ```
- **Branch.** Work happens on branch `atlas-design`, which already holds the spec and this plan.

## Review focus

These are five inputs no happy-path test exercises. Each has a test pinned in the task that owns it.

1. **`lut.json` without an `extent` field** (cases built before this change, or a structure erased later). Following must hide its controls with no console errors. Task 6 `sliceRange(undefined)` and the Task 8 browser check.
2. **Oblique affines.** Mirroring must still put each voxel at the mirrored world point. Task 3 `test_mirror_oblique_affine`.
3. **Structures touching the volume edge**, or a point label on the first or last slice. Ranges must be clamped to `0…n-1`. Task 6 `pointRange` / `sliceRange` edge tests.
4. **Window narrowed to 760 px or less while running.** It must drop to a single view with no stale reference lines. Task 7 browser check.
5. **Dataset files that aren't laid out as expected.**
   - Blank or odd cells in `subInfo_*.xlsx` are skipped, not crashed on.
   - Zip members in unexpected folders are found by basename.
   - Task 4 `test_blank_cells_are_skipped` and `test_extract_finds_members_in_any_folder`.

---

### Task 1: Housekeeping and test setup

**Files:**
- Modify: `tools/serve.py`
  - Add `DEFAULT_PORT = 8004` and use it as the `--port` default.
  - Update the docstring's port.
- Modify: `README.md`
  - Change the port to 8004.
  - Add a "Tests" line: `venv/bin/pip install -r requirements-dev.txt`, then `venv/bin/python -m pytest` and `node --test tests/viewer/`.
- Modify: `.gitignore`: add `.superpowers/`, `data/knee-mri-left/` (the left copy is generated) and `data/cand-*/` (the candidate cases are temporary).
- Modify: `CLAUDE.md`, applying the spec's §10:
  - Region order: knee → hip, then the rest.
  - "Where it runs": the owner's own Mac and laptop. The workstation and departmental-server framing becomes an optional future note.
  - The port becomes 8004 everywhere it appears.
  - The Key-decisions row "ARIA sidebar shows name only" keeps the decision, but its rationale no longer says the atlas isn't a teaching resource.
  - The "Build sequence" block is replaced with the spec's §9 list. Phase D is now "painting mode (see spec §5)".
  - Link the spec path near the top.
- Create: `requirements-dev.txt` containing `-r requirements.txt` and `pytest>=8`.
- Create: `tests/conftest.py`, which puts `tools/` on `sys.path`.
- Test: `tests/test_serve.py`

- [ ] **Step 1: Install dev dependencies**
  Run: `venv/bin/pip install -r requirements-dev.txt`. Expected: pytest is installed.
- [ ] **Step 2: Write the failing test** `test_default_port_is_8004`: `import serve; assert serve.DEFAULT_PORT == 8004`.
- [ ] **Step 3: Run it.** `venv/bin/python -m pytest tests/test_serve.py -v` should FAIL with an AttributeError.
- [ ] **Step 4: Make the `serve.py`, README, `.gitignore` and CLAUDE.md changes listed above.**
- [ ] **Step 5: Run it again.** `venv/bin/python -m pytest tests/test_serve.py -v` should PASS.
- [ ] **Step 6: Start the dataset download now**, in the background (Task 5 step 1). It is about 12.6 GB and takes a while.
- [ ] **Step 7: Commit** `tools/serve.py README.md .gitignore CLAUDE.md requirements-dev.txt tests/conftest.py tests/test_serve.py` with the message "Housekeeping: port 8004, test setup, CLAUDE.md follows the design".

---

### Task 2: Shared case library and structure extents

**Files:**
- Create: `tools/atlaslib.py`
- Modify: `tools/build_case.py`
  - Move the helpers out into `atlaslib`.
  - Wrap the body of `main()` in `build_case()`.
- Modify: `tools/make_demo_case.py`: build each LUT entry with `atlaslib.lut_entry` (keeping its extra `"class"` key) and register it with `register_case`.
- Test: `tests/test_atlaslib.py`, `tests/test_build_case.py`

**Interfaces (produces):**

`tools/atlaslib.py`:
```python
PLANES = ("sagittal", "coronal", "axial")          # array axis 0, 1, 2 of a RAS-canonical volume
def load_ras(path: Path) -> nib.Nifti1Image        # moved from build_case
def clean_header(img: nib.Nifti1Image) -> None     # moved
def same_grid(a, b) -> bool                        # moved
def structure_extents(mask: np.ndarray, affine: np.ndarray) -> dict[str, dict]
    # {"sagittal": {"start_mm": float, "end_mm": float, "widest_mm": float, "anchor_mm": [x, y, z]}, "coronal": …, "axial": …}
def lut_entry(mask: np.ndarray, affine: np.ndarray, sid: str, name: str, rgb: list[int]) -> dict
    # keys: id, name, rgb, voxels, centroid_vox, centroid_mm, extent
def build_lut(arr: np.ndarray, affine: np.ndarray, base: dict[int, dict]) -> dict[str, dict]
    # base[value] holds at least id, name, rgb; extra keys are kept; values absent from arr are skipped
def register_case(root: Path, entry: dict) -> None                      # replace by case_id in data/index.json, creating it if missing
def patch_case(root: Path, case_id: str, fields: dict) -> None          # merge fields into an existing entry
def read_index(root: Path) -> list[dict]
```

`tools/build_case.py`:
```python
def build_case(root: Path, case_id: str, *, title: str, region: str,
               seqs: list[tuple[str, str, Path]], labels: Path | None = None,
               mapping: dict[int, str] | None = None, side: str = "", plane: str = "sagittal",
               source: str, licence: str, citation: str = "",
               index_extra: dict | None = None) -> dict   # returns meta
```
- Its index entry gains `"side"`, merged with `index_extra`.
- `main()` keeps today's CLI flags and calls `build_case(ROOT, …)`.

**Extent rules** (spec §4.2):
- **Slice coordinate.** For each plane's array axis, a slice's world coordinate is `(affine @ [i, j, k, 1])[axis]`, evaluated at the anchor voxel's other two indices.
- **Start and end** are the first and last slices containing the structure.
- **Widest** is the slice with the most voxels. If there's a tie, the lowest index wins.
- **Anchor** is the voxel inside the mask, on the widest slice, nearest that slice's in-slice centroid.
- **Rounding.** All mm values are rounded to 0.01.
- **Speed.** Crop to `scipy.ndimage.find_objects` bounding boxes, so a 100-label DESS map builds in seconds.

- [ ] **Step 1: Write failing tests** in `tests/test_atlaslib.py`:
  - `test_extents_box`:
    - Identity affine, 1 mm voxels, a box at x 10–14, y 20–29, z 5–7.
    - Expect sagittal `start_mm == 10`, `end_mm == 14`; coronal `20`/`29`; axial `5`/`7`.
  - `test_widest_slice_and_anchor_inside`:
    - A mask whose x = 12 slice has the most voxels.
    - Expect sagittal `widest_mm == 12` and `anchor_mm[0] == 12`.
    - The anchor, mapped back to an index, is `True` in the mask.
  - `test_extents_use_affine`:
    - Affine `diag(0.5, 0.5, 0.5)`, origin `(-10, 0, 0)`, mask starting at i = 10.
    - Expect sagittal `start_mm == -5.0`.
  - `test_build_lut_keeps_base_fields_and_skips_absent`:
    - Base has values 1 and 2, the array contains only 1.
    - Expect the result to have key `"1"` only, with the extra `"class"` key kept and the `extent` key present.
  - `test_register_case_replaces_and_patch_merges`:
    - Registering the same `case_id` twice leaves one entry.
    - `patch_case` adds `mirror` and keeps `title`.
- [ ] **Step 2: Write failing tests** in `tests/test_build_case.py`:
  - `test_build_case_writes_case(tmp_path)`:
    - A synthetic 20³ image plus a label map with values 1 and 3, and `mapping={1: "femur", 3: "tibia"}`.
    - `meta.json` has `side`, `licence` and `reference_sequence`.
    - `lut.json` has keys `"1"` and `"3"`, each with an `extent`.
    - `labels.nii.gz` has `header.get_intent()[0] == "label"`.
    - The `data/index.json` entry has `side`.
  - `test_build_case_without_labels_writes_empty_map`: `lut == {}`, and the label map is all zeros on the image grid.
- [ ] **Step 3: Run them.** `venv/bin/python -m pytest tests/test_atlaslib.py tests/test_build_case.py -v` should FAIL: the module and function are missing.
- [ ] **Step 4: Implement `atlaslib.py`.** Then refactor `build_case.py` and `make_demo_case.py` onto it.
- [ ] **Step 5: Run them again.** Same command; should PASS.
- [ ] **Step 6: Regenerate the demo.**
  - Run: `venv/bin/python tools/make_demo_case.py`
  - Then: `venv/bin/python -c "import json;l=json.load(open('data/demo-knee-synthetic/lut.json'));print(sorted(l['19']['extent']))"`
  - Expected: `['axial', 'coronal', 'sagittal']`.
- [ ] **Step 7: Commit** `tools/atlaslib.py tools/build_case.py tools/make_demo_case.py tests/test_atlaslib.py tests/test_build_case.py` with the message "Shared case library; per-plane structure extents in lut.json".

---

### Task 3: Mirrored copy (right knee → left)

**Files:**
- Create: `tools/mirror_case.py`
- Test: `tests/test_mirror_case.py`

**Interfaces:**
- **Consumes** from `atlaslib` (Task 2): `load_ras`, `clean_header`, `build_lut`, `register_case`, `patch_case`, `read_index`.
- **Produces:**
  ```python
  def mirror_affine(affine: np.ndarray, nx: int) -> np.ndarray
      # diag(-1, 1, 1, 1) @ affine @ F, where F = [[-1,0,0,nx-1],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
  def mirror_image(img: nib.Nifti1Image) -> nib.Nifti1Image          # data[::-1] with mirror_affine; dtype and intent kept
  def mirror_case(root: Path, src_id: str, dst_id: str | None = None) -> str   # returns dst_id
  ```
  CLI: `python tools/mirror_case.py <src_id> [--dst ID]`

**Rules** (spec §7.1, "Left knee: a flipped copy"):
- **The mirror** is world x → −x.
- **Default `dst_id`:** `<src>-left` when the source side is `right`, `<src>-right` when it is `left`. Raise `ValueError` for any other side, or when the source's meta has `mirror_of`.
- **Volumes and label map** are mirrored with `mirror_image`.
- **`lut.json`** is recomputed with `build_lut`, with base = `{int(k): v for k, v in src_lut.items()}`, so ids, names, colours and extra keys carry over, and the centroids and extents are recomputed.
- **`points.json`:** each `xyz_mm` has x negated.
- **`meta.json`:**
  - Copy the source meta.
  - Set `case_id = dst`.
  - Flip `side`.
  - Set `title` to the source title + ` · left (mirrored)` (or `right`).
  - Add `"mirror_of": src_id`.
- **`index.json`:**
  - Register the destination: the source entry's fields, plus `case_id`, `title`, `side` and `mirror_of`.
  - `patch_case(src, {"mirror": dst})`.

- [ ] **Step 1: Write failing tests**
  - `test_mirror_affine_maps_voxel_to_mirrored_world`:
    - `A = diag(0.36, 0.36, 0.7)` with origin `(-30, -40, -20)`, `nx = 50`.
    - For j in (0, 7, 49): `mirror_affine(A, 50) @ [j, 3, 4, 1]` equals `diag(-1, 1, 1, 1) @ A @ [49 - j, 3, 4, 1]`.
  - `test_mirror_keeps_ras_and_handedness`: `nib.aff2axcodes(mirrored) == ("R", "A", "S")`, and the sign of `det` is unchanged.
  - `test_mirror_oblique_affine` (Review focus 2):
    - An affine rotated 10° about z.
    - For five labelled voxels, the source value at world point p equals the mirrored image's value at `(-p_x, p_y, p_z)`, using nearest-voxel lookup through `inv(affine)`.
  - `test_mirror_case_swaps_sides(tmp_path)`:
    - Build a case with `build_case`, side `right`: label 1 `medial_tibial_cartilage` at x < 0, label 2 `lateral_tibial_cartilage` at x > 0.
    - After `mirror_case`, the left copy's lateral `centroid_mm[0]` is less than its medial `centroid_mm[0]`.
    - The left copy's lateral sagittal `start_mm` equals minus the source's lateral sagittal `end_mm`, within 0.01.
  - `test_mirror_case_points_and_index`:
    - Points have x negated.
    - The index's source entry has `mirror == "<src>-left"`, and the destination has `mirror_of == src`.
    - The destination meta has `side == "left"`.
  - `test_refuses_to_mirror_a_mirror`: `ValueError`.
- [ ] **Step 2: Run them.** `venv/bin/python -m pytest tests/test_mirror_case.py -v` should FAIL.
- [ ] **Step 3: Implement `tools/mirror_case.py`.**
- [ ] **Step 4: Run them again.** Same command; should PASS. Then `venv/bin/python -m pytest` should show everything green.
- [ ] **Step 5: Mirror the demo.**
  - Run: `venv/bin/python tools/mirror_case.py demo-knee-synthetic`
  - Expected: it prints `demo-knee-synthetic-left`, and `data/demo-knee-synthetic-left/` exists.
- [ ] **Step 6: Commit** `tools/mirror_case.py tests/test_mirror_case.py` with the message "Mirrored left-knee copy tool".

---

### Task 4: OAIZIB-CM candidates tool

**Files:**
- Create: `tools/oaizib.py`
- Test: `tests/test_oaizib.py`

**Interfaces:**
- **Consumes:** `build_case.build_case` (Task 2), and `atlaslib.read_index` / `register_case`.
- **Produces:**
  ```python
  CITATION = "Yao Y et al. CartiMorph: a framework for automated knee articular cartilage morphometrics. Med Image Anal 2024;91:103035. Data from the Osteoarthritis Initiative."
  @dataclass(frozen=True)
  class Subject: cmt_id: str; subject_id: int; split: str; kl: int; sex: str; age: int; bmi: float
  def xlsx_rows(data: bytes) -> list[list[str]]            # stdlib zipfile + ElementTree: first sheet, shared strings, numbers as text
  def read_subjects(info_zip: Path) -> list[Subject]       # info/subInfo_train.xlsx → "train", info/subInfo_test.xlsx → "test", found by basename
  def candidates(subjects, max_age=55, bmi_min=18.5, bmi_max=25.0) -> list[Subject]   # kl == 0, bounds inclusive, sorted by cmt_id
  def image_name(cmt_id: str) -> str        # f"oaizib_{cmt_id}_0000.nii.gz"
  def label_name(cmt_id: str) -> str        # f"oaizib_{cmt_id}.nii.gz"
  def extract(zip_path: Path, names: set[str], out_dir: Path) -> list[Path]   # match by basename; skip an existing same-size file; raise naming any missing
  def candidate_case_id(cmt_id: str) -> str # f"cand-{cmt_id}"
  def candidate_title(s: Subject) -> str    # f"Candidate {cmt} · {sex} {age} · BMI {bmi:.1f}"
  ```

**Real file facts** (checked 2026-11-05 against `info.zip`):
- **Header row:** `SubjectID, CMT-ID, Path, MRBarCode, KneeSide, KLGrade, Gender, Age, BMI`.
- **Gender:** 1 = M, 2 = F. Subject 049 / 9208055 is Gender 2, age 46, BMI 21.7, which matches CLAUDE.md's "F, 46".
- **BMI** is stored as text like `21.699999999999999`.

**CLI:** `python tools/oaizib.py {list|extract|build-candidates|remove-candidates} [--root ~/datasets/OAIZIB-CM]`. Expand `~` in `--root`.
- **`list`:** prints one row per candidate: cmt, split, sex, age, BMI.
- **`extract`:**
  - Images come from `imagesTr.zip` or `imagesTs.zip` (by split). Labels come from `labelsTr.zip` or `labelsTs.zip`.
  - Everything goes into `<root>/candidates/`.
- **`build-candidates`:** calls `build_case` for each candidate with:
  - case id `cand-<cmt>`, title `candidate_title`, region `knee`, side `right`;
  - `seqs=[("dess_3d", "DESS 3D", <image>)]`, `labels=None`;
  - source `OAIZIB-CM candidate <cmt> (OAI baseline, KL0)`, licence `CC BY-NC 4.0`, citation `CITATION`;
  - `index_extra={"candidate": True}`.
- **`remove-candidates`:** deletes only folders `data/cand-*` whose index entry has `candidate: true`, and drops those entries.

- [ ] **Step 1: Write failing tests**
  - **Fixture helper** `make_xlsx(rows: list[list[str|float]]) -> bytes`: a zip with `xl/sharedStrings.xml` and `xl/worksheets/sheet1.xml`, strings shared and numbers inline. `make_info_zip(tmp_path, train_rows, test_rows) -> Path`.
  - `test_xlsx_rows_reads_shared_strings_and_numbers`.
  - `test_read_subjects_from_info_zip`:
    - Both splits are read.
    - A row with `Gender 2` gives `sex == "F"`.
    - BMI `"21.699999999999999"` gives `21.7` when rounded to 1 decimal.
  - `test_blank_cells_are_skipped` (Review focus 5): rows with blank Age or BMI, or KL `"NA"`, are skipped.
  - `test_candidates_filter`:
    - Age 55 is kept and 56 dropped.
    - BMI 18.5 and 25.0 are kept, 25.1 dropped.
    - KL 1 is dropped.
  - `test_extract_finds_members_in_any_folder` (Review focus 5):
    - Members `imagesTr/oaizib_049_0000.nii.gz` and `deep/x/oaizib_414_0000.nii.gz` are both extracted.
    - A missing name raises an error whose message contains that name.
  - `test_remove_candidates_only_touches_candidates(tmp_path)`: `data/cand-049` (candidate) is removed; `data/knee-mri` stays.
- [ ] **Step 2: Run them.** `venv/bin/python -m pytest tests/test_oaizib.py -v` should FAIL.
- [ ] **Step 3: Implement `tools/oaizib.py`.**
- [ ] **Step 4: Run them again.** Same command, then the full `venv/bin/python -m pytest`; both should PASS.
- [ ] **Step 5: Commit** `tools/oaizib.py tests/test_oaizib.py` with the message "OAIZIB-CM candidates: list, extract, build, remove".

---

### Task 5: Download, build the 17 candidates, ask the owner to pick (owner gate)

There is no new code in this task. It uses Tasks 2 and 4.

- [ ] **Step 1: Download** to `~/datasets/OAIZIB-CM/`. The dataset is public and not gated, so no account is needed. In the background:
  ```bash
  mkdir -p ~/datasets/OAIZIB-CM && cd ~/datasets/OAIZIB-CM && for f in info.zip labelsTr.zip labelsTs.zip imagesTs.zip imagesTr.zip; do curl -L -C - -o "$f" "https://huggingface.co/datasets/YongchengYAO/OAIZIB-CM/resolve/main/$f"; done
  ```
- [ ] **Step 2: Verify the byte sizes.**

  | File | Bytes |
  |---|---|
  | `info.zip` | 51680 |
  | `labelsTr.zip` | 57538129 |
  | `labelsTs.zip` | 14122969 |
  | `imagesTs.zip` | 2544663978 |
  | `imagesTr.zip` | 10032464145 |

  Re-run step 1 to resume if any file is short.
- [ ] **Step 3: List the candidates.**
  - Run: `venv/bin/python tools/oaizib.py list`
  - Expected: 17 rows.
    - Train: 002 003 007 008 027 029 035 036 039 046 049 055 068 076.
    - Test: 414 420 422.
  - 049 shows `F 46 · BMI 21.7`.
- [ ] **Step 4: Extract.**
  - Run: `venv/bin/python tools/oaizib.py extract`
  - Expected: 34 files in `~/datasets/OAIZIB-CM/candidates/`.
- [ ] **Step 5: Build.**
  - Run: `venv/bin/python tools/oaizib.py build-candidates`
  - Expected: 17 `cand-*` cases in `data/index.json`.
  - `git status --short` shows nothing new under `data/`, because `data/cand-*/` is ignored.
- [ ] **Step 6: Serve.**
  - Run `venv/bin/python tools/serve.py` in the background.
  - Check that `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8004/viewer/` gives `200`.
- [ ] **Step 7: Ask the owner.**
  - Send them the links `http://127.0.0.1:8004/viewer/?case=cand-<cmt>` for all 17.
  - Ask them to scroll each one for meniscal, marrow and ligament findings and reply with the one to use.
  - **Do not wait.** Carry on with Task 6. Task 10 needs their answer.

---

### Task 6: `viewer/core.js` (pure helpers, tested with Node)

**Files:**
- Create: `viewer/core.js`: a UMD-style wrapper that sets `module.exports` under Node and `window.atlasCore` in the browser.
- Test: `tests/viewer/core.test.mjs` (`node:test`, `node:assert/strict`, loaded with `createRequire`).

**Interfaces (produces):**
```js
PLANES            // ["sagittal", "coronal", "axial"]
PLANE_AXIS        // { sagittal: 0, coronal: 1, axial: 2 }
HERO_FRACTION     // 0.7
otherPlanes(main) -> [string, string]           // the remaining planes, in PLANES order
layoutFor(main, sliceTypes) -> [{ sliceType, position: [l, t, w, h] }, …]   // fractions of the canvas
    // [0] main at [0, 0, 0.7, 1]; [1] otherPlanes[0] at [0.7, 0, 0.3, 0.5]; [2] otherPlanes[1] at [0.7, 0.5, 0.3, 0.5]
refLineOrientation(main, small) -> "vertical" | "horizontal"
tileAt(tiles, x, y) -> number                   // tiles = nv.screenSlices (leftTopWidthHeight, device px); -1 when none
sliceRange(planeExtent, mmToIndex, n) -> { start, end, widest } | null   // null when planeExtent is missing; sorted; clamped to [0, n-1]
pointRange(index, halfWidth, n) -> { start, end, widest }                // widest = index; clamped
trackGradient(start, end, n, on, off) -> string // CSS linear-gradient for the slider track
mirrorMM([x, y, z]) -> [-x, y, z]
counterpart(cases, caseId) -> string | null     // via the index entry's mirror / mirror_of
pickerGroups(cases) -> { cases: [...], candidates: [...] }   // candidate: true goes to candidates
```

**Reference-line orientations:**

| Main plane | Small view | Line |
|---|---|---|
| sagittal | coronal | vertical |
| sagittal | axial | vertical |
| coronal | sagittal | vertical |
| coronal | axial | horizontal |
| axial | sagittal | horizontal |
| axial | coronal | horizontal |

- [ ] **Step 1: Write failing tests**
  - `layoutFor("sagittal")`: positions exactly as above, small views `coronal` then `axial`, and no two tiles overlap.
  - `refLineOrientation`: all six pairs.
  - `tileAt`: returns the tile index when inside a tile, and `-1` in a gap or off-canvas.
  - `sliceRange` (Review focus 1 and 3):
    - `sliceRange(undefined, …)` is `null`.
    - Start and end come back sorted when the mm order is reversed (as in a mirrored case).
    - Values outside the volume are clamped to `0` and `n-1`.
  - `pointRange` (Review focus 3): `pointRange(0, 2, 100)` is `{start: 0, end: 2, widest: 0}`, and `pointRange(99, 2, 100)` is `{start: 97, end: 99, widest: 99}`.
  - `trackGradient(10, 20, 101, …)` contains `10%` and `20%`.
  - `mirrorMM([12.5, -3, 4])` is `[-12.5, -3, 4]`.
  - `counterpart`: works in both directions, and gives `null` for a case without a mirror.
  - `pickerGroups`: candidates are separate, and a mirrored copy stays in `cases`.
- [ ] **Step 2: Run them.** `node --test tests/viewer/` should FAIL (module not found).
- [ ] **Step 3: Implement `viewer/core.js`.**
- [ ] **Step 4: Run them again.** `node --test tests/viewer/` should PASS.
- [ ] **Step 5: Commit** `viewer/core.js tests/viewer/core.test.mjs` with the message "Viewer core helpers: layout, reference lines, ranges, mirror".

---

### Task 7: Reference lines and shared cursor

**Files:**
- Modify: `viewer/index.html`

**Interfaces:**
- **Consumes:** `atlasCore` (Task 6). It loads with `<script src="core.js">` before the inline script.
- **Produces** (used by Tasks 8 and 9): `applyLayout()`, `mainSliceType()`, `isHero()`. `window.atlas` also exposes `core`, `applyLayout` and `isHero`.

**Behaviour** (spec §4.1, owner's choices):
- **Hero layout.** `isHero()` means `MODE === "standalone"` and the window is wider than 760 px.
  - Hero: `nv.setCustomLayout(core.layoutFor(state.plane, {sagittal: nv.sliceTypeSagittal, coronal: nv.sliceTypeCoronal, axial: nv.sliceTypeAxial}))`.
  - Otherwise: `nv.clearCustomLayout()` and `nv.setSliceType(...)`, as now.
  - Re-apply on a `matchMedia("(max-width: 760px)")` change.
- **Remove "3-up".** Remove the 3-up button, key `4`, and the `multi` plane. A `?plane=multi` URL falls back to `sagittal`.
- **Plane keys.** `1`–`3` set the main plane, and the small views follow. `crosshairWidth` stays 0, because NiiVue's own crosshair is not used.
- **Reference lines.** A new overlay `#reflines` (`pointer-events: none`) draws, for each small tile, one line through the projection of `nv.scene.crosshairPos`.
  - Use `nv.frac2canvasPosWithTile(frac, tile.axCorSag)`.
  - Orientation comes from `refLineOrientation`, and the line spans that tile's `leftTopWidthHeight`.
  - Convert device px to CSS px by dividing by the device pixel ratio, as `drawMarkers` does.
  - The colour is a new CSS variable, `--refline: #e0a458`.
  - Redraw from the existing `drawScene` wrapper and on `mousemove`.
- **Hover marker.** While the pointer is over the main tile (`tileAt === 0`), each small tile shows a small ring at the hovered point's projection. Moving the pointer never changes `crosshairPos`.
- **Click on the main tile:**
  - Set `crosshairPos` to the clicked frac, so the small views move through that point.
  - If there's a structure there, `select(t)` it (panel as now).
  - Clicking where there's no structure keeps the current selection. Only Esc clears it. *(My call: a stray click shouldn't drop the structure being followed.)*
- **Click on a small tile:**
  - Set `crosshairPos` to the clicked frac, so the main slice moves to pass through it.
  - The selection is unchanged.
  - Ignore clicks where `canvasPos2frac` returns an invalid frac (`frac[0] < 0`).
- **Wheel over a small tile does nothing.** Add a capture-phase `wheel` listener on `#canvasWrap`: when `isHero()` and `tileAt(...) > 0`, call `preventDefault()` and `stopPropagation()`.
- **Hover names everywhere.** Hovering in any tile still names the structure (`pickAt` works per tile).
- **Point markers** draw only in the main tile: use `frac2canvasPosWithTile(…, mainSliceType())`.
- **Help text:** `1`–`3` plane, plus "click a small view to jump there". Remove `4`.

**Verification:** use a real browser on the Mac (Playwright MCP or Claude in Chrome) at 1400×900 on `?case=demo-knee-synthetic`. Every check runs through `window.atlas` and the DOM.
- [ ] **Step 1: Implement the behaviour above.**
- [ ] **Step 2: Layout.** `atlas.nv.screenSlices.length === 3`. Tile 0 is the width of the other two combined or more.
- [ ] **Step 3: Hover.** After hovering over the main tile, `#reflines` holds 2 lines (vertical, because the main plane is sagittal) and 2 hover rings. `atlas.nv.scene.crosshairPos` is unchanged.
- [ ] **Step 4: Small-tile click.**
  - Clicking inside the coronal tile changes `#slice`'s value to that point's sagittal index.
  - `atlas.state.selected` is unchanged.
- [ ] **Step 5: Wheel.** Wheel over a small tile leaves `#slice` unchanged. Wheel over the main tile changes it.
- [ ] **Step 6: Coronal main.** Press `2`: the small tiles are sagittal (vertical line) and axial (horizontal line).
- [ ] **Step 7: Narrow window** (Review focus 4). Resize to 700×900: `screenSlices.length === 1` and `#reflines` is empty. Resize back: 3 tiles again.
- [ ] **Step 8: Sidebar.** `?mode=sidebar&case=demo-knee-synthetic` shows a single view with name-on-hover. The browser console has no errors in any check.
- [ ] **Step 9: Commit** `viewer/index.html` with the message "Viewer: main view with reference-line side views and shared cursor".

---

### Task 8: Follow one structure

**Files:**
- Modify: `viewer/index.html`

**Interfaces:**
- **Consumes:**
  - `lut[v].extent` (Task 2);
  - `core.sliceRange`, `core.pointRange`, `core.trackGradient` (Task 6);
  - `mainSliceType()` and `isHero()` (Task 7).
- **Produces:** `followRange() -> {start, end, widest} | null`, `jump(which: "start" | "widest" | "end")`. Both are exposed on `window.atlas`.

**Behaviour** (spec §4.2):
- **Selecting is following.**
  - `activeValue()` now prefers `state.selected` over `state.hover`, so the followed structure stays lit.
  - Hovering another structure only shows its name in `#hoverbar`.
- **Converting the range.**
  - `mmToIndex(mm)`: on the main plane's axis, make a point with that coordinate and the crosshair's other coordinates. Then `frac2vox(nv.mm2frac(point), 0)[axis]`. This works on any sequence grid.
  - Points use `pointRange(index, halfWidth, n)`, where `halfWidth = ceil(max(1.5, 1.5 * pix) / pix)`, matching `drawMarkers`' visibility rule.
- **Follow row.** A new `#followRow` (`full-only`) sits in `#sliceRow`. It shows the structure's name, "slices S–E", and buttons **Start**, **Widest** and **End**.
  - The `#slice` track gets `background: trackGradient(...)`.
  - Both are hidden or cleared when nothing is selected, or when `followRange()` is `null` (Review focus 1).
- **Jumps.**
  - **Start** and **End** call `setSlice(index)`, changing the main slice only.
  - **Widest** sets `crosshairPos` to `extent[plane].anchor_mm`, so the main slice is the widest one and the small views pass through the structure. For a point, it uses the point's `xyz_mm`.
- **Find and the panel's Related chips** select, then `jump("widest")`. This replaces the centroid centring in `select(…, {center: true})`.
- **Clicking in the image** selects, with the crosshair at the clicked point (Task 7). There's no jump.
- **Changing plane** recomputes the range and gradient for the new main plane.
- **Esc** clears the selection, follow row and gradient.

- [ ] **Step 1: Implement the behaviour above.**
- [ ] **Step 2: Find.** Find "Posterior cruciate ligament": `#slice` value equals `mmToIndex(lut[pcl].extent.sagittal.widest_mm)`, and `#followRow` is visible with start and end matching `followRange()`.
- [ ] **Step 3: Start and End.** Pressing Start makes `#slice` equal `followRange().start`; End makes it `.end`.
- [ ] **Step 4: Highlight stays.** With the PCL selected, hovering the femur leaves `atlas.nv.opts.atlasActiveIndex` equal to the PCL's value, and `#hoverbar` shows "Femur".
- [ ] **Step 5: Point label.** Find "Gerdy’s tubercle": the range is at most 5 slices, and Widest equals the point's slice.
- [ ] **Step 6: Missing extent** (Review focus 1).
  - In the console, delete `extent` from every `atlas.state.lut` entry, then select the femur.
  - `#followRow` is hidden, the track has no gradient, and the console has no errors.
- [ ] **Step 7: Esc** hides `#followRow` and clears the gradient.
- [ ] **Step 8: Commit** `viewer/index.html` with the message "Viewer: follow a structure (slider range, start / widest / end)".

---

### Task 9: Right/left switch and case picker groups

**Files:**
- Modify: `viewer/index.html`

**Interfaces:**
- **Consumes:**
  - `core.counterpart`, `core.mirrorMM`, `core.pickerGroups` (Task 6);
  - the index fields `mirror`, `mirror_of`, `candidate` and `side` (Tasks 2–4);
  - `jump` and `followRange` (Task 8).
- **Produces:** `switchSide()`, exposed on `window.atlas`.

**Behaviour** (spec §7.1):
- **Case picker.** `#caseSel` uses `<optgroup label="Cases">` and `<optgroup label="Candidates — pick one">` from `pickerGroups`. The candidates group is left out when empty.
- **Side switch.** A new `#sideGroup` (`full-only`) has buttons **R** and **L**, with the current side pressed. It's shown only when `counterpart(...)` exists.
- **`switchSide()`** remembers the current mm point (`frac2mm(crosshairPos)`), the selected structure's id, and the plane. It then:
  1. loads the counterpart case, keeping the plane (`loadCase` gets a `{keepPlane}` option);
  2. sets `crosshairPos = mm2frac(mirrorMM(mm))`;
  3. re-selects the same id with `findById`, without jumping.
- **Banner.** `#banner` shows "Mirrored copy of the right knee" when `meta.mirror_of` is set. The synthetic note stays, joined with " · " if both apply.

- [ ] **Step 1: Implement the behaviour above.**
- [ ] **Step 2: Grouped picker.** `#caseSel` lists `demo-knee-synthetic` and `demo-knee-synthetic-left` under "Cases". There's no candidates group, unless Task 5 already built them, in which case 17 are listed there.
- [ ] **Step 3: Switch to the left.**
  - On `demo-knee-synthetic`, find the PCL, then press `L`.
  - `atlas.state.caseId === "demo-knee-synthetic-left"`.
  - `nv.frac2mm(nv.scene.crosshairPos)[0]` is the negative of its value before, within half a voxel.
  - `atlas.state.selected.id === "pcl"` and the plane is unchanged.
  - The banner shows the mirrored text.
- [ ] **Step 4: Lateral side.** In the left copy, `lut` LCL `centroid_mm[0] < 0`, and `pickAt` at the LCL centroid's on-screen position in the coronal view names the LCL.
- [ ] **Step 5: Back to the right.** Press `R`: back on `demo-knee-synthetic` at the original point, within half a voxel.
- [ ] **Step 6: Commit** `viewer/index.html` with the message "Viewer: right / left switch for mirrored copies; grouped case picker".

---

### Task 10: Build the chosen knee (needs the owner's pick from Task 5)

- [ ] **Step 1: Get the owner's choice.** Call it `<cmt>`.
- [ ] **Step 2: Build.**
  ```bash
  venv/bin/python tools/build_case.py knee-mri --title "Knee — OAI 3D DESS" --region knee --side right \
    --seq dess_3d "DESS 3D" ~/datasets/OAIZIB-CM/candidates/oaizib_<cmt>_0000.nii.gz \
    --labels ~/datasets/OAIZIB-CM/candidates/oaizib_<cmt>.nii.gz --preset oaizib-cm \
    --source "OAIZIB-CM subject <cmt> (OAI baseline, KL0)" --licence "CC BY-NC 4.0" \
    --citation "Yao Y et al. CartiMorph: a framework for automated knee articular cartilage morphometrics. Med Image Anal 2024;91:103035. Data from the Osteoarthritis Initiative."
  ```
  Expected: values 1–5 are printed with large voxel counts and no "unmapped" flags. This matches the dataset README: 1 femur, 2 femoral cartilage, 3 tibia, 4 medial tibial cartilage, 5 lateral tibial cartilage.
- [ ] **Step 3: Orientation check.**
  - In `data/knee-mri/lut.json`, the lateral tibial cartilage `centroid_mm[0]` must be greater than the medial one's, because this is a right knee in RAS.
  - **If not, stop and tell the owner.** The image header's orientation is suspect.
- [ ] **Step 4: Mirror.**
  - Run: `venv/bin/python tools/mirror_case.py knee-mri`
  - Expected: `knee-mri-left` exists, and the inequality from Step 3 is reversed in its `lut.json`.
- [ ] **Step 5: Remove the candidates.**
  - Run: `venv/bin/python tools/oaizib.py remove-candidates`
  - Expected: `data/cand-*` is gone, and `index.json` lists `knee-mri`, `knee-mri-left` and the demos.
- [ ] **Step 6: Owner checks the look.**
  - Ask the owner to open `http://127.0.0.1:8004/viewer/?case=knee-mri`.
  - Sagittal should have anterior on screen left. Coronal should have the fibular head on screen left (right knee).
  - They follow the femur and tibial cartilage, and switch to L.
- [ ] **Step 7: Record it in CLAUDE.md.**
  - The Knee section gets the chosen subject (CMT-ID and OAI subject ID, no images).
  - The Build sequence marks steps 1–2 as done.
- [ ] **Step 8: Commit** `data/knee-mri/meta.json data/knee-mri/lut.json data/knee-mri/points.json CLAUDE.md` with the message "Knee case: OAIZIB-CM <cmt> built; mirrored left copy generated locally".
  - These are the per-case JSON files CLAUDE.md says to version.
  - **Never** commit `data/knee-mri-left/` (now ignored) or any `.nii.gz`.
