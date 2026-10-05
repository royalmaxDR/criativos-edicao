#!/usr/bin/env python3
"""Borra rostos, limpa metadados e (opcional) anexa um extensor ate a duracao alvo.

Um unico passo por video: detecta rostos -> aplica o efeito -> codifica -> anexa o extensor
PRE-RENDERIZADO (uma vez, em cache) por copia de stream. Funciona em Windows/macOS/Linux.

Exemplos:
  python blur_pipeline.py --out saida --extender extensor.mp4 --target 600 videos/
  python blur_pipeline.py --out saida --style mosaic criativo1.mp4 criativo2.mp4
  python blur_pipeline.py --out saida --style none --extender extensor.mp4 videos/   # so extensor + limpeza

Com --plan blur_plan.json so os videos marcados (Lens citou nome) recebem o efeito.
Estilos: strong (borrao horizontal forte olhos/nariz/boca, derrota reconhecimento facial),
         mosaic (pixelizacao quadrada, a mais segura), none (nao toca nos rostos).
"""
import argparse, glob, hashlib, json, os, shutil, subprocess, sys, tempfile, time
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(os.path.dirname(HERE), "models")
DET_MODEL = os.path.join(MODELS, "yunet.onnx")
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


# ----------------------------------------------------------------------------- ffmpeg helpers
def find_tool(name):
    env = os.environ.get(name.upper())
    if env and os.path.exists(env):
        return env
    p = shutil.which(name)
    if p:
        return p
    sys.exit(f"ERRO: '{name}' nao encontrado. Instale o ffmpeg (https://ffmpeg.org) ou defina a variavel {name.upper()}.")


FFMPEG = FFPROBE = None


def tools():
    global FFMPEG, FFPROBE
    if FFMPEG is None:
        FFMPEG, FFPROBE = find_tool("ffmpeg"), find_tool("ffprobe")
    return FFMPEG, FFPROBE


def probe(path):
    _, fp = tools()
    r = subprocess.run([fp, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe falhou em {path}: {r.stderr.strip()}")
    return json.loads(r.stdout)


def duration_of(path):
    return float(probe(path)["format"]["duration"])


def best_encoder(pref):
    ff, _ = tools()
    if pref != "auto":
        return pref
    for enc in ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"):
        t = subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2", "-c:v", enc,
                            "-f", "null", "-"], capture_output=True)
        if t.returncode == 0:
            return enc
    return "libx264"


def enc_args(enc, cq, fps):
    if enc == "h264_nvenc":
        a = ["-c:v", enc, "-preset", "p4", "-cq", str(cq), "-b:v", "0"]
    elif enc == "h264_qsv":
        a = ["-c:v", enc, "-global_quality", str(cq)]
    elif enc == "h264_amf":
        a = ["-c:v", enc, "-quality", "balanced", "-rc", "cqp", "-qp_i", str(cq), "-qp_p", str(cq)]
    elif enc == "h264_videotoolbox":
        a = ["-c:v", enc, "-q:v", str(max(1, 100 - cq * 2))]
    else:
        a = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(cq)]
    return a + ["-g", str(fps), "-bf", "0", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]


def scale_vf(size, fps):
    w, h = size
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps={fps},format=yuv420p")


# ----------------------------------------------------------------------------- face effects
def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    i = max(0, x2 - x1) * max(0, y2 - y1)
    return i / (a[2] * a[3] + b[2] * b[3] - i + 1e-9)


def effect_strong(fr, d, W, H):
    """Borrao horizontal forte sobre olhos/nariz/boca (+ margem), calculado em versao reduzida (rapido)."""
    x, y, w, h = d[:4]
    lm = d[4:14].reshape(5, 2)
    eye_y = (lm[0, 1] + lm[1, 1]) / 2
    mouth_y = (lm[3, 1] + lm[4, 1]) / 2
    dd = max(mouth_y - eye_y, 0.25 * h)
    top, bot, cx, hw = eye_y - 1.25 * dd, mouth_y + 1.0 * dd, x + w / 2, w * 0.78
    x0, x1 = int(max(0, cx - hw)), int(min(W, cx + hw))
    y0, y1 = int(max(0, top)), int(min(H, bot))
    if x1 - x0 < 6 or y1 - y0 < 6:
        return
    pad = int(0.25 * (y1 - y0))
    ax0, ax1, ay0, ay1 = max(0, x0 - pad), min(W, x1 + pad), max(0, y0 - pad), min(H, y1 + pad)
    roi = fr[ay0:ay1, ax0:ax1].copy()
    S = 4
    rh, rw = roi.shape[:2]
    sm = cv2.resize(roi, (max(2, rw // S), max(2, rh // S)), interpolation=cv2.INTER_AREA)
    k = max(3, int(w * 1.6 / S)) | 1
    sm = cv2.blur(sm, (k, 1))
    sm = cv2.blur(sm, (k, 1))
    sg = max(1, w * 0.14 / S)
    sm = cv2.GaussianBlur(sm, (0, 0), sigmaX=sg, sigmaY=sg)
    bl = cv2.resize(sm, (rw, rh), interpolation=cv2.INTER_LINEAR)
    m = np.zeros((max(2, rh // S), max(2, rw // S)), np.float32)
    cv2.ellipse(m, (((x0 - ax0 + x1 - ax0) // 2) // S, ((y0 - ay0 + y1 - ay0) // 2) // S),
                (((x1 - x0) // 2) // S, ((y1 - y0) // 2) // S), 0, 0, 360, 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), max(1, (y1 - y0) * 0.28 / S))
    m = cv2.resize(m, (rw, rh), interpolation=cv2.INTER_LINEAR)[..., None]
    m = np.clip(m * 2.2, 0, 1)
    fr[ay0:ay1, ax0:ax1] = (bl * m + roi * (1 - m)).astype(np.uint8)


def effect_mosaic(fr, d, W, H, blocks=9, pad=0.18):
    x, y, w, h = d[:4]
    s = max(w, h) * (1 + pad)
    cx, cy = x + w / 2, y + h / 2
    x0, y0, x1, y1 = int(max(0, cx - s / 2)), int(max(0, cy - s / 2)), int(min(W, cx + s / 2)), int(min(H, cy + s / 2))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    r = fr[y0:y1, x0:x1]
    bw, bh = max(2, (x1 - x0) // blocks), max(2, (y1 - y0) // blocks)
    sm = cv2.resize(r, (max(1, (x1 - x0) // bw), max(1, (y1 - y0) // bh)), interpolation=cv2.INTER_AREA)
    fr[y0:y1, x0:x1] = cv2.resize(sm, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)


EFFECTS = {"strong": effect_strong, "mosaic": effect_mosaic, "none": None}


# ----------------------------------------------------------------------------- extender cache
def prerender_extender(opt, enc):
    """Renderiza o extensor UMA vez (mesmo tamanho/fps/encoder) e guarda em cache. Retorna (caminho, duracao)."""
    ff, _ = tools()
    st = os.stat(opt["extender"])
    key = hashlib.sha1(f"{os.path.abspath(opt['extender'])}|{st.st_size}|{st.st_mtime}|{opt['size']}|{opt['fps']}|"
                       f"{opt['target']}|{enc}|{opt['cq']}".encode()).hexdigest()[:12]
    cache = os.path.join(opt["out"], ".cache")
    os.makedirs(cache, exist_ok=True)
    pre = os.path.join(cache, f"extensor_{key}.mp4")
    if not os.path.exists(pre):
        t0 = time.time()
        cmd = [ff, "-v", "error", "-y", "-i", opt["extender"], "-vf", scale_vf(opt["size"], opt["fps"]),
               "-t", str(opt["target"]), "-map_metadata", "-1", "-map_chapters", "-1",
               *enc_args(enc, opt["cq"], opt["fps"]), "-force_key_frames", "expr:gte(t,n_forced*1)", pre + ".tmp.mp4"]
        subprocess.run(cmd, check=True)
        os.replace(pre + ".tmp.mp4", pre)
        print(f"[extensor] pre-renderizado em {time.time() - t0:.0f}s -> {pre}", flush=True)
    return pre, duration_of(pre)


# ----------------------------------------------------------------------------- per-video work
def work(args):
    vin, opt, ext_pre = args
    ff, _ = tools()
    t0 = time.time()
    stem = os.path.splitext(os.path.basename(vin))[0]
    out = os.path.join(opt["out"], f"{stem}-{opt['suffix']}.mp4")
    tmp = tempfile.mkdtemp(prefix="crp_", dir=opt["out"])
    try:
        info = probe(vin)
        has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
        cap = cv2.VideoCapture(vin)
        fps_in = cap.get(cv2.CAP_PROP_FPS) or 30.0
        W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        style = opt["style"]
        if opt.get("plan") is not None and not opt["plan"].get(stem, True):
            style = "none"  # o plano diz que este video nao tem rosto sensivel
        effect = EFFECTS[style]
        det = cv2.FaceDetectorYN.create(DET_MODEL, "", (W, H), opt["min_score"], 0.3, 5000) if effect else None
        step, hold = opt["step"], int(fps_in * opt["hold"])
        part = os.path.join(tmp, "part.mp4")
        audio_in = ["-i", vin] if has_audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        cmd = [ff, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps_in),
               "-i", "-", *audio_in, "-map", "0:v", "-map", "1:a", "-vf", scale_vf(opt["size"], opt["fps"]),
               "-af", "aformat=sample_rates=44100:channel_layouts=stereo", "-shortest",
               "-map_metadata", "-1", "-map_chapters", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
               "-flags:a", "+bitexact", *enc_args(opt["enc"], opt["cq"], opt["fps"]),
               "-force_key_frames", "expr:gte(t,0)", part]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        tracks, n, blurred = [], 0, 0
        while True:
            ok, fr = cap.read()
            if not ok:
                break
            if effect and n % step == 0:
                _, fs = det.detect(fr)
                dets = [f[:14].astype(float) for f in (fs if fs is not None else [])]
                used = set()
                for t in tracks:
                    best, bi = 0.2, -1
                    for i, d in enumerate(dets):
                        if i in used:
                            continue
                        v = iou(t["d"][:4], d[:4])
                        if v > best:
                            best, bi = v, i
                    if bi >= 0:
                        used.add(bi)
                        t["d"] = 0.6 * dets[bi] + 0.4 * t["d"]
                        t["age"] = 0
                    else:
                        t["age"] += step
                tracks += [{"d": d, "age": 0} for i, d in enumerate(dets) if i not in used]
                tracks = [t for t in tracks if t["age"] <= hold]
            if tracks:
                for t in tracks:
                    effect(fr, t["d"], W, H)
                blurred += 1
            p.stdin.write(fr.tobytes())
            n += 1
        p.stdin.close()
        if p.wait() != 0:
            raise RuntimeError("ffmpeg falhou ao codificar o criativo")
        L = duration_of(part)
        target = opt["target"]
        if ext_pre and target and L < target - 0.05:
            tail = os.path.join(tmp, "tail.mp4")
            subprocess.run([ff, "-v", "error", "-y", "-i", ext_pre, "-t", f"{target - L:.3f}", "-c", "copy", tail], check=True)
            lst = os.path.join(tmp, "list.txt")
            with open(lst, "w", encoding="utf-8") as fh:
                for f in (part, tail):
                    fh.write("file '" + f.replace("\\", "/").replace("'", "'\\''") + "'\n")
            subprocess.run([ff, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-t", str(target),
                            "-c", "copy", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
                            "-flags:a", "+bitexact", "-movflags", "+faststart", out], check=True)
        else:  # sem extensor, ou criativo ja >= alvo: so remux/corta
            cut = ["-t", str(target)] if target and L > target else []
            subprocess.run([ff, "-v", "error", "-y", "-i", part, *cut, "-c", "copy", "-map_metadata", "-1",
                            "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
                            "-movflags", "+faststart", out], check=True)
        return {"input": vin, "output": out, "style": style, "frames": n, "frames_with_effect": blurred,
                "duration": round(duration_of(out), 3), "seconds": round(time.time() - t0, 1)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ----------------------------------------------------------------------------- main
def collect_inputs(items):
    files = []
    for it in items:
        if os.path.isdir(it):
            for e in VIDEO_EXT:
                files += glob.glob(os.path.join(it, "*" + e))
        else:
            files += glob.glob(it) or [it]
    return sorted(dict.fromkeys(os.path.abspath(f) for f in files if os.path.isfile(f)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="videos e/ou pastas")
    ap.add_argument("--out", required=True, help="pasta de saida")
    ap.add_argument("--style", choices=list(EFFECTS), default="strong")
    ap.add_argument("--extender", help="video extensor a anexar apos o criativo (opcional)")
    ap.add_argument("--target", type=float, default=600, help="duracao final em segundos (padrao 600; 0 = sem limite)")
    ap.add_argument("--size", default="1080x1920", help="LxA da saida (padrao 1080x1920)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--encoder", default="auto", help="auto|h264_nvenc|h264_qsv|h264_amf|h264_videotoolbox|libx264")
    ap.add_argument("--cq", type=int, default=28, help="qualidade (maior = menor arquivo). Padrao 28")
    ap.add_argument("--workers", type=int, default=0, help="videos em paralelo (0 = automatico)")
    ap.add_argument("--min-score", type=float, default=0.5, help="confianca minima do detector. 0.5 (padrao) prioriza privacidade; subir (0.7) reduz borroes em objetos mas deixa escapar rostos pequenos/de perfil")
    ap.add_argument("--step", type=int, default=2, help="detectar a cada N quadros")
    ap.add_argument("--hold", type=float, default=0.6, help="segundos que o efeito persiste sem deteccao")
    ap.add_argument("--suffix", default=None, help="sufixo do arquivo de saida (padrao EXT10 com extensor, senao final)")
    ap.add_argument("--plan", help="blur_plan.json (de triage.py): borra so os videos com rosto sensivel; os demais saem sem efeito")
    ap.add_argument("--json", action="store_true", help="imprime resumo em JSON no final")
    a = ap.parse_args()

    if a.style != "none" and not os.path.exists(DET_MODEL):
        sys.exit(f"ERRO: modelo ausente {DET_MODEL}. Rode scripts/setup_check.py")
    w, h = (int(v) for v in a.size.lower().split("x"))
    files = collect_inputs(a.inputs)
    if not files:
        sys.exit("ERRO: nenhum video encontrado")
    os.makedirs(a.out, exist_ok=True)
    enc = best_encoder(a.encoder)
    workers = a.workers or (3 if enc != "libx264" else max(1, (os.cpu_count() or 2) // 2))
    opt = dict(out=os.path.abspath(a.out), style=a.style, extender=a.extender, target=a.target, size=(w, h), fps=a.fps,
               enc=enc, cq=a.cq, min_score=a.min_score, step=max(1, a.step), hold=a.hold,
               suffix=a.suffix or ("EXT10" if a.extender else "final"), plan=None)
    print(f"[config] {len(files)} video(s) | estilo={a.style} | encoder={enc} | paralelo={workers} | saida={opt['out']}", flush=True)
    t0 = time.time()
    ext_pre = None
    if a.extender:
        if not os.path.exists(a.extender):
            sys.exit(f"ERRO: extensor nao encontrado: {a.extender}")
        ext_pre, ext_dur = prerender_extender(opt, enc)
        if a.target and ext_dur < a.target - 5:
            print(f"[aviso] extensor ({ext_dur:.0f}s) mais curto que o alvo ({a.target:.0f}s): videos ficarao mais curtos", flush=True)
    results = []
    if a.plan:
        pl = json.load(open(a.plan, encoding="utf-8"))["videos"]
        opt["plan"] = {k: v["blur"] for k, v in pl.items()}
        print(f"[plano] borrar {sum(1 for v in opt['plan'].values() if v)} de {len(opt['plan'])} videos do plano; "
              f"videos fora do plano seguem com o estilo '{a.style}'", flush=True)
    with Pool(min(workers, len(files))) as pool:
        for r in pool.imap_unordered(work, [(f, opt, ext_pre) for f in files]):
            print(f"[ok] {os.path.basename(r['output'])}: {r['duration']}s, estilo={r['style']}, efeito em {r['frames_with_effect']}/{r['frames']} quadros, {r['seconds']}s", flush=True)
            results.append(r)
    print(f"[total] {time.time() - t0:.0f}s", flush=True)
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
