# SPDX-License-Identifier: GPL-3.0-or-later
# The network in _build() is adapted from DOSMA (https://github.com/ad12/DOSMA,
# dosma/models/oaiunet2d.py, IWOAIOAIUnet2D), which is GPL-3.0; this file carries that licence.
"""Run DOSMA's iwoai-2019-t6-normalized knee U-Net on one NIfTI, without installing DOSMA.

    venv-autoseg/bin/python tools/autoseg/dosma_unet.py <in.nii.gz> <out.nii.gz>

Writes uint8 on the input grid: 1 femoral cartilage, 2 tibial cartilage, 3 patellar cartilage,
4 menisci. DOSMA's own package breaks on NumPy 2, so the U-Net is rebuilt here with tf_keras
(Keras 2 API, which the Keras 2.1.6 weights file needs). The weights download once to
~/.cache/anatomy-atlas/dosma/ and are checked against a pinned sha256. TensorFlow is imported
only inside predict(), so the orientation and download helpers run in the main venv.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import nibabel as nib
import numpy as np

WEIGHTS_URL = ("https://huggingface.co/arjundd/dosma-models/resolve/main/iwoai-2019-t6-normalized/"
               "iwoai-2019-unet2d-normalized_fc-tc-pc-men_weights.h5")
WEIGHTS_SHA256 = "a175bf63f22c9c2308a0fc7d0fdb8b5ecf6cd2f875dde1de8f385dc4e0e91fd1"
WEIGHTS_SIZE = 138536872
CACHE = Path("~/.cache/anatomy-atlas/dosma")

# The model sees sagittal slices with rows superior → inferior and columns anterior → posterior;
# a flipped input breaks it. As a nibabel orientation: axes (S reversed, A reversed, R).
SAGITTAL = np.array([[2, -1], [1, -1], [0, 1]])


def _check(path: Path) -> None:
    """Raise ValueError (and delete the file) unless it is the pinned weights file."""
    size = path.stat().st_size
    if size != WEIGHTS_SIZE:
        path.unlink()
        raise ValueError(f"{path.name}: size {size} bytes, expected {WEIGHTS_SIZE}; deleted it")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    if h.hexdigest() != WEIGHTS_SHA256:
        path.unlink()
        raise ValueError(f"{path.name}: sha256 {h.hexdigest()} does not match the pinned "
                         f"{WEIGHTS_SHA256}; deleted it")


def weights_path(cache: Path = CACHE) -> Path:
    """The checked weights file in `cache`, downloading it first if it isn't there."""
    cache = Path(cache).expanduser()
    path = cache / WEIGHTS_URL.rsplit("/", 1)[1]
    if path.exists():
        _check(path)
        return path
    cache.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    print(f"downloading DOSMA weights ({WEIGHTS_SIZE / 1e6:.0f} MB) to {cache}", file=sys.stderr)
    try:
        with urllib.request.urlopen(WEIGHTS_URL, timeout=60) as r, open(part, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        _check(part)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    part.rename(path)
    return path


def to_model(arr: np.ndarray, affine: np.ndarray) -> np.ndarray:
    """arr → (slices left → right, rows superior → inferior, columns anterior → posterior)."""
    t = nib.orientations.ornt_transform(nib.orientations.io_orientation(affine), SAGITTAL)
    return np.ascontiguousarray(np.transpose(nib.orientations.apply_orientation(arr, t), (2, 0, 1)))


def from_model(arr_model: np.ndarray, affine: np.ndarray) -> np.ndarray:
    """Inverse of to_model: back to the input array's axes."""
    t = nib.orientations.ornt_transform(SAGITTAL, nib.orientations.io_orientation(affine))
    return np.ascontiguousarray(nib.orientations.apply_orientation(np.transpose(arr_model, (1, 2, 0)), t))


def normalise(x: np.ndarray) -> np.ndarray:
    """Whole-volume (x - mean) / std, as DOSMA does for its "-normalized" models."""
    x = np.asarray(x, np.float64)
    return ((x - x.mean()) / x.std()).astype(np.float32)


def _build(input_shape):
    import tf_keras as keras
    from tf_keras.layers import BatchNormalization, Concatenate, Conv2D, Conv2DTranspose, Dropout, Input, MaxPooling2D

    nfeatures = [2 ** f * 32 for f in range(6)]  # 32 … 1024
    inputs = Input(input_shape)
    skips, x = [], inputs
    for d, n in enumerate(nfeatures):
        x = Conv2D(n, (3, 3), padding="same", activation="relu")(x)
        x = Conv2D(n, (3, 3), padding="same", activation="relu")(x)
        x = BatchNormalization(axis=-1, momentum=0.95, epsilon=0.001)(x)
        x = Dropout(rate=0.0)(x)
        skips.append(x)
        if d < len(nfeatures) - 1:
            x = MaxPooling2D(pool_size=(2, 2) if x.shape[1] % 2 == 0 else (3, 3))(x)
    for d in range(len(nfeatures) - 2, -1, -1):
        stride = (2, 2) if skips[d].shape[1] % 2 == 0 else (3, 3)
        x = Concatenate(axis=3)([Conv2DTranspose(nfeatures[d], (3, 3), padding="same", strides=stride)(x), skips[d]])
        x = Conv2D(nfeatures[d], (3, 3), padding="same", activation="relu")(x)
        x = Conv2D(nfeatures[d], (3, 3), padding="same", activation="relu")(x)
        x = BatchNormalization(axis=-1, momentum=0.95, epsilon=0.001)(x)
        x = Dropout(rate=0.0)(x)
    out = Conv2D(4, (1, 1), padding="same", activation="sigmoid")(x)
    return keras.models.Model(inputs=[inputs], outputs=[out])


def predict(img: nib.Nifti1Image, weights: Path, batch_size: int = 16) -> np.ndarray:
    """uint8 label map on img's grid: 1 fc, 2 tc, 3 pc, 4 menisci (channels over 0.5; ties → higher)."""
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ["TF_USE_LEGACY_KERAS"] = "1"
    x = normalise(to_model(np.asanyarray(img.dataobj), img.affine))[..., None]
    model = _build(x.shape[1:])
    model.load_weights(str(weights))
    prob = model.predict(x, batch_size=batch_size, verbose=0)  # (slices, SI, AP, 4)
    over = prob > 0.5
    lab = np.where(over.any(-1), np.argmax(np.where(over, prob, 0), -1) + 1, 0).astype(np.uint8)
    return from_model(lab, img.affine)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path, help="knee NIfTI (sagittal DESS)")
    ap.add_argument("output", type=Path, help="label map to write (uint8, same grid)")
    args = ap.parse_args(argv)
    img = nib.load(str(args.input))
    t0 = time.time()
    lab = predict(img, weights_path())
    out = nib.Nifti1Image(lab, img.affine)
    out.header.set_intent("label")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    nib.save(out, str(args.output))
    counts = {c: int((lab == v).sum()) for v, c in enumerate(["fc", "tc", "pc", "men"], 1)}
    print(f"DOSMA: {counts} in {time.time() - t0:.0f} s", file=sys.stderr)


if __name__ == "__main__":
    main()
