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

Imaging files stay out of git. See `CLAUDE.md` for the full plan.
