#!/usr/bin/env python3
"""Seleciona os anuncios mais antigos (ou mais impressos) do JSON gerado por collect_ads.js e baixa video/poster.

Uso:
  python fetch_media.py ads.json --top 10 --sort oldest --out baixados          # baixa os 10 ativos ha mais tempo
  python fetch_media.py ads.json --top 20 --sort impressions --posters-only --out thumbs
Os videos baixados saem SEM metadados (ffmpeg -c copy -map_metadata -1) e nomeados <library_id>.mp4.
Anuncios duplicados (mesmo video em mais de um anuncio) sao agrupados: baixa-se um so.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def asset_key(ad):
    """Chave de duplicidade: asset id embutido na URL (param efg) ou a propria URL sem query."""
    import base64
    src = ad.get("src") or ad.get("poster") or ""
    m = re.search(r"[?&]efg=([^&]+)", src)
    if m:
        try:
            s = m.group(1).replace("%3D", "=").replace("-", "+").replace("_", "/")
            s += "=" * (-len(s) % 4)
            return str(json.loads(base64.b64decode(s)).get("xpv_asset_id") or src.split("?")[0])
        except Exception:
            pass
    return src.split("?")[0]


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def strip_meta(path):
    ff = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not ff:
        return
    tmp = path + ".clean.mp4"
    r = subprocess.run([ff, "-v", "error", "-y", "-i", path, "-map", "0", "-map_metadata", "-1", "-map_chapters", "-1",
                        "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", "-c", "copy",
                        "-movflags", "+faststart", tmp])
    if r.returncode == 0:
        os.replace(tmp, path)
    elif os.path.exists(tmp):
        os.remove(tmp)


def one(args):
    ad, out, posters_only = args
    lid = ad["library_id"]
    res = {"library_id": lid, "start_date": ad.get("start_date"), "file": None, "poster": None, "error": None}
    try:
        if ad.get("poster"):
            p = os.path.join(out, f"{lid}.jpg")
            download(ad["poster"], p)
            res["poster"] = p
        if not posters_only and ad.get("src"):
            v = os.path.join(out, f"{lid}.mp4")
            download(ad["src"], v)
            strip_meta(v)
            res["file"] = v
    except Exception as e:
        res["error"] = str(e)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ads_json")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--sort", choices=["oldest", "newest", "impressions"], default="oldest",
                    help="oldest = ativos ha mais tempo (data de inicio); impressions = ordem de aparicao na biblioteca")
    ap.add_argument("--out", required=True)
    ap.add_argument("--posters-only", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    ads = json.load(open(a.ads_json, encoding="utf-8"))
    if isinstance(ads, dict):
        ads = ads.get("ads", [])
    ads = [x for x in ads if x.get("src") or x.get("poster")]
    for i, x in enumerate(ads):
        x.setdefault("rank", i)
    if a.sort == "impressions":
        ads.sort(key=lambda x: x["rank"])
    else:
        # empate de data: preserva a ordem de impressoes (rank)
        ads.sort(key=lambda x: (x.get("start_date") or "9999", x["rank"]), reverse=False)
        if a.sort == "newest":
            ads.sort(key=lambda x: (x.get("start_date") or "0000", -x["rank"]), reverse=True)
    seen, picked = set(), []
    for x in ads:
        k = asset_key(x)
        if k in seen:
            continue
        seen.add(k)
        picked.append(x)
        if len(picked) >= a.top:
            break
    os.makedirs(a.out, exist_ok=True)
    with ThreadPoolExecutor(a.workers) as ex:
        results = list(ex.map(one, [(x, a.out, a.posters_only) for x in picked]))
    json.dump(results, open(os.path.join(a.out, "baixados.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in results:
        print(("OK   " if not r["error"] else "ERRO ") + f"{r['library_id']} inicio={r['start_date']} {r['error'] or ''}")
    print(f"{sum(1 for r in results if not r['error'])}/{len(results)} baixados em {a.out}")


if __name__ == "__main__":
    main()
