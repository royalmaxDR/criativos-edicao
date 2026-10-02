# -*- coding: utf-8 -*-
"""Trata a narracao: deixa a voz mais grave/imponente e nivela o volume. Tambem mede a voz (tom medio) para comparar com a referencia.

Uso:
  python scripts/voice_fx.py vo.wav vo_forte.wav --preset imponente
  python scripts/voice_fx.py vo.wav vo_ok.wav --preset neutro
  python scripts/voice_fx.py --stats vo.wav referencia.wav        # tom (F0) mediano e volume de cada arquivo
Presets: imponente (1 semitom abaixo, corpo em 110 Hz, presenca em 3,2 kHz, compressao), suave, neutro (so nivela).
Ajuste fino: --pitch 0.92 (menor = mais grave; 0.944 = -1 semitom, 0.891 = -2).
"""
import argparse, subprocess, sys, wave
import numpy as np

PRESETS = {
    "imponente": dict(pitch=0.944, eq="highpass=f=60,equalizer=f=110:t=q:w=0.9:g=4,equalizer=f=3200:t=q:w=1.2:g=2.5",
                      comp="acompressor=threshold=-20dB:ratio=4:attack=5:release=120:makeup=4"),
    "suave": dict(pitch=1.0, eq="highpass=f=70,equalizer=f=180:t=q:w=1.0:g=2,equalizer=f=6000:t=q:w=1.5:g=-1.5",
                  comp="acompressor=threshold=-22dB:ratio=2.5:attack=10:release=200:makeup=2"),
    "neutro": dict(pitch=1.0, eq="highpass=f=60", comp=None),
}


def has_filter(name):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
    return f" {name} " in r.stdout


def process(src, dst, preset="imponente", pitch=None, lufs=-14):
    p = PRESETS[preset]; pitch = pitch or p["pitch"]; chain = []
    if abs(pitch - 1.0) > 1e-3:
        if has_filter("rubberband"):
            chain.append(f"rubberband=pitch={pitch}:formant=preserved")
        else:                                                            # ffmpeg sem librubberband: muda o tom por reamostragem e corrige a duracao
            chain.append(f"aresample=44100,asetrate={int(44100 * pitch)},aresample=44100,atempo={1 / pitch:.5f}")
            print("aviso: ffmpeg sem 'rubberband' - usando metodo alternativo (timbre um pouco menos natural)")
    chain.append(p["eq"])
    if p["comp"]:
        chain.append(p["comp"])
    chain.append(f"loudnorm=I={lufs}:TP=-1.5:LRA=7")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", ",".join(chain), "-ar", "44100", "-ac", "1", dst], check=True)
    return dst


def stats(path):
    tmp = path + ".__tmp.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", tmp], check=True)
    w = wave.open(tmp); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768; w.close()
    import os; os.remove(tmp)
    fl = int(sr * 0.04); hop = int(sr * 0.01); f0 = []; rms = []; lo, hi = int(sr / 300), int(sr / 60)
    for i in range(0, len(x) - fl, hop):
        fr = x[i:i + fl]; e = float(np.sqrt(np.mean(fr ** 2)))
        if e < 0.02:
            continue
        fr = fr - fr.mean(); ac = np.correlate(fr, fr, "full")[fl - 1:]; ac /= ac[0] + 1e-9; k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.5:
            f0.append(sr / k); rms.append(e)
    if not f0:
        return dict(erro="sem voz detectada")
    f0 = np.array(f0)
    return dict(f0_mediana=round(float(np.median(f0)), 1), p10=round(float(np.percentile(f0, 10)), 1), p90=round(float(np.percentile(f0, 90)), 1), rms=round(float(np.mean(rms)), 3))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+"); ap.add_argument("--preset", default="imponente", choices=list(PRESETS)); ap.add_argument("--pitch", type=float)
    ap.add_argument("--lufs", type=float, default=-14); ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.stats:
        for f in a.files:
            print(f, stats(f))
        sys.exit(0)
    if len(a.files) != 2:
        sys.exit("uso: voice_fx.py entrada.wav saida.wav [--preset ...]")
    process(a.files[0], a.files[1], a.preset, a.pitch, a.lufs); print("ok ->", a.files[1], stats(a.files[1]))
