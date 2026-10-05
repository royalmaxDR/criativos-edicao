#!/usr/bin/env python3
"""Varre os videos e agrupa os rostos em PESSOAS DISTINTAS (sem saber quem sao).

Para cada pessoa distinta gera: melhor recorte do rosto, em quais videos/segundos aparece e quanto tempo fica
em tela. Serve para (a) decidir onde borrar, (b) alimentar uma busca reversa de imagem (lens_search.py) ou
uma pessoa, que e quem decide se alguem e figura publica.

IMPORTANTE: este script NAO identifica ninguem. So agrupa "rosto igual a rosto igual".

Uso: python scan_faces.py --out analise videos_ou_pastas...
Saidas: analise/report.json, analise/crops/Pxx.jpg, analise/gallery_N.jpg (grade com todas as pessoas)
"""
import argparse, glob, json, os, sys
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(os.path.dirname(HERE), "models")


def nm(v):
    v = v.flatten().astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=float, default=0.5, help="amostrar a cada N segundos")
    ap.add_argument("--threshold", type=float, default=0.40, help="similaridade para considerar a mesma pessoa")
    ap.add_argument("--min-face", type=int, default=24, help="menor rosto (px) considerado")
    ap.add_argument("--min-hits", type=int, default=3, help="descarta grupos com menos aparicoes que isso")
    a = ap.parse_args()

    files = []
    for it in a.inputs:
        files += (glob.glob(os.path.join(it, "*.mp4")) if os.path.isdir(it) else (glob.glob(it) or [it]))
    files = sorted(dict.fromkeys(os.path.abspath(f) for f in files if os.path.isfile(f)))
    if not files:
        sys.exit("nenhum video encontrado")
    os.makedirs(os.path.join(a.out, "crops"), exist_ok=True)
    det = cv2.FaceDetectorYN.create(os.path.join(MODELS, "yunet.onnx"), "", (320, 320), 0.75, 0.3, 5000)
    rec = cv2.FaceRecognizerSF.create(os.path.join(MODELS, "sface.onnx"), "")
    clusters = []
    for path in files:
        vid = os.path.splitext(os.path.basename(path))[0]
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        W, H = int(cap.get(3)), int(cap.get(4))
        if not W:
            print("erro ao abrir", path)
            continue
        sc = min(1.0, 720.0 / max(W, H))
        w2, h2 = int(W * sc), int(H * sc)
        det.setInputSize((w2, h2))
        step = max(1, round(fps * a.every))
        n = faces = 0
        while True:
            if not cap.grab():
                break
            if n % step == 0:
                ok, fr = cap.retrieve()
                if ok:
                    sm = cv2.resize(fr, (w2, h2)) if sc < 1 else fr
                    _, fs = det.detect(sm)
                    for f in (fs if fs is not None else []):
                        if f[2] < a.min_face or f[3] < a.min_face:
                            continue
                        ft = nm(rec.feature(rec.alignCrop(sm, f)))
                        t = n / fps
                        faces += 1
                        sims = [float(np.dot(ft, c["c"])) for c in clusters]
                        bi = int(np.argmax(sims)) if sims else -1
                        if bi >= 0 and sims[bi] >= a.threshold:
                            c = clusters[bi]
                            c["s"] += ft
                            c["c"] = nm(c["s"])
                        else:
                            c = {"s": ft.copy(), "c": ft.copy(), "hits": [], "best": (0, None)}
                            clusters.append(c)
                        c["hits"].append((vid, round(t, 1)))
                        x, y, w, h = f[:4].astype(int)
                        if w * h > c["best"][0]:
                            p = int(0.4 * max(w, h))
                            c["best"] = (w * h, sm[max(0, y - p):min(h2, y + h + p), max(0, x - p):min(w2, x + w + p)].copy())
            n += 1
        cap.release()
        print(f"{vid}: {round(n / fps)}s, {faces} rostos amostrados", flush=True)
    keep = sorted([c for c in clusters if len(c["hits"]) >= a.min_hits], key=lambda c: -len(c["hits"]))
    report, tiles = [], []
    for i, c in enumerate(keep, 1):
        spans = {}
        for vid, t in c["hits"]:
            s = spans.setdefault(vid, [])
            if s and t - s[-1][1] <= 1.5 + a.every:
                s[-1][1] = t
            else:
                s.append([t, t])
        pid = f"P{i:02d}"
        crop_path = os.path.join(a.out, "crops", pid + ".jpg")
        cv2.imwrite(crop_path, c["best"][1])
        report.append({"id": pid, "seconds_on_screen": round(len(c["hits"]) * a.every, 1), "crop": crop_path,
                       "appearances": {v: [f"{x:.0f}-{y:.0f}s" for x, y in sp] for v, sp in spans.items()}})
        im = cv2.resize(c["best"][1], (160, 200))
        cv2.rectangle(im, (0, 0), (160, 16), (0, 0, 0), -1)
        cv2.putText(im, f"{pid} {len(spans)}v {len(c['hits']) * a.every:.0f}s", (3, 12), 0, 0.4, (0, 255, 255), 1)
        tiles.append(im)
    json.dump(report, open(os.path.join(a.out, "report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k in range(0, len(tiles), 40):
        ch = tiles[k:k + 40]
        rows = []
        for r in range(0, len(ch), 10):
            row = ch[r:r + 10] + [np.zeros((200, 160, 3), np.uint8)] * (10 - len(ch[r:r + 10]))
            rows.append(np.hstack(row))
        cv2.imwrite(os.path.join(a.out, f"gallery_{k // 40}.jpg"), np.vstack(rows))
    print(f"{len(report)} pessoas distintas -> {a.out}/report.json, crops/, gallery_*.jpg")


if __name__ == "__main__":
    main()
