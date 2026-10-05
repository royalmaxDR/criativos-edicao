#!/usr/bin/env python3
"""Confere os videos finais: tecnico (duracao/tamanho/decodificacao/metadados) e privacidade (rostos remanescentes).

Uso:
  python verify.py final1.mp4 final2.mp4 --expect-duration 600 --expect-size 1080x1920
  python verify.py final.mp4 --source original.mp4 --seconds 120      # compara tambem com o original

Com --source, mede com o reconhecedor facial (SFace) se o rosto do video final ainda "bate" com o do original:
similaridade >= 0.363 = ainda reconhecivel por maquina. O criativo e o trecho inicial do final (--seconds).
"""
import argparse, json, os, shutil, subprocess, sys
import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(os.path.dirname(HERE), "models")
sys.path.insert(0, HERE)
STRONG = 0.7


def tool(n):
    p = os.environ.get(n.upper()) or shutil.which(n)
    if not p:
        sys.exit(f"{n} nao encontrado")
    return p


def technical(path, dur, size):
    ff, fp = tool("ffmpeg"), tool("ffprobe")
    j = json.loads(subprocess.run([fp, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                                  capture_output=True, text=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    d = float(j["format"]["duration"])
    tags = {k: v for k, v in (j["format"].get("tags") or {}).items() if k.lower() not in ("major_brand", "minor_version", "compatible_brands")}
    dec = subprocess.run([ff, "-v", "error", "-i", path, "-f", "null", "-"], capture_output=True, text=True).stderr
    dec = "\n".join(l for l in dec.splitlines() if "QT chapter" not in l and "Application provided duration" not in l)
    res = {"file": os.path.basename(path), "duration": round(d, 3), "size": f"{v['width']}x{v['height']}",
           "streams": [s["codec_type"] for s in j["streams"]], "extra_metadata": tags, "decode_errors": dec.strip() or None}
    probs = []
    if dur and abs(d - dur) > 0.5:
        probs.append(f"duracao {d:.2f}s != {dur}s")
    if size and res["size"] != size:
        probs.append(f"tamanho {res['size']} != {size}")
    if tags:
        probs.append(f"metadados restantes: {tags}")
    if dec.strip():
        probs.append("erros de decodificacao")
    res["problems"] = probs
    return res


def privacy(final, source, seconds):
    det_path, rec_path = os.path.join(MODELS, "yunet.onnx"), os.path.join(MODELS, "sface.onnx")
    cf = cv2.VideoCapture(final)
    W2, H2 = int(cf.get(3)), int(cf.get(4))
    fps2 = cf.get(cv2.CAP_PROP_FPS) or 30
    detf = cv2.FaceDetectorYN.create(det_path, "", (W2, H2), 0.5, 0.3, 5000)
    rec = cv2.FaceRecognizerSF.create(rec_path, "")
    cs = cv2.VideoCapture(source) if source else None
    if cs:
        W, H = int(cs.get(3)), int(cs.get(4))
        dets = cv2.FaceDetectorYN.create(det_path, "", (W, H), 0.5, 0.3, 5000)
        sc = min(W2 / W, H2 / H)
        ox, oy = (W2 - W * sc) / 2, (H2 - H * sc) / 2
    found = low = tot = 0
    sims = []
    t = 0.0
    while t < seconds:
        cf.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cf.read()
        if not ok:
            break
        tot += 1
        _, fs = detf.detect(fr)
        if fs is not None and len(fs):
            strong = [f for f in fs if f[14] >= STRONG]
            found += int(len(strong) > 0)
            low += int(len(strong) == 0)
        if cs:
            cs.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok2, fo = cs.read()
            if ok2:
                _, so = dets.detect(fo)
                for f in (so if so is not None else []):
                    if f[14] < STRONG or min(f[2], f[3]) < 24:  # so rostos reais (alta confianca)
                        continue
                    g = f.copy()
                    g[:14] = g[:14] * sc
                    g[0:14:2] += ox
                    g[1:14:2] += oy
                    try:
                        s = float(rec.match(rec.feature(rec.alignCrop(fo, f)), rec.feature(rec.alignCrop(fr, g)),
                                            cv2.FaceRecognizerSF_FR_COSINE))
                        sims.append(s)
                    except Exception:
                        pass
        t += 1.0
    out = {"frames_checked": tot, "frames_with_detectable_face": found,
           "frames_with_only_low_confidence_detections": low,
           "note": "detectavel = confianca >= %.1f; as de baixa confianca costumam ser falsos positivos (textura, luz, maos)" % STRONG}
    if sims:
        s = np.array(sims)
        out.update({"recognizer_similarity_mean": round(float(s.mean()), 3), "recognizer_max": round(float(s.max()), 3),
                    "samples_above_0.363": int((s >= 0.363).sum()), "samples": len(s)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--expect-duration", type=float)
    ap.add_argument("--expect-size")
    ap.add_argument("--source", help="video original (uma unica entrada) para o teste de reconhecimento")
    ap.add_argument("--seconds", type=float, default=120, help="quantos segundos iniciais testar a privacidade")
    ap.add_argument("--no-privacy", action="store_true")
    a = ap.parse_args()
    bad = 0
    for v in a.videos:
        r = technical(v, a.expect_duration, a.expect_size)
        if not a.no_privacy:
            r["privacy"] = privacy(v, a.source if len(a.videos) == 1 else None, a.seconds)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        bad += bool(r["problems"])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
