# -*- coding: utf-8 -*-
"""Folha de contato de uma pasta de imagens (para escolher b-roll olhando). Imagens corrompidas sao puladas e listadas.
Uso: python scripts/sheet.py pasta_broll [--out sheet.jpg] [--cols 10]"""
import argparse, glob, os
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("folder"); ap.add_argument("--out"); ap.add_argument("--cols", type=int, default=10)
a = ap.parse_args()
fs = sorted(f for f in glob.glob(os.path.join(a.folder, "*")) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and not os.path.basename(f).startswith("_"))
ok = []; bad = []
for f in fs:
    try:
        im = Image.open(f).convert("RGB"); im.thumbnail((170, 170)); ok.append((f, im))
    except Exception:
        bad.append(os.path.basename(f))
if not ok:
    raise SystemExit("nenhuma imagem valida em " + a.folder)
rows = (len(ok) + a.cols - 1) // a.cols
s = Image.new("RGB", (a.cols * 170, rows * 190), "black"); d = ImageDraw.Draw(s)
for i, (f, im) in enumerate(ok):
    x, y = (i % a.cols) * 170, (i // a.cols) * 190
    s.paste(im, (x, y + 18)); d.text((x + 3, y + 3), os.path.splitext(os.path.basename(f))[0], fill="yellow")
out = a.out or os.path.join(a.folder, "_folha.jpg"); s.save(out, quality=80)
print(len(ok), "imagens ->", out)
if bad:
    print("invalidas (apague e baixe de novo):", ", ".join(bad))
