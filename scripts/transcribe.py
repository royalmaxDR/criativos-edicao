# -*- coding: utf-8 -*-
"""Tempos palavra a palavra de um audio/video (faster-whisper). Base das legendas e dos cortes.

Uso: python scripts/transcribe.py vo.wav --out words.json [--lang pt] [--model small]
Saida: [{"w": "palavra,", "s": 0.00, "e": 0.22}, ...]
"""
import argparse, json


def transcribe(path, lang=None, model="small"):
    from faster_whisper import WhisperModel
    try:
        m = WhisperModel(model, device="cuda", compute_type="float16")
        segs, _ = m.transcribe(path, language=lang, word_timestamps=True, vad_filter=True); segs = list(segs)
    except Exception:                                                     # sem CUDA/cuBLAS: CPU resolve (1 min de audio ~ 20 s)
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(path, language=lang, word_timestamps=True, vad_filter=True); segs = list(segs)
    return [dict(w=w.word.strip(), s=round(w.start, 2), e=round(w.end, 2)) for s in segs for w in (s.words or []) if w.word.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("media"); ap.add_argument("--out", default="words.json"); ap.add_argument("--lang"); ap.add_argument("--model", default="small")
    a = ap.parse_args(); words = transcribe(a.media, a.lang, a.model)
    json.dump(words, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(words), "palavras ->", a.out); print(" ".join(w["w"] for w in words))
