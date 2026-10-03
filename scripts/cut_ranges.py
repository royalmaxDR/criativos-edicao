# -*- coding: utf-8 -*-
"""Remove trechos de um criativo (video + audio juntos), mantendo a voz original e o sincronismo.
Gera os tres arquivos que o plano de edicao usa: avatar.mp4 (video), vo.wav (audio) e, se pedir, words.json.

Uso:
  python scripts/cut_ranges.py original.mp4 --remove 60.25-102.35 --end 109.3 --out pasta [--transcribe --lang pt]
  --remove  um ou mais intervalos em segundos, separados por virgula (ex. 12.0-18.5,60.2-102.3)
  --end     ignora tudo depois desse instante (ex. extensao colada no fim)
Corte nos silencios entre frases (veja os tempos com transcribe.py); cada emenda leva um fade de audio de 0,1 s.
"""
import argparse, os, subprocess, sys

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("video"); ap.add_argument("--remove", default=""); ap.add_argument("--end", type=float); ap.add_argument("--out", default=".")
ap.add_argument("--size", default="1080:1920"); ap.add_argument("--transcribe", action="store_true"); ap.add_argument("--lang")
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video], capture_output=True, text=True).stdout.strip())
end = min(a.end or dur, dur)
rem = sorted(tuple(float(v) for v in r.split("-")) for r in a.remove.split(",") if r.strip())
keep = []; t = 0.0
for x, y in rem:
    if x > t:
        keep.append((t, min(x, end)))
    t = max(t, y)
if t < end:
    keep.append((t, end))
keep = [(x, y) for x, y in keep if y - x > 0.05]
if not keep:
    sys.exit("nada sobrou depois dos cortes")
fc = []; lab = ""
for i, (x, y) in enumerate(keep):
    d = y - x
    fc.append(f"[0:v]trim={x}:{y},setpts=PTS-STARTPTS,scale={a.size},setsar=1[v{i}]")
    af = f"[0:a]atrim={x}:{y},asetpts=PTS-STARTPTS"
    if i > 0:
        af += ",afade=t=in:d=0.08"
    if i < len(keep) - 1:
        af += f",afade=t=out:st={max(0, d - 0.1):.3f}:d=0.1"
    fc.append(af + f"[a{i}]"); lab += f"[v{i}][a{i}]"
fc.append(f"{lab}concat=n={len(keep)}:v=1:a=1[v][a]")
tmp = os.path.join(a.out, "_cut.mov")
enc = ["-c:v", "libx264", "-preset", "fast", "-crf", "16"]
if subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True).returncode == 0:
    enc = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "17"]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]"] + enc + ["-c:a", "pcm_s16le", "-ar", "44100", tmp], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-an", "-c:v", "copy", os.path.join(a.out, "avatar.mp4")], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-vn", "-c:a", "pcm_s16le", os.path.join(a.out, "vo.wav")], check=True)
os.remove(tmp)
print("mantido:", ", ".join(f"{x:.2f}-{y:.2f}" for x, y in keep), f"| total {sum(y - x for x, y in keep):.2f} s -> {a.out}/avatar.mp4 + vo.wav")
if a.transcribe:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import json, transcribe as T
    w = T.transcribe(os.path.join(a.out, "vo.wav"), lang=a.lang); json.dump(w, open(os.path.join(a.out, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(" ".join(x["w"] for x in w))
