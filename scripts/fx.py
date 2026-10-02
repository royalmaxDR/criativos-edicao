# -*- coding: utf-8 -*-
"""Registro de efeitos de transicao (plugavel).

Um efeito e uma funcao  fn(img, k, c) -> img
  img : frame float32 BGR (H, W, 3), 0..255, ja composto (avatar/b-roll + vinheta)
  k   : frame relativo ao corte, em passos de 1/30 s (k=0 e o primeiro frame depois do corte)
  c   : Ctx (medidas, mapas prontos, gerador aleatorio do frame, dt em segundos, layout atual)

Registre com @effect(...). Arquivos .py dentro de plugins/ sao carregados sozinhos (veja plugins/README.md).
"""
import glob, importlib.util, math, os, random
import cv2
import numpy as np

REG = {}


def effect(name, pre=0.0, post=0.0, focus=None, sfx=(), desc=""):
    """pre/post: janela em segundos em volta do corte em que fn e chamada.
    focus: (inicio_s, fim_s, sigma, potencia) -> desfoque que 'assenta' depois do corte (rack focus).
    sfx: lista de (som, atraso_s, ganho[, parametros]) - sons: whoosh, boom, crackle, riser, hit."""
    def deco(fn):
        REG[name] = dict(fn=fn, pre=pre, post=post, focus=focus, sfx=tuple(sfx), desc=desc)
        return fn
    return deco


class Ctx:
    """Mapas e utilitarios calculados uma vez por render."""

    def __init__(self, W, H, intensity=1.0):
        self.W, self.H, self.S = W, H, H / 1920.0
        self.intensity = intensity
        self.yy, self.xx = np.mgrid[0:H, 0:W].astype(np.float32)
        yy, xx = self.yy, self.xx
        rr = ((xx - W / 2) / (W * 0.60)) ** 2 + ((yy - H / 2) / (H * 0.60)) ** 2
        self.vig_shape = np.clip(rr - 0.38, 0, 1)[..., None]
        self.VIG = 1 - 0.72 * self.vig_shape
        hue = ((xx * 0.35 + yy * 0.9) / H * 540) % 180
        full = np.full_like(hue, 255)
        self.RAIN = cv2.cvtColor(np.dstack([hue, full, full]).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
        self.RAINV = cv2.cvtColor(np.dstack([(yy / H * 400) % 180, np.full_like(hue, 230), full]).astype(np.uint8),
                                  cv2.COLOR_HSV2BGR).astype(np.float32)
        n = self.odd(71)
        self.KDIAG = np.eye(n, dtype=np.float32) / n
        self.rng = random.Random(0)
        self.nrng = np.random.RandomState(0)
        self.dt = 0.0
        self.layout = "full"
        self.seam = 0.5

    def px(self, v):
        return max(1, int(round(v * self.S)))

    def odd(self, v):
        v = self.px(v)
        return v if v % 2 else v + 1

    def warp(self, img, scale, ang, cy=0.36):
        M = cv2.getRotationMatrix2D((self.W / 2, self.H * cy), ang, scale)
        return cv2.warpAffine(img, M, (self.W, self.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def shift(self, img, dx, dy):
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(img, M, (self.W, self.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    def chroma(self, img, d, vertical=False):
        d = int(round(d * self.S))
        if d == 0:
            return img
        o = img.copy(); ax = 0 if vertical else 1
        o[..., 2] = np.roll(img[..., 2], d, ax); o[..., 0] = np.roll(img[..., 0], -d, ax)
        return o

    def blur(self, img, sigma):
        return cv2.GaussianBlur(img, (0, 0), max(0.1, sigma * self.S))

    @staticmethod
    def gray(img):
        return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)


# ------------------------------------------------------------------ presets extraidos do criativo de referencia
@effect("A", pre=0.11, post=0.15, focus=(0.16, 0.55, 7, 2), sfx=(("whoosh", -0.12, 0.20), ("boom", 0.05, 0.42)),
        desc="prisma + zoom-blur: borrao vertical com separacao de cor, 1 frame limpo, zoom 1.9x girado que assenta com foco")
def fx_prisma(img, k, c):
    g = c.gray
    if k == -3:
        return c.blur(img, 4)
    if k in (-2, -1):
        o = cv2.blur(img, (c.odd(9), c.odd(141))); o = c.chroma(o, 34, True)
        return np.clip(o * 0.92 + c.RAINV * 0.20 * (cv2.blur(g(img), (c.odd(9), c.odd(141)))[..., None] / 255 + 0.15), 0, 255)
    if k == 1:
        o = c.chroma(cv2.filter2D(c.warp(img, 1.5, 6), -1, c.KDIAG), 46)
        return np.clip(o * 0.9 + c.RAIN * 0.22 * (g(o)[..., None] / 255 + 0.35), 0, 255)
    if k == 2:
        return c.chroma(c.blur(c.warp(img, 1.9, -5), 13), 16)
    if k == 3:
        return c.chroma(c.blur(c.warp(img, 1.28, -2), 7), 9)
    if k == 4:
        return c.chroma(c.blur(c.warp(img, 1.09, 0), 3.5), 4)
    return img


@effect("B", pre=0.04, post=0.18, focus=(0.2, 0.45, 4, 2), sfx=(("crackle", -0.02, 0.16), ("boom", 0.02, 0.34, dict(d=0.7, f0=46))),
        desc="estrobo solarizado: duotone roxo, negativo verde com contorno, estouro quente, negativo P&B")
def fx_estrobo(img, k, c):
    g = c.gray(img); vig2 = c.VIG[..., 0] ** 2
    if k == -1:
        return c.chroma(c.blur(img, 6) * 1.15, 10) + np.array([40, 0, 25], np.float32)
    if k == 0:
        v = np.clip(np.abs(g - 110) * 2.3 - 30, 0, 255) * vig2
        return np.dstack([v, v * 0.42, v * 0.80])
    if k in (1, 2):
        gw = c.gray(c.warp(img, 1.55, -9)); v = np.clip(gw * 1.9 - 150, 0, 255)
        e = cv2.GaussianBlur(cv2.dilate(cv2.Canny(gw.astype(np.uint8), 50, 120), np.ones((3, 3), np.uint8)).astype(np.float32), (0, 0), 1.5)
        v = np.clip(v * 0.8 + e * 1.1, 0, 255) * vig2
        return np.dstack([v * 0.66, v, v * 0.62])
    if k == 3:
        return np.clip(c.warp(img, 0.94, 0) * 1.75 + np.array([10, 45, 70], np.float32), 0, 255)
    if k == 4:
        v = np.clip((255 - g) * 1.6 - 80, 0, 255); return np.dstack([v, v, v])
    if k == 5:
        v = np.clip(g * 2.0 + 50, 0, 255); return np.dstack([v, v, v])
    return img


@effect("C", pre=0.08, post=0.12, focus=(0.13, 0.5, 5, 2), sfx=(("crackle", -0.05, 0.20, dict(d=0.3)), ("boom", 0.0, 0.40, dict(d=0.8))),
        desc="glitch RGB / datamosh: fatias deslocadas, separacao de cor, blocos coloridos e ruido")
def fx_glitch(img, k, c):
    it = {-2: 0.25, -1: 0.45, 0: 1.0, 1: 1.0, 2: 0.8, 3: 0.35}.get(k)
    if it is None:
        return img
    H, W, r = c.H, c.W, c.rng
    o = c.chroma(img, int(60 * it) + 6)
    for _ in range(int(14 * it) + 3):
        y = r.randint(0, H - c.px(120)); h = r.randint(c.px(14), c.px(120)); o[y:y + h] = np.roll(o[y:y + h], r.randint(-c.px(240), c.px(240)), 1)
    for _ in range(int(9 * it)):
        y = r.randint(0, H - c.px(80)); x = r.randint(0, max(1, W - c.px(420)))
        o[y:y + r.randint(c.px(10), c.px(60)), x:x + r.randint(c.px(160), c.px(420))] = [r.randint(0, 255) for _ in range(3)]
    noise = c.nrng.randn(H // 4 + 1, W // 4 + 1, 1).astype(np.float32).repeat(4, 0).repeat(4, 1)[:H, :W]
    return np.clip(o * (1 - 0.12 * it) + c.RAIN * 0.14 * it + noise * 14 * it, 0, 255)


@effect("D", pre=0.04, post=0.56, sfx=(("whoosh", -0.08, 0.14, dict(d=0.3)),),
        desc="rasgo horizontal: barras brancas deslocando faixas e varredura de luz quente sobre o b-roll")
def fx_rasgo(img, k, c):
    H, W, r = c.H, c.W, c.rng
    if -1 <= k <= 3:
        img = img.copy()
        for _ in range(3):
            y = r.randint(int(H * 0.25), int(H * 0.6)); h = r.randint(c.px(50), c.px(170))
            img[y:y + h] = np.roll(img[y:y + h], r.randint(-c.px(150), c.px(150)), 1)
            img[y:y + c.px(7)] = 255
            a = max(0, y - c.px(14)); img[a:y] = np.clip(img[a:y] * 1.6 + 40, 0, 255)
    dt = c.dt
    if 0.05 < dt < 0.55:
        top = H * (c.seam if c.layout == "split" else 0.0)
        band = np.exp(-((c.xx - W * (-0.2 + 1.5 * (dt - 0.05) / 0.5)) / (120.0 * c.S)) ** 2) * np.clip((c.yy - top) / (80.0 * c.S), 0, 1)
        img = img + band[..., None] * np.array([150, 200, 235], np.float32) * (1 - (dt - 0.05) / 0.5)
    return img


@effect("bsw", sfx=(("whoosh", -0.08, 0.07, dict(d=0.25)),),
        desc="troca de b-roll dentro da tela dividida (zoom-blur de 0,2 s feito pelo layout; aqui so o som)")
def fx_bsw(img, k, c):
    return img


# ------------------------------------------------------------------ efeitos extras (alem do criativo de referencia)
@effect("flash", pre=0.04, post=0.2, sfx=(("hit", 0.0, 0.30),), desc="clarao branco que decai em 5 frames")
def fx_flash(img, k, c):
    a = {-1: 0.35, 0: 1.0, 1: 0.7, 2: 0.45, 3: 0.25, 4: 0.12, 5: 0.05}.get(k, 0)
    return img + (255 - img) * a if a else img


@effect("dip", pre=0.14, post=0.17, desc="mergulho no preto (fade out 4 frames, fade in 5)")
def fx_dip(img, k, c):
    a = {-4: 0.75, -3: 0.5, -2: 0.25, -1: 0.05, 0: 0.0, 1: 0.2, 2: 0.45, 3: 0.7, 4: 0.9}.get(k, 1.0)
    return img * a


@effect("whip", pre=0.11, post=0.14, focus=(0.1, 0.3, 3, 2), sfx=(("whoosh", -0.14, 0.18, dict(d=0.32)),),
        desc="whip pan: chicote lateral com borrao de movimento horizontal")
def fx_whip(img, k, c):
    amt = {-3: 0.25, -2: 0.6, -1: 1.0, 0: 1.0, 1: 0.6, 2: 0.3, 3: 0.12}.get(k)
    if amt is None:
        return img
    kw = c.odd(260 * amt)
    o = cv2.blur(img, (kw, 1))
    return c.shift(o, (-1 if k < 0 else 1) * c.W * 0.22 * amt, 0)      # sai para a esquerda, entra pela direita


@effect("punch", post=0.22, sfx=(("hit", 0.0, 0.22),), desc="soco de zoom: entra 16% maior e assenta em 6 frames")
def fx_punch(img, k, c):
    if not 0 <= k <= 6:
        return img
    z = 1 + 0.16 * math.exp(-k / 1.6)
    o = c.warp(img, z, 0, cy=0.42)
    return c.blur(o, 5 * math.exp(-k / 1.2)) if k < 3 else o


@effect("shake", post=0.3, sfx=(("boom", 0.0, 0.36, dict(d=0.6, f0=48)),), desc="tremor de impacto que decai em 9 frames")
def fx_shake(img, k, c):
    if not 0 <= k <= 8:
        return img
    a = c.px(46) * math.exp(-k / 2.6)
    return c.chroma(c.shift(img, c.rng.uniform(-a, a), c.rng.uniform(-a, a)), 10 * math.exp(-k / 2.0))


@effect("leak", pre=0.2, post=0.5, desc="vazamento de luz quente (light leak) atravessando o quadro")
def fx_leak(img, k, c):
    p = (c.dt + 0.2) / 0.7
    if not 0 <= p <= 1:
        return img
    cx = c.W * (1.15 - 1.3 * p); cy = c.H * 0.3
    blob = np.exp(-(((c.xx - cx) / (c.W * 0.55)) ** 2 + ((c.yy - cy) / (c.H * 0.6)) ** 2))[..., None]
    return img + blob * np.array([60, 140, 255], np.float32) * 0.9 * math.sin(math.pi * p)


@effect("vhs", pre=0.07, post=0.2, sfx=(("crackle", -0.05, 0.14, dict(d=0.25)),), desc="VHS: linhas, salto vertical e cor deslocada")
def fx_vhs(img, k, c):
    it = {-2: 0.4, -1: 0.8, 0: 1.0, 1: 1.0, 2: 0.8, 3: 0.6, 4: 0.4, 5: 0.2}.get(k)
    if it is None:
        return img
    o = c.chroma(np.roll(img, int(c.rng.uniform(-1, 1) * c.px(90) * it), 0), 18 * it)
    lines = (0.82 + 0.18 * np.sin(c.yy * math.pi / max(2, c.px(4))))[..., None]
    y = c.rng.randint(0, c.H - c.px(160)); h = c.px(c.rng.randint(40, 150))
    o[y:y + h] = np.roll(o[y:y + h], c.px(c.rng.randint(-120, 120)), 1)
    g = c.gray(o)[..., None]
    return np.clip((o * 0.7 + g * 0.3) * (1 - it + it * lines) + c.nrng.randn(c.H, 1, 1).astype(np.float32) * 10 * it, 0, 255)


# ------------------------------------------------------------------ plugins
def load_plugins(folder=None):
    folder = folder or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins")
    for p in sorted(glob.glob(os.path.join(folder, "*.py"))):
        if os.path.basename(p).startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location("plugin_" + os.path.splitext(os.path.basename(p))[0], p)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)


def apply_all(img, t, fx_list, c, fps):
    """Aplica todos os efeitos ativos no instante t. Devolve (img, sigma_de_foco)."""
    sig = 0.0
    for ft, kind in fx_list:
        e = REG.get(kind)
        if e is None:
            continue
        dt = t - ft
        f = e["focus"]
        hi = max(e["post"], f[1] if f else 0)
        if dt < -e["pre"] - 0.02 or dt > hi + 0.02:
            continue
        c.dt = dt
        if -e["pre"] - 0.02 <= dt <= e["post"] + 0.02:
            img = e["fn"](img, int(round(dt * 30)), c)
        if f and f[0] < dt < f[1]:
            sig = max(sig, f[2] * c.intensity * (1 - (dt - f[0]) / (f[1] - f[0])) ** f[3])
    return img, sig
