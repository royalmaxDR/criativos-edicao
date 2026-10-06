#!/usr/bin/env python3
"""Garimpagem AUTOMATICA da Biblioteca de Anuncios: abre um Chrome visivel, roda collect_ads.js na pagina e salva ads.json.

Equivale a colar collect_ads.js no console, mas sem copiar/colar nada (as URLs dos videos sao longas e frageis).
Nao exige login. Se a Meta pedir verificacao, o script espera voce resolver na janela.

Uso:
  python collect_cdp.py "<link da Biblioteca>" --out trabalho/ads.json --target 80
Opcoes: --chrome CAMINHO  --port 9223  --max-minutes 8
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lens_search import WS, find_chrome  # cliente CDP minimo ja usado na busca reversa


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", default="ads.json")
    ap.add_argument("--target", type=int, default=80, help="parar ao coletar N anuncios (o Facebook costuma travar em 40-60)")
    ap.add_argument("--max-minutes", type=float, default=8)
    ap.add_argument("--stall-seconds", type=float, default=150, help="desiste se a contagem nao crescer por N segundos")
    ap.add_argument("--chrome")
    ap.add_argument("--port", type=int, default=9223)
    a = ap.parse_args()

    js = open(os.path.join(HERE, "collect_ads.js"), encoding="utf-8").read()
    prof = tempfile.mkdtemp(prefix="crp_collect_")
    proc = subprocess.Popen([find_chrome(a.chrome), f"--remote-debugging-port={a.port}", f"--user-data-dir={prof}",
                             "--no-first-run", "--no-default-browser-check", "--window-size=1200,900", a.url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        page = None
        for _ in range(60):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{a.port}/json"))
                page = next(t for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.5)
        if not page:
            sys.exit("nao consegui conectar ao Chrome")
        w = WS(page["webSocketDebuggerUrl"])
        time.sleep(8)  # carregamento inicial da biblioteca
        print("injetando coletor...", flush=True)
        w.ev(js)
        w.call("Page.bringToFront")
        print("coletando:", w.ev(f"CRP.start({{target:{a.target}, maxMinutes:{a.max_minutes}, stallTicks:{int(a.stall_seconds / 1.5)}}})"), flush=True)
        t0, last = time.time(), -1
        while time.time() - t0 < a.max_minutes * 60 + 30:
            for _ in range(2):  # rolagem real (roda do mouse): dispara o carregamento preguicoso melhor que scrollTo
                w.call("Input.dispatchMouseEvent", type="mouseWheel", x=600, y=500, deltaX=0, deltaY=2500)
                time.sleep(2.5)
            st = w.ev("JSON.stringify(CRP.status())")
            if not st:
                continue
            st = json.loads(st)
            if st["count"] != last:
                print(f"  {st['count']} anuncios (parado={st['stalled']})", flush=True)
                last = st["count"]
            if not st["running"]:
                break
        ads = json.loads(w.ev("CRP.result()"))
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(ads, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        dated = sum(1 for x in ads if x.get("start_date"))
        print(f"{len(ads)} anuncios salvos em {a.out} ({dated} com data de inicio)")
        if len(ads) >= 30 and dated:
            ds = sorted(x["start_date"] for x in ads if x.get("start_date"))
            print(f"datas: {ds[0]} .. {ds[-1]}")
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    main()
