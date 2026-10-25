"""Make the Veil look's textures (app/art/), all generated here from noise:

    python3 tools/art/make_art.py

fog.jpg   the drifting fog behind every screen: near black, a pale ground mist low
          down, thin wisps and a dark edge (portrait, aspect-filled on any phone)
fog_l.jpg the same fog for a landscape box (the info pop-ups)
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(os.path.dirname(HERE)), "app", "art")


def _smooth(t):
    return t * t * (3 - 2 * t)


def value_noise(w: int, h: int, cell: float, rng: np.random.Generator) -> np.ndarray:
    """Smooth value noise in 0..1 with features about ``cell`` pixels wide (tiles in x)."""
    gw, gh = int(np.ceil(w / cell)) + 2, int(np.ceil(h / cell)) + 2
    grid = rng.random((gh, gw))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    gx, gy = xs / cell, ys / cell
    x0, y0 = np.floor(gx).astype(int), np.floor(gy).astype(int)
    fx, fy = _smooth(gx - x0), _smooth(gy - y0)
    a = grid[y0, x0]
    b = grid[y0, x0 + 1]
    c = grid[y0 + 1, x0]
    d = grid[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(w: int, h: int, cell: float, octaves: int, rng: np.random.Generator, gain: float = 0.5) -> np.ndarray:
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    for _ in range(octaves):
        out += amp * value_noise(w, h, cell, rng)
        total += amp
        amp *= gain
        cell /= 2.0
    return out / total


def warp(field: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    """``field`` sampled (bilinear) at (x + dx, y + dy): the fog drawn out along the flow."""
    h, w = field.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    sx = np.clip(xs + dx, 0, w - 1.001)
    sy = np.clip(ys + dy, 0, h - 1.001)
    x0, y0 = np.floor(sx).astype(int), np.floor(sy).astype(int)
    fx, fy = sx - x0, sy - y0
    return ((field[y0, x0] * (1 - fx) + field[y0, x0 + 1] * fx) * (1 - fy)
            + (field[y0 + 1, x0] * (1 - fx) + field[y0 + 1, x0 + 1] * fx) * fy)


def ridged(field: np.ndarray) -> np.ndarray:
    """Thin bright ridges where the field crosses its middle: the strands of a wisp."""
    return (1.0 - np.abs(field * 2.0 - 1.0)) ** 6


def fog(w: int, h: int, seed: int, mist_at: float = 0.8, mist: float = 1.0) -> np.ndarray:
    """Luminance 0..1: drifting smoke, a pale ground mist round ``mist_at`` (0 top, 1
    bottom) and a dark edge. Mostly well below 0.35, so pale type stays readable on it."""
    rng = np.random.default_rng(seed)
    flow_x = (fbm(w, h, w / 1.2, 3, rng) - 0.5) * w * 0.9
    flow_y = (fbm(w, h, w / 1.2, 3, rng) - 0.5) * w * 0.25
    smoke = warp(fbm(w, h, w / 2.0, 6, rng), flow_x, flow_y)
    strands = warp(fbm(w, h, w / 1.4, 5, rng), flow_x * 1.3, flow_y * 0.5)
    smoke = np.clip((smoke - 0.38) * 2.6, 0, 1) ** 1.4
    wisps = ridged(strands) * (0.35 + 0.65 * smoke)
    ys = np.linspace(0, 1, h)[:, None]
    xs = np.linspace(-1, 1, w)[None, :]
    ground = np.exp(-((ys - mist_at) / 0.16) ** 2) * mist          # the mist lying low
    lum = 0.03 + 0.2 * smoke + 0.16 * wisps + 0.14 * ground * (0.45 + 0.9 * smoke)
    vignette = 1.0 - 0.6 * np.clip(xs ** 2 * 0.75 + (ys * 2 - 1) ** 2 * 0.5, 0, 1)
    return np.clip(lum * vignette, 0, 1)


def grain(img: np.ndarray, seed: int, amount: float = 0.012) -> np.ndarray:
    rng = np.random.default_rng(seed + 99)
    return np.clip(img + rng.normal(0, amount, img.shape), 0, 1)


def save(arr: np.ndarray, name: str, quality: int = 80) -> str:
    os.makedirs(ART, exist_ok=True)
    path = os.path.join(ART, name)
    Image.fromarray((arr * 255).astype(np.uint8), "L").save(path, quality=quality, optimize=True)
    return path


def main(argv=None) -> int:
    paths = [
        save(grain(fog(750, 1624, 7), 7), "fog.jpg"),
        save(grain(fog(900, 600, 11, mist_at=0.9, mist=0.7), 11), "fog_l.jpg"),
    ]
    for p in paths:
        print("%s  %.0f KB" % (p, os.path.getsize(p) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
