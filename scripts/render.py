# -*- coding: utf-8 -*-
"""Renderiza um criativo a partir de um plano (plan.json) no estilo de edicao aprendido.

Uso:
  python scripts/render.py plan.json                  # video inteiro (com e sem legenda, conforme o plano)
  python scripts/render.py plan.json --preview 0-12   # so um trecho, para conferir antes de gastar tempo
  python scripts/render.py plan.json --jobs 4 --encoder nvenc

O formato do plano esta em docs/PLANO.md. O render e dividido em pedacos paralelos (cada um um processo) e depois unido.
"""
import argparse, json, math, os, shutil, subprocess, sys, tempfile, time
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fx as FXM            # noqa: E402
import look as LOOK         # noqa: E402
import audio_engine as AUD  # noqa: E402

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi")
DEFAULTS = dict(
    name="CRIATIVO", size=[1080, 1920], fps=30, avatar=None, avatar_face=None, voice=None, words=None, speech_end=None,
    segments=[], fx=[], banners=[], fx_intensity=1.0, seed=21,
    captions=dict(mode="both", style="box", keywords=[], fix={}, max_chars=14, max_words=2, uppercase=True, size=74,
                  box_color=[200, 16, 24], key_color=[255, 214, 0], font=None, y_split=0.484, y_full=0.672),
    end_card=dict(dur=4.3, lines=[["CLIQUE ABAIXO", [255, 255, 255], 120], ["SAIBA MAIS", [40, 220, 70], 150]], chevrons=True),
    camera=dict(split_zoom=1.30, split_face_y=0.20, pan=0.035, pan_period=9.0, breath=0.012, overshoot=0.10, overshoot_tau=0.11,
                pull_out=0.05, push_in=0.035, anticipation=0.13, shake=1.6, diffusion=0.16),
    look=dict(lut=None, lut_strength=1.0, broll_grade="frio", vignette=0.72, chroma=2, contrast=1.07, lift=12, grain=3.2, ffmpeg_vf=None),
    audio=dict(bed="synth", bed_rms=0.036, bed_loop=None, sfx=True, sfx_gain=1.0, voice_gain=1.0),
)


def load_plan(path):
    plan = json.load(open(path, encoding="utf-8")); base = os.path.dirname(os.path.abspath(path))
    out = json.loads(json.dumps(DEFAULTS))
    for k, v in plan.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v

    def rp(p):
        if not p or not isinstance(p, str) or p.startswith("gen:") or p in ("WAVE", "synth", "none"):
            return p
        if os.path.isabs(p):
            return p
        for b in (base, ROOT):
            if os.path.exists(os.path.join(b, p)):
                return os.path.join(b, p)
        return os.path.join(base, p)

    for k in ("avatar", "voice", "words"):
        out[k] = rp(out[k])
    out["look"]["lut"] = rp(out["look"]["lut"]); out["captions"]["font"] = rp(out["captions"]["font"])
    if out["audio"]["bed"] not in ("synth", "none", None, False):
        out["audio"]["bed"] = rp(out["audio"]["bed"])
    for s in out["segments"]:
        if s.get("broll"):
            s["broll"] = rp(s["broll"])
    out["fx"] = [(float(a), str(b)) for a, b in out["fx"]]
    if not out["words"]:
        out["captions"]["mode"] = "off"
    out["_base"] = base
    return out


def media_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip())


def timeline(plan):
    se = plan["speech_end"] or (media_dur(plan["voice"]) if plan["voice"] else max(s["e"] for s in plan["segments"]))
    card = plan["end_card"]["dur"] if plan.get("end_card") else 0.0
    return float(se), float(card), float(se) + float(card)


def pick_encoder(pref="auto"):
    table = {"nvenc": ("h264_nvenc", ["-preset", "p5", "-cq", "17", "-b:v", "0"]),
             "videotoolbox": ("h264_videotoolbox", ["-q:v", "62"]),
             "x264": ("libx264", ["-preset", "medium", "-crf", "17"])}
    order = ["nvenc", "videotoolbox", "x264"] if pref == "auto" else [pref]
    for k in order:
        name, args = table[k]
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2", "-c:v", name, "-f", "null", "-"], capture_output=True)
        if r.returncode == 0:
            return k
    return "x264"


def enc_proc(out, W, H, fps, enc, vf):
    table = {"nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "17", "-b:v", "0"],
             "videotoolbox": ["-c:v", "h264_videotoolbox", "-q:v", "62"],
             "x264": ["-c:v", "libx264", "-preset", "medium", "-crf", "17"]}
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if vf:
        cmd += ["-vf", vf]
    return subprocess.Popen(cmd + table[enc] + ["-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)


# ====================================================================== legendas / textos
def load_font(path, size):
    cands = [path, os.path.join(ROOT, "fonts", "Anton-Regular.ttf"), "impact.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
             "/System/Library/Fonts/Supplemental/Impact.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for f in cands:
        if not f:
            continue
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


def build_captions(plan):
    cc = plan["captions"]
    if not plan["words"] or cc["mode"] == "off":
        return []
    words = json.load(open(plan["words"], encoding="utf-8")); fix = cc.get("fix") or {}; P = ",.!?;:"
    cur = []; groups = []
    for w in words:
        raw = w["w"].strip(); core = raw.strip(P); tail = raw[len(raw.rstrip(P)):]
        txt = (fix[core] + tail) if core in fix else raw
        if not txt:
            continue
        if cur and (len(" ".join(x[0] for x in cur)) + len(txt) > cc["max_chars"] or len(cur) >= cc["max_words"] or cur[-1][0][-1] in P):
            groups.append(cur); cur = []
        cur.append((txt, w["s"], w["e"]))
    if cur:
        groups.append(cur)
    caps = []
    for gi, g in enumerate(groups):
        end = groups[gi + 1][0][1] if gi + 1 < len(groups) else g[-1][2] + 0.3
        toks = [x[0].strip(P) for x in g]
        caps.append((g[0][1], min(end, g[-1][2] + 0.6), [t.upper() if cc["uppercase"] else t for t in toks]))
    return caps


class Text:
    def __init__(self, plan, W, H):
        self.W, self.H, self.S = W, H, H / 1920.0; cc = plan["captions"]; self.cc = cc
        self.f_cap = load_font(cc["font"], max(10, int(cc["size"] * self.S))); self.f_ban = load_font(cc["font"], max(10, int(44 * self.S)))
        self.keys = {k.lower() for k in cc["keywords"]}

    def caption(self, img, toks, y):
        d = ImageDraw.Draw(img); S = self.S; sp = int(18 * S); f = self.f_cap; cc = self.cc
        ws = [d.textbbox((0, 0), t, font=f)[2] for t in toks]; x = (self.W - sum(ws) - sp * (len(toks) - 1)) // 2
        hh = d.textbbox((0, 0), "ÁGjp", font=f)[3]
        keyi = next((i for i, t in enumerate(toks) if t.lower() in self.keys), len(toks) - 1)
        for i, t in enumerate(toks):
            fill = "white"
            if i == keyi and cc["style"] == "box":
                d.rectangle([x - int(12 * S), y - int(6 * S), x + ws[i] + int(12 * S), y + hh + int(8 * S)], fill=tuple(cc["box_color"]))
            elif i == keyi and cc["style"] == "color":
                fill = tuple(cc["key_color"])
            d.text((x, y), t, font=f, fill=fill, stroke_width=max(1, int(4 * S)), stroke_fill="black"); x += ws[i] + sp

    def banner(self, img, bn, t):
        d = ImageDraw.Draw(img); S = self.S; W = self.W; a = min(1, (t - bn["s"]) / 0.25); bh = int(84 * S)
        d.rectangle([0, 0, W, int(bh * a)], fill=tuple(bn.get("color", [18, 150, 40])))
        if a >= 1:
            tx = bn.get("text", "TOQUE NO BOTÃO ABAIXO"); tb = d.textbbox((0, 0), tx, font=self.f_ban); x = (W - tb[2]) // 2
            d.text((x, (bh - tb[3]) // 2 - int(4 * S)), tx, font=self.f_ban, fill="white")
            if bn.get("arrows", True):
                for cx in (x - int(46 * S), x + tb[2] + int(46 * S)):
                    y0 = int(bh * 0.24) + int(6 * S * math.sin(t * 7)); r = int(16 * S)
                    d.rectangle([cx - r // 3, y0, cx + r // 3, y0 + r], fill="white")
                    d.polygon([(cx - r, y0 + r), (cx + r, y0 + r), (cx, y0 + int(2.1 * r))], fill="white")

    def end_card(self, u, card):
        W, H, S = self.W, self.H, self.S; pil = Image.new("RGB", (W, H), "black"); d = ImageDraw.Draw(pil); a = min(1, u / 0.3); y = int(700 * S)
        for ln in card["lines"]:
            tx, col, sz = ln[0], ln[1], (ln[2] if len(ln) > 2 else 120); f = load_font(self.cc["font"], int(sz * S)); tb = d.textbbox((0, 0), tx, font=f)
            if tb[2] > W * 0.94:
                f = load_font(self.cc["font"], int(sz * S * W * 0.94 / tb[2])); tb = d.textbbox((0, 0), tx, font=f)
            d.text(((W - tb[2]) // 2, y + int(40 * S * (1 - a))), tx, font=f, fill=tuple(int(v * a) for v in col)); y += int(tb[3] * 1.12)
        if card.get("chevrons", True):
            y += int(90 * S)
            for k in range(3):
                ph = (u * 1.6 - k * 0.22) % 1.0; yb = y + int((k * 95 + 30 * ph) * S); al = int(255 * (0.35 + 0.65 * (1 - abs(ph - 0.5) * 2)))
                d.line([(W // 2 - int(120 * S), yb), (W // 2, yb + int(80 * S)), (W // 2 + int(120 * S), yb)], fill=(al, al, al), width=max(2, int(34 * S)), joint="curve")
        arr = np.asarray(pil)
        if u < 0.14:
            arr = np.clip(arr.astype(np.float32) + 255 * (1 - u / 0.14), 0, 255).astype(np.uint8)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


# ====================================================================== fontes de imagem
class Avatar:
    def __init__(self, path, W, H, face=None):
        self.W, self.H = W, H; self.cap = cv2.VideoCapture(path); self.fps = self.cap.get(5) or 25; self.n = int(self.cap.get(7))
        ok, f0 = self.cap.read()
        if not ok:
            raise SystemExit(f"nao consegui abrir o avatar: {path}")
        self.ah, self.aw = f0.shape[:2]; self.i = 0; self.fr = f0; self.fx, self.fy, self.fw = 0.5, 0.33, 0.40
        if face:
            self.fx, self.fy, self.fw = face
        else:
            model = os.path.join(ROOT, "models", "yunet.onnx")
            if os.path.exists(model):
                det = cv2.FaceDetectorYN.create(model, "", (self.aw, self.ah), 0.6, 0.3, 50); _, fs = det.detect(f0)
                if fs is not None and len(fs):
                    b = max(fs, key=lambda x: x[2] * x[3])
                    self.fx, self.fy, self.fw = float(b[0] + b[2] / 2) / self.aw, float(b[1] + b[3] / 2) / self.ah, float(b[2]) / self.aw
        self.cover = max(W / self.aw, H / self.ah)

    def frame(self, t):
        ai = min(int(t * self.fps), self.n - 1)
        while self.i < ai:
            if self.i + 1 < ai:
                self.cap.grab()
            else:
                ok, fr = self.cap.read()
                if ok:
                    self.fr = fr
            self.i += 1
        return self.fr

    def view(self, fr, zoom, cy_out, dx=0.0, dy=0.0):
        W, H = self.W, self.H; s = self.cover * zoom; iw, ih = max(W, int(self.aw * s)), max(H, int(self.ah * s))
        im = cv2.resize(fr, (iw, ih), interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA)      # ampliacao em cubico: menos borrado que linear
        cx = int(self.fx * iw + dx); cy = int(self.fy * ih + dy)
        x0 = min(max(cx - W // 2, 0), iw - W); y0 = min(max(cy - int(H * cy_out), 0), ih - H)
        return im[y0:y0 + H, x0:x0 + W].astype(np.float32)


class Broll:
    def __init__(self, W, grade):
        self.W = W; self.grade = grade; self.img = {}; self.vid = {}

    def wave(self, t, tw, th):
        S = th / 1120.0; im = np.zeros((th, tw, 3), np.float32); im[:] = (38, 14, 6); xs = np.arange(tw)
        for k in range(9):
            ph = t * (1.6 + 0.25 * k) + k * 0.7; amp = (150 - 12 * k) * S
            ys = th / 2 + amp * np.sin(xs / (160.0 * S) + ph) * np.sin(xs / (610.0 * S) + ph * 0.4 + k) * np.exp(-((xs - tw / 2) / (520.0 * S)) ** 2)
            pts = np.stack([xs, ys], 1).astype(np.int32).reshape(-1, 1, 2); cv2.polylines(im, [pts], False, (255, 190 - 12 * k, 60 + 10 * k), max(1, int(3 * S)), cv2.LINE_AA)
        return np.clip(im + cv2.GaussianBlur(im, (0, 0), 14 * S) * 1.4, 0, 255)

    def _video(self, path, tloc):
        v = self.vid.get(path)
        if v is None:
            cap = cv2.VideoCapture(path); v = self.vid[path] = dict(cap=cap, fps=cap.get(5) or 25, n=max(1, int(cap.get(7))), i=-1, fr=None)
        idx = int(tloc * v["fps"]) % v["n"]
        if idx != v["i"]:
            if idx != v["i"] + 1:
                v["cap"].set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, fr = v["cap"].read()
            if ok:
                v["fr"] = fr
            v["i"] = idx
        if v["fr"] is None:
            raise SystemExit(f"nao consegui ler o b-roll: {path}")
        return v["fr"]

    def get(self, path, p, kz, t, tloc, tw, th, kb=1, grade=None):
        if path in ("WAVE", "gen:wave"):
            return self.wave(t, tw, th)
        if path.lower().endswith(VIDEO_EXT):
            fr = self._video(path, tloc); bh, bw = fr.shape[:2]; s = max(tw / bw, th / bh) * 1.25
            im = cv2.resize(fr, (int(bw * s) + 1, int(bh * s) + 1), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        else:
            key = (path, tw, th)
            if key not in self.img:
                src = cv2.imread(path)
                if src is None:
                    raise SystemExit(f"nao consegui ler o b-roll: {path}")
                bh, bw = src.shape[:2]; s = max(tw / bw, th / bh) * 1.25
                self.img[key] = cv2.resize(src, (int(bw * s) + 1, int(bh * s) + 1), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
            im = self.img[key]
        bh, bw = im.shape[:2]; pp = p if kb >= 0 else 1 - p
        z = (1.0 + 0.12 * pp * (1 if kb else 0)) * kz; cw = min(bw, int(bw / (1.25 * z))); ch = min(int(cw * th / tw), bh)
        x0 = int((bw - cw) / 2 + (bw - cw) * 0.10 * (pp - 0.5)); y0 = int(max(0, (bh - ch) * (0.30 + 0.15 * pp)))
        crop = cv2.resize(im[y0:y0 + ch, x0:x0 + cw], (tw, th), interpolation=cv2.INTER_LINEAR).astype(np.float32)
        return LOOK.grade_broll(crop, self.grade if grade is None else grade)


def shot_class(seg, av):
    if seg.get("shot"):
        return "close" if seg["shot"] in ("close", "xclose") else seg["shot"]
    if "face_w" in seg:
        return "close" if seg["face_w"] >= 0.55 else ("wide" if seg["face_w"] < 0.47 else "medium")
    z = seg.get("zoom", 1.0)
    return "close" if z >= 1.3 else ("wide" if z < 1.1 else "medium")


def seg_zoom(seg, av, default=1.0):
    if "face_w" in seg and av is not None:
        return seg["face_w"] / max(av.fw * av.cover * av.aw / av.W, 1e-3)
    return seg.get("zoom", default)


# ====================================================================== render de um intervalo de frames
def render_range(plan, F0, F1, tmp, enc):
    W, H = plan["size"]; FPS = plan["fps"]; S = H / 1920.0; SE, CARD, TOTAL = timeline(plan); NF = int(TOTAL * FPS); F1 = min(F1, NF)
    cam, lk, seed = plan["camera"], plan["look"], plan["seed"]
    FXM.load_plugins()
    c = FXM.Ctx(W, H, plan["fx_intensity"]); c.VIG = 1 - lk["vignette"] * c.vig_shape
    SEG = plan["segments"]; FXL = plan["fx"]; BAN = plan["banners"]
    av = Avatar(plan["avatar"], W, H, plan["avatar_face"]) if plan["avatar"] else None
    if av is not None and F0 == 0:
        print(f"avatar: {av.aw}x{av.ah} rosto em ({av.fx:.2f}, {av.fy:.2f}) largura {av.fw:.2f} do quadro -> na saida com zoom 1.0: {av.fw * av.cover * av.aw / W:.2f}", flush=True)
    br = Broll(W, lk["broll_grade"]); txt = Text(plan, W, H); CAPS = build_captions(plan); mode = plan["captions"]["mode"]
    lut = LOOK.Lut(lk["lut"], lk.get("lut_strength", 1.0)) if lk.get("lut") else None
    yy, xx = c.yy, c.xx; BH = int(round(H * 1120 / 1920)); c.seam = 0.5
    alpha = np.clip((yy - 880 * S) / (150.0 * S), 0, 1)[..., None]; alpha = alpha * alpha * (3 - 2 * alpha)
    SEAMDARK = (1 - 0.45 * np.exp(-((yy - 955 * S) / (70.0 * S)) ** 2))[..., None]
    BV = (1 - 0.55 * np.clip((((xx[:BH] - W / 2) / (W * 0.62)) ** 2 + ((yy[:BH] - BH / 2) / (700.0 * S)) ** 2) - 0.35, 0, 1))[..., None]
    rs = np.random.RandomState(seed); shake = np.cumsum(rs.randn(NF + 5, 2), 0); shake -= cv2.blur(shake, (1, 45)); shake = cv2.blur(shake, (1, 7)) * cam["shake"] * S
    outs = []
    if mode in ("both", "on"):
        outs.append(("cap", enc_proc(os.path.join(tmp, f"cap_{F0:06d}.mp4"), W, H, FPS, enc, lk.get("ffmpeg_vf"))))
    if mode in ("both", "off"):
        outs.append(("nocap", enc_proc(os.path.join(tmp, f"nocap_{F0:06d}.mp4"), W, H, FPS, enc, lk.get("ffmpeg_vf"))))
    import random
    t0 = time.time()
    for n in range(F0, F1):
        t = n / FPS; c.rng = random.Random(seed * 100003 + n); c.nrng = np.random.RandomState((seed * 100003 + n) % (2 ** 31))
        if t < SE:
            si = next((i for i, s in enumerate(SEG) if s["s"] <= t < s["e"]), len(SEG) - 1); seg = SEG[si]; lay = seg.get("layout", "full")
            if av is None and lay != "broll":
                lay = "broll"
            dt0 = t - seg["s"]; p = min(1.0, dt0 / max(seg["e"] - seg["s"], 0.01)); sx, sy = shake[n]; c.layout = lay
            prev = SEG[si - 1].get("layout", "full") if si > 0 else None
            if lay == "split":
                fr = av.frame(t); zs = seg_zoom(seg, av, cam["split_zoom"])
                top = av.view(fr, zs * (1 + cam["breath"] * math.sin(2 * math.pi * t / 7.0)), cam["split_face_y"],
                              W * cam["pan"] * math.sin(2 * math.pi * t / cam["pan_period"]) + sx, sy)
                kz = 1.0; bsig = 0
                if prev == "split" and dt0 < 0.2:
                    kz = 1 + 0.18 * (1 - dt0 / 0.2) ** 2; bsig = 9 * S * (1 - dt0 / 0.2)
                bimg = br.get(seg["broll"], p, kz, t, dt0, W, BH, seg.get("kb", 1), seg.get("grade"))
                if bsig > 0.3:
                    bimg = cv2.GaussianBlur(bimg, (0, 0), bsig)
                bot = np.zeros((H, W, 3), np.float32); bot[H - BH:] = bimg * BV; img = (top * (1 - alpha) + bot * alpha) * SEAMDARK
                cap_y = int(H * plan["captions"]["y_split"])
            elif lay == "broll":
                kz = 1.0; bsig = 0
                if prev == "broll" and dt0 < 0.2:
                    kz = 1 + 0.18 * (1 - dt0 / 0.2) ** 2; bsig = 9 * S * (1 - dt0 / 0.2)
                img = br.get(seg["broll"], p, kz, t, t if seg.get("sync") else dt0, W, H, seg.get("kb", 1), seg.get("grade")); img = c.shift(img, sx, sy) if cam["shake"] else img
                if bsig > 0.3:
                    img = cv2.GaussianBlur(img, (0, 0), bsig)
                cap_y = int(H * plan["captions"]["y_full"])
            else:
                fr = av.frame(t); tgt = seg_zoom(seg, av, 1.0); cls = shot_class(seg, av)
                z = tgt * (1 + cam["overshoot"] * math.exp(-dt0 / cam["overshoot_tau"]))
                z *= (1 - cam["pull_out"] * p) if cls == "close" else (1 + cam["push_in"] * p)
                if si + 1 < len(SEG) and SEG[si + 1].get("layout") == "split" and seg["e"] - t < 0.17:
                    z *= 1 + cam["anticipation"] * (1 - (seg["e"] - t) / 0.17) ** 1.5
                img = av.view(fr, z, 0.30 if cls == "wide" else 0.33, sx * 1.4, sy * 1.4); cap_y = int(H * plan["captions"]["y_full"])
                if cls == "close" and cam["diffusion"]:
                    img = img * (1 - cam["diffusion"] * 0.625) + cv2.GaussianBlur(img, (0, 0), 14 * S) * cam["diffusion"]
            if lut is not None:
                img = lut.apply(img)
            img = img * c.VIG
            img, sig = FXM.apply_all(img, t, FXL, c, FPS)
            if sig > 0.3:
                img = cv2.GaussianBlur(img, (0, 0), sig * S)
            img = LOOK.finish(img, c, lk, c.nrng)
            pil = Image.fromarray(cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB))
            bn = next((b for b in BAN if b["s"] <= t < b["e"]), None)
            if bn:
                txt.banner(pil, bn, t)
            nocap = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR).tobytes(); withcap = nocap
            cp = next((x for x in CAPS if x[0] <= t < x[1]), None)
            if cp and mode != "off":
                txt.caption(pil, cp[2], seg.get("cap_y") and int(H * seg["cap_y"]) or cap_y); withcap = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR).tobytes()
        else:
            nocap = withcap = txt.end_card(t - SE, plan["end_card"]).tobytes()
        for kind, pr in outs:
            pr.stdin.write(withcap if kind == "cap" else nocap)
        if (n - F0) % 150 == 0:
            el = time.time() - t0; print(f"[{F0}-{F1}] frame {n} ({(n - F0) / max(el, 1e-3):.1f} fps)", flush=True)
    for _, pr in outs:
        pr.stdin.close(); pr.wait()
        if pr.returncode:
            raise SystemExit("ffmpeg falhou ao codificar o pedaco")
    print("PEDACO OK", F0, F1, flush=True)


# ====================================================================== orquestracao
def validate(plan):
    errs = []; SEG = plan["segments"]
    if not SEG:
        errs.append("plano sem 'segments'")
    for i, s in enumerate(SEG):
        lay = s.get("layout", "full")
        if lay in ("split", "broll") and not s.get("broll"):
            errs.append(f"segmento {i} ({lay}) sem 'broll'")
        b = s.get("broll")
        if b and b not in ("WAVE", "gen:wave") and not os.path.exists(b):
            errs.append(f"segmento {i}: b-roll nao encontrado: {b}")
        if i and abs(s["s"] - SEG[i - 1]["e"]) > 0.02:
            errs.append(f"segmento {i}: comeca em {s['s']} mas o anterior termina em {SEG[i - 1]['e']}")
        if lay in ("split", "full") and not plan["avatar"]:
            errs.append(f"segmento {i} usa avatar ({lay}) mas o plano nao tem 'avatar'")
    for t, k in plan["fx"]:
        if k not in FXM.REG:
            errs.append(f"efeito desconhecido '{k}' em {t}s (disponiveis: {', '.join(sorted(FXM.REG))})")
    for k in ("avatar", "voice", "words"):
        if plan[k] and not os.path.exists(plan[k]):
            errs.append(f"{k} nao encontrado: {plan[k]}")
    if plan["look"]["lut"] and not os.path.exists(plan["look"]["lut"]):
        errs.append(f"LUT nao encontrada: {plan['look']['lut']} (rode scripts/make_luts.py ou aponte um .cube)")
    return errs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan"); ap.add_argument("--jobs", type=int, default=max(2, (os.cpu_count() or 4) // 2), help="processos paralelos (padrao: metade das threads da CPU)"); ap.add_argument("--preview", help="trecho em segundos, ex. 0-12")
    ap.add_argument("--encoder", default="auto", choices=["auto", "nvenc", "videotoolbox", "x264"]); ap.add_argument("--out", help="pasta de saida (padrao: a do plano)")
    ap.add_argument("--keep", action="store_true", help="nao apagar os pedacos temporarios"); ap.add_argument("--check", action="store_true", help="so validar o plano")
    ap.add_argument("--worker", nargs=2, type=int, help=argparse.SUPPRESS); ap.add_argument("--tmp", help=argparse.SUPPRESS)
    a = ap.parse_args(); plan = load_plan(a.plan)
    if a.worker:
        cv2.setNumThreads(2)                                              # cada processo usa 2 threads: os N processos dividem a CPU sem disputa
        render_range(plan, a.worker[0], a.worker[1], a.tmp, a.encoder); return
    FXM.load_plugins(); errs = validate(plan)
    if errs:
        print("PLANO COM PROBLEMAS:"); [print("  -", e) for e in errs]; sys.exit(2)
    SE, CARD, TOTAL = timeline(plan); FPS = plan["fps"]; NF = int(TOTAL * FPS)
    kinds = {}
    for _, k in plan["fx"]:
        kinds[k] = kinds.get(k, 0) + 1
    print(f"plano ok: {len(plan['segments'])} segmentos, {len(plan['fx'])} transicoes {kinds}, fala {SE:.2f}s + cartao {CARD:.1f}s = {TOTAL:.2f}s")
    if a.check:
        return
    f0, f1 = 0, NF
    if a.preview:
        x, y = a.preview.split("-"); f0, f1 = int(float(x) * FPS), min(NF, int(float(y) * FPS))
    enc = pick_encoder(a.encoder); out_dir = a.out or plan["_base"]; os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="render_", dir=out_dir); jobs = max(1, min(a.jobs, (f1 - f0) // (FPS * 4) or 1))
    step = math.ceil((f1 - f0) / jobs); ranges = [(s, min(f1, s + step)) for s in range(f0, f1, step)]
    print(f"encoder: {enc} | {len(ranges)} processo(s) | frames {f0}-{f1}"); t0 = time.time()
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), a.plan, "--worker", str(x), str(y), "--tmp", tmp, "--encoder", enc]) for x, y in ranges]
    if any(p.wait() for p in procs):
        sys.exit("um dos pedacos falhou - veja as mensagens acima")
    bed = AUD.build(os.path.join(tmp, "bed_sfx.wav"), TOTAL, SE, plan["fx"], FXM.REG, plan["audio"], tmp)
    mix = os.path.join(tmp, "mix.wav"); vg = plan["audio"].get("voice_gain", 1.0)
    if plan["voice"]:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", plan["voice"], "-i", bed, "-filter_complex",
                        f"[0:a]aresample=44100,volume={vg},apad=whole_dur={TOTAL}[vo];[vo][1:a]amix=inputs=2:normalize=0:duration=shortest,alimiter=limit=0.95[a]",
                        "-map", "[a]", "-t", f"{TOTAL}", "-ac", "2", mix], check=True)
    else:
        mix = bed
    made = []; suffix = f" PREVIA {a.preview}" if a.preview else ""
    for kind, label in (("cap", " LEGENDA"), ("nocap", " SEM LEGENDA")):
        parts = [os.path.join(tmp, f"{kind}_{x:06d}.mp4") for x, _ in ranges]
        if not all(os.path.exists(p) for p in parts):
            continue
        lst = os.path.join(tmp, kind + ".txt"); open(lst, "w", encoding="utf-8").write("".join(f"file '{p.replace(os.sep, '/')}'\n" for p in parts))
        single = plan["captions"]["mode"] != "both" or not plan["words"]
        out = os.path.join(out_dir, plan["name"] + ("" if single else label) + suffix + ".mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ss", f"{f0 / FPS}", "-t", f"{(f1 - f0) / FPS}", "-i", mix,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-map_metadata", "-1", "-map_chapters", "-1", "-fflags", "+bitexact", "-movflags", "+faststart", out], check=True)
        made.append(out)
        if single:
            break
    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"pronto em {time.time() - t0:.0f}s:"); [print("  ", m) for m in made]


if __name__ == "__main__":
    main()
