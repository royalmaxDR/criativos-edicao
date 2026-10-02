# -*- coding: utf-8 -*-
"""Busca imagens de b-roll em DOMINIO PUBLICO / CC0 no Wikimedia Commons (sem chave de API) e baixa as melhores.

Uso:
  python scripts/broll_commons.py --out broll "q01=Qumran caves" "q02=Dead Sea Scrolls jar" "q03=gold coins pile"
  python scripts/broll_commons.py --out broll --file buscas.json        # {"q01": "Qumran caves", ...}
Opcoes: --per 3 (candidatos por busca)  --min-width 900  --any-license (aceita CC-BY/CC-BY-SA: exige credito ao autor!)

Saida: broll/<chave>_<n>.jpg + broll/_fontes.json (titulo, licenca e pagina de cada imagem - guarde para comprovar a origem)
       broll/_previa.jpg (grade com todos os candidatos para escolher olhando)
Dica: buscas em ingles e com o nome da obra/autor acham muito mais ("Guido Reni Saint Michael" > "anjo").
"""
import argparse, json, os, re, sys
import requests

UA = {"User-Agent": "criativos-edicao/1.0 (b-roll em dominio publico; uso local)"}
API = "https://commons.wikimedia.org/w/api.php"


def search(q, per, min_w, any_lic):
    r = requests.get(API, params=dict(action="query", generator="search", gsrsearch=q + " filetype:bitmap", gsrnamespace=6, gsrlimit=20, prop="imageinfo",
                                      iiprop="url|size|extmetadata", iiurlwidth=1280, format="json"), headers=UA, timeout=30).json()
    c = []
    for p in (r.get("query", {}).get("pages", {}) or {}).values():
        ii = p["imageinfo"][0]; lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
        free = bool(re.search(r"public domain|cc0|\bpd\b", lic, re.I))
        if not free and not (any_lic and re.search(r"cc[ -]by", lic, re.I)):
            continue
        if ii["width"] < min_w or not ii.get("thumburl"):
            continue
        c.append(dict(rank=p.get("index", 99), title=p["title"], w=ii["width"], h=ii["height"], license=lic, url=ii["thumburl"], page=ii.get("descriptionurl"),
                      author=re.sub("<[^>]+>", "", ii.get("extmetadata", {}).get("Artist", {}).get("value", ""))[:80], needs_credit=not free))
    c.sort(key=lambda x: x["rank"])
    return c[:per]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("queries", nargs="*"); ap.add_argument("--file"); ap.add_argument("--out", default="broll"); ap.add_argument("--per", type=int, default=3)
    ap.add_argument("--min-width", type=int, default=900); ap.add_argument("--any-license", action="store_true")
    a = ap.parse_args(); qs = {}
    if a.file:
        qs.update(json.load(open(a.file, encoding="utf-8")))
    for i, q in enumerate(a.queries):
        k, _, v = q.partition("="); qs[k if v else f"q{i + 1:02d}"] = v or k
    if not qs:
        sys.exit("informe ao menos uma busca")
    os.makedirs(a.out, exist_ok=True); src_file = os.path.join(a.out, "_fontes.json")
    fontes = json.load(open(src_file, encoding="utf-8")) if os.path.exists(src_file) else {}; got = []
    for key, q in qs.items():
        try:
            c = search(q, a.per, a.min_width, a.any_license)
        except Exception as e:
            print(key, "erro na busca:", e); continue
        print(f"{key}: {q} -> {len(c)} imagem(ns)")
        for k, it in enumerate(c):
            fn = os.path.join(a.out, f"{key}_{k}.jpg")
            try:
                open(fn, "wb").write(requests.get(it["url"], headers=UA, timeout=60).content)
            except Exception as e:
                print("    erro ao baixar:", e); continue
            fontes[os.path.basename(fn)] = dict(query=q, **{x: it[x] for x in ("title", "license", "author", "page", "needs_credit")}); got.append(fn)
            print(f"    {os.path.basename(fn)}  {it['w']}x{it['h']}  {it['license']}{'  (EXIGE CREDITO)' if it['needs_credit'] else ''}")
    json.dump(fontes, open(src_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try:
        from PIL import Image, ImageDraw
        tw, th, cols = 240, 240, 6; rows = (len(got) + cols - 1) // cols
        if got:
            sheet = Image.new("RGB", (cols * tw, rows * (th + 20)), "black"); d = ImageDraw.Draw(sheet)
            for i, fn in enumerate(got):
                im = Image.open(fn).convert("RGB"); im.thumbnail((tw, th)); x, y = (i % cols) * tw, (i // cols) * (th + 20)
                sheet.paste(im, (x, y + 20)); d.text((x + 4, y + 3), os.path.basename(fn), fill="yellow")
            sheet.save(os.path.join(a.out, "_previa.jpg"), quality=80); print("previa ->", os.path.join(a.out, "_previa.jpg"))
    except Exception as e:
        print("sem previa:", e)


if __name__ == "__main__":
    main()
