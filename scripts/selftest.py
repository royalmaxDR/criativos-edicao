# -*- coding: utf-8 -*-
"""Teste de ponta a ponta SEM nenhum arquivo externo: cria um 'apresentador' sintetico, narracao de teste, b-roll gerado,
monta o plano com cada estilo e renderiza 8 s. Se terminar com 'SELFTEST OK', a maquina esta pronta.
Uso: python scripts/selftest.py [--keep]"""
import json, os, shutil, subprocess, sys
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); T = os.path.join(ROOT, "_selftest")
shutil.rmtree(T, ignore_errors=True); os.makedirs(os.path.join(T, "broll"))
run = lambda *a: subprocess.run(list(a), check=True)
# apresentador sintetico: fundo em degrade + "rosto" oval que mexe (o detector pode nao achar rosto - o render usa a posicao padrao)
vw = cv2.VideoWriter(os.path.join(T, "avatar_raw.avi"), cv2.VideoWriter_fourcc(*"MJPG"), 25, (360, 640))
yy, xx = np.mgrid[0:640, 0:360]
for i in range(25 * 16):
    fr = np.dstack([60 + yy // 8, 40 + xx // 6, 30 + yy // 10]).astype(np.uint8)
    cv2.ellipse(fr, (180 + int(4 * np.sin(i / 9)), 215), (62, 82), 0, 0, 360, (150, 180, 225), -1); cv2.circle(fr, (158, 200), 7, (40, 40, 40), -1); cv2.circle(fr, (204, 200), 7, (40, 40, 40), -1)
    cv2.ellipse(fr, (181, 252), (20, 4 + int(6 * abs(np.sin(i / 2.2)))), 0, 0, 360, (60, 60, 150), -1); cv2.rectangle(fr, (90, 300), (270, 640), (120, 70, 40), -1); vw.write(fr)
vw.release()
run("ffmpeg", "-v", "error", "-y", "-i", os.path.join(T, "avatar_raw.avi"), "-c:v", "libx264", "-pix_fmt", "yuv420p", os.path.join(T, "avatar.mp4")); os.remove(os.path.join(T, "avatar_raw.avi"))
run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=140:duration=16", "-af", "tremolo=f=3.5:d=0.9,volume=0.5", os.path.join(T, "vo_raw.wav"))
run(sys.executable, os.path.join(HERE, "voice_fx.py"), os.path.join(T, "vo_raw.wav"), os.path.join(T, "vo.wav"), "--preset", "imponente")
txt = ("Em 1947, arqueologos encontraram um pergaminho. Ele continha uma frase esquecida, guardada por seculos. Poucos sabem o que ela dizia. "
       "Hoje voce vai descobrir. Toque no botao abaixo, agora.").split()
dur = 15.6 / len(txt); json.dump([dict(w=w, s=round(i * dur, 2), e=round(i * dur + dur * 0.85, 2)) for i, w in enumerate(txt)], open(os.path.join(T, "words.json"), "w", encoding="utf-8"))
for k in range(5):
    im = np.zeros((900, 1400, 3), np.uint8); im[:] = (40 + 40 * k, 90, 200 - 35 * k)
    for j in range(12):
        cv2.circle(im, (100 + 110 * j, 450 + int(200 * np.sin(j + k))), 60, (255 - 20 * j, 200, 40 * k), -1)
    cv2.putText(im, f"B-ROLL {k + 1}", (380, 480), cv2.FONT_HERSHEY_DUPLEX, 3.5, (255, 255, 255), 8); cv2.imwrite(os.path.join(T, "broll", f"b{k + 1}.jpg"), im)
styles = ["cinematico_revelacao", "ugc_dinamico", "narracao_broll"]; ok = True
for s in styles:
    plan = os.path.join(T, f"plan_{s}.json"); args = ["--words", os.path.join(T, "words.json"), "--voice", os.path.join(T, "vo.wav"), "--broll", os.path.join(T, "broll"), "--style", s, "--name", "TESTE " + s, "--out", plan]
    if s != "narracao_broll":
        args += ["--avatar", os.path.join(T, "avatar.mp4")]
    run(sys.executable, os.path.join(HERE, "make_plan.py"), *args)
    p = json.load(open(plan, encoding="utf-8")); p["size"] = [540, 960]; json.dump(p, open(plan, "w", encoding="utf-8"), ensure_ascii=False, indent=1)   # meia resolucao: teste rapido
    r = subprocess.run([sys.executable, os.path.join(HERE, "render.py"), plan, "--preview", "0-8", "--jobs", "2"]); ok = ok and r.returncode == 0
outs = [f for f in os.listdir(T) if f.endswith(".mp4") and f.startswith("TESTE")]
print("\narquivos:", outs); ok = ok and len(outs) >= 5
print("SELFTEST OK" if ok else "SELFTEST FALHOU")
if ok and "--keep" not in sys.argv:
    shutil.rmtree(T, ignore_errors=True)
sys.exit(0 if ok else 1)
