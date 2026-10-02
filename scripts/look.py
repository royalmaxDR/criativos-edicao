# -*- coding: utf-8 -*-
"""Cor: LUTs 3D (.cube), tratamento do b-roll e acabamento (vinheta, aberracao cromatica, contraste, grao)."""
import os
import cv2
import numpy as np


def load_cube(path):
    """Le um arquivo .cube (LUT 3D). Devolve tabela float32 [B, G, R, 3(RGB)] em 0..1."""
    size = None; rows = []; lo = [0.0, 0.0, 0.0]; hi = [1.0, 1.0, 1.0]
    with open(path, encoding="utf-8", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            up = ln.upper()
            if up.startswith("LUT_3D_SIZE"):
                size = int(ln.split()[-1]); continue
            if up.startswith("DOMAIN_MIN"):
                lo = [float(v) for v in ln.split()[1:4]]; continue
            if up.startswith("DOMAIN_MAX"):
                hi = [float(v) for v in ln.split()[1:4]]; continue
            if ln[0].isdigit() or ln[0] in "-.":
                p = ln.split()
                if len(p) >= 3:
                    rows.append((float(p[0]), float(p[1]), float(p[2])))
    if not size or len(rows) != size ** 3:
        raise ValueError(f"LUT invalida ou nao 3D: {path} (size={size}, linhas={len(rows)})")
    t = np.asarray(rows, np.float32).reshape(size, size, size, 3)        # eixo 0 = B, 1 = G, 2 = R (R varia mais rapido)
    lo, hi = np.float32(lo), np.float32(hi)
    return (t - lo) / np.maximum(hi - lo, 1e-6)


class Lut:
    """Aplica a LUT como 'diferenca em relacao a identidade' numa grade 64^3: rapido e sem faixas (banding)."""
    N = 64

    def __init__(self, path, strength=1.0):
        cube = load_cube(path); n = cube.shape[0]; N = self.N
        g = np.linspace(0, n - 1, N, dtype=np.float32)
        i0 = np.clip(np.floor(g).astype(int), 0, n - 2); f = g - i0
        t = cube
        for ax in range(3):                                              # interpolacao linear eixo a eixo -> grade N^3
            a = np.take(t, i0, axis=ax); b = np.take(t, i0 + 1, axis=ax)
            sh = [1, 1, 1, 1]; sh[ax] = N
            t = a + (b - a) * f.reshape(sh)
        grid = np.linspace(0, 1, N, dtype=np.float32)
        ident = np.stack(np.meshgrid(grid, grid, grid, indexing="ij")[::-1], -1)   # [B,G,R] -> (r,g,b)
        delta_rgb = (t - ident) * 255.0 * strength
        self.delta = np.ascontiguousarray(delta_rgb[..., ::-1]).astype(np.float32)  # saida em BGR
        self.name = os.path.basename(path)

    def apply(self, img):
        q = np.clip(img * ((self.N - 1) / 255.0) + 0.5, 0, self.N - 1).astype(np.uint8)
        return img + self.delta[q[..., 0], q[..., 1], q[..., 2]]


BROLL_GRADES = {
    # sat: quanto da cor original fica; tint: cor (BGR) somada a partir do cinza; gain/lift: brilho
    "frio": dict(sat=0.62, tint=[0.30, 0.36, 0.42], gain=1.05, lift=-6),          # o do criativo de referencia (azulado, dessaturado)
    "quente": dict(sat=0.70, tint=[0.20, 0.30, 0.40], gain=1.04, lift=-4),
    "pb": dict(sat=0.0, tint=[1.0, 1.0, 1.0], gain=1.08, lift=-8),
    "none": None,
}


def grade_broll(crop, grade):
    if isinstance(grade, str):
        grade = BROLL_GRADES.get(grade, BROLL_GRADES["frio"])
    if not grade:
        return crop
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)[..., None]
    return np.clip((crop * grade["sat"] + g * np.array(grade["tint"], np.float32)) * grade["gain"] + grade["lift"], 0, 255)


def finish(img, c, look, nrng):
    """Acabamento global depois dos efeitos: aberracao cromatica leve, contraste, grao."""
    ca = look.get("chroma", 2)
    if ca:
        img = c.chroma(img, ca)
    img = (img - look.get("lift", 12)) * look.get("contrast", 1.07)
    gr = look.get("grain", 3.2)
    if gr:
        H, W = c.H, c.W
        img = img + nrng.randn(H // 2 + 1, W // 2 + 1, 1).astype(np.float32).repeat(2, 0).repeat(2, 1)[:H, :W] * gr
    return img
