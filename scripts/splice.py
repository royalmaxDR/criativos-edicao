# -*- coding: utf-8 -*-
"""Emenda clipes prontos num so (hook + corpo, ou comeco refeito + resto do render antigo), sem renderizar tudo de novo.

Uso:
  python scripts/splice.py saida.mp4 hook.mp4 corpo.mp4
  python scripts/splice.py saida.mp4 "previa 0-5.6.mp4:0:5.6" "render_antigo.mp4:5.6:"     # arquivo:inicio:fim (fim vazio = ate o final)
Todos os clipes devem ter o mesmo tamanho de quadro. Sai em 30 fps, H.264 + AAC, metadados limpos.
Quando so o comeco muda: renderize  render.py plan.json --preview 0-T  (T num corte de segmento) e emende com o antigo a partir de T.
"""
import subprocess, sys

if len(sys.argv) < 4:
    sys.exit(__doc__)
out, parts = sys.argv[1], sys.argv[2:]
ins = []; fc = []; lab = ""
for i, p in enumerate(parts):
    f, s, e = (p.rsplit(":", 2) + ["", ""])[:3] if p.count(":") >= 2 and not p[1:3] == ":\\" and not p[1:3] == ":/" else (p, "", "")
    if p.count(":") >= 2 and (p[1:3] in (":\\", ":/")):                      # caminho do Windows (C:\...) com ou sem :inicio:fim
        bits = p.split(":")
        f, s, e = (":".join(bits[:2]), "", "") if len(bits) == 2 else (":".join(bits[:-2]), bits[-2], bits[-1])
    ins += ["-i", f]
    tv = f"trim=start={s or 0}" + (f":end={e}" if e else ""); ta = f"atrim=start={s or 0}" + (f":end={e}" if e else "")
    fc.append(f"[{i}:v]fps=30,format=yuv420p,setsar=1,{tv},setpts=PTS-STARTPTS[v{i}]")
    fc.append(f"[{i}:a]aresample=44100,{ta},asetpts=PTS-STARTPTS[a{i}]"); lab += f"[v{i}][a{i}]"
fc.append(f"{lab}concat=n={len(parts)}:v=1:a=1[v][a]")
enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "17"]
if subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2", "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True).returncode == 0:
    enc = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "17"]
subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]"] + enc +
               ["-c:a", "aac", "-b:a", "192k", "-map_metadata", "-1", "-movflags", "+faststart", out], check=True)
print("ok ->", out)
