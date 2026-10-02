# -*- coding: utf-8 -*-
"""Finaliza um hook gerado por IA: sobe para 1080x1920 com nitidez, aplica falhas de 'sinal caindo' (chiado de TV),
monta a trilha (fala, batida de porta, respiracao ofegante, chiado) e grava um clipe pronto para emendar no criativo.

Uso:
  python scripts/hook_signal.py cena.mp4 fala.wav --out hook.mp4 --door 2.1 --speech 2.4 --glitch 5.2,6.9 [--tempo 1.08] [--dur 10]
  --door    instante (s) da batida da porta na cena      --speech  onde a fala comeca
  --glitch  instantes (s) das quedas de sinal (0,35 s cada)  --tempo  acelera a fala (1.0 = original)
"""
import argparse, math, os, subprocess, sys, wave
import cv2
import numpy as np

SR = 44100; W, H, FPS = 1080, 1920, 30


def rd(p):
    t = p + ".tmp.wav"; subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ac", "1", "-ar", str(SR), t], check=True)
    w = wave.open(t); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768; w.close(); os.remove(t); return x


def door_slam(rs):
    n = int(0.9 * SR); t = np.arange(n) / SR
    thud = np.sin(2 * math.pi * 62 * t) * np.exp(-t * 9) + 0.6 * np.sin(2 * math.pi * 118 * t) * np.exp(-t * 14)
    crack = rs.randn(n) * np.exp(-t * 60)
    rattle = rs.randn(n) * np.exp(-((t - 0.07) / 0.05) ** 2) * 0.25
    room = np.convolve(rs.randn(n) * np.exp(-t * 7), np.ones(40) / 40, "same") * 0.3
    s = thud * 0.9 + crack * 0.8 + rattle + room
    return (s / np.abs(s).max()).astype(np.float32)


def static(n, rs):
    s = rs.randn(n).astype(np.float32); s = s - np.convolve(s, np.ones(6) / 6, "same")        # chiado agudo de TV
    return s / (np.abs(s).max() + 1e-9)


def breath(n, rs):
    t = np.arange(n) / SR; env = np.clip(np.sin(2 * math.pi * 1.6 * t), 0, 1) ** 2
    s = np.convolve(rs.randn(n), np.ones(30) / 30, "same") * env
    return (s / (np.abs(s).max() + 1e-9)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene"); ap.add_argument("speech"); ap.add_argument("--out", default="hook.mp4"); ap.add_argument("--door", type=float, required=True)
    ap.add_argument("--speech-at", dest="speech_at", type=float, required=True); ap.add_argument("--glitch", default=""); ap.add_argument("--tempo", type=float, default=1.0)
    ap.add_argument("--door-sfx", nargs="*", default=[], help="arquivos reais de impacto para a porta, formato arquivo:pico_s:ganho (ex. impacto.mp3:0.09:1.0)")
    ap.add_argument("--static-sfx", nargs="*", default=[], help="arquivos de chiado/glitch, formato arquivo:pico_s:ganho; alternam entre as quedas de sinal")
    ap.add_argument("--voice-gain", dest="voice_gain", type=float, default=0.7, help="volume da fala (a porta precisa soar mais alta que a voz)")
    ap.add_argument("--events", help="JSON com sons sincronizados: [{f, t, pk, g, lp, rate}] (arquivo, instante, pico no arquivo, ganho, passa-baixa Hz, velocidade/tom)")
    ap.add_argument("--dur", type=float, default=10.0); ap.add_argument("--scene-gain", type=float, default=0.0, help="volume do audio original da cena (0 = mudo)")
    a = ap.parse_args(); rs = np.random.RandomState(7)
    G = [float(x) for x in a.glitch.split(",") if x.strip()]
    # ---------------- video
    cap = cv2.VideoCapture(a.scene); sfps = cap.get(5) or 24; frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    n_out = int(a.dur * FPS); tmpv = a.out + ".v.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-vf", "unsharp=5:5:0.8:5:5:0",
                            "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "16", "-pix_fmt", "yuv420p", tmpv], stdin=subprocess.PIPE)
    for i in range(n_out):
        t = i / FPS; f = frames[min(len(frames) - 1, int(t * sfps))]
        fh, fw = f.shape[:2]; s = max(W / fw, H / fh); img = cv2.resize(f, (int(fw * s + 0.5), int(fh * s + 0.5)), interpolation=cv2.INTER_LANCZOS4)
        y0 = (img.shape[0] - H) // 2; x0 = (img.shape[1] - W) // 2; img = img[y0:y0 + H, x0:x0 + W].astype(np.float32)
        if a.door <= t < a.door + 0.25:                                                                   # tranco da porta: a camera treme
            k = 1 - (t - a.door) / 0.25; M = np.float32([[1, 0, rs.uniform(-14, 14) * k], [0, 1, rs.uniform(-22, 22) * k]])
            img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        for g in G:
            d = t - g
            if 0 <= d < 0.35:
                k = int(d * FPS)
                if k in (2, 6):                                                                            # quadro inteiro de chiado
                    v = rs.randint(0, 255, (H // 3, W // 3, 1)).astype(np.float32).repeat(3, 0).repeat(3, 1)
                    img = np.repeat(v, 3, 2) * 0.85 + img * 0.15
                elif k == 4:
                    img = img * 0.08                                                                       # sinal some (quase preto)
                else:
                    o = img.copy(); sh = rs.randint(-60, 60); o[..., 2] = np.roll(img[..., 2], sh, 1); o[..., 0] = np.roll(img[..., 0], -sh, 1)
                    for _ in range(9):
                        yy = rs.randint(0, H - 60); hh = rs.randint(10, 90); o[yy:yy + hh] = np.roll(o[yy:yy + hh], rs.randint(-200, 200), 1)
                    roll = int((d / 0.35) * H * 0.6); o = np.roll(o, roll, 0)                              # imagem 'rolando' como TV sem sincronismo
                    v = rs.randn(H // 4 + 1, W // 4 + 1, 1).astype(np.float32).repeat(4, 0).repeat(4, 1)[:H, :W]
                    img = np.clip(o * 0.75 + v * 55 + 20, 0, 255)
        lines = (0.93 + 0.07 * np.sin(np.arange(H) * math.pi / 3))[:, None, None]                         # leve textura de tela de celular
        img = img * lines + rs.randn(H // 2 + 1, W // 2 + 1, 1).astype(np.float32).repeat(2, 0).repeat(2, 1)[:H, :W] * 3
        enc.stdin.write(np.clip(img, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close(); enc.wait()
    # ---------------- audio
    N = int(a.dur * SR); mix = np.zeros(N, np.float32)
    sp = rd(a.speech)
    if abs(a.tempo - 1) > 1e-3:
        tmp = a.out + ".sp.wav"; subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.speech, "-af", f"atempo={a.tempo}", "-ac", "1", "-ar", str(SR), tmp], check=True)
        sp = rd(tmp); os.remove(tmp)
    i0 = int(a.speech_at * SR); j = min(N, i0 + len(sp)); mix[i0:j] += sp[:j - i0] * a.voice_gain
    if a.scene_gain:
        sc = rd(a.scene)[:N]; mix[:len(sc)] += sc * a.scene_gain
    def place(spec, t0, default_gain):
        f, pk, g = (spec.split(":") + ["0", str(default_gain)])[:3] if spec.count(":") < 2 else spec.rsplit(":", 2)
        x = rd(f); i = int((t0 - float(pk)) * SR); x = x[max(0, -i):]; i = max(0, i); j = min(N, i + len(x)); mix[i:j] += x[:j - i] * float(g)
    if a.door_sfx:                                                                                        # porta: camadas de impactos reais + estalo do trinco
        for spec in a.door_sfx:
            place(spec, a.door, 1.0)
        d = door_slam(rs); i = int(a.door * SR); j = min(N, i + len(d)); mix[i:j] += d[:j - i] * 0.30
        sw = static(int(0.22 * SR), rs) * np.linspace(0, 1, int(0.22 * SR)) ** 2 * 0.06                 # ar da porta vindo antes do impacto
        i = int((a.door - 0.22) * SR); mix[i:i + len(sw)] += sw[:max(0, min(len(sw), N - i))]
    else:
        d = door_slam(rs); i = int(a.door * SR); j = min(N, i + len(d)); mix[i:j] += d[:j - i] * 0.95
    b = breath(int(4.5 * SR), rs); i = int(max(0, a.door - 1.6) * SR); j = min(N, i + len(b)); mix[i:j] += b[:j - i] * 0.10      # ofegante na corrida
    for g in G:
        n = int(0.4 * SR); s = static(n, rs) * np.concatenate([np.linspace(0.3, 1, n // 4), np.ones(n - n // 4)]); i = int(g * SR); j = min(N, i + n)
        mix[i:j] = mix[i:j] * 0.35 + s[:j - i] * 0.30                                                     # chiado engole a voz por um instante
    if a.events:                                                                                          # passos, macaneta, trinco... cada um no quadro exato
        import json
        cache = {}
        for e in json.load(open(a.events, encoding="utf-8")):
            key = (e["f"], e.get("lp"), e.get("rate", 1.0))
            if key not in cache:
                af = []
                if e.get("rate", 1.0) != 1.0:
                    af.append(f"asetrate={int(SR * e['rate'])},aresample={SR}")
                if e.get("lp"):
                    af.append(f"lowpass=f={e['lp']}")
                tmp = a.out + ".ev.wav"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", e["f"]] + (["-af", ",".join(af)] if af else []) + ["-ac", "1", "-ar", str(SR), tmp], check=True)
                cache[key] = rd(tmp); os.remove(tmp)
            x = cache[key]; i = int((e["t"] - e.get("pk", 0) / e.get("rate", 1.0)) * SR); x = x[max(0, -i):]; i = max(0, i); j = min(N, i + len(x))
            mix[i:j] += x[:j - i] * e.get("g", 1.0)
    for k, g in enumerate(G):
        if a.static_sfx:
            place(a.static_sfx[k % len(a.static_sfx)], g + 0.05, 0.6)
    lo = np.convolve(rs.randn(N), np.ones(200) / 200, "same").astype(np.float32); mix += lo / (np.abs(lo).max() + 1e-9) * 0.02    # zumbido do quarto
    mix = np.tanh(mix * 1.15) / np.tanh(1.15); aw = a.out + ".a.wav"; o = wave.open(aw, "w"); o.setnchannels(1); o.setsampwidth(2); o.setframerate(SR); o.writeframes((mix * 32767).astype(np.int16).tobytes()); o.close()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmpv, "-i", aw, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest",
                    "-map_metadata", "-1", "-movflags", "+faststart", a.out], check=True)
    os.remove(tmpv); os.remove(aw); print("ok ->", a.out)


if __name__ == "__main__":
    main()
