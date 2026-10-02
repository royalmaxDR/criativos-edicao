# -*- coding: utf-8 -*-
"""Gera LUTs 3D (.cube, 33^3) proprias em luts/ - sem licenca de terceiros.
Uso: python scripts/make_luts.py
Qualquer .cube de outra origem (DaVinci, Premiere, pacotes gratuitos) tambem funciona: basta salvar em luts/."""
import os
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "luts")
N = 33


def luma(c):
    return (c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722)[..., None]


def sat(c, s):
    y = luma(c); return y + (c - y) * s


def curve(c, contrast=1.0, pivot=0.45, lift=0.0, gamma=1.0):
    c = np.clip((c - pivot) * contrast + pivot + lift, 0, 1)
    return c ** gamma


def split_tone(c, shadows, highlights, amount):
    y = luma(c)
    return c + (np.float32(shadows) * (1 - y) ** 2 + np.float32(highlights) * y ** 2) * amount


LOOKS = {
    # sombras azul-esverdeadas, pele/alta luz quente - o "cinema" classico
    "teal_orange": lambda c: split_tone(sat(curve(c, 1.12), 1.08), [-0.06, 0.02, 0.07], [0.07, 0.02, -0.07], 1.0),
    # frio, dessaturado, contraste alto - misterio / revelacao (proximo do criativo de referencia)
    "frio_misterio": lambda c: split_tone(sat(curve(c, 1.18, lift=-0.015), 0.72), [-0.03, 0.0, 0.06], [-0.01, 0.0, 0.03], 1.0),
    # quente, pretos levantados - nostalgia / depoimento
    "quente_filme": lambda c: split_tone(sat(curve(c, 0.94, lift=0.03), 0.92), [0.03, 0.01, -0.02], [0.06, 0.03, -0.05], 1.0),
    # quase preto e branco, contraste forte - noticia / denuncia
    "noir": lambda c: sat(curve(c, 1.30, lift=-0.02), 0.12),
    # sepia de documento antigo - historico / arqueologia
    "sepia_antigo": lambda c: curve(luma(c) * np.float32([1.07, 0.95, 0.78]) * 0.85 + c * 0.15, 1.06),
    # bleach bypass: pouco croma, muito contraste, alta luz estourada
    "bleach": lambda c: sat(curve(c, 1.35, gamma=0.95), 0.45),
}


def write(name, fn):
    g = np.linspace(0, 1, N, dtype=np.float32)
    b, gg, r = np.meshgrid(g, g, g, indexing="ij")                     # R varia mais rapido na ordem do .cube
    rgb = np.stack([r, gg, b], -1)
    out = np.clip(fn(rgb), 0, 1).reshape(-1, 3)
    p = os.path.join(OUT, name + ".cube")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f'TITLE "{name}"\nLUT_3D_SIZE {N}\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n')
        f.write("\n".join(f"{a:.6f} {b_:.6f} {c_:.6f}" for a, b_, c_ in out)); f.write("\n")
    return p


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for k, fn in LOOKS.items():
        print("lut:", write(k, fn))
