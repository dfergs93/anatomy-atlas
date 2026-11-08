import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from autoseg import dosma_unet

ROOT = Path(__file__).resolve().parents[1]
AUTOSEG_PY = ROOT / "venv-autoseg" / "bin" / "python"
CAND = Path("~/datasets/OAIZIB-CM/candidates").expanduser()

# cand-049 (OAI DESS): RAS, ~4° oblique (same matrix as tests/viewer/core.test.mjs)
CAND_AFFINE = np.array([
    [0.6982881426811218, 0.025432050228118896, 0.0, 8.507220268249512],
    [-0.04882906749844551, 0.3636952340602875, 8.095376441806596e-17, -70.65251922607422],
    [1.084223100155002e-17, 0.0, 0.3645833432674408, -85.64833068847656],
    [0, 0, 0, 1],
])


def test_orientation_round_trip():
    a = np.random.default_rng(0).random((4, 5, 6))
    m = dosma_unet.to_model(a, CAND_AFFINE)
    assert m.shape == (4, 6, 5)  # (slices L→R, rows S→I, columns A→P)
    assert np.array_equal(dosma_unet.from_model(m, CAND_AFFINE), a)
    for i in range(4):
        assert np.array_equal(m[i], a[i, ::-1, ::-1].T)


def test_orientation_follows_the_affine_not_the_array():
    # an LPS-stored copy of the same volume gives the same model input
    a = np.random.default_rng(1).random((4, 5, 6))
    stored = a[::-1, ::-1, :]  # stored voxel (i, j, k) is a's (3 - i, 4 - j, k)
    lps_affine = CAND_AFFINE @ np.array([[-1, 0, 0, 3], [0, -1, 0, 4], [0, 0, 1, 0], [0, 0, 0, 1]], float)
    assert nib.aff2axcodes(lps_affine) == ("L", "P", "S")
    assert np.array_equal(dosma_unet.to_model(stored, lps_affine), dosma_unet.to_model(a, CAND_AFFINE))
    assert np.array_equal(dosma_unet.from_model(dosma_unet.to_model(stored, lps_affine), lps_affine), stored)


def test_normalise_zero_mean_unit_std():
    x = np.random.default_rng(2).normal(50, 7, (10, 11, 12)).astype(np.int16)
    z = dosma_unet.normalise(x)
    assert z.dtype == np.float32
    assert abs(float(z.mean())) < 1e-5
    assert abs(float(z.std()) - 1) < 1e-5


def test_weights_path_rejects_bad_hash(tmp_path, monkeypatch):
    name = dosma_unet.WEIGHTS_URL.rsplit("/", 1)[1]
    bad = tmp_path / name
    with open(bad, "wb") as f:
        f.truncate(dosma_unet.WEIGHTS_SIZE)  # right size, wrong bytes
    monkeypatch.setattr(dosma_unet.urllib.request, "urlopen",
                        lambda *a, **k: pytest.fail("must not download when the file is already there"))
    with pytest.raises(ValueError, match="sha256"):
        dosma_unet.weights_path(tmp_path)
    assert not bad.exists()  # not left behind looking valid


def test_weights_path_checks_a_download(tmp_path, monkeypatch):
    import io

    monkeypatch.setattr(dosma_unet.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"x" * 10))
    with pytest.raises(ValueError, match="size"):
        dosma_unet.weights_path(tmp_path)
    assert list(tmp_path.iterdir()) == []  # the .part file is removed too


def _cached_weights():
    p = Path("~/.cache/anatomy-atlas/dosma").expanduser() / dosma_unet.WEIGHTS_URL.rsplit("/", 1)[1]
    return p if p.exists() and p.stat().st_size == dosma_unet.WEIGHTS_SIZE else None


@pytest.mark.skipif(not (AUTOSEG_PY.exists() and _cached_weights() and (CAND / "oaizib_036_0000.nii.gz").exists()),
                    reason="needs venv-autoseg, cached DOSMA weights and OAIZIB-CM subject 036")
def test_dosma_real_dice(tmp_path):
    out = tmp_path / "pred.nii.gz"
    subprocess.run([str(AUTOSEG_PY), str(ROOT / "tools" / "autoseg" / "dosma_unet.py"),
                    str(CAND / "oaizib_036_0000.nii.gz"), str(out)], check=True, capture_output=True)
    pred = np.asanyarray(nib.load(out).dataobj)
    truth = np.asanyarray(nib.load(CAND / "oaizib_036.nii.gz").dataobj)
    assert pred.dtype == np.uint8 and pred.shape == truth.shape
    a, b = pred == 1, truth == 2  # femoral cartilage
    dice = 2 * (a & b).sum() / (a.sum() + b.sum())
    assert dice >= 0.70, dice
