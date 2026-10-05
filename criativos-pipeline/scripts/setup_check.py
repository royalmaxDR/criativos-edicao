#!/usr/bin/env python3
"""Verifica (e orienta a corrigir) o ambiente: python, opencv, numpy, ffmpeg/ffprobe, encoder de GPU, modelos."""
import importlib, os, shutil, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(os.path.dirname(HERE), "models")
URLS = {  # espelhos oficiais do OpenCV Zoo (so usados se o arquivo local faltar)
    "yunet.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg):
    print(f"  [FALTA] {msg}")
    return 1


def main():
    problems = 0
    print(f"Python {sys.version.split()[0]}")
    for mod, pipname in (("cv2", "opencv-python"), ("numpy", "numpy")):
        try:
            m = importlib.import_module(mod)
            ok(f"{mod} {getattr(m, '__version__', '')}")
        except Exception:
            problems += bad(f"{mod}  ->  pip install {pipname}")
    ff = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    fp = os.environ.get("FFPROBE") or shutil.which("ffprobe")
    if ff and fp:
        ok(f"ffmpeg: {ff}")
        enc = "libx264 (CPU)"
        for e in ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox"):
            r = subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2", "-c:v", e,
                                "-f", "null", "-"], capture_output=True)
            if r.returncode == 0:
                enc = f"{e} (GPU)"
                break
        ok(f"encoder escolhido automaticamente: {enc}")
    else:
        problems += bad("ffmpeg/ffprobe  ->  instale em https://ffmpeg.org (ou defina FFMPEG/FFPROBE)")
    os.makedirs(MODELS, exist_ok=True)
    for name, url in URLS.items():
        p = os.path.join(MODELS, name)
        if os.path.exists(p) and os.path.getsize(p) > 100_000:
            ok(f"modelo {name}")
            continue
        print(f"  baixando {name} ...")
        try:
            urllib.request.urlretrieve(url, p)
            ok(f"modelo {name} baixado")
        except Exception as e:
            problems += bad(f"modelo {name}: {e}. Baixe manualmente de {url}")
    print("\nTudo pronto." if not problems else f"\n{problems} pendencia(s) acima.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
