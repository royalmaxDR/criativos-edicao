# -*- coding: utf-8 -*-
"""Casa o b-roll com a fala e acelera as trocas de imagem de um plano ja criado pelo make_plan.py.

Uso:
  python scripts/assign_broll.py plan.json --map mapa.json --broll pasta_broll [--max-shot 2.4] [--exclude a,b,c]

mapa.json: lista ordenada de [palavra-ou-frase, imagem]  (imagem = nome do arquivo sem extensao, ou "WAVE" para as ondas sonoras)
  [["buraco negro", "n03_0"], ["frequência", "WAVE"], ["moisés", "n09_0"]]
Para cada segmento com b-roll (layouts split e broll), usa a primeira entrada do mapa cuja palavra aparece no campo "say";
se nenhuma aparecer, pega a proxima imagem da pasta. Nunca repete a mesma imagem em seguida.
--max-shot: segmento mais longo que isso (s) e dividido em dois, com outra imagem e a transicao "bsw" no meio (mais dinamica).
O mapa em outra lingua serve para a versao traduzida: mesma pasta de imagens, palavras-chave do idioma novo.
"""
import argparse, glob, json, os, re

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("plan"); ap.add_argument("--map"); ap.add_argument("--broll", required=True); ap.add_argument("--max-shot", dest="max_shot", type=float, default=2.4)
ap.add_argument("--exclude", default="", help="imagens que nao devem ser usadas (nomes sem extensao, separados por virgula)")
a = ap.parse_args()
norm = lambda s: re.sub(r"[^\w ]", "", s.lower())
P = json.load(open(a.plan, encoding="utf-8")); base = os.path.dirname(os.path.abspath(a.plan))
M = json.load(open(a.map, encoding="utf-8")) if a.map else []
bad = {x.strip() for x in a.exclude.split(",") if x.strip()}
bdir = a.broll if os.path.isabs(a.broll) else os.path.join(base, a.broll) if os.path.isdir(os.path.join(base, a.broll)) else a.broll
files = {os.path.splitext(os.path.basename(f))[0]: f for f in sorted(glob.glob(os.path.join(bdir, "*")))
         if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov")) and not os.path.basename(f).startswith("_")}
pool = [k for k in files if k not in bad]
if not pool:
    raise SystemExit("nenhuma midia de b-roll em " + bdir)
rel = lambda k: "gen:wave" if k == "WAVE" else os.path.relpath(files[k], base).replace(os.sep, "/")
used = []; last = None; k = 0; hits = 0
for s in P["segments"]:
    if s.get("layout") not in ("split", "broll") or s.get("sync"):
        continue
    say = norm(s.get("say", "")); pick = None
    for key, img in M:
        if norm(key) in say and img != last and (img == "WAVE" or (img in files and img not in bad and img not in used[-2:])):
            pick = img; hits += 1; break
    if not pick:
        while pool[k % len(pool)] == last or (len(pool) > 5 and pool[k % len(pool)] in used[-4:]):
            k += 1
        pick = pool[k % len(pool)]; k += 1
    s["broll"] = rel(pick); used.append(pick); last = pick
out = []; fx = {round(t, 2): v for t, v in P.get("fx", [])}; e = 0; cuts = 0
for s in P["segments"]:
    d = s["e"] - s["s"]
    if s.get("layout") in ("split", "broll") and not s.get("sync") and d > a.max_shot and s.get("broll") != "gen:wave":
        m = round(s["s"] + d / 2, 2); x = dict(s, e=m); y = dict(s, s=m)
        while rel(pool[e % len(pool)]) == s["broll"]:
            e += 1
        y["broll"] = rel(pool[e % len(pool)]); y["kb"] = -s.get("kb", 1); e += 3; out += [x, y]; fx[m] = "bsw"; cuts += 1
    else:
        out.append(s)
P["segments"] = out; P["fx"] = sorted([[t, v] for t, v in fx.items()])
json.dump(P, open(a.plan, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
n = sum(1 for s in out if s.get("layout") in ("split", "broll"))
print(f"{len(out)} segmentos ({n} com b-roll, {hits} casados pelo mapa, {cuts} divididos) | duracao media {out[-1]['e'] / len(out):.2f} s")
