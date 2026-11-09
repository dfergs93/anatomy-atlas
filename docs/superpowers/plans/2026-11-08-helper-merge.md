# Helper Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A helper paints a copy of a case on their own computer and sends the paint back as one file. The owner merges it in structure by structure, and the same kind of file brings back a save that was refused.

**Architecture:**
- **Owner → helper.** `tools/share_case.py pack` zips the case without its backups or model outputs. The helper's `unpack` puts it in `data/` and registers it.
- **Helper → owner.** Painting mode's "Download paint file" writes one `.atlaspaint` file: JSON holding the grid, the structure list, the points and a gzipped bitmap.
- **Merging.** The owner opens that file in painting mode with "Merge in a paint file…". The logic is pure and node-tested (`viewer/merge-core.js`); the screen is `viewer/merge.js`. Each accept is an ordinary undoable edit, written by the existing Save.

**Tech Stack:**
- Python 3.13 (`zipfile`) with nibabel, numpy and scipy.
- Plain JS with `CompressionStream` / `DecompressionStream`, on NiiVue 0.69.0 (vendored).
- pytest and `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-05-anatomy-atlas-design.md`, §5.6 (with §5.5). This builds on `docs/superpowers/plans/2026-11-08-painting-mode.md`; the rulings in its "Build record" still hold.

## Global Constraints

- **Nothing image-bearing goes to git.**
  - Imaging and label maps never go to git.
  - A paint file holds a label map, so `*.atlaspaint` and `*-share-*.zip` are git-ignored.
  - `.gitignore` un-ignores `data/**/*.json`, which is why a paint file must not end in `.json`.
- **The helper's machine.**
  - The helper path needs only the standard library plus `requirements.txt` (nibabel, numpy, scipy).
  - The helper may be on Windows or Linux, so there is no Mac-only code, and keys take Ctrl as well as ⌘.
- **Dataset terms.**
  - CC BY-NC 4.0: personal and non-commercial, and the CartiMorph paper must be cited.
  - Confirmed 2026-11-08 on https://huggingface.co/datasets/YongchengYAO/OAIZIB-CM, which sets no other sharing terms.
  - A helper gets a copy by direct transfer, never via git.
- **Merging rules.**
  - Merging writes nothing to disk. Accepted items stay unsaved until Save, and each one can be undone with ⌘/Ctrl+Z.
  - A merge never removes a structure or a point that the owner has and the file lacks.
  - Where an incoming structure overlaps a different structure in the owner's map, the owner's voxels win, unless the owner picks "theirs wins" for that item.
- **Never touch `data/knee-mri` in tests or browser checks.** Don't paint, save, merge into or unpack over it.
  - Use a scratch copy, `data/merge-test`: registered in `data/index.json` and removed afterwards, behind a scratch server on port 8014.
  - Task 1's two new `meta.json` keys are the only change made to `knee-mri`.
- **Commits.** Stage files by name, never `git add -A`, and end commits with the repo's trailer lines.
- **Suites.** `venv/bin/python -m pytest -q` and `node --test "tests/viewer/*.test.mjs"`.

## Review Focus

1. **A stale model outline from the helper's copy.**
   - The owner has hand-fixed a model's outline that the helper never touched.
   - The helper's untouched `auto` structure must not be offered as a replacement: it is left out, and named.
   - Test: Task 2, `mergeItems leaves out incoming auto outlines and names them`.
2. **Edits to a model outline in a refused save's file.**
   - Those edits must come back. The file marks a structure `auto` only when saving right now would keep it auto.
   - Test: Task 2, `paintLut keeps auto only for unchanged, unchecked outlines`.
3. **A paint file for another case, the mirrored left copy, or a rebuilt grid.** It is refused before anything changes.
   - Test: Task 2, `checkPaintFile refuses another case, another grid, a moved grid`.
4. **A zip whose paths climb out of the case folder.** It is refused, and nothing is written.
   - Test: Task 1, `test_unpack_refuses_paths_outside_the_case`.
5. **Unpacking a fresh copy over the helper's own paint.**
   - It is refused unless `--replace` is given, and `--replace` backs the paint up first.
   - Test: Task 1, `test_unpack_refuses_over_paint_unless_replace`.

---

### Task 1: Pack a case for a helper, unpack it on theirs

**Files:**
- Create: `tools/share_case.py`, `tests/test_share_case.py`, `tests/test_helper_path.py`
- Modify: `data/knee-mri/meta.json` (two keys), `.gitignore`

**Interfaces:**
- **Consumes:**
  - `atlaslib.read_index(root)`, `atlaslib.register_case(root, entry)`, `atlaslib.backup_case(case_dir)`.
  - `make_case(root, side="right")` from `tests/test_save_case.py`, which builds and registers `data/knee-t` with sequence file `volumes/dess_3d.nii.gz`.
- **Produces:**
  - `class ShareError(Exception)`
  - `pack(root: Path, case_id: str, out: Path | None = None) -> Path`
  - `unpack(root: Path, zip_path: Path, *, replace: bool = False) -> str` (returns the case id)
  - CLI: `python tools/share_case.py pack <case> [-o FILE]` and `python tools/share_case.py unpack FILE [--replace]`
- **Zip layout:**
  - `atlas-share.json`: `{"format": "anatomy-atlas share", "version": 1, "case_id", "made": <UTC ISO>, "index_entry": {...}}`
  - `<case>/meta.json`, `<case>/lut.json`, `<case>/points.json` (when present), `<case>/labels.nii.gz`
  - `<case>/<file>` for every `meta["sequences"][*]["file"]`
  - Never `backups/` or `auto/`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_share_case.py`, import `make_case` from `test_save_case`. Each test uses two roots: `owner = tmp_path / "o"` and `helper = tmp_path / "h"`. `zipped(path, {name: bytes})` is a local helper that writes a zip.

```python
def test_pack_unpack_round_trip(tmp_path):
    case = make_case(owner)
    mirror_case(owner, "knee-t")  # the owner's index entry now has "mirror"
    z = pack(owner, "knee-t", tmp_path / "s.zip")
    names = set(zipfile.ZipFile(z).namelist())
    assert {"atlas-share.json", "knee-t/labels.nii.gz", "knee-t/volumes/dess_3d.nii.gz"} <= names
    assert not any("/backups/" in n or "/auto/" in n for n in names)
    assert unpack(helper, z) == "knee-t"
    for f in ("labels.nii.gz", "lut.json", "meta.json", "volumes/dess_3d.nii.gz"):
        assert (helper / "data/knee-t" / f).read_bytes() == (case / f).read_bytes()
    entry = next(c for c in read_index(helper) if c["case_id"] == "knee-t")
    assert "mirror" not in entry  # the helper's first save rebuilds the left copy and adds it back

def test_pack_refuses_a_mirror_and_an_unlicensed_case(tmp_path):
    # mirror_case(owner, "knee-t"); pack(owner, "knee-t-left") -> ShareError whose message names knee-t
    # meta.json with "licence" removed (synthetic false) -> ShareError matching "licence"

def test_unpack_refuses_paths_outside_the_case(tmp_path):
    # for each bad name in ["../evil", "/abs", "knee-t/../../evil", "other/x", "knee-t\\..\\x"]:
    #   a zip with a good atlas-share.json + knee-t/meta.json + that member -> ShareError,
    #   and afterwards no file exists anywhere under `helper`

def test_unpack_refuses_over_paint_unless_replace(tmp_path):
    # unpack once; overwrite helper's labels.nii.gz with other bytes; unpack again -> ShareError matching "--replace",
    # the changed bytes still there; unpack(..., replace=True) -> backups/ holds one folder whose labels.nii.gz
    # is the changed bytes, and labels.nii.gz equals the owner's again

def test_unpack_fills_a_folder_holding_only_tracked_json(tmp_path):
    # helper/data/knee-t/ holds only lut.json, meta.json, points.json (what a git clone has) -> unpack works without replace

def test_unpack_refuses_a_bad_manifest(tmp_path):
    # no atlas-share.json; format "other"; version 2; case_id "../x" -> ShareError each time, nothing written
```

Write each test in full, with the assertions given in its comments.

In `tests/test_helper_path.py`:

```python
def test_helper_path_needs_only_requirements():
    # Walk the imports of tools/serve.py and tools/share_case.py with ast, following modules that live in tools/
    # (also imports inside functions). Every other top-level module name must be in sys.stdlib_module_names
    # or named in requirements.txt.
    assert outside == set()
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `venv/bin/python -m pytest tests/test_share_case.py tests/test_helper_path.py -q`
Expected: FAIL. `test_share_case` fails with `ModuleNotFoundError: share_case`; `test_helper_path` fails because `tools/share_case.py` is missing.

- [ ] **Step 3: Implement `tools/share_case.py`**

**`pack`** raises `ShareError` in these cases:
- no `meta.json` → `no case <id>`
- `meta.mirror_of` is set → `<id> is a mirrored copy; pack <source> instead`
- the case is not synthetic and has no `licence` → `record the dataset's licence in data/<id>/meta.json first`
- `labels.nii.gz` or a sequence file is missing → name the missing file

What `pack` writes:
- **`index_entry`:** the case's `data/index.json` entry without `mirror`. When the case isn't indexed, build it from meta's `case_id`, `title`, `region`, `modality`, `side` and `synthetic`.
- **Default `out`:** `~/Downloads/<case>-share-<YYYYMMDD>.zip` when `~/Downloads` exists, otherwise the current directory.
- **Compression:** `ZIP_DEFLATED`.
- **Printed output:** meta's `licence` and its `sharing` note (when present), then the path.

**`unpack`** checks everything before writing anything:
- **The manifest:** the right format, version 1, and a case id matching `^[A-Za-z0-9_-]+$`.
- **Member names:** each is `atlas-share.json` or `<case_id>/<relative POSIX path>`, with no `..`, no backslash, no drive letter and no leading `/`.
- **Existing paint:**
  - If `data/<id>/labels.nii.gz` exists and `replace` is false, raise `ShareError`: `data/<id> already has a label map (your paint?). Download your paint file first, then run unpack again with --replace (it keeps a backup).`
  - With `replace`, call `backup_case` first.

Then `unpack`:
- writes each member through a temporary file and `os.replace`;
- calls `register_case(root, index_entry without "mirror")`;
- returns the id.

**CLI.**
- The root is the script's own repo, `Path(__file__).resolve().parents[1]`, as in `serve.py`.
- After `unpack`, print `Unpacked <id>. Start the server: python tools/serve.py — then open http://127.0.0.1:8004/viewer/?case=<id>&mode=author`.
- On a `ShareError`, print the message and exit with status 1, with no traceback.

- [ ] **Step 4: Record the terms and ignore the files**

Add two keys to `data/knee-mri/meta.json`:
- `"licence_url": "https://huggingface.co/datasets/YongchengYAO/OAIZIB-CM"`
- `"sharing": "CC BY-NC 4.0 (checked 2026-11-08 on the Hugging Face page, which sets no other sharing terms): non-commercial copies with attribution; citing the CartiMorph paper is compulsory. Give a helper a copy with tools/share_case.py, never via git."`

Add `*.atlaspaint` and `*-share-*.zip` to `.gitignore`.

- [ ] **Step 5: Run the tests and watch them pass**

Run: `venv/bin/python -m pytest -q`
Expected: all pass. That is 88 + the new tests.

Run: `git check-ignore -q a.atlaspaint && git check-ignore -q k-share-20261108.zip && echo ignored`
Expected: `ignored`.

- [ ] **Step 6: Commit**

```bash
git add tools/share_case.py tests/test_share_case.py tests/test_helper_path.py data/knee-mri/meta.json .gitignore
git commit -m "share_case: pack a case for a helper, unpack it on theirs"
```

---

### Task 2: Merge logic (`viewer/merge-core.js`)

**Files:**
- Create: `viewer/merge-core.js` (same module wrapper as `paint-core.js`: global `atlasMerge` in the browser, `module.exports` in node), `tests/viewer/merge-core.test.mjs`

**Interfaces:**
- **Paint file, version 1:**
  `{format: "anatomy-atlas paint", version: 1, case_id, made: <ISO>, why: "paint"|"unsaved", dims: [nx,ny,nz], affine: number[4][4], lut, checked: [ids], points: [{id,name,xyz_mm}], labels_gz_b64}`.
  `lut` is the output of `paintLut`. The bitmap is uint8, x fastest (NIfTI order).
- **Produces:**
  - `PAINT_FORMAT = "anatomy-atlas paint"`
  - `paintLut(savedLut, assigned: Map<id,value>, nameOf: (id) => string, checked: Set<id>, bitmap, savedBitmap) -> {[value]: {id, name, auto?: true}}`
    - Only values present in `bitmap` are included.
    - Each id and name comes from `savedLut[v]`, or else from the id that `assigned` maps to `v` (with `nameOf(id)`).
    - `auto: true` only when `savedLut[v].auto` is set, `!checked.has(id)`, and `sameVoxels(bitmap, savedBitmap, v)`.
  - `sameVoxels(a, b, value) -> boolean`
  - `encodeLabels(bitmap) -> Promise<string>` (gzip, then base64)
  - `decodeLabels(b64, n) -> Promise<Uint8Array>`. It rejects with `This paint file's label map is damaged.` when the data doesn't decode to exactly `n` bytes.
  - `checkPaintFile(obj, here: {caseId, dims, affine}) -> string | null`
  - `mergeItems(own, inc, rows) -> {items, same, autoLeft: [names], unknown: [ids]}`
    - `own` and `inc` each look like `{bitmap, lut: {[v]: {id, name, auto?}}, points}`.
    - `rows` are the checklist rows: `{id, name, type}`.
    - Each item is `{key: "<kind>:<id>", kind: "region"|"point", status: "new"|"changed"|"checked"|"moved", id, name}`.
    - A region item adds `incValue, ownValue (0 when none), incCount, ownCount, added, removed, overlap: [{id, name, count}], overlapCount`.
    - A point item adds `xyz_mm, movedMM`.
  - `regionChanges(own, inc, incValue, ownValue, incomingWins) -> {idx: Uint32Array, val: Uint8Array}`
  - `focusOf(bitmap, dims, value, axis) -> {slice, vox: [x, y, z]} | null`

- [ ] **Step 1: Write the failing tests** in `tests/viewer/merge-core.test.mjs`

```js
const M = require("../../viewer/merge-core.js");
const A = [[1,0,0,-2],[0,1,0,-1],[0,0,1,-1],[0,0,0,1]];
const here = { caseId: "k", dims: [4, 2, 2], affine: A };
const rows = ["femur","tibia","acl","pcl"].map((id) => ({ id, name: id.toUpperCase(), type: "R" }))
  .concat([{ id: "trochlea", name: "Trochlea", type: "P" }]);
const L = (o) => Object.fromEntries(Object.entries(o).map(([v, id]) => [v, { id, name: id.toUpperCase() }]));

test("paintLut keeps auto only for unchanged, unchecked outlines", () => {
  const saved = Uint8Array.from([1,1,2,2,3,3,0,0]), now = Uint8Array.from([1,1,2,0,3,3,4,0]);
  const lut = { 1: {id:"femur",name:"Femur",auto:{}}, 2: {id:"tibia",name:"Tibia",auto:{}}, 3: {id:"acl",name:"ACL",auto:{}}, 5: {id:"gone",name:"Gone"} };
  assert.deepEqual(M.paintLut(lut, new Map([["pcl", 4]]), (id) => id.toUpperCase(), new Set(["acl"]), now, saved), {
    1: {id:"femur",name:"Femur",auto:true}, 2: {id:"tibia",name:"Tibia"}, 3: {id:"acl",name:"ACL"}, 4: {id:"pcl",name:"PCL"} });
});

test("labels survive encode -> decode; a wrong length or junk is refused", async () => {
  const bm = Uint8Array.from({ length: 1000 }, (_, i) => i % 7);
  assert.deepEqual(await M.decodeLabels(await M.encodeLabels(bm), 1000), bm);
  await assert.rejects(M.decodeLabels(await M.encodeLabels(bm), 999), /damaged/);
  await assert.rejects(M.decodeLabels("not base64!", 1000), /damaged/);
});

test("checkPaintFile refuses another case, another grid, a moved grid", () => {
  const ok = { format: M.PAINT_FORMAT, version: 1, case_id: "k", dims: [4,2,2], affine: A, lut: L({1: "femur"}), checked: [], points: [], labels_gz_b64: "" };
  assert.equal(M.checkPaintFile(ok, here), null);
  const shifted = A.map((r) => r.slice()); shifted[0][3] += 0.5;
  const flipped = A.map((r) => r.slice()); flipped[0][0] = -1;
  for (const [bad, re] of [[{ case_id: "k-left" }, /for k-left, not k/], [{ dims: [2,4,2] }, /grid \(2×4×2\)/],
      [{ affine: shifted }, /placed differently/], [{ affine: flipped }, /placed differently/], [{ version: 2 }, /version 2/],
      [{ lut: { 300: { id: "x", name: "x" } } }, /damaged/], [{ points: "no" }, /damaged/], [{ checked: [1] }, /damaged/]])
    assert.match(M.checkPaintFile({ ...ok, ...bad }, here), re);
  assert.match(M.checkPaintFile({ hello: 1 }, here), /isn't an atlas paint file/);
});

test("mergeItems: new, changed (added/removed), overlap, same; checklist order; maps by id", () => {
  const own = { bitmap: Uint8Array.from([1,1,2,2,0,0,4,0]), lut: L({1:"femur",2:"tibia",4:"pcl"}), points: [] };
  const inc = { bitmap: Uint8Array.from([0,9,9,6,6,0,7,0]), lut: L({9:"acl",6:"tibia",7:"pcl"}), points: [] };
  const r = M.mergeItems(own, inc, rows);
  assert.deepEqual(r.items.map((i) => [i.id, i.status]), [["tibia","changed"], ["acl","new"]]);
  const [tib, acl] = r.items;
  assert.deepEqual([tib.incValue, tib.ownValue, tib.added, tib.removed, tib.overlapCount], [6, 2, 1, 1, 0]);
  assert.deepEqual([acl.ownValue, acl.added, acl.overlapCount], [0, 2, 2]);
  assert.deepEqual(acl.overlap.map((o) => [o.id, o.count]), [["femur",1], ["tibia",1]]);
  assert.equal(r.same, 1); // pcl: the same voxels under another value
  // femur is absent from the file: never offered for removal
});

test("mergeItems leaves out incoming auto outlines and names them", () => {
  const own = { bitmap: Uint8Array.from([1,1,0,0]), lut: L({1:"femur"}), points: [] };
  const inc = { bitmap: Uint8Array.from([1,0,0,0]), lut: { 1: { id: "femur", name: "FEMUR", auto: true } }, points: [] };
  assert.deepEqual(M.mergeItems(own, inc, rows), { items: [], same: 0, autoLeft: ["FEMUR"], unknown: [] });
});

test("mergeItems offers a check when the voxels match and only theirs is checked", () => {
  const bm = Uint8Array.from([1,1,0,0]);
  const own = { bitmap: bm, lut: { 1: { id: "femur", name: "FEMUR", auto: true } }, points: [] };
  assert.equal(M.mergeItems(own, { bitmap: bm, lut: L({1:"femur"}), points: [] }, rows).items[0].status, "checked");
});

test("mergeItems: unknown ids and points (new / moved / same)", () => {
  const z = Uint8Array.from([0,0,0,0]);
  const own = { bitmap: z, lut: {}, points: [{ id: "trochlea", name: "Trochlea", xyz_mm: [0,0,0] }] };
  const inc = { bitmap: Uint8Array.from([5,0,0,0]), lut: L({5:"mystery"}),
    points: [{ id: "trochlea", name: "Trochlea", xyz_mm: [0,0,3] }, { id: "zzz", name: "Z", xyz_mm: [1,1,1] }] };
  const r = M.mergeItems(own, inc, rows);
  assert.deepEqual(r.items.map((i) => [i.id, i.status, i.movedMM]), [["trochlea","moved",3]]);
  assert.deepEqual(r.unknown.sort(), ["mystery", "zzz"]);
  inc.points = [{ id: "trochlea", name: "Trochlea", xyz_mm: [0,0,0.005] }];
  assert.equal(M.mergeItems(own, inc, rows).items.length, 0); // within 0.01 mm: the same
});

test("regionChanges: owner wins overlaps unless incomingWins; undo restores", () => {
  const own = Uint8Array.from([1,2,0,3,3]), inc = Uint8Array.from([5,5,5,0,0]);
  const a = M.regionChanges(own, inc, 5, 3, false), b = M.regionChanges(own, inc, 5, 3, true);
  assert.deepEqual([[...a.idx], [...a.val]], [[2,3,4], [3,0,0]]);
  assert.deepEqual([[...b.idx], [...b.val]], [[0,1,2,3,4], [3,3,3,0,0]]);
  // apply b to a copy, keep old values, put them back with paint-core's undoChange: equals `own` again
});

test("focusOf picks the fullest slice and its in-plane centre", () => {
  const bm = new Uint8Array(12); // dims [2,2,3]
  bm[0] = 1; bm[8] = 1; bm[9] = 1; bm[11] = 1; // z=0: (0,0); z=2: (0,0) (1,0) (1,1)
  assert.deepEqual(M.focusOf(bm, [2,2,3], 1, 2), { slice: 2, vox: [1,0,2] });
  assert.equal(M.focusOf(bm, [2,2,3], 4, 2), null);
});
```

Complete the undo assertion in `regionChanges` using `require("../../viewer/paint-core.js").undoChange`.

- [ ] **Step 2: Run the tests and watch them fail**

Run: `node --test tests/viewer/merge-core.test.mjs`
Expected: FAIL with `Cannot find module '../../viewer/merge-core.js'`.

- [ ] **Step 3: Implement `viewer/merge-core.js`**

**`checkPaintFile` copy, exactly.** Return the first message that applies:
1. `This isn't an atlas paint file.` (wrong or missing `format`)
2. `This paint file is version ${v}; this atlas reads version 1.`
3. `This paint file is for ${case_id}, not ${here.caseId}. Open ${case_id} in painting mode to merge it.`
4. `This paint file's grid (${dims.join("×")}) doesn't match this case's (${here.dims.join("×")}), so its paint would land in the wrong voxels.`
5. `This paint file's grid is placed differently from this case's (rebuilt or mirrored?), so its paint would land in the wrong voxels.` (any affine element off by more than 1e-3)
6. `This paint file's structure list is damaged.`, when:
   - a `lut` key is not an integer from 1 to 255, or an entry lacks a string `id`;
   - `points` is not an array of `{id: string, name: string, xyz_mm: [3 finite numbers]}`;
   - `checked` is not an array of strings.

**`mergeItems`.**
- **One pass over the two bitmaps.**
  - Keep per-value counters in 256-long typed arrays, and overlap pairs in a `Map` keyed `incValue * 256 + ownValue`.
  - Knee-mri has about 24 M voxels, so 40 structures must not mean 40 passes.
- **Mapping.**
  - Incoming and owner values are matched by id.
  - "Same" means `inc === a` and `own === ownValueOf(a)`.
  - `added = incCount − same`, `removed = ownCount − same`.
  - Overlap means `inc === a` while `own` is neither 0 nor `ownValueOf(a)`.
- **What is offered.**
  - **Known ids:** a region id must be a checklist row id or an id in `own.lut`; a point id must be a row id or an owner point id. Anything else goes to `unknown`, because the save would refuse it.
  - **`auto` structures** are never offered. Their names go to `autoLeft` when their voxels differ from the owner's.
  - **Identical voxels** give the item `checked` when the owner's entry is `auto`. Otherwise they are counted in `same`.
  - **Points:**
    - `moved` when any coordinate differs by more than 0.01 mm; `movedMM` is the distance, rounded to 0.1 mm.
    - `new` when the owner has no point with that id.
    - otherwise counted in `same`.
- **Order.**
  - Items follow the checklist's row order; unknown ids come last.
  - `overlap` is sorted by count, highest first; ties follow checklist order.

**`regionChanges`.** For each voxel:
- If it holds `incValue` in the incoming map:
  - it becomes `ownValue` when the owner's voxel is 0, or when `incomingWins` is set;
  - it is unchanged when it already is `ownValue`.
- Otherwise, an owner voxel equal to `ownValue` becomes 0.
- Only changed voxels are returned.

**`focusOf`.** The slice along `axis` with the most voxels of `value` (lowest index on ties). The in-plane coordinates are that slice's centroid, rounded.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `node --test "tests/viewer/*.test.mjs"`
Expected: all pass (39 + the new ones).

- [ ] **Step 5: Commit**

```bash
git add viewer/merge-core.js tests/viewer/merge-core.test.mjs
git commit -m "merge-core: paint file checks, one-pass merge comparison, per-structure changes"
```

---

### Task 3: Download a paint file (one file, also after a refused save)

**Files:**
- Modify: `viewer/author.js`, `viewer/index.html` (load `merge-core.js` before `author.js`; add `merge: window.atlasMerge` to the ctx passed to `attachAuthor`)

**Interfaces:**
- **Consumes:** from Task 2, `paintLut`, `encodeLabels` and `PAINT_FORMAT`.
- **Produces, in `makeAuthor`:**
  - `S.savedBitmap`: the bitmap as last loaded or saved.
  - `ownLut()`: `paintLut(S.savedLut, S.assigned, nameOf, S.checked, before, S.savedBitmap)`, where `nameOf` uses the checklist row name, or else the id.
  - `paintFile(why) -> Promise<object>`, where `why` is `"paint"` or `"unsaved"`. It returns the version 1 object:
    - `dims` = `nv.volumes[1].hdr.dims[1..3]`
    - `affine` = `nv.volumes[1].hdr.affine`, as plain arrays
    - `checked` = `[...S.checked]`
    - `points` = a copy of `state.points`
  - `downloadPaintFile(why) -> Promise<void>`
    - File name: `${caseId}-${why}-${YYYYMMDD-HHMM local}.atlaspaint`.
    - Blob type: `application/octet-stream`, so browsers keep the extension.
  - The session object exports `paintFile` and `downloadPaintFile`. They replace `downloadPaint` and `downloadUnsaved`.

- [ ] **Step 1: Track the saved bitmap**
  - `loadDrawing` sets `S.savedBitmap = before.slice()`.
  - `runSave` snapshots `const sent = before.slice()` alongside `raw`.
  - After a successful save, `runSave` sets `S.savedBitmap = sent`.

- [ ] **Step 2: Add `paintFile` / `downloadPaintFile`, and the panel button**
  - Add a new `<section class="ap-share">` under `.ap-save`, holding `#apDownload` "Download paint file".
  - Its title: "One file with this case's paint, points and checked marks: send it to whoever merges it, or merge it back in later".

- [ ] **Step 3: The refused save offers the paint file**
  - **Download:** the button stays "Download my unsaved work" and calls `downloadPaintFile("unsaved")`. One file replaces the old `.nii.gz` + `-points.json` pair.
  - **Message:** the existing first sentence (409 or other) stays. After it comes: `The download is one file, <code>${case}-unsaved-….atlaspaint</code>; after reloading, “Merge in a paint file…” brings it back.`
  - Remove `pointsOrChecksUnsaved`'s now-unused download branch. Keep the function only if something else still uses it.

- [ ] **Step 4: Browser check**

Set up the scratch copy:
1. `cp -R data/knee-mri data/merge-test`, then `rm -rf data/merge-test/backups`.
2. Set `case_id` and `title` in its `meta.json`.
3. Register it with `register_case`, copying knee-mri's index entry without `mirror`.
4. Start `venv/bin/python tools/serve.py --port 8014`.

Open `http://127.0.0.1:8014/viewer/?case=merge-test&mode=author`. Then:
- **(a) A paint file of fresh edits.**
  - Paint a few voxels of a new structure; erase a little of an `auto` structure; press K on another `auto` structure; place a point.
  - Then `const f = await atlasAuthor.paintFile("paint")`. Check that:
    - `case_id` is `merge-test`;
    - `dims` are knee-mri's;
    - the edited and the K'd ids have no `auto`, and an untouched auto id has `auto: true`;
    - `points` has the new point;
    - `await atlasMerge.decodeLabels(f.labels_gz_b64, n)` equals `atlasAuthor.before`.
- **(b) The download.** Click "Download paint file" and confirm one `.atlaspaint` file is downloaded.
- **(c) A refused save.**
  - On disk, append a space to `data/merge-test/points.json`, then press Save.
  - Expect a 409 message naming the `.atlaspaint` file, and a button that downloads one file.

Report the timings of `paintFile` and of the download. Leave the scratch case for Task 4, or rebuild it there.

- [ ] **Step 5: Run the suites and commit**

Run: both suites. Expected: all pass.

```bash
git add viewer/author.js viewer/index.html
git commit -m "Author mode: one .atlaspaint download for sharing and for a refused save"
```

---

### Task 4: The merge screen, and the helper's instructions

**Files:**
- Create: `viewer/merge.js` (global `makeMerge`, loaded before `author.js`)
- Modify:
  - `viewer/author.js`: the api, the "Merge in…" button, key routing, `canPaint`, undo/save/reattach hooks
  - `viewer/index.html`: script tag, `setMergePreview`, drawing in `drawExpected`
  - `CLAUDE.md`, `README.md`

**Interfaces:**
- **Consumes:**
  - From Task 2: `checkPaintFile`, `decodeLabels`, `mergeItems`, `regionChanges`, `focusOf`.
  - From Task 3: `ownLut()` and `S.savedBitmap`.
- **Produces:**
  - `makeMerge(api) -> {open(file: File): Promise<void>, close(): void, active(): boolean, onKey(e): boolean, refresh(): void}`
  - **The `api` object, built in `makeAuthor`:**
    - `{ nv, $, esc, M: window.atlasMerge, caseId, region: state.meta.region }`
    - `here(): {caseId, dims, affine}`
    - `rows(): S.rows`
    - `own(): {bitmap: before, lut: ownLut(), points: state.points}`
    - `valueFor(id) -> number`, which throws `RangeError` when no value is free
    - `applyChanges(id, value, {idx, val})`, which:
      - sets `nv.drawBitmap` and `before`;
      - pushes undo `{kind: "paint", idx, old}`;
      - adds a new id to `S.assigned`;
      - calls `applyColours()`, `refreshDrawing` and `edited()`.
    - `markChecked(id)`: `S.checked.add` plus undo `{kind: "check", id}`
    - `setPoint(p)`: replaces or adds the point; undo `{kind: "point", before}`; then `drawMarkers` and `edited`
    - `note(kind, html)`, `clearNote()`, `renderAuthor()`
    - `setPreview(p | null)`
    - `goToVox([x, y, z])`, `goToMM(xyz)`, `mainAxis() -> 0 | 1 | 2`
  - **`ctx.setMergePreview(p | null)` in `index.html`**, where `p = {inc, value, own, ownValue}`. `drawExpected` draws it on the main view in author mode:
    - yellow `#ffd60a` dots on the boundary of `inc === value`, using `boundaryDots` with the same spacing as the expected outlines;
    - a red `#ff453a` dot on every voxel where `inc === value` and `own` is neither 0 nor `ownValue`.

- [ ] **Step 1: Build the screen** (`viewer/merge.js` + the author hooks)

**Opening a file.**
- `#apMergeIn` "Merge in a paint file…" in `.ap-share` opens a hidden `<input type="file" accept=".atlaspaint">`. It is disabled while a save is in flight.
- A refused or unreadable file gives `note("error", <message>)` and changes nothing. Bad JSON gets `This isn't an atlas paint file.`

**While merging,** `#apMerge` replaces the current-structure card, the tools, the point section and the structure list. Top to bottom:
1. **Header:** `Merging <b>${file name}</b>`, then muted `${why === "unsaved" ? "unsaved work" : "paint"} from ${made, local date and time}`.
2. **The shown item:** its name, then a status line:
   - new region: `New — you haven't painted it · ${incCount} voxels`
   - changed: `Theirs adds ${added} voxels and removes ${removed} of yours`
   - checked: `They marked the model's outline checked; the voxels are the same as yours`
   - new point: `New point`
   - moved point: `Moved ${movedMM} mm from yours`
3. **Overlap line,** only when `overlapCount > 0`: `${overlapCount} of its voxels are your ${names joined with ", "} (red dots): yours are kept`.
4. **Buttons:**
   - `Accept · Enter`
   - `Accept — theirs wins the overlap` (only when there is an overlap)
   - `Skip · N`
   - `Accept all the rest`, with the title "Accepts every item left; where one overlaps your other structures, yours are kept"
   - `Stop merging · Esc`
5. **Summary:** `${items.length} to review · ${same} the same as yours`, plus, when non-empty:
   - `Left out — model outlines they didn't check: ${names}`
   - `Left out — not on your checklist (add them to checklists/${region}.md to merge): ${ids}`
6. **The remaining items,** as a clickable list.

When no items are left, show: `Nothing left to merge. ` + (`Save to keep what you accepted.` if anything was accepted, otherwise `Nothing in this file differs from yours.`).

**Behaviour.**
- **Showing an item** previews it. A region item calls `setPreview({inc, value: incValue, own: before, ownValue})`; a point item calls `setPreview(null)`.
- **The cursor moves only when the shown item changes:**
  - a region item goes to `focusOf(inc, dims, incValue, mainAxis())`;
  - a point item goes to its `xyz_mm`.
- **Accept:**
  - Region: `value = api.valueFor(id)` (a `RangeError` becomes an error note, and nothing changes); then `api.applyChanges(id, value, M.regionChanges(before, inc, incValue, value, wins))`.
  - Checked: `api.markChecked(id)`.
  - Point: `api.setPoint({id, name, xyz_mm})`.
  - Then `refresh()`: recompute `mergeItems(api.own(), inc, api.rows())` minus the skipped keys, and show the next item in list order.
- **Skip** adds the key to the skipped set, then shows the next item.
- **Accept all** accepts each item in turn, with the owner winning overlaps and one undo entry per item. It ends with the note `Accepted ${n}. Save to keep them.`
- **Undo, save and reattach:**
  - ⌘/Ctrl+Z runs the author's undo, then `refresh()`, so an undone item reappears.
  - `reloadAfterSave` ends with `merge.refresh()`.
  - `reattach` (a sequence change) closes an open merge.
- **While merging:**
  - `canPaint()` is false, so a click neither paints nor places a point.
  - The author's tool keys B, E, W, F, G, P, K and Delete do nothing.
  - Enter, N and Esc go to the merge.
  - ⌘/Ctrl+S, ⌘/Ctrl+Z, O, the arrows and the wheel still work.
- **Esc or "Stop merging"** clears the preview and restores the panel. Accepted edits stay, unsaved.
- **Key help** gains: `<p><b>Sharing:</b> “Download paint file” writes one .atlaspaint file · “Merge in a paint file…” goes through it one structure at a time</p>`.

- [ ] **Step 2: Browser check, end to end, on scratch copies only**

Set up both sides:
1. **Owner side:** `data/merge-test` (as in Task 3) on port 8014.
2. **Helper side:**
   - `rsync -a --exclude data --exclude 'venv*' --exclude .git ./ <scratchpad>/helper-root/`
   - `venv/bin/python tools/share_case.py pack merge-test -o <scratchpad>/mt-share.zip`
   - `venv/bin/python <scratchpad>/helper-root/tools/share_case.py unpack <scratchpad>/mt-share.zip` (it unpacks into the helper root's `data/`)
   - serve with `venv/bin/python <scratchpad>/helper-root/tools/serve.py --port 8015`

**As the helper, on 8015:**
- paint a new structure on three slices and press F;
- erase part of an `auto` outline;
- press K on another;
- paint over one of the owner's structures with "Paint over other structures" on;
- place a point;
- Save; expect no error, and the left copy rebuilt;
- click "Download paint file".

**As the owner, on 8014:**
- Merge in that file. Expect items for the new structure (`new`), the erased outline (`changed`), the K'd one (`checked`) and the point (`new`).
- Check the yellow outline and the red overlap dots by screenshot.
- Accept one with "theirs wins". Check that ⌘Z brings the item back.
- Skip one, then Accept all.
- Save. With Python, check that `data/merge-test/labels.nii.gz` has the accepted structures, that the skipped one is as before, and that the owner's other structure was kept at the overlap except where "theirs wins" was chosen.

Then:
- **Refused file:** merge in a file built for `knee-mri-left`, or with a shifted affine. Expect the refusal message and no change.
- **Timings:** report open-to-first-item and per-accept times on knee-mri's grid. The target is under 2 s and under 0.5 s.
- **Clean up:**
  - stop 8014 and 8015;
  - remove `data/merge-test` and its index entry, and the helper root;
  - delete the downloaded `.atlaspaint` files.
  - `data/knee-mri` must be byte-identical to before, apart from Task 1's `meta.json` keys.

- [ ] **Step 3: Docs**

**`CLAUDE.md`, Painting mode section:**
- replace the failed-save download sentence;
- add a "Sharing and merging" paragraph covering pack/unpack, the paint file, the merge rules (by id, owner wins overlaps, never removes, auto outlines left out, unknown ids left out, nothing written until Save), keys, and the 409 recovery (reload, then Merge in);
- change "Not built" to drop the helper merge.

**`CLAUDE.md`, elsewhere:**
- Repo structure: add `viewer/merge-core.js`, `viewer/merge.js`, `tools/share_case.py`.
- Build sequence: step 4 is done.

**`README.md`: a "Helping paint" section.**
- **The owner:** runs `pack`.
- **The helper:**
  - gets the code;
  - creates `python3 -m venv venv` and installs `requirements.txt` (Windows: `py -3 -m venv venv`, `venv\Scripts\python -m pip install -r requirements.txt`);
  - runs `tools/share_case.py unpack <zip>`, then `tools/serve.py`;
  - opens the printed URL, paints, saves, and sends the "Download paint file" file back;
  - should not commit `checklists/knee.md`: their saves tick it in their copy.
- **The owner, again:** uses "Merge in a paint file…", then saves.

- [ ] **Step 4: Run the suites and commit**

Run: both suites. Expected: all pass.

```bash
git add viewer/merge.js viewer/author.js viewer/index.html CLAUDE.md README.md
git commit -m "Merge screen: bring a helper's paint file in structure by structure"
```

## Build record (2026-11-09)

Built subagent-driven: one builder and one reviewer per task, then a whole-branch review (opus) and one fix pass (cc84b12..dcbba15). Fix rounds: Task 2 (regionChanges guard), Task 4 (Accept all order hole). Suites at the end: pytest 106, node 59. Browser checks ran on scratch copies only (owner side 8014, helper root 8015); knee-mri's files were hash-checked unchanged after each.

### Rulings made during the build

- Ruling R1: in mergeItems, "same" voxels exist only when the owner has a value for the id (ownValue > 0); a region whose id the owner lacks has same 0, added = incCount, removed 0, status "new" — the plan's literal rule would count a new structure painted on empty voxels as identical and never offer it (spec §5.6: every incoming structure is offered) — T2 adds a test: a new id painted only on empty voxels is offered "new" with added = incCount — cost if wrong: none.
- Ruling R2: checkPaintFile also returns its "isn't an atlas paint file" message for a non-object (null, array, number), and "structure list is damaged" when two lut values share an id or two points share an id — mergeItems matches by id and save_case refuses duplicate points — T2 adds those cases to the checkPaintFile test — cost if wrong: none.
- Ruling R3: paintLut computes presence and changed-ness in one pass over the two bitmaps (not one sameVoxels pass per auto value) — T4 calls it on every refresh; target < 0.5 s per accept on 24 M voxels — cost if wrong: none.
- Ruling R4: unpack refuses (ShareError, nothing written) a manifest whose index_entry is not a dict with case_id equal to the manifest's case_id — it is registered in data/index.json as-is — T1 adds the case to test_unpack_refuses_a_bad_manifest — cost if wrong: none.
- Ruling R5: the scratch case keeps side "right" (the helper-side check needs the left copy rebuilt); owner-side cleanup also removes data/merge-test-left and its index entry and restores checklists/knee.md with `git checkout checklists/knee.md` (a save of the non-synthetic scratch case ticks it); `git status` must show nothing from the checks afterwards — cost if wrong: none.
- Ruling R6: plan 3's Ruling P1 carries — work in the main checkout on helper-merge; the owner's 8004 server serves this checkout's viewer files (its Python stays the merged main's until restarted) and briefly lists merge-test in the case picker — cost if wrong: the owner sees in-progress viewer files on 8004.
- Ruling R7: Task 3 removes its scratch case at the end (server stopped, data/merge-test + index entry gone) and Task 4 rebuilds it — a server left running between agents can't be stopped by the next one — cost: one cp of knee-mri (~seconds).
- Task 4: Ruling: accepted items stay off the list until an undo changes them (`taken`, merge-core itemsLeft, node-tested) — an accept that kept the owner's overlap still differs from the file, so the plan's "recompute mergeItems minus skipped" would re-offer it at once and the list would never empty — cost if wrong: an item accepted then changed by hand isn't re-offered until the file is opened again.
- Task 4: Ruling: the done text is conditional so it never says "Nothing in this file differs from yours" after skips or a save — the plan's two-way text would be false then — cost: none.
- Task 4: Ruling: api.valueFor treats the current (selected, unpainted) structure's value as taken, and the api gains unsaved() — without it an incoming new structure could get the same value as the current structure and the two would merge into one — cost: none.
- Task 4: Ruling: keep checkPaintFile's "Open <case> in painting mode" copy even when <case> is a mirrored copy — painting mode never writes a paint file for a mirror (it refuses them), so only a hand-made file can name one — cost if wrong: a confusing line on a hand-edited file.
- Final: Ruling: Important 2's fix in this pass = (a) "Accept all the rest" on a helper's file (why "paint") takes new, checked and point items only and leaves "changed" ones for one-by-one review, saying so in its title and end note; on a refused save's own file (why "unsaved") it still takes everything (the file is the owner's own latest work); (b) CLAUDE.md + README say plainly what is and isn't protected; the pack-time fingerprint (three-way merge that leaves out structures the helper never changed) goes to the owner as the follow-up — the narrowed Accept all removes the silent bulk revert, one-by-one review shows "Theirs adds … and removes … of yours" before each — cost if wrong: a few extra Enter presses on a helper's file; the stale-copy item still shows up one by one until the follow-up lands.
- Final: Ruling: README "don't commit checklists/knee.md" becomes "you don't need to commit anything" in the same docs edit (unpack and saves also change tracked data/<case>/*.json) — same paragraph as Important 2's docs fix — cost: none.
- Final: Ruling: declined-to-judge lines all stand — owner running unpack --replace on their own machine (misuse), zip bombs/decompression caps and Windows reserved names (files pass between trusted people; already deferred), save_case write phase not atomic + serve.py 500 text (pre-existing; the encoding fix removes the trigger found), minimum Python version unaudited, CompressionStream support (Save already needs it), ZIP_DEFLATED on gzipped members (time only), theirs-wins dropping auto from an overlapped owner outline (same as paint-over), preview not marking voxels a changed accept would clear (status line states the removed count), Accept all pushing edits off the 100-deep undo stack (pre-existing limit; Save unaffected) — cost if wrong: owner asks for one of them.

### Deferred minors (not fixed; for a later pass)

- Task 1: a zip with a bare "knee-t/" directory entry (zip -r / Finder) is refused as "unsafe or unexpected file"; pack never writes one.
- Task 1: CASE_ID regex uses match with $ (trailing newline passes); use fullmatch.
- Task 1: tests could pin more — "pack knee-t instead", index_entry without mirror inside atlas-share.json, the full --replace refusal text.
- Task 1: CLI main() untested; malformed meta.json / OSError / zlib.error in pack or unpack still print a traceback; errors go to stdout.
- Task 1: a failed copy leaves a .part file; a fresh unpack failing after labels.nii.gz is written leaves a folder the next run refuses as "your paint".
- Task 1: --replace over a helper case with points.json, from an owner case without one, keeps the helper's stale points.json (the backup has it; those points would be offered again as new).
- Task 1: unpack requires only <case>/meta.json, not labels.nii.gz or the sequence files; Windows alternate-stream names (knee-t/x:s) pass the drive check.
- Task 2: encode/decode test only 1000 bytes (one chunk); no >24 KB incompressible or truncated-gzip test.
- Task 2: focusOf tested on axis 2 only; tie rule and half-rounding untested; allocates an array per matching voxel.
- Task 2: the extra checkPaintFile rules (malformed dims/affine, non-string labels_gz_b64) are untested.
- Task 2: lut entry name not validated as a string (mergeItems uses e.name || id).
- Task 2: sort comparators rely on Infinity - Infinity = NaN → 0; compare explicitly.
- Task 2: incoming bitmap values with no lut entry are dropped silently (not in unknown).
- Task 2: a point id counts as known if any checklist row has it, including a region row.
- Task 2: decodeLabels has no cap on decompressed size before the length check.
- Task 2: regionChanges checks the value's range, not that it's free (it has no owner map); Task 4 must pass api.valueFor(id).
- Task 3: if reloadAfterSave throws after a successful save, S.savedLut stays stale while savedBitmap = sent, so a structure the save un-auto'd could be written auto: true in a paint file (warning already shown).
- Task 3: runSave holds raw (Blob copy) + sent (slice) — one full-size copy avoidable.
- Task 3: #apDownload stays enabled during encode; a double click downloads twice.
- Task 3: `why` not validated in paintFile/downloadPaintFile (only two literals passed today).
- Task 4: Accept all has no try/finally; an unexpected exception mid-loop skips refresh.
- Task 4: #apMergeIn stays enabled on a refused sequence (drawing closed); an accept then throws TypeError on null nv.drawBitmap, nothing applied.
- Task 4: goToVox repeats index.html's moveCursor; .am-actions kbd style repeats .ap-next kbd.
- Task 4: done text says "Save to keep what you accepted." after every accept was undone and the rest skipped.
- Task 4: an accept that changes no voxels adds no undo step, so ⌘Z can't bring that item back (reopening the file offers it again).
- Final: a refused save's file can't bring back a full erasure or a deleted point (paint file holds only painted values; merge never removes) — spec §5.5; follow-up: carry a removed-ids list and name it when why === "unsaved".
- Final: an accepted point keeps the file's name instead of the owner's checklist row name.
- Final: a truncated/corrupt zip gives a traceback after a partial write (BadZipFile/CRC not ShareError); z.testzip() before writing would keep "nothing written".
- Final: the encoding guard test treats Path.open() with no arguments as ZipFile.open and doesn't flag it (no such call in tools/ today); encoding=None or a positional encoding isn't judged.
- Final: bulkTakes treats any why other than "paint" as take-all; a hand-edited file with no why gets take-all while the panel calls it paint.

(Fixed during the build, so not listed: CLAUDE.md's two-file download sentence, replaced in Task 4; Task 4's empty undo entry for an accept that changes nothing, removed in its fix round.)

### Follow-up for the owner

- Pack-time base (three-way merge): `pack` records a per-structure fingerprint, the helper's paint file marks structures unchanged since unpack, and the merge leaves those out and names them, as it does unchecked model outlines. Until then a structure the owner changed after packing shows as "changed" and is left for one-at-a-time review (Accept all skips it on a helper's file).
