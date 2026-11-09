# anatomy-atlas

Self-hosted MSK MRI anatomy atlas: scroll a normal scan, hover a structure to see its name, click for details. Works offline. Personal / departmental, non-commercial use.

## Try it

```
pip install -r requirements.txt
python tools/make_demo_case.py   # synthetic test knee (shapes, not anatomy)
python tools/serve.py            # open http://127.0.0.1:8004/
```

Sidebar view (as embedded in ARIA): `http://127.0.0.1:8004/viewer/?mode=sidebar`

**Controls:** mouse wheel or ↑/↓ = slice · left-drag = window/level · right-drag = pan · click = details · click a small view to jump there · `1`–`3` plane · `O` overlay · `/` find · `R` reset · `Esc` clear

## Paint

```
python tools/serve.py
```

Then open `http://127.0.0.1:8004/viewer/?case=knee-mri&mode=author` (or the "Paint" link in the viewer header). Pick a structure from the checklist, paint, press `Enter` to save and move to the next. Saves are backed up first and work on this computer only. See `CLAUDE.md` → Painting mode.

## Helping paint

Someone else can paint a copy of a case on their own computer (Mac, Windows or Linux) and send the paint back.

**The owner** packs the case and hands the zip over directly (never via git):

```
python tools/share_case.py pack knee-mri      # writes knee-mri-share-<date>.zip to ~/Downloads
```

**The helper** gets this repo's code, then:

```
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python tools/share_case.py unpack knee-mri-share-<date>.zip
venv/bin/python tools/serve.py
```

On Windows: `py -3 -m venv venv`, `venv\Scripts\python -m pip install -r requirements.txt`, then the same commands with `venv\Scripts\python`.

Open the URL `unpack` printed, paint, save, then click "Download paint file" and send that `.atlaspaint` file back. You don't need to commit anything: unpacking and your saves also change the case's tracked JSON and the checklist in your copy.

**The owner** opens the case in painting mode, clicks "Merge in a paint file…", goes through it one structure at a time (Enter accept, N skip, Esc stop), then saves. Model outlines the helper never checked are left out, but a structure you have changed since packing shows as "changed", and accepting it brings back the helper's (packed) version, so on a helper's file "Accept all the rest" leaves those for you to look at one at a time.

## Tests

```
venv/bin/pip install -r requirements-dev.txt
venv/bin/python -m pytest
node --test "tests/viewer/*.test.mjs"
```

## Add a real case

Download a public dataset (see `CLAUDE.md` → Data sources), then:

```
python tools/build_case.py knee-mri --title "Knee — OAI 3D DESS" --region knee --side right \
  --seq dess_3d "DESS 3D" path/to/image.nii.gz \
  --labels path/to/labels.nii.gz --preset oaizib-cm \
  --source "OAIZIB-CM" --licence "CC BY-NC 4.0"
```

## Auto-labels

Models add the menisci (split into anterior horn, body and posterior horn) and the patellar cartilage, so painting starts from them. They run in their own venv:

```
python3.13 -m venv venv-autoseg && venv-autoseg/bin/pip install -r requirements-autoseg.txt
venv/bin/python tools/autolabels.py knee-mri
```

Existing labels always win, the case is backed up first, and the mirrored left copy is rebuilt. Patella and fibula are painted; TotalSegmentator could add them with a free academic licence (see `CLAUDE.md` → Base auto-labels).

Imaging files stay out of git. See `CLAUDE.md` for the full plan.
