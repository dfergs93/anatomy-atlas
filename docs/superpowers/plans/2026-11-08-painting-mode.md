# Painting mode: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner (or a helper) paint the knee checklist in the browser:
- pick structures from the checklist, never typing names;
- paint with a brush, a magic wand, fill-between-slices and grow;
- place points;
- save with backups.

Every save rebuilds the left copy and ticks the checklist.

**Architecture:**
- **The drawing layer is the label map.**
  - In `?mode=author` the viewer copies `labels.nii.gz` into NiiVue's drawing bitmap (uint8, same voxel order: our volumes are RAS-canonical, so NiiVue's `permRAS` is the identity).
  - Painting edits that bitmap.
  - Saving posts it, gzipped, to `serve.py`.
- **Every edit goes through one guard.** NiiVue's own no-overwrite flag covers only shapes, and its undo can't follow our corrections, so the guard is ours. After every operation it compares the bitmap with the last accepted state and restores any voxel the rules forbid. It then records the change for our own undo.
- **The smart tools:**
  - **Wand and grow** are our own intensity region-growing, in `paint-core.js`, tested in node. NiiVue's click-to-segment previews on hover and hijacks the wheel. Its `drawGrowCut` grows every label at once and needs a background seed.
  - **Fill between slices** uses NiiVue's `interpolateMaskSlices`, run on a bitmap that holds only the current structure, one pair of painted slices at a time. On its own it ignores keyframes in between and processes every label.
- **Saving is server-side** (`tools/save_case.py`):
  - check the save, then back up;
  - rebuild `lut.json`, dropping `auto` from changed or checked structures;
  - write the files;
  - rebuild the mirror, labels only;
  - tick the checklist.

**Tech stack:**
- Python 3.13 (`venv/`) with `requirements.txt` only (nibabel, numpy, scipy) plus the standard library, and pytest.
- NiiVue 0.69.0 (vendored).
- Plain JS with `node --test`. Browser checks run in Playwright on the owner's Mac.

**Spec:** `docs/superpowers/specs/2026-11-05-anatomy-atlas-design.md`:
- §5.1–5.3 (getting started, no typing names, the tools);
- §5.5 (saving);
- §5.6 (helper path: stdlib + `requirements.txt`);
- §5.7 (expected locations, points);
- §6 (expected-location note);
- §7.1 (mirrored copy refused, rebuilt after every save).

**Not in this plan:**
- **§5.6 helper merge.** It is its own subsystem (a tool that brings a helper's map in structure by structure) and the next plan.
- **§5.4 AI click-to-outline.** Deferred by the spec.

**NiiVue 0.69.0 facts this plan relies on** (read from the vendored bundle, 2026-11-08):
- **Bitmap.** `drawBitmap` is a `Uint8Array`, x fastest, in RAS-permuted order. It equals the NIfTI voxel order when `volumes[i].permRAS` is `[1,2,3]`.
- **Loading a map.** Load with `createEmptyDrawing(); drawBitmap.set(u8); drawAddUndoBitmap(); refreshDrawing(true)`.
- **Colours.** `setDrawColormap({R,G,B,A,I,labels})` takes the same object as `buildColormap(lut)`. `I` must start at 0. The maximum label value is 255.
- **Pen.** `setPenValue(v, false)` paints value `v` (0 erases). `opts.penSize` is in voxels, a square pen in the plane of the tile.
- **Mouse.** Painting needs the left button set to `DRAG_MODE.crosshair` while `setDrawingEnabled(true)`.
- **Change callback.** `nv.onDrawingChanged(action)` fires `"draw"` after each stroke. Flood fill, grow-cut and interpolation don't fire it.
- **Interpolation.** `interpolateMaskSlices(lo, hi, {sliceType, useIntensityGuided})` (`sliceType`: 0 axial, 1 coronal, 2 sagittal):
  - it interpolates each label only between its first and last slice in [lo, hi];
  - it overwrites other labels;
  - it takes no undo snapshot.
- **Saving the drawing.** `saveImage({filename: "x.nii.gz", isSaveDrawing: true})` downloads the drawing as NIfTI.

## Global constraints

- **No new dependencies.** The helper's path stays `python tools/serve.py` with `requirements.txt` (spec §5.1, §5.6). Nothing from `venv-autoseg`.
- **No imaging in git.** Stage files by name; never `git add -A` or `git add .`.
- **Saving.**
  - The server binds 127.0.0.1 only, port 8004.
  - Saves are refused unless the `Host` is `127.0.0.1:<port>` or `localhost:<port>`, any `Origin` matches, and the `Content-Type` is `application/json`.
- **Backups.** Every save first backs up via `atlaslib.backup_case` (newest 20 kept).
- **Mirrored copies are never painted.**
  - Author mode refuses a case with `mirror_of` and links to its source.
  - The save endpoint refuses one too.
  - Every save rebuilds the copy.
- **The "auto" contract** (CLAUDE.md, Base auto-labels):
  - A save drops `auto` from any structure whose voxels changed, or that the user marked as checked.
  - An untouched auto structure keeps `auto`.
- **Label values stay 1–255** (the drawing is uint8). Existing structures keep their values; a new structure takes max + 1.
- **Painting is restricted to the current structure** (spec §5.3).
  - Painting writes the current value only into empty voxels or the current structure's own.
  - Erasing clears only the current structure.
  - The "Paint over other structures" switch (off by default) also lets painting overwrite others and erasing clear them.
- **Keys** (no clashes with the viewer's ↑↓, 1–3, O, R, /, Esc):

  | Key | Action |
  |---|---|
  | B | brush |
  | E | eraser |
  | W | wand |
  | F | fill between |
  | G | grow |
  | P | place point |
  | [ ] | brush size |
  | Enter | save, then next structure |
  | ⌘/Ctrl+S | save |
  | ⌘/Ctrl+Z | undo |
  | K | mark checked |
  | Delete | remove the current point |

- **Tests.** `venv/bin/python -m pytest` and `node --test "tests/viewer/*.test.mjs"`. Browser checks use `?case=knee-mri&mode=author` on the running server.
- **Never leave test paint in `knee-mri`.** Browser checks that save must use a scratch copy, `cp -R data/knee-mri data/paint-test` with that case registered, and delete it afterwards. The owner's case is saved only by the owner.
- **Commit messages** end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018rxg1P1FJjBGEHBhNbSmQY
  ```
- **Branch:** `painting-mode`, made from `main` at da3dc91. It holds this plan.

## Review focus

1. **Another structure's voxels change** under the pen, eraser, wand, fill-between or grow while "Paint over other structures" is off. They must stay unchanged. Task 4 `guardChanges` tests; Task 6 browser check.
2. **Saving after the case changed on disk** (another tab, or `tools/autolabels.py`). The save is refused with 409 and nothing is written. The page keeps the paint and offers to download it. Task 2 `test_save_refuses_stale_token`; Task 5 browser check.
3. **A web page in the same browser posting to the save endpoint** (cross-site request or DNS rebinding). Refused with 403. Task 3 `test_save_rejects_foreign_host_and_origin`, `test_save_requires_json`.
4. **Reloading or closing with unsaved paint.** The browser warns, and Enter saves before moving on. Task 5 browser check.
5. **A bad payload:** wrong bitmap size, a value with no structure, an unknown or duplicate id, malformed points. Refused with 400, and the case is byte-identical. Task 2 `test_save_rejects_bad_payload_case_untouched`.

---

### Task 1: Checklist: read, tick, next

**Files:**
- Create: `tools/checklist.py`
- Modify: `viewer/core.js`
- Modify: `checklists/knee.md`:
  - Legend: add `E = expected location (painted where it lies; shown as a dotted outline, visible only when distended)`.
  - Type of the four bursa rows: `P` → `E` (spec §5.7).
- Test: `tests/test_checklist.py`, `tests/viewer/core.test.mjs`

**Interfaces:**
- Produces:
  - **Python:** `Row` (dataclass: `id, name, type, labelled: bool, content: bool, group`).
  - **Python:** `read_checklist(path) -> list[Row]`. It reads table rows whose first cell matches `[a-z0-9_]+` and isn't `id`. `group` is the latest `## ` heading.
  - **Python:** `set_labelled(path, ids: set[str]) -> int`. It rewrites only the Labelled cell's brackets (`[x]` or `[ ]`), keeps padding and every other byte, and returns the number of rows changed.
  - **JS, `core.parseChecklist(md)`:** returns `[{id, name, type, labelled, group}]`, the same rows.
  - **JS, `core.nextStructure(rows, done: Set, afterId = null)`:** the first row not in `done` after `afterId`, in checklist order, wrapping round; `null` when all are done.

- [ ] **Step 1: Write the failing tests.**
  - `test_read_checklist_knee`: the real file has 94 − 8 = 86 rows. Types are only in {R, P, E}. Bursae are E. `fibula` is R. The group of `fibula` is "Bones and landmarks".
  - `test_set_labelled_changes_only_those_cells`: on a tmp copy, ticking {femur, acl} changes 2 rows; the diff touches only those two cells; running again returns 0.
  - Node `parseChecklist matches the Python reader`: parse `checklists/knee.md` and check the same count and the same first and last ids.
  - Node `nextStructure skips done and wraps`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the four functions, and edit `checklists/knee.md`.
- [ ] **Step 4: Run them.** Expected: PASS, full suites green.
- [ ] **Step 5: Commit** `tools/checklist.py viewer/core.js checklists/knee.md tests/test_checklist.py tests/viewer/core.test.mjs` with the message "Checklist: read, tick, next structure; bursae are expected locations".

### Task 2: `save_case`: write a painted map safely

**Files:**
- Create: `tools/save_case.py`
- Modify: `tools/mirror_case.py`. Add `mirror_case(root, src_id, dst_id=None, *, volumes=True)`. With `volumes=False` and an existing copy of the same source, it rewrites only labels, lut, points and meta. With no copy yet, it builds the whole thing.
- Test: `tests/test_save_case.py`, `tests/test_mirror_case.py`

**Interfaces:**
- Consumes: `atlaslib.backup_case`, `build_lut`, `clean_header`, `patch_case`, `read_index`; `build_case.colour`; `checklist.read_checklist` and `set_labelled`; `autolabels.voxel_print`.
- Produces:
  - `class SaveError(Exception)`, with `.status` set to 400 or 409.
  - `case_token(case_dir) -> str`: sha256 over the bytes of `labels.nii.gz`, `lut.json` and `points.json` (missing files count as empty), first 16 hex characters.
  - `save_case(root, case_id, *, token: str, labels: bytes, values: dict[int, str], checked: list[str], points: list[dict]) -> dict`:
    - returns `{"token", "structures": int, "labelled": [id], "mirror": id | None}`;
    - `labels` is the raw uint8 bitmap, x fastest, length nx·ny·nz of `labels.nii.gz`.
- **Order** (every check comes before any write; all of them raise `SaveError`):
  1. **Case.** The case exists. A case with `mirror_of` → 400, with a message naming the source.
  2. **Token.** It equals `case_token`, else 409: "changed on disk since you opened it".
  3. **Bitmap size.** The length is right.
  4. **Values.** Every non-zero value present is a key of `values`.
  5. **Ids.** Ids in `values` are unique, and each is a checklist id for `meta.region` or already in `lut.json`.
  6. **Points.** `points` is a list of `{id: str, name: str, xyz_mm: [3 finite numbers]}` with unique ids, each a checklist id.
  7. **Write.** Then `backup_case`; new array = bitmap reshaped in Fortran order to (nx, ny, nz), as uint16.
  8. **LUT base per present value.**
     - If the old LUT has this value with the same id, start from that entry; otherwise start from `{id, name (checklist name, else id), rgb: colour(id, value)}`.
     - Drop `auto` if the id is in `checked`, or if `voxel_print(old_arr, v) != voxel_print(new_arr, v)`.
     - Set `expected: true` exactly when the checklist type is E; otherwise remove the key.
  9. **Files.** `build_lut`; write `labels.nii.gz` (intent label, `clean_header`, the old affine), `lut.json` (indent=1) and `points.json` (indent=2), each through a temp file + `os.replace`.
  10. **Index.** `patch_case(structure_count)`, only when the case is in `data/index.json`.
  11. **Mirror.** If `meta.side` is set: `mirror_case(root, case_id, volumes=False)`.
  12. **Checklist.** `set_labelled(checklists/<region>.md, ids)`, where ids = LUT ids without `auto` ∪ point ids.

- [ ] **Step 1: Write the failing tests.** They use a synthetic case made with `build_case` in `tmp_path`, plus a tmp `checklists/knee.md` holding 6 rows (R, R, R, P, E, R).
  - `test_save_round_trip`: load the label bytes in Fortran order, paint one new value as a checklist id, and save. The new LUT has the id with its colour, the old entries are unchanged, a backup exists, the checklist is ticked and the returned token equals `case_token`.
  - `test_save_refuses_stale_token`: after changing `points.json`, the save gets 409 and the case files are byte-identical.
  - `test_save_rejects_bad_payload_case_untouched`: parametrised over the wrong length, an unmapped value, a duplicate id, an unknown id, a point with 2 coordinates, and a mirrored case. Each gets 400, and the bytes are identical with no backup folder.
  - `test_auto_dropped_only_when_changed_or_checked`: three auto structures, one edited, one in `checked`, one untouched. Only the untouched one keeps `auto`.
  - `test_expected_flag_from_checklist_type`
  - `test_points_saved_and_ticked`
  - `test_save_rebuilds_mirror_labels_only`: the second save leaves the mirror's volume files' mtime unchanged, and the mirrored LUT carries the new id with x negated.
  - In `test_mirror_case.py`, `test_mirror_labels_only_keeps_volumes`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** `save_case.py` and the `volumes` flag.
- [ ] **Step 4: Run them.** Expected: PASS, full suite green.
- [ ] **Step 5: Commit** `tools/save_case.py tools/mirror_case.py tests/test_save_case.py tests/test_mirror_case.py` with the message "Saving a painted map: checks first, backup, auto contract, mirror, checklist".

### Task 3: Save endpoint in `serve.py`

**Files:**
- Modify: `tools/serve.py`. The root comes from the handler's `directory`; add `make_server(root, port) -> ThreadingHTTPServer` so tests can serve a tmp root on port 0.
- Test: `tests/test_serve.py`

**Interfaces:**
- Consumes: `save_case.save_case`, `case_token`, `SaveError`.
- Produces:
  - `GET /api/token?case=<id>` → `200 {"token"}`, or 404.
  - `POST /api/save`:
    - body JSON `{case_id, token, labels_gz_b64, values: {"<value>": "<id>"}, checked: [id], points: [...]}`;
    - returns `200 {token, structures, labelled, mirror}`, or `{"error": msg}` with 400 / 403 / 409 / 413.
  - The body is limited to 64 MB.
  - One save at a time (a `threading.Lock`).
  - Both routes check `Host`, and `Origin` when present, against `127.0.0.1:<port>` and `localhost:<port>`.
  - POST needs `Content-Type: application/json`, so a cross-site page can't send it without a preflight, and the server never answers preflights.

- [ ] **Step 1: Write the failing tests.** These run a live server in a thread on a tmp root holding the synthetic case.
  - `test_token_then_save`
  - `test_save_requires_json` (`text/plain` → 403)
  - `test_save_rejects_foreign_host_and_origin`:
    - `Host: evil.example:8004` → 403;
    - `Origin: http://evil.example` → 403;
    - the case is unchanged.
  - `test_save_error_statuses` (stale → 409, bad → 400, oversize `Content-Length` → 413).
  - `test_static_files_still_served`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement it.** Errors from `SaveError` map to their status; anything else gives 500 with the message, and the case is unchanged because `save_case` checks first.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** `tools/serve.py tests/test_serve.py` with the message "serve.py: save and token endpoints, localhost-only".

### Task 4: `paint-core.js`: the guard, undo and the growing tools

**Files:**
- Create: `viewer/paint-core.js`. Same UMD wrapper as `core.js`; global `atlasPaint`.
- Create: `tests/fixtures/colours.json`, a list of `[id, value, [r,g,b]]` covering:
  - every PALETTE keyword;
  - a muscle;
  - the three meniscus parts.
- Test: `tests/viewer/paint-core.test.mjs`, `tests/test_build_case.py` (fixture check)

**Interfaces:**
- **`colour(id, value) -> [r,g,b]`:** port of `build_case.colour`. Both languages are checked against the fixture.
- **`valueFor(id, lut, assigned: Map<string, number>) -> number`:** the LUT value for the id; else its value in `assigned`; else max(all) + 1. Throws `RangeError` above 255.
- **`guardChanges(before, after, cur, overwrite) -> {idx: Uint32Array, old: Uint8Array, restored: number}`.** A voxel may change from `o` to `n` only if:
  - `n === cur && (o === 0 || overwrite)`, or
  - `n === 0 && (o === cur || overwrite)`.

  Every other change is put back into `after`. Allowed changes are copied into `before` and returned, with their old values, for undo.
- **`undoChange(change, bitmap, before)`:** writes the old values back into both arrays.
- **`seedWindow(img, dims, seed, axis, tolerance, range) -> [lo, hi]`:** the median of the 3×3 in-plane neighbourhood ± tolerance·(range[1] − range[0]). `range` is the sequence's cal_min and cal_max.
- **`wandMask(img, dims, seed, {lo, hi, is2D, axis, maxDistMM, voxMM}) -> Uint32Array`:** a breadth-first fill from the seed through voxels with lo ≤ value ≤ hi. It is 4-connected in the seed's plane when `is2D`, else 6-connected, and keeps within `maxDistMM` (Euclidean, using `voxMM`) of the seed.
- **`growMask(img, dims, bitmap, cur, {tolerance, range, steps}) -> Uint32Array`:**
  - It spreads from all voxels equal to `cur` into voxels whose bitmap is 0, 6-connected, for at most `steps` layers.
  - It accepts intensities within [p5 − t·span, p95 + t·span] of the structure's own voxels.
  - With no `cur` voxels it returns empty.
- **`keySlices(bitmap, dims, value, axis) -> number[]`:** the sorted slice indices along `axis` that contain `value`.

- [ ] **Step 1: Write the failing tests** (small synthetic arrays):
  - `guard keeps other structures`: an eraser and a pen over labels 2 and 3, with cur = 2.
  - `guard with overwrite`
  - `undo restores exactly`
  - `valueFor reuses, assigns next, refuses 256`
  - `colour matches the Python fixture`
  - `wand stops at an edge and at maxDistMM`
  - `wand 2D stays on its slice`
  - `grow fills a matching region only into empty voxels`
  - `grow with nothing painted does nothing`
  - `keySlices`

  Also `test_colour_fixture` in pytest.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement it.** Typed arrays throughout, and no per-voxel allocations: the guard runs over 23.6 M voxels after every stroke.
- [ ] **Step 4: Run them.** Expected: PASS. Also time `guardChanges` on a 160×384×384 array in node and log it. Expected: < 150 ms. If it's slower, ledger it and narrow the guard to the stroke's bounding slices.
- [ ] **Step 5: Commit** `viewer/paint-core.js tests/viewer/paint-core.test.mjs tests/fixtures/colours.json tests/test_build_case.py` with the message "paint-core: guard, undo, wand, grow, colours".

### Task 5: Author mode: structures, brush, eraser, undo, save

**Files:**
- Create: `viewer/author.js`. It defines `attachAuthor(ctx)` and runs only when called.
- Modify: `viewer/index.html`:
  - script tags for `paint-core.js` and `author.js`;
  - in `loadSequence`, after loading, `if (MODE === "author") attachAuthor({...})`;
  - `pickAt` reads the region value through `labelValueAt(vox)` (the drawing bitmap in author mode, the label volume otherwise);
  - `pointerup` in author mode is handed to `author.onClick(frac, e)`;
  - `keydown` in author mode is offered to `author.onKey(e)` first;
  - a "Paint" link in the header for standalone mode when the host is 127.0.0.1 or localhost and the case isn't mirrored.

**Interfaces:**
- **`ctx`:** `{nv, state, core, paint: atlasPaint, $, DATA, getJSON, buildColormap, setSlice, setPlane, cursorWorld, worldToFrac, fracToWorld, frac2vox, drawMarkers, showHover, escapeHTML}`.
- **`attachAuthor` refuses** (with a banner, not a crash) in these cases:
  - a mirrored case (link to `?case=<mirror_of>&mode=author`);
  - a host other than 127.0.0.1 or localhost;
  - a narrow screen;
  - `permRAS` not `[1,2,3]` on either volume;
  - any label value over 255.
- **It sets up:**
  - the label overlay's opacity to 0;
  - the drawing as in the facts above;
  - `setDrawColormap(buildColormap(lut))`, with new structures added using `colour()`;
  - `drawOpacity` 0.5;
  - mouse: left primary = crosshair, Shift = windowing, Ctrl = pan; right = pan.
- **The panel** (replaces the details panel in author mode):
  - the current structure (name, type, an "auto" badge if it has `auto`);
  - "Next: <name> · Enter";
  - a filter box with the checklist list (groups, ✓ labelled), where a click makes a row current;
  - the tools (brush, eraser, size 1–25 shown in voxels, default 3);
  - "Paint over other structures" (off);
  - Save, the status ("Saved" / "● Unsaved"), and the key help.
- **Edits.** `nv.onDrawingChanged = (a) => a === "draw" && afterEdit()`. `afterEdit()` runs `guardChanges` against `before`, refreshes the drawing if anything was restored, pushes the change (undo depth 100) and sets unsaved.
- **Save.** `save()` gzips `drawBitmap` with `CompressionStream("gzip")`, base64s it, and posts it with `values` (from the LUT plus assigned values), `checked` and `points`. On 200 it reloads `lut.json` and the checklist, updates the colours and the token, and clears unsaved.
  - **On 409** it shows the message plus a "Download my unsaved paint" button (`saveImage({filename: "<case>-unsaved-paint.nii.gz", isSaveDrawing: true})`), keeping everything.
  - **On other errors** it shows the message and keeps everything.
- **Keys.** Enter = save if unsaved, then make `nextStructure(rows, done, current)` current. `done` = LUT ids without `auto` ∪ point ids. `beforeunload` warns while unsaved.

- [ ] **Step 1: Wire it and check it in the browser** on a scratch copy of the case:
  - `cp -R data/knee-mri data/paint-test`.
  - In `data/paint-test/meta.json`, set `case_id` to `paint-test` and `side` to `""`, so there is no mirror.
  - Register it with `atlaslib.register_case`, as a copy of the `knee-mri` index entry with `case_id` `paint-test`, title "Paint test" and no `mirror` key.

  Then in Playwright at `?case=paint-test&mode=author`:
  - **Next and Enter.** The panel shows "Next: Fibula"; Enter makes it current.
  - **Brush across a ground-truth bone.** A stroke over the femur leaves the femur's value unchanged (count `drawBitmap` values before and after). The stroke's value equals `valueFor("fibula", …)`.
  - **Eraser on the femur.** Nothing changes.
  - **Undo** restores the bitmap exactly.
  - **Unsaved paint.** "● Unsaved" shows, and `beforeunload` returns a string.
  - **Save.** It returns 200; `lut.json` has `fibula`; the checklist row shows ✓; a backup exists.
  - **Stale save.** Edit `points.json` on disk, paint, save: the 409 message and the download button appear, and the bitmap is kept.
  - **Refusals.** `?case=knee-mri-left&mode=author` shows the refusal banner with a link. The standalone view shows "Paint" on 127.0.0.1.

  Afterwards, `git checkout checklists/knee.md` (the scratch case ticked it), remove `data/paint-test` and its index entry, and confirm `git status` shows nothing from the check.
- [ ] **Step 2: Run the suites.** Expected: green, no change in counts.
- [ ] **Step 3: Commit** `viewer/author.js viewer/index.html` with the message "Author mode: checklist-driven brush, eraser, undo and save".

### Task 6: Wand, fill between slices, grow

**Files:**
- Modify: `viewer/author.js`

**Interfaces:**
- Consumes: `seedWindow`, `wandMask`, `growMask`, `keySlices` (Task 4); `afterEdit` (Task 5).
- **Wand (W):**
  - A click in the main view paints `cur` into the `wandMask` voxels, then `nv.refreshDrawing(true); afterEdit()`.
  - Panel settings: "Tolerance" (default 0.12) and "3D" (off; 2D = the current plane).
  - `maxDistMM` 40.
  - The window comes from the clicked voxel via `seedWindow`, with the sequence's `cal_min` and `cal_max`.
- **Fill between (F):** a button that runs immediately.
  1. Save `full = drawBitmap.slice()`.
  2. Leave only `cur` in `drawBitmap`.
  3. For each pair of consecutive `keySlices(…, axis of state.plane)` at least 2 apart, call `interpolateMaskSlices(a, b, {sliceType, useIntensityGuided: true})` (sliceType: sagittal 2, coronal 1, axial 0).
  4. Copy the voxels that became `cur` into `full`, put `full` back, then refresh and `afterEdit()`.
  - With fewer than 2 key slices, it shows "Paint at least two slices first".
- **Grow (G):** a button that runs immediately: `growMask(img, dims, drawBitmap, cur, {tolerance: 0.05, range, steps: 12})`, then the same apply path.

- [ ] **Step 1: Wire them and check in the browser** on `paint-test` (made as in Task 5):
  - **Wand on the ACL.** Choose `acl` and click the ACL on a mid-sagittal slice. A non-empty fill appears, staying within the dark band and off the femur and tibia.
  - **Fill between.** Brush the ACL on two sagittal slices 4 apart, then F. The 3 slices in between gain ACL voxels, and no other structure changed.
  - **Grow.** Choose `medial_gastrocnemius`, brush 3 strokes inside it, then G. It grows within the muscle and stops at fat and fascia. Look at it in all three planes.
  - **Defaults.** Adjust a default only if the check shows it's wrong, and ledger the new value and why.
  - **Undo** reverses each of the three.
  - **Clean up** as in Task 5.
- [ ] **Step 2: Run the suites.** Expected: green.
- [ ] **Step 3: Commit** `viewer/author.js` with the message "Author mode: wand, fill between slices, grow".

### Task 7: Points, and marking auto outlines as checked

**Files:**
- Modify: `viewer/author.js`

**Interfaces:**
- **Point structures.** When the current structure has type P:
  - drawing is disabled;
  - a click in the main view sets its point (`{id, name, xyz_mm: fracToWorld(frac)}`), replacing any earlier one;
  - Delete removes it;
  - both are undoable (an undo entry `{kind: "point", before}`), and both set unsaved;
  - `drawMarkers()` redraws.
- **Region structures with an earlier point.** Choosing an R or E structure that already has a point leaves that point alone.
- **K, "Looks right: mark checked".** Shown only when the current structure has `auto`. It adds the id to `checked` and sets unsaved. After the save, the badge and the panel note are gone.

- [ ] **Step 1: Wire it and check in the browser** on `paint-test`:
  - **A point.** Choose a P structure (`superior_lateral_genicular_artery`), click, save. `points.json` has it, the checklist is ticked, and the marker shows in standalone mode.
  - **Mark checked.** Choose `lateral_meniscus_body`, press K, save. Its LUT entry has no `auto`, and the other five parts keep `auto`.
  - **Clean up** as in Task 5.
- [ ] **Step 2: Run the suites.** Expected: green.
- [ ] **Step 3: Commit** `viewer/author.js` with the message "Author mode: points; mark automatic outlines as checked".

### Task 8: Expected locations in the standalone view

**Files:**
- Modify: `viewer/core.js`. Add:
  - `boundaryDots(slice, w, h, values: Set, every = 2) -> Int32Array`: flat `[i, j, …]` of voxels whose value is in `values` and that have a 4-neighbour with a different value, keeping every `every`-th in raster order;
  - `expectedNote(entry) -> string | null`, returning `"Visible only when distended — outlined where it usually lies"`.
- Modify: `viewer/index.html`:
  - `buildColormap` gives A = 0 for `expected` entries (never filled);
  - a `<canvas id="expected">` overlay draws `boundaryDots` of expected values on the main view's current slice, 2 px dots in the structure's colour, redrawn with the reference lines;
  - the voxel → canvas mapping comes from `frac2canvasPosWithTile` at three voxels of the slice (an affine in 2D);
  - `showPanel` adds the note, as it does `autoNote`.
- Test: `tests/viewer/core.test.mjs`

- [ ] **Step 1: Write the failing tests:** `boundaryDots outlines a square, skips its inside`, `boundaryDots every 2`, `expectedNote`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement it.**
- [ ] **Step 4: Run them, then check in the browser.** In `paint-test` author mode, paint `pes_anserine_bursa` (E) and save. In standalone mode it shows as a dotted outline with no fill in Fill mode, hover names it, and the panel shows the note. Clean up as in Task 5.
- [ ] **Step 5: Commit** `viewer/core.js viewer/index.html tests/viewer/core.test.mjs` with the message "Expected-location structures: dotted outline, never filled; panel note".

### Task 9: Help and docs

**Files:**
- Modify: `viewer/author.js` (the help block in the panel), `CLAUDE.md`, `README.md`

- [ ] **Step 1: Write the docs.**
  - **CLAUDE.md:**
    - Viewer modes table "Author" row: what exists now.
    - A "Painting mode" section: the tools and keys, the rule that painting is restricted to the current structure, the save checks and what a save does, the "auto" hand-off (painting a structure, or K, marks it checked), backups, and E-type structures.
    - Repo structure: `author.js`, `paint-core.js`, `save_case.py`, `checklist.py`.
    - Build step 4: "✓ done <date> except the helper merge (next plan)".
  - **README:** a "Paint" section with the one command and the URL.
- [ ] **Step 2: Run the suites.** Expected: green.
- [ ] **Step 3: Commit** `viewer/author.js CLAUDE.md README.md` with the message "Docs and help for painting mode".

---

## Build record (2026-11-08)

Built subagent-driven: one builder and one reviewer per task, then a whole-branch review (opus) and one fix pass (05bac41..6b4b78b). Suites at the end: pytest 88, node 39.

### Rulings made during the build

- Ruling P1: work in the main checkout on branch painting-mode, not a worktree — the imaging (gitignored) lives only there and plans 1–2 did the same — cost if wrong: the owner's 8004 server shows in-progress viewer files.
- Ruling P2: set_labelled sets the Labelled column to exactly `ids` (ticks those, unticks the rest; returns rows changed) — spec §5.2 "Labelled status updates automatically when you save", so an erased structure unticks — cost if wrong: a hand-ticked row for something not in the map is cleared on the next save.
- Ruling P3: Task 6's grow check uses `gastrocnemius_medial_head` (the checklist id) for "medial_gastrocnemius" — cost: none.
- Ruling P4: Task 8's A=0 for `expected` entries applies to the standalone label overlay only; author mode's drawing colormap keeps expected structures filled so they can be painted (spec §5.7: dashed outline is how they are *shown*) — cost if wrong: none.
- Ruling P5: author mode also refuses (banner) when the background volume's dims differ from the label map's — the bitmap↔labels copy assumes one grid; knee-mri is single-sequence so no effect today — cost if wrong: a future multi-grid case can't be painted until handled.
- Ruling P6: serve.py gunzips labels with a cap (decompressed > 512 MB → 400) — a 64 MB gzip body could otherwise expand without bound — cost if wrong: none for real volumes (knee = 23.6 MB).
- Ruling P7: Task 5's undo entries carry `kind: "paint"` so Task 7 can add `{kind: "point", before}` — cost: none.
- Ruling P8: browser checks run on a second server started from the branch on port 8014 (the 8004 server predates the save endpoint and the owner may be using it); stopped afterwards — cost: none.
- Task 2: Ruling: fix shape — (a) check phase refuses 400 when side is right/left and data/<mirror id> exists without mirror_of == case_id (nothing written); (b) mirror runs only when the case is in data/index.json (same condition as patch_case), else skipped with a warning — a helper's unregistered copy can still save; (c) steps 10–12 failures are caught and returned as `warnings: [msg]` beside the new token, so the browser knows the paint landed — cost if wrong: a warning the page must show (Task 5 shows result.warnings).
- Ruling P9: Task 3's endpoints reject a case_id not matching [A-Za-z0-9_-]+ (400 on save, 404 on token) — closes the deferred path-join minor at the boundary — cost if wrong: none (all case ids match).
- Task 3: Ruling: ⚠️ tailnet path — a phone browser's POST carries Origin http://duncans-macbook-pro:8004 → 403 regardless of Host; a non-browser tailnet client is the owner's own device, outside the threat model (other web pages in the same browser) — verify Host pass-through when 8004 is restarted after merge — cost if wrong: a tailnet curl could save to the case.
- Ruling P10: author mode keeps the main + two reference views layout on a wide window (spec §5.3: the ligament workflow uses the reference lines to follow the course); strokes paint in the main view only — a pointerdown on a small view keeps its standalone behaviour (main view jumps there) and paints nothing — cost if wrong: the owner wanted to paint in the small views too (easy to allow later).
- Ruling P11: silence NiiVue's own hotkeys (viewModeHotKey, clipPlaneHotKey, cycleClipPlaneHotKey → "") in every mode, carried into Task 6's dispatch — V breaks the main + small views layout and P would also fire NiiVue's clip-plane cycle — cost if wrong: the owner loses NiiVue keys the viewer never documented.
- Task 6: Ruling: wand tolerance default 0.12 → 0.10 — over 35 clicks along the ACL, 0.12 spilled 14× (up to 16k voxels, through bone), 0.10 5×, 0.08 never but ~50 vox/click (plan: adjust a default only if the check shows it's wrong, and ledger it) — cost if wrong: the owner nudges the tolerance slider.
- Task 6: Ruling: grow doesn't stop at fascia on DESS (adjacent muscles share signal); kept as-is — each G is 12 layers, so the owner presses G until the muscle is full and erases any spill; tell the owner — cost if wrong: more erasing on big muscles than hoped.
- Ruling P12: silence every NiiVue keyboard action that can change the drag mode or open a dialog (at least M and ?), in every mode, carried into Task 7's dispatch — a modal alert mid-case and a silently changed drag mode break painting — cost if wrong: none.
- Task 7: Ruling: P key places the current P structure's point at the pointer's last main-view position (no-op with a short note for a region structure or with no pointer position) — plan key table — cost if wrong: none.
- Task 7: Ruling: on a failed save the download also writes `<case>-unsaved-points.json` ({points, checked}) when points or K marks are unsaved, and both failure notes say what each file holds — spec §5.5 nothing lost — cost if wrong: one extra file in Downloads.
- Ruling P13: Task 8 also fixes the pre-existing `.group[hidden]` CSS bug (R|L and sequence buttons show when they should be hidden), found in Task 5 — it touches index.html anyway and the bug is visible in standalone — cost: none.
- Ruling P14: expected-location dots draw in standalone and sidebar (single view) whenever the overlay is outline or fill, not when it is off — spec §5.7 "drawn with a dashed outline and never a fill" applies to the atlas, not only standalone — cost if wrong: dots in the ARIA sidebar.
- Task 8: Ruling: P14 amended — in the sidebar (overlay always off there) and in Off mode, a hovered/followed E structure shows its own dots as its highlight, because NiiVue's highlight would fill it and P14's sidebar clause could never apply as written — cost if wrong: one branch to delete (index.html:840).
- Final: Ruling: final #4 (auto dropped when an auto outline is nicked under "Paint over other structures") — keep the plan's rule (CLAUDE.md contract: drop auto from any structure a save changes; the fingerprint is the record) — cost if wrong: a nicked outline counts as checked and ticked; raise with the owner.
- Final: Ruling: declined-to-judge lines (tailnet Host pass-through; 20 backups; dotted vs dashed; bone colours; grow at fascia; no reload of a downloaded 409 file; static root exposes backups/; register_case reorders index) — all stand as ruled/deferred; bone colours, dotted wording and a "Save anyway" after 409 go to the owner — cost if wrong: owner asks for a change.

### Deferred minors (not fixed; for a later pass)

- Task 1: set_labelled silently ignores ids with no checklist row (typo'd id never surfaces).
- Task 1: no tests pin prefix ids / odd padding / missing trailing pipe; nextStructure with unknown afterId untested.
- Task 1: set_labelled writes knee.md in place (not temp + os.replace); text mode would turn CRLF into LF.
- Task 1: legend says "dotted outline"; spec §5.7 says "dashed" — wording to settle in Task 8/9.
- Task 2: huge-int coordinate → OverflowError (500 not 400) in _check_points.
- Task 2: save_case has no lock of its own (Task 3 handler's lock covers the endpoint).
- Task 2: case_id not validated before the path join (only meta.json folders reachable; Task 3 to check id form).
- Task 2: result "structures" = len(lut) vs index structure_count = len(lut)+len(points).
- Task 2: private autolabels._replace imported across modules; a failed write leaves .tmp-<name>.
- Task 2: test gaps — NaN/inf/bool/duplicate/unknown point refusals, stale `expected` removal, backup contents, explicit F-order equality, mirror labels rewritten.
- Task 2: suite run with -W ignore hid 3 SWIG DeprecationWarnings from a dependency import.
- Task 2: read_index after the writes is outside any try (unreadable index.json → raw exception); corrupt mirror meta.json in the check phase → JSONDecodeError (500, nothing written).
- Task 3: Content-Length uses isdigit() → '²' gives 500 not 400.
- Task 3: no socket timeout; a short body holds a handler thread.
- Task 3: top-level save_case import loads numpy/nibabel at startup; docstring still says "standard library only"; a broken import also stops the static reader.
- Task 3: a 500 logs no traceback on the server.
- Task 3: gunzip_capped ignores unused_data; unconsumed_tail branch unreachable.
- Task 3: refuse /api/ requests carrying X-Forwarded-For / Tailscale-User-Login (so the tailnet guarantee doesn't rest on Host pass-through).
- Task 3: test gaps — foreign hostname with the right port, loose 400/404, OPTIONS headers, Origin null, charset variant, Host without port; unused imports mid-file; non-API POST/OPTIONS answer HTML.
- Task 4: growMask fully sorts the structure's intensities for p5/p95 (~100–300 ms on a big muscle); histogram/quickselect would be linear.
- Task 4: wandMask/growMask allocate a 23.6 MB visited array per call (GC-able).
- Task 4: wandMask/seedWindow don't bounds-check the seed.
- Task 4: colours.json one number per line, no trailing newline; no id matching two palette keywords.
- Task 4: timing test prints every run and asserts no bound; undoChange's LIFO requirement uncommented.
- Task 5: Enter during an in-flight save is dropped; ⌘S during a save joins it.
- Task 5: Enter on a focused panel button/select is taken as save-then-next; ⌘S in the filter box opens the browser's Save Page.
- Task 5: O hides the paint while the brush stays live (strokes invisible, still guarded).
- Task 5: no way to load a downloaded unsaved-paint file back (helper-merge plan); download with the drawing closed → unhandled rejection.
- Task 5: alt-tab mid-stroke without mouseleave leaves `stroking` set until the next pointerup (Enter deferred, nothing lost); a no-op afterEdit leaves a stale "info" note.
- Task 6: applyPen can re-enable drawing mid-gesture (W then B/E while dragging; B/E/[/] during a small-view gesture) → a drag paints with `stroking` false; if it then leaves the canvas the guard is skipped until the next edit and a save in between would omit those visible voxels.
- Task 6: "ok" tool notes (Wand/Filled … voxels added) persist past later strokes and ⌘Z.
- Task 6: fill between rescans + uploads the whole drawing per gap (~0.2 s/gap, no progress shown).
- Task 6: P11 sentinel "" could match an empty KeyboardEvent.code (clip-plane branches only; harmless in 2D).
- Task 7: undoLast always bumps the edit counter (K/place then ⌘Z → "● Unsaved" with nothing to save; Enter runs a no-op save that rotates a backup).
- Task 7: "Placed on sagittal slice N" stale after a plane switch; deletePoint/markChecked lack the S.refused guard; no warn if NiiVue's keyDownListener is renamed; keyUpListener "" sentinel vs empty e.code; ok notes persist across structure switch; unsaved points count as done for Next; hover name stale until the mouse moves.
- Task 7: Chrome may ask once per site to allow the second download; unsaved-points check compares JSON strings (key order).
- Task 8: a followed E structure looks like every other E structure in Outline/Fill; dot spacing ignores structure (touching bursae share one seam); voxelToCanvas calls canvasPos2frac every frame; sub-pixel dots look soft/faint; stale comment author.js:754; buildColormap expectedFilled / hideExpected / zoom spacing untested (glue).
- Task 9: CLAUDE.md mouse row doesn't say Shift = window/level, Ctrl/right = pan; Save paragraph doesn't say autolabels backups share the 20; README could point a phone visitor to the refusal list; Backspace not in CLAUDE.md Panel line; README Controls doesn't mark K/P author-only.
- Final: Windows helper — write_text turns knee.md/lut.json/points.json into CRLF (whole-file git diffs).
- Final: open-time "Saving won't work" note isn't sticky (a later hint replaces it); "checklist not ticked (synthetic)" note omitted when there are warnings; a restored structure whose id is on neither the checklist nor lut.json still gets 400 (recoverable with overwrite erase); a kept point whose checklist row is gone can't be chosen/deleted in the page; an erased-saved-undone auto outline comes back without auto (per the final ruling).
- (Fixed in the final pass: token fetched before the case files; refusal banner cleared on a later attach; serve.py / CLAUDE.md "standard library only" wording.)
