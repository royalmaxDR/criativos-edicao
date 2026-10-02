# -*- coding: utf-8 -*-
"""Prepara e confere a maquina. Uso: python scripts/setup.py [--check]   (--check so confere, nao instala nada)

1) instala os pacotes Python (requirements.txt)   2) baixa o detector de rosto YuNet (OpenCV Zoo, licenca MIT)
3) baixa a fonte Anton (Google Fonts, licenca OFL) 4) gera as LUTs em luts/   5) confere o FFmpeg e o que ele traz
"""
import importlib, os, platform, shutil, subprocess, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); CHECK = "--check" in sys.argv
ok_all = True


def line(ok, name, detail=""):
    global ok_all
    ok_all = ok_all and (ok is not False)
    print(f"  [{'ok' if ok else ('--' if ok is None else 'FALTA')}] {name}{(' - ' + detail) if detail else ''}")


def fetch(url, dst, min_size):
    if os.path.exists(dst) and os.path.getsize(dst) >= min_size:
        return True
    if CHECK:
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dst)
        return os.path.getsize(dst) >= min_size
    except Exception as e:
        print("     erro ao baixar:", e); return False


print("Python:", sys.version.split()[0], "|", platform.platform())
line(sys.version_info >= (3, 10), "Python 3.10 ou mais novo")
if not CHECK:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(ROOT, "requirements.txt")], check=False)
print("Pacotes:")
for mod, pip in (("cv2", "opencv-python"), ("numpy", "numpy"), ("PIL", "pillow"), ("requests", "requests"), ("faster_whisper", "faster-whisper")):
    try:
        m = importlib.import_module(mod); line(True, pip, getattr(m, "__version__", ""))
    except Exception as e:
        line(False, pip, f"pip install {pip}  ({e})")
try:
    import cv2
    line(hasattr(cv2, "FaceDetectorYN"), "OpenCV com FaceDetectorYN (precisa 4.8+)")
except Exception:
    pass
print("Arquivos:")
line(fetch("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx", os.path.join(ROOT, "models", "yunet.onnx"), 100000),
     "models/yunet.onnx (detector de rosto)")
line(fetch("https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf", os.path.join(ROOT, "fonts", "Anton-Regular.ttf"), 50000) or None,
     "fonts/Anton-Regular.ttf (legendas)", "" if os.path.exists(os.path.join(ROOT, "fonts", "Anton-Regular.ttf")) else "sem ela usa Impact/Arial/DejaVu do sistema")
if not CHECK:
    subprocess.run([sys.executable, os.path.join(HERE, "make_luts.py")], capture_output=True)
n_lut = len([f for f in os.listdir(os.path.join(ROOT, "luts")) if f.endswith(".cube")]) if os.path.isdir(os.path.join(ROOT, "luts")) else 0
line(n_lut > 0, f"luts/*.cube ({n_lut})", "" if n_lut else "python scripts/make_luts.py")
print("FFmpeg:")
ff = shutil.which("ffmpeg"); line(bool(ff and shutil.which("ffprobe")), "ffmpeg + ffprobe no PATH", ff or "veja INSTALL.md")
if ff:
    flt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    encs = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    line(" libx264 " in encs, "encoder libx264 (obrigatorio como reserva)")
    for name, why in (("rubberband", "voz mais grave com timbre natural (sem ele usa metodo alternativo)"), ("lut3d", "LUT direto no ffmpeg (opcional)"),
                      ("subtitles", "legendas .ass via libass (opcional)"), ("xfade", "transicoes entre clipes (opcional)"), ("frei0r", "plugins de efeito frei0r (opcional)")):
        line(True if f" {name} " in flt else None, f"filtro {name}", "" if f" {name} " in flt else why)

    def works(enc):
        return subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2", "-c:v", enc, "-f", "null", "-"], capture_output=True).returncode == 0
    gpu = "nvenc (NVIDIA)" if works("h264_nvenc") else ("videotoolbox (Apple)" if works("h264_videotoolbox") else None)
    line(True if gpu else None, "codificacao por GPU", gpu or "nao disponivel - o render usa libx264 (CPU), so fica mais lento")
print("\nTUDO CERTO - teste com: python scripts/selftest.py" if ok_all else "\nHa itens em FALTA acima. Veja INSTALL.md.")
sys.exit(0 if ok_all else 1)
