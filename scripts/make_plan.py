# -*- coding: utf-8 -*-
"""Monta o rascunho do plano de edicao (plan.json) a partir da narracao e de um estilo.

Uso:
  python scripts/make_plan.py --words words.json --voice vo.wav --avatar avatar.mp4 --broll broll --style cinematico_revelacao --name "MEU-CRIATIVO v1" --out plan.json
  python scripts/make_plan.py ... --style pasta_da_referencia/style.json      # estilo extraido por extract_style.py
  python scripts/make_plan.py --list-styles

O rascunho corta nos limites de frase, alterna os layouts no ritmo do estilo, sorteia os efeitos de cada tipo de passagem
e distribui o b-roll em ordem. Cada segmento leva o campo "say" (o que e dito ali): o agente deve trocar o b-roll para
casar com a fala, ajustar palavras de destaque e conferir com  render.py --check  e  --preview.
"""
import argparse, glob, json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
P = ",.!?;:"
MEDIA = (".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mkv", ".webm")
KNOWN_FX = {"A", "B", "C", "D", "flash", "whip", "punch", "shake", "leak", "vhs", "dip"}


def load_style(ref):
    p = ref if os.path.exists(ref) else os.path.join(ROOT, "presets", "styles", ref + ".json")
    if not os.path.exists(p):
        sys.exit(f"estilo nao encontrado: {ref} (veja --list-styles)")
    s = json.load(open(p, encoding="utf-8"))
    return from_extracted(s) if "source" in s else s


def from_extracted(s):
    """Converte o style.json medido (extract_style.py) no formato de preset usado aqui."""
    pc, cam, lay = s["pacing"], s["camera"], s["layouts"]; segs = s.get("segments", [])
    lay_of = lambda x: x.get("layout") or x.get("layout_guess")
    full = sorted(x["dur"] for x in segs if lay_of(x) == "full") or [3.0]; swap = pc.get("broll_swap_every_s") or 2.2
    q = lambda xs, a: xs[min(len(xs) - 1, int(len(xs) * a))]
    lv = [x["face_w"] for x in cam.get("full_face_w_levels", []) if x.get("n", 1) >= 1] or [0.50, 0.58]
    shots = {}; seq = []
    for i, w in enumerate(sorted(lv)[:4]):
        nm = ["wide", "medium", "close", "xclose"][i if len(lv) > 2 else i + 1]; shots[nm] = dict(face_w=w); seq.append(nm)
    mix = {(e.get("kind") or e.get("kind_guess")): 0 for e in s.get("transitions", [])}
    for e in s.get("transitions", []):
        mix[e.get("kind") or e.get("kind_guess")] += 1
    pool = sorted((k for k in mix if k in KNOWN_FX), key=lambda k: -mix[k]) or ["A", "B"]
    has_split = lay.get("split_share", 0) > 0.08; only_broll = lay.get("broll_share", 0) > 0.7
    clamp = lambda v, lo, hi, d: d if v is None else max(lo, min(hi, v))
    return dict(
        name="extraido:" + s["source"].get("file", "?"), layouts=("broll",) if only_broll else (("split", "full") if has_split else ("full",)),
        pacing=dict(open_with="split" if has_split else ("broll" if only_broll else "full"), split_run_s=[swap * 2.2, swap * 4.2], broll_swap_s=[swap * 0.75, swap * 1.3],
                    full_run_s=[q(full, 0.5) * 1.2, q(full, 0.8) * 2], full_cut_s=[max(1.2, q(full, 0.25)), q(full, 0.75)]),
        shots=dict(sequence=[x for x in seq if x != "wide"] or seq, levels=shots, split=dict(face_w=cam.get("split_face_w") or 0.46)),
        fx={"split>full": pool, "full>full": pool, "full>split": [k for k in pool if k in ("D", "whip", "flash", "leak")] or pool, "split>split": ["bsw"], "broll>broll": ["bsw"],
            "broll>full": pool, "full>broll": pool, "split>broll": pool, "broll>split": pool},
        cta=dict(last_s=4.0, shot="wide", banner="TOQUE NO BOTÃO ABAIXO"),
        plan=dict(camera=dict(pan=clamp(cam.get("split_pan_amp"), 0, 0.06, 0.035),
                              split_face_y=clamp(cam.get("split_face_cy"), 0.14, 0.30, 0.20)),
                  look=dict(vignette=clamp((s.get("look", {}).get("vignette_est") or 0.3) * 1.6, 0, 0.85, 0.72)),
                  audio=dict(bed="synth" if s.get("audio", {}).get("bed_guess") else "none")))


def beats_from_words(words, max_len=3.4):
    """Frases (ate a pontuacao ou pausa > 0,35 s); frases longas sao partidas na palavra mais perto do meio."""
    ph = []; cur = []
    for i, w in enumerate(words):
        cur.append(w); nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or w["w"][-1:] in P or nxt["s"] - w["e"] > 0.35:
            ph.append(cur); cur = []
    out = []
    for g in ph:
        stack = [g]
        while stack:
            x = stack.pop(0)
            if x[-1]["e"] - x[0]["s"] > max_len and len(x) >= 4:
                mid = (x[0]["s"] + x[-1]["e"]) / 2; k = min(range(2, len(x) - 1), key=lambda j: abs(x[j]["s"] - mid)); stack = [x[:k], x[k:]] + stack
            else:
                out.append(x)
    return [dict(s=b[0]["s"], e=b[-1]["e"], text=" ".join(w["w"] for w in b), strong=b[-1]["w"][-1:] in ".!?") for b in out]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--words"); ap.add_argument("--voice"); ap.add_argument("--avatar"); ap.add_argument("--broll", help="pasta com imagens/videos de b-roll")
    ap.add_argument("--style", default="cinematico_revelacao"); ap.add_argument("--name", default="CRIATIVO v1"); ap.add_argument("--out", default="plan.json")
    ap.add_argument("--seed", type=int, default=21); ap.add_argument("--lut"); ap.add_argument("--no-end-card", action="store_true"); ap.add_argument("--list-styles", action="store_true")
    a = ap.parse_args()
    if a.list_styles:
        for p in sorted(glob.glob(os.path.join(ROOT, "presets", "styles", "*.json"))):
            s = json.load(open(p, encoding="utf-8")); print(f"{os.path.splitext(os.path.basename(p))[0]:26s} {s.get('desc', '')}")
        return
    if not a.words:
        sys.exit("--words e obrigatorio (gere com scripts/transcribe.py)")
    st = load_style(a.style); rng = random.Random(a.seed); words = json.load(open(a.words, encoding="utf-8")); beats = beats_from_words(words)
    out_dir = os.path.dirname(os.path.abspath(a.out)); rel = lambda p: os.path.relpath(os.path.abspath(p), out_dir).replace(os.sep, "/") if p else None
    end = words[-1]["e"] + 0.3
    if a.voice:
        import subprocess
        end = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice], capture_output=True, text=True).stdout.strip())
    pool = sorted(p for p in glob.glob(os.path.join(a.broll, "*")) if p.lower().endswith(MEDIA) and not os.path.basename(p).startswith("_")) if a.broll else []
    if not pool:
        print("aviso: nenhuma midia de b-roll - usando 'gen:wave' como marcador; troque depois")
    layouts = list(st.get("layouts", ("split", "full")))
    if not a.avatar:
        layouts = ["broll"]
    pc = st["pacing"]; mode = pc.get("open_with", layouts[0]); mode = mode if mode in layouts else layouts[0]
    for i, b in enumerate(beats):                                         # cada batida vai ate o inicio da proxima (corte um pouco antes da fala)
        b["s"] = 0.0 if i == 0 else round(max(beats[i - 1]["s"] + 0.3, b["s"] - 0.06), 2)
    for i, b in enumerate(beats):
        b["e"] = beats[i + 1]["s"] if i + 1 < len(beats) else round(end, 2)
    cta = st.get("cta") or {}; cta_from = None
    if cta.get("last_s") and a.avatar:
        k = next((i for i in range(len(beats) - 1, 0, -1) if end - beats[i]["s"] >= cta["last_s"] and beats[i - 1]["strong"]), None)
        cta_from = k if k and k > len(beats) // 2 else None
    segs = []; bi = 0; shot_i = 0; i = 0; n_main = cta_from if cta_from is not None else len(beats)
    shots = st.get("shots", {}); seq = shots.get("sequence") or ["medium", "close"]; lv = shots.get("levels") or {"wide": {"zoom": 1.0}, "medium": {"zoom": 1.18}, "close": {"zoom": 1.42}}

    def merged(lo):                                                       # junta batidas ate a duracao minima
        nonlocal i
        s = beats[i]["s"]; txt = []
        while i < n_main:
            txt.append(beats[i]["text"]); e = beats[i]["e"]; i += 1
            if e - s >= lo:
                break
        return s, e, " ".join(txt)

    while i < n_main:
        rmin, rmax = pc["split_run_s"] if mode in ("split", "broll") else pc["full_run_s"]; target = rng.uniform(rmin, rmax); run_s = beats[i]["s"]
        while i < n_main:
            if mode in ("split", "broll"):
                s, e, txt = merged(rng.uniform(*pc["broll_swap_s"])); seg = dict(s=s, e=e, layout=mode, broll=rel(pool[bi % len(pool)]) if pool else "gen:wave", say=txt); bi += 1
                if mode == "split" and shots.get("split"):
                    seg.update(shots["split"])
            else:
                s, e, txt = merged(rng.uniform(*pc["full_cut_s"])); nm = seq[shot_i % len(seq)]; shot_i += 1; seg = dict(s=s, e=e, layout="full", shot=nm, say=txt, **lv.get(nm, {"zoom": 1.2}))
            segs.append(seg)
            if e - run_s >= target and (beats[i - 1]["strong"] or e - run_s >= rmax * 1.3):
                break
        if len(layouts) > 1:
            mode = layouts[(layouts.index(mode) + 1) % len(layouts)]
    banners = []
    if cta_from is not None:
        s = beats[cta_from]["s"]; nm = cta.get("shot", "wide")
        segs.append(dict(s=s, e=round(end, 2), layout="full", shot=nm, say=" ".join(b["text"] for b in beats[cta_from:]), **lv.get(nm, {"zoom": 1.0})))
        if cta.get("banner"):
            banners.append(dict(s=round(s + 0.25, 2), e=round(end, 2), text=cta["banner"]))
    if segs and segs[-1]["e"] - segs[-1]["s"] < 0.8 and len(segs) > 1:      # sobra curta no fim: funde com o anterior
        last = segs.pop(); segs[-1]["e"] = last["e"]; segs[-1]["say"] += " " + last["say"]
    segs[-1]["e"] = round(end, 2)
    fx = []; rr = {}
    for a_, b_ in zip(segs[:-1], segs[1:]):
        key = f"{a_['layout']}>{b_['layout']}"; opts = st["fx"].get(key) or st["fx"].get("full>full") or ["A"]; k = rr.get(key, rng.randrange(len(opts))); rr[key] = k + 1
        fx.append([b_["s"], opts[k % len(opts)]])
    stop = set("para como mais muito quando porque então também sobre entre depois antes ainda apenas todos todas".split())
    keys = sorted({w["w"].strip(P).lower() for w in words if (len(w["w"].strip(P)) >= 7 or w["w"].strip(P).isdigit()) and w["w"].strip(P).lower() not in stop})
    plan = dict(name=a.name, size=[1080, 1920], fps=30, avatar=rel(a.avatar), voice=rel(a.voice), words=rel(a.words), segments=segs, fx=fx, banners=banners,
                captions=dict(mode="both", keywords=keys), seed=a.seed, _style=st.get("name"))
    for k, v in (st.get("plan") or {}).items():
        plan[k] = {**v, **plan.get(k, {})} if isinstance(v, dict) else v
    if a.lut:
        plan.setdefault("look", {})["lut"] = rel(a.lut) if os.path.exists(a.lut) else a.lut
    if a.no_end_card:
        plan["end_card"] = None
    json.dump(plan, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kinds = {}
    for _, k in fx:
        kinds[k] = kinds.get(k, 0) + 1
    print(f"plano -> {a.out}: {len(segs)} segmentos ({sum(1 for s in segs if s['layout'] == 'split')} divididos, {sum(1 for s in segs if s['layout'] == 'full')} tela cheia, "
          f"{sum(1 for s in segs if s['layout'] == 'broll')} b-roll), {len(fx)} transicoes {kinds}, duracao da fala {end:.2f}s")
    print("proximos passos: revisar 'broll' de cada segmento conforme o campo 'say'; python scripts/render.py", a.out, "--check ; depois --preview 0-12")


if __name__ == "__main__":
    main()
