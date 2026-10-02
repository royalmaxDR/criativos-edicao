# -*- coding: utf-8 -*-
"""Trilha: base grave (drone sintetizado ou arquivo de musica em loop) + efeitos sonoros nas transicoes."""
import math, os, subprocess, wave
import numpy as np

SR = 44100


def _rs(seed):
    return np.random.RandomState(seed)


def whoosh(d=0.42, seed=1):
    m = int(d * SR); ns = _rs(seed).randn(m).astype(np.float32); k = np.arange(m); fc = 500 + 6500 * (k / m) ** 1.5
    a1 = np.exp(-2 * math.pi * fc / SR); a2 = np.exp(-2 * math.pi * fc * 0.35 / SR); out = np.zeros(m, np.float32); y1 = y2 = 0.0
    for i in range(m):
        y1 = (1 - a1[i]) * ns[i] + a1[i] * y1; y2 = (1 - a2[i]) * ns[i] + a2[i] * y2; out[i] = y1 - y2
    return out * (np.sin(np.linspace(0, math.pi, m)) ** 2) / (np.abs(out).max() + 1e-9)


def boom(d=0.9, f0=52, seed=0):
    tt = np.arange(int(d * SR)) / SR
    return (np.sin(2 * math.pi * f0 * tt) * np.exp(-tt * 5.5) + 0.25 * np.sin(2 * math.pi * f0 * 2 * tt) * np.exp(-tt * 9)).astype(np.float32)


def crackle(d=0.24, seed=2):
    r = _rs(seed); m = int(d * SR); s = r.randn(m).astype(np.float32)
    s = np.repeat(s[::12], 12)[:m] * (r.rand(m) > 0.35)
    return s * np.linspace(1, 0.2, m) / 3


def hit(d=0.35, seed=3):
    m = int(d * SR); tt = np.arange(m) / SR
    return ((_rs(seed).randn(m) * np.exp(-tt * 38) * 0.6 + np.sin(2 * math.pi * 70 * tt) * np.exp(-tt * 14))).astype(np.float32) * 0.8


def riser(d=1.2, seed=4):
    m = int(d * SR); tt = np.arange(m) / SR
    ph = 2 * math.pi * (180 * tt + (900 / (2 * d)) * tt ** 2)
    return (np.sin(ph) * 0.5 + _rs(seed).randn(m) * 0.15).astype(np.float32) * (tt / d) ** 2


SOUNDS = dict(whoosh=whoosh, boom=boom, crackle=crackle, hit=hit, riser=riser)


def drone(n, seed=7):
    """Base grave continua (30-220 Hz) com batida lenta e um 'pulso' a cada ~8,5 s - o clima do criativo de referencia."""
    t = np.arange(n) / SR; r = _rs(seed); out = np.zeros((n, 2), np.float32)
    for ch in range(2):
        x = np.zeros(n, np.float32)
        for f, a, lf in ((41.2, 0.30, 0.07), (55.0, 0.60, 0.05), (82.4, 0.62, 0.09), (110.3, 0.50, 0.11), (164.8, 0.34, 0.13), (220.5, 0.22, 0.08), (329.6, 0.12, 0.06), (440.9, 0.06, 0.10)):
            x += (a * np.sin(2 * math.pi * f * (1 + 0.002 * ch) * t + r.rand() * 6.28) * (0.72 + 0.28 * np.sin(2 * math.pi * lf * t + r.rand() * 6.28))).astype(np.float32)
        spec = np.fft.rfft(r.randn(n)); fr = np.fft.rfftfreq(n, 1 / SR)
        spec *= np.exp(-((np.log2(np.maximum(fr, 1) / 95.0)) ** 2) / 1.4) + 0.10 * np.exp(-((np.log2(np.maximum(fr, 1) / 520.0)) ** 2) / 0.8)   # ronco em ~95 Hz + ar em ~520 Hz
        rumble = np.fft.irfft(spec, n).astype(np.float32); rumble /= np.abs(rumble).max() + 1e-9
        out[:, ch] = x / 2.2 + rumble * 0.75
    pulse = boom(2.2, 38); pos = int(2.0 * SR)
    while pos + len(pulse) < n:
        out[pos:pos + len(pulse)] += pulse[:, None] * 0.9; pos += int(8.5 * SR)
    return out / (np.sqrt(np.mean(out ** 2)) + 1e-9)                                  # rms = 1


def file_bed(path, n, a=0.0, b=None, xfade=0.6, tmp="."):
    """Musica/ambiente de um arquivo, em loop com crossfade. a/b = trecho (s) usado no loop."""
    w = os.path.join(tmp, "_bed_src.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", w], check=True)
    f = wave.open(w); x = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).reshape(-1, 2).astype(np.float32) / 32768; f.close()
    loop = x[int(a * SR):int(b * SR) if b else len(x)]
    if len(loop) >= n:
        out = loop[:n].copy()
    else:
        xf = min(int(xfade * SR), len(loop) // 3); L = len(loop) - xf; out = np.zeros((n + len(loop), 2), np.float32); pos = 0
        fi = np.linspace(0, 1, xf)[:, None]; fo = 1 - fi
        while pos < n:
            seg = loop.copy(); seg[:xf] *= fi; seg[-xf:] *= fo; out[pos:pos + len(seg)] += seg; pos += L
        out = out[:n]
    return out / (np.sqrt(np.mean(out ** 2)) + 1e-9)


def build(out_path, total, speech_end, fx_list, fx_reg, audio_cfg, tmp="."):
    """Gera bed + sfx (wav estereo). audio_cfg: bed ('synth' | caminho | 'none'), bed_rms, bed_loop [a, b], sfx (bool), sfx_gain."""
    n = int(total * SR); cfg = audio_cfg or {}
    bed_kind = cfg.get("bed", "synth")
    if bed_kind in (None, "none", False):
        bed = np.zeros((n, 2), np.float32)
    else:
        if bed_kind == "synth":
            bed = drone(n)
        else:
            lp = cfg.get("bed_loop") or [0.0, None]
            bed = file_bed(bed_kind, n, lp[0], lp[1], tmp=tmp)
        env = np.ones(n, np.float32); f = min(int(0.8 * SR), n // 4); g = min(int(1.5 * SR), n // 4)
        env[:f] = np.linspace(0, 1, f); env[-g:] = np.linspace(1, 0, g)
        bed = bed * env[:, None] * cfg.get("bed_rms", 0.036)            # referencia: rms da base ~0,03 contra voz ~0,17
    sfx = np.zeros((n, 2), np.float32)
    if cfg.get("sfx", True):
        sg = cfg.get("sfx_gain", 1.0); cache = {}

        def add(t, name, gain, params):
            key = (name, tuple(sorted(params.items())))
            if key not in cache:
                cache[key] = SOUNDS[name](**params)
            sig = cache[key]; i = max(0, int(t * SR)); j = min(n, i + len(sig))
            if j > i:
                sfx[i:j] += (sig[:j - i] * gain * sg)[:, None]

        for t, kind in fx_list:
            for s in fx_reg.get(kind, {}).get("sfx", ()):
                add(t + s[1], s[0], s[2], s[3] if len(s) > 3 else {})
        if total > speech_end + 0.5:                                      # entrada do cartao final
            add(speech_end, "boom", 0.5, dict(d=1.4, f0=44)); add(speech_end - 0.15, "whoosh", 0.15, dict(d=0.3))
    mix = np.clip(bed + sfx, -1, 1)
    o = wave.open(out_path, "w"); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR)
    o.writeframes((mix * 32767).astype(np.int16).tobytes()); o.close()
    return out_path
