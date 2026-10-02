# -*- coding: utf-8 -*-
"""Extrai o ESTILO DE EDICAO de um criativo de referencia.

Uso:
  python scripts/extract_style.py referencia.mp4 --out estilo_ref [--transcribe] [--lang pt]

Gera na pasta de saida:
  style.json      medidas: ritmo de cortes, layouts, niveis de zoom, movimentos de camera, foco, transicoes, cor, audio
  REPORT.md       resumo legivel + lista do que o agente precisa CONFIRMAR olhando as imagens
  sheet_NN.jpg    folhas de contato (1 frame por segundo, com tempo)
  trans_NN_T.jpg  14 frames em volta de cada transicao (para classificar o efeito)
  spec.png        espectrograma do audio
  track.json      medidas quadro a quadro (rosto, nitidez, diferenca entre frames)

As classificacoes ('layout', 'kind') sao PALPITES por heuristica. Quem decide e o agente, olhando as tiras.
"""
import argparse, json, math, os, re, statistics as st, subprocess, sys, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def r3(v):
    return None if v is None else round(float(v), 3)


def med(xs, default=None):
    xs = [x for x in xs if x is not None]
    return float(st.median(xs)) if xs else default


def font(sz):
    for f in (os.path.join(ROOT, "fonts", "Anton-Regular.ttf"), "arialbd.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except Exception:
            pass
    return ImageFont.load_default()


# ---------------------------------------------------------------- passagem 1: medidas por frame
def pass1(path):
    cap = cv2.VideoCapture(path); fps = cap.get(5) or 30; W = int(cap.get(3)); H = int(cap.get(4)); n = int(cap.get(7))
    sw = 360; sh = int(round(H * sw / W / 2)) * 2; det = None
    model = os.path.join(ROOT, "models", "yunet.onnx")
    if os.path.exists(model):
        det = cv2.FaceDetectorYN.create(model, "", (sw, sh), 0.6, 0.3, 50)
    else:
        print("aviso: models/yunet.onnx nao encontrado (rode scripts/setup.py) - sem medidas de rosto/camera")
    rows = []; prev = None; a, b = int(sh * 0.45), int(sh * 0.55)
    for i in range(n):
        ok, fr = cap.read()
        if not ok:
            break
        sm = cv2.resize(fr, (sw, sh), interpolation=cv2.INTER_AREA); g = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            d = cv2.absdiff(g, prev); da, dt_, db = float(d.mean()), float(d[:a].mean()), float(d[b:].mean())
        else:
            da = dt_ = db = 0.0
        prev = g
        hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
        row = dict(i=i, t=round(i / fps, 3), d=round(da, 2), dtop=round(dt_, 2), dbot=round(db, 2), luma=round(float(g.mean()), 1),
                   sat=round(float(hsv[..., 1].mean()), 1), sharp=round(float(cv2.Laplacian(g, cv2.CV_64F).var()), 1),
                   white=round(float((g > 245).mean()), 4), rowjump=round(float(np.abs(np.diff(g.mean(1))).mean()), 2),
                   cx=None, cy=None, w=None, fsharp=None)
        if det is not None:
            _, f = det.detect(sm)
            if f is not None and len(f):
                bb = max(f, key=lambda x: x[2] * x[3]); x, y, w, h = [int(v) for v in bb[:4]]
                roi = g[max(0, y):y + h, max(0, x):x + w]
                row.update(cx=round(float(bb[0] + bb[2] / 2) / sw, 4), cy=round(float(bb[1] + bb[3] / 2) / sh, 4), w=round(float(bb[2]) / sw, 4),
                           fsharp=round(float(cv2.Laplacian(roi, cv2.CV_64F).var()), 1) if roi.size else None)
        rows.append(row)
    cap.release()
    return rows, dict(w=W, h=H, fps=round(fps, 3), frames=len(rows), dur=round(len(rows) / fps, 2))


# ---------------------------------------------------------------- eventos (cortes / transicoes)
def find_events(rows, fps):
    d = np.array([r["d"] for r in rows]); thr = max(9.0, float(np.median(d)) * 4)
    db = np.array([r["dbot"] for r in rows]); dtp = np.array([r["dtop"] for r in rows])
    act = (d > thr) | ((db > thr * 1.3) & (dtp < thr * 0.5))
    ev = []; i = 0; N = len(rows)
    while i < N:
        if not act[i]:
            i += 1; continue
        j = i
        while j + 1 < N and (act[j + 1] or (j + 2 < N and act[j + 2]) or (j + 3 < N and act[j + 3])):
            j += 1
        while not act[j]:
            j -= 1
        ev.append((i, j)); i = j + 1
    sharp_med = float(np.median([r["sharp"] for r in rows])) or 1.0; rj_med = float(np.median([r["rowjump"] for r in rows])) or 1.0
    sat_med = float(np.median([r["sat"] for r in rows])) or 1.0
    out = []
    for a, b in ev:
        win = rows[max(0, a - 2):min(N, b + 3)]; core = rows[a:b + 1]; pk = max(core, key=lambda r: r["d"])
        bottom_only = float(np.mean([r["dtop"] for r in core])) < thr * 0.5 and float(np.max([r["dbot"] for r in core])) > thr
        m = dict(frames=b - a + 1, luma_swing=round(max(r["luma"] for r in win) - min(r["luma"] for r in win), 1),
                 sat_min_ratio=round(min(r["sat"] for r in win) / sat_med, 2), white_max=round(max(r["white"] for r in win), 3),
                 rowjump_ratio=round(max(r["rowjump"] for r in win) / rj_med, 2), sharp_min_ratio=round(min(r["sharp"] for r in win) / sharp_med, 2),
                 peak_diff=pk["d"])
        if bottom_only:
            kind = "bsw"
        elif m["frames"] <= 2 and m["luma_swing"] < 25 and m["sharp_min_ratio"] > 0.5:
            kind = "corte"
        elif m["white_max"] > 0.45 and m["frames"] <= 7 and m["sat_min_ratio"] > 0.5:
            kind = "flash"
        elif m["luma_swing"] >= 45 or m["sat_min_ratio"] < 0.45:
            kind = "B"
        elif m["rowjump_ratio"] >= 2.2:
            kind = "D" if m["white_max"] > 0.03 else "C"
        elif m["sharp_min_ratio"] < 0.35:
            kind = "A"
        else:
            kind = "corte"
        out.append(dict(t=pk["t"], frame=pk["i"], f0=a, f1=b, region="bottom" if bottom_only else "full", kind_guess=kind, metrics=m))
    return out, thr


# ---------------------------------------------------------------- segmentos, camera, foco
def analyse_segments(rows, events, info):
    fps = info["fps"]; N = len(rows); cuts = [e for e in events if e["region"] == "full"]
    bounds = [0] + [e["frame"] for e in cuts] + [N]; segs = []; fx_end = {e["frame"]: e["f1"] for e in cuts}
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b - a < 3:
            continue
        rr = rows[a:b]; fc = [r for r in rr if r["w"]]; share = len(fc) / len(rr); a1 = fx_end.get(a, a)      # a1 = ultimo frame do efeito de entrada
        nb = sum(1 for e in events if e["region"] == "bottom" and a <= e["frame"] < b)
        s = dict(s=round(a / fps, 2), e=round(b / fps, 2), dur=round((b - a) / fps, 2), face_share=round(share, 2), bsw=nb)
        if share < 0.3:
            s["layout_guess"] = "broll"
        else:
            cy = med([r["cy"] for r in fc]); s["face_cy"] = r3(cy); s["face_w"] = r3(med([r["w"] for r in fc])); s["face_cx"] = r3(med([r["cx"] for r in fc]))
            s["layout_guess"] = "split" if (cy < 0.27 or nb > 0) else "full"
            body = fc[6:] if len(fc) > 14 else fc; wmed = med([r["w"] for r in body])
            if len(fc) > 14 and wmed:
                post = [r for r in fc if r["i"] > a1] or fc
                s["overshoot_pct"] = r3((max(r["w"] for r in post[:3]) - wmed) / wmed * 100)
                xs = np.array([r["i"] for r in body], float); ys = np.array([r["w"] for r in body], float)
                s["drift_pct"] = r3(np.polyfit(xs, ys, 1)[0] * (xs[-1] - xs[0]) / wmed * 100)
                cxs = np.array([r["cx"] for r in fc]); k = min(15, len(cxs) // 2 * 2 - 1)
                if k >= 3:
                    sm = np.convolve(cxs, np.ones(k) / k, "same"); s["shake_px"] = r3(float(np.std((cxs - sm)[k:-k])) * 1080 if len(cxs) > 3 * k else None)
                s["pan_amp"] = r3((np.percentile(cxs, 95) - np.percentile(cxs, 5)) / 2)
                s["end_push_pct"] = r3((med([r["w"] for r in fc[-4:]]) - wmed) / wmed * 100)
                fs = [r["fsharp"] for r in fc if r["fsharp"]]; fm = med(fs)
                if fm:
                    k2 = next((r["i"] for r in post[:24] if r["fsharp"] and r["fsharp"] >= 0.8 * fm), None)
                    s["focus_settle_s"] = r3((k2 - a1) / fps) if k2 is not None else None
        segs.append(s)
    return segs


def levels(vals, tol=0.035):
    vals = sorted(v for v in vals if v); out = []
    for v in vals:
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [dict(face_w=r3(st.median(g)), n=len(g)) for g in out]


# ---------------------------------------------------------------- audio
def analyse_audio(path, out, events, dur):
    wav = os.path.join(out, "_audio.wav")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", wav], capture_output=True)
    if r.returncode or not os.path.exists(wav):
        return dict(present=False)
    w = wave.open(wav); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768; w.close()
    nf, hop = 1024, 512; win = np.hanning(nf); nfr = max(1, (len(x) - nf) // hop)
    idx = np.arange(nf)[None, :] + hop * np.arange(nfr)[:, None]; S = np.abs(np.fft.rfft(x[idx] * win, axis=1)); fr = np.fft.rfftfreq(nf, 1 / sr); tt = (np.arange(nfr) * hop + nf / 2) / sr

    def band(lo, hi):
        return np.sqrt((S[:, (fr >= lo) & (fr < hi)] ** 2).mean(1))

    lf, vo, hf = band(30, 220), band(300, 3400), band(5000, 10000)
    speech = vo > 0.15 * np.percentile(vo, 90); frm = np.sqrt((x[idx] ** 2).mean(1))
    last = float(tt[np.where(speech)[0][-1]]) if speech.any() else 0.0; gaps = (~speech) & (tt < last)
    res = dict(present=True, speech_end=round(last, 2), tail_s=round(dur - last, 2),
               voice_rms=r3(frm[speech].mean()) if speech.any() else None, gap_rms=r3(frm[gaps].mean()) if gaps.sum() > 5 else None,
               tail_rms=r3(frm[tt > last + 0.3].mean()) if (tt > last + 0.3).sum() > 5 else None,
               lf_share_in_gaps=r3((lf[gaps].mean() / (vo[gaps].mean() + 1e-9))) if gaps.sum() > 5 else None)
    res["bed_guess"] = bool((res["gap_rms"] or 0) > 0.012 or (res["tail_rms"] or 0) > 0.012)
    for e in events:
        m = (tt > e["t"] - 0.3) & (tt < e["t"] + 0.3); nb = (tt > e["t"] - 3) & (tt < e["t"] + 3)
        if m.any() and nb.any():
            e["sfx"] = dict(hf_ratio=r3(hf[m].max() / (np.median(hf[nb]) + 1e-9)), lf_ratio=r3(lf[m].max() / (np.median(lf[nb]) + 1e-9)))
            e["sfx"]["whoosh_guess"] = bool(e["sfx"]["hf_ratio"] >= 4); e["sfx"]["boom_guess"] = bool(e["sfx"]["lf_ratio"] >= 3)
    f0 = []; fl = int(sr * 0.04); lo, hi = int(sr / 300), int(sr / 60)
    for i in range(0, len(x) - fl, int(sr * 0.02)):
        seg = x[i:i + fl]
        if np.sqrt(np.mean(seg ** 2)) < 0.02:
            continue
        seg = seg - seg.mean(); ac = np.correlate(seg, seg, "full")[fl - 1:]; ac /= ac[0] + 1e-9; k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.5:
            f0.append(sr / k)
    if f0:
        res["voice_f0"] = dict(median=round(float(np.median(f0)), 1), p10=round(float(np.percentile(f0, 10)), 1), p90=round(float(np.percentile(f0, 90)), 1))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, errors="ignore")
    m = re.findall(r"I:\s+(-?\d+\.\d+) LUFS", r.stderr)
    if m:
        res["lufs"] = float(m[-1])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-lavfi", "showspectrumpic=s=1600x500:legend=1:fscale=log", "-frames:v", "1", "-update", "1",
                    os.path.join(out, "spec.png")], capture_output=True)
    os.remove(wav)
    return res


# ---------------------------------------------------------------- imagens (folhas de contato e tiras de transicao)
def make_images(path, out, info, events, max_strips=48):
    fps = info["fps"]; N = info["frames"]; step = max(1, int(round(fps * max(1.0, info["dur"] / 150))))
    sheet_idx = list(range(0, N, step)); ev = sorted(events, key=lambda e: -e["metrics"]["peak_diff"])[:max_strips]; ev = sorted(ev, key=lambda e: e["frame"])
    strip_of = {}
    for k, e in enumerate(ev):
        for j in range(e["frame"] - 5, e["frame"] + 9):
            if 0 <= j < N:
                strip_of.setdefault(j, []).append(k)
    need = set(sheet_idx) | set(strip_of); cap = cv2.VideoCapture(path); tw = 216; th = int(info["h"] * tw / info["w"]); thumbs = {}; i = 0; last = max(need)
    while i <= last:
        if i in need:
            ok, fr = cap.read()
            if not ok:
                break
            thumbs[i] = cv2.cvtColor(cv2.resize(fr, (tw, th), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        else:
            cap.grab()
        i += 1
    cap.release(); f = font(18); files = []
    cols, rws = 6, 4; per = cols * rws
    for s in range(0, len(sheet_idx), per):
        chunk = sheet_idx[s:s + per]; im = Image.new("RGB", (cols * tw, rws * (th + 24)), "black"); d = ImageDraw.Draw(im)
        for k, fi in enumerate(chunk):
            if fi not in thumbs:
                continue
            x, y = (k % cols) * tw, (k // cols) * (th + 24); im.paste(Image.fromarray(thumbs[fi]), (x, y + 24)); d.text((x + 4, y + 2), f"{fi / fps:.1f}s", font=f, fill="yellow")
        name = f"sheet_{s // per + 1:02d}.jpg"; im.save(os.path.join(out, name), quality=82); files.append(name)
    for k, e in enumerate(ev):
        idxs = [j for j in range(e["frame"] - 5, e["frame"] + 9) if j in thumbs]
        if not idxs:
            continue
        sw = 154; sh2 = int(th * sw / tw); im = Image.new("RGB", (len(idxs) * sw, sh2 + 22), "black"); d = ImageDraw.Draw(im)
        for q, j in enumerate(idxs):
            im.paste(Image.fromarray(thumbs[j]).resize((sw, sh2)), (q * sw, 22)); rel = j - e["frame"]
            d.text((q * sw + 4, 2), f"{rel:+d}" if rel else f"0 ({e['t']:.2f}s)", font=f, fill="red" if rel == 0 else "yellow")
        name = f"trans_{k + 1:02d}_{e['t']:.2f}.jpg"; im.save(os.path.join(out, name), quality=85); e["strip"] = name
    return files


def look_stats(path, info):
    cap = cv2.VideoCapture(path); N = info["frames"]; vals = []
    for i in np.linspace(0, N - 1, min(40, N)).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, fr = cap.read()
        if not ok:
            continue
        fr = cv2.resize(fr, (180, 320)); g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32); hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
        corner = np.mean([g[:40, :30].mean(), g[:40, -30:].mean(), g[-40:, :30].mean(), g[-40:, -30:].mean()]); center = g[100:220, 50:130].mean()
        hp = g - cv2.GaussianBlur(g, (0, 0), 1.2)
        vals.append((1 - corner / (center + 1e-6), hsv[..., 1].mean(), np.percentile(g, 95) - np.percentile(g, 5), float(np.median(np.abs(hp))), *fr.reshape(-1, 3).mean(0)))
    cap.release()
    if not vals:
        return {}
    v = np.median(np.array(vals), 0)
    return dict(vignette_est=r3(v[0]), saturation=r3(v[1]), contrast_p5_p95=r3(v[2]), grain_est=r3(v[3]), mean_bgr=[r3(v[4]), r3(v[5]), r3(v[6])])


# ---------------------------------------------------------------- relatorio
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("--out", default=None); ap.add_argument("--transcribe", action="store_true"); ap.add_argument("--lang", default=None)
    a = ap.parse_args(); out = a.out or os.path.splitext(a.video)[0] + "_estilo"; os.makedirs(out, exist_ok=True)
    print("1/4 medindo frames..."); rows, info = pass1(a.video); info["file"] = os.path.basename(a.video)
    events, thr = find_events(rows, info["fps"]); segs = analyse_segments(rows, events, info)
    print("2/4 audio..."); audio = analyse_audio(a.video, out, events, info["dur"])
    print("3/4 imagens..."); sheets = make_images(a.video, out, info, events); look = look_stats(a.video, info)
    json.dump([[r[k] for k in ("i", "t", "cx", "cy", "w", "fsharp", "d", "dtop", "dbot", "luma", "sat", "sharp")] for r in rows], open(os.path.join(out, "track.json"), "w"))
    full = [s for s in segs if s["layout_guess"] == "full"]; split = [s for s in segs if s["layout_guess"] == "split"]; brl = [s for s in segs if s["layout_guess"] == "broll"]
    tot = sum(s["dur"] for s in segs) or 1; mix = {}
    for e in events:
        mix[e["kind_guess"]] = mix.get(e["kind_guess"], 0) + 1
    nbsw = sum(1 for e in events if e["kind_guess"] == "bsw"); split_t = sum(s["dur"] for s in split)
    lv = levels([s.get("face_w") for s in full])
    cam = dict(full_face_w_levels=lv, split_face_w=r3(med([s.get("face_w") for s in split])), split_face_cy=r3(med([s.get("face_cy") for s in split])),
               full_face_cy=r3(med([s.get("face_cy") for s in full])), overshoot_pct=r3(med([s.get("overshoot_pct") for s in full])),
               drift_pct_full=r3(med([s.get("drift_pct") for s in full])), end_push_pct=r3(med([s.get("end_push_pct") for s in full])),
               split_pan_amp=r3(med([s.get("pan_amp") for s in split])), shake_px=r3(med([s.get("shake_px") for s in segs])),
               focus_settle_s=r3(med([s.get("focus_settle_s") for s in segs])))
    style = dict(source=info,
                 pacing=dict(blocks=len(segs), block_avg_s=r3(tot / max(1, len(segs))), block_med_s=r3(med([s["dur"] for s in segs])),
                             transitions_per_min=r3(len([e for e in events if e["region"] == "full"]) / info["dur"] * 60),
                             broll_swap_every_s=r3(split_t / (nbsw + len(split))) if split else None),
                 layouts=dict(split_share=r3(split_t / tot), full_share=r3(sum(s["dur"] for s in full) / tot), broll_share=r3(sum(s["dur"] for s in brl) / tot)),
                 camera=cam, fx_mix=mix, look=look, audio=audio, segments=segs, transitions=events, diff_threshold=r3(thr))
    if a.transcribe:
        print("4/4 transcrevendo...")
        import transcribe as T
        words = T.transcribe(a.video, lang=a.lang); json.dump(words, open(os.path.join(out, "words.json"), "w", encoding="utf-8"), ensure_ascii=False)
        open(os.path.join(out, "transcricao.txt"), "w", encoding="utf-8").write(" ".join(w["w"] for w in words))
        if words:
            style["speech"] = dict(words=len(words), words_per_s=r3(len(words) / max(1e-3, words[-1]["e"] - words[0]["s"])))
    json.dump(style, open(os.path.join(out, "style.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = [f"# Estilo de edicao - {info['file']}", "",
         f"- video: {info['w']}x{info['h']} {info['fps']} fps, {info['dur']} s",
         f"- blocos: {len(segs)} (media {style['pacing']['block_avg_s']} s) | transicoes de quadro inteiro por minuto: {style['pacing']['transitions_per_min']}",
         f"- layouts (palpite): tela dividida {style['layouts']['split_share']:.0%}, apresentador em tela cheia {style['layouts']['full_share']:.0%}, so b-roll {style['layouts']['broll_share']:.0%}",
         f"- troca de b-roll a cada ~{style['pacing']['broll_swap_every_s']} s" if split else "- sem tela dividida detectada",
         f"- niveis de zoom em tela cheia (largura do rosto / largura do quadro): {', '.join(str(x['face_w']) + ' (x' + str(x['n']) + ')' for x in lv) or 'n/d'}",
         f"- tela dividida: rosto com largura {cam['split_face_w']} na altura {cam['split_face_cy']}; balanco lateral +-{cam['split_pan_amp']}",
         f"- camera: estouro de escala na entrada {cam['overshoot_pct']}%, deriva no bloco {cam['drift_pct_full']}%, empurrao no fim {cam['end_push_pct']}%, tremor {cam['shake_px']} px, foco assenta em {cam['focus_settle_s']} s "
         "(medido DEPOIS do fim de cada efeito; o estouro de zoom e a retomada de foco costumam acontecer dentro da propria transicao - veja as tiras)",
         f"- cor: {look}", "- audio: " + json.dumps(audio, ensure_ascii=False),
         f"- mistura de efeitos (palpite): {mix}", "", "## Transicoes (confirme olhando cada tira)", "",
         "| # | t (s) | frames | palpite | variacao de luz | nitidez min | salto de linhas | whoosh | boom | tira |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, e in enumerate(events):
        m = e["metrics"]; sx = e.get("sfx", {})
        L.append(f"| {k + 1} | {e['t']:.2f} | {m['frames']} | {e['kind_guess']} | {m['luma_swing']} | {m['sharp_min_ratio']} | {m['rowjump_ratio']} | "
                 f"{'sim' if sx.get('whoosh_guess') else '-'} | {'sim' if sx.get('boom_guess') else '-'} | {e.get('strip', '-')} |")
    L += ["", "## Blocos", "", "| inicio | fim | layout (palpite) | largura do rosto | altura do rosto | trocas de b-roll |", "|---|---|---|---|---|---|"]
    L += [f"| {s['s']} | {s['e']} | {s['layout_guess']} | {s.get('face_w', '-')} | {s.get('face_cy', '-')} | {s['bsw']} |" for s in segs]
    L += ["", "## O que o agente precisa confirmar olhando as imagens", "",
          f"1. Folhas de contato ({', '.join(sheets)}): layout real de cada bloco, estilo da legenda (posicao, fonte, cor de destaque, palavras por tela), faixas/banners, cartao final.",
          "2. Tiras `trans_*.jpg`: qual preset cada transicao parece (A prisma/zoom-blur, B estrobo solarizado, C glitch, D rasgo, flash, whip, punch, shake, leak, vhs, dip, corte seco) "
          "- ou se e um efeito novo que merece um plugin em `plugins/`.",
          "3. `spec.png`: base grave continua (faixa escura constante embaixo), whoosh (riscos verticais em alta frequencia) e booms (manchas em baixa) nos tempos das transicoes.",
          "4. Depois de confirmar, grave as correcoes em `style.json` (campos `layout`, `kind`) e use `make_plan.py --style` para aplicar o estilo num roteiro novo."]
    open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("ok ->", out); print("\n".join(L[:14]))


if __name__ == "__main__":
    sys.path.insert(0, HERE); main()
