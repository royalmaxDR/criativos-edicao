#!/usr/bin/env python3
"""Envia imagens (recortes de rosto) ao Google Lens num Chrome REAL e devolve o que o Lens encontrou.

- Abre um Chrome visivel com perfil temporario e controla via DevTools Protocol (so biblioteca padrao).
- Se o Google pedir CAPTCHA, o script ESPERA voce resolver na janela. Ele NAO tenta burlar CAPTCHA.
- O resultado sao PISTAS (resumo de IA do Lens + paginas parecidas), nao prova de identidade. Quem confirma e uma pessoa.

Regra do projeto: se o Lens CITAR QUALQUER NOME para o rosto (mesmo que errado/diferente a cada busca), o rosto
é sensivel e o video vai para o borrao. O script grava, alem do .md, um *_veredito.json (nomeou | sem_nome | pendente).

Uso: python lens_search.py --out lens_resultados.md crops/P01.jpg crops/P02.jpg ...
Opcoes: --chrome CAMINHO  --port 9222  --captcha-wait 300  --keep-open
"""
import argparse, base64, json, os, platform, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from namecheck import analyze


class WS:  # cliente WebSocket minimo (so o necessario para o CDP)
    def __init__(s, url):
        host, path = url[5:].split("/", 1)
        h, p = host.split(":")
        s.sk = socket.create_connection((h, int(p)))
        key = base64.b64encode(os.urandom(16)).decode()
        s.sk.send(f"GET /{path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        r = b""
        while b"\r\n\r\n" not in r:
            r += s.sk.recv(1)
        s.i = 0

    def send(s, o):
        d = json.dumps(o).encode()
        m = os.urandom(4)
        n = len(d)
        hd = b"\x81" + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536
                        else bytes([0x80 | 127]) + struct.pack(">Q", n))
        s.sk.send(hd + m + bytes(b ^ m[i % 4] for i, b in enumerate(d)))

    def rx(s, n):
        b = b""
        while len(b) < n:
            c = s.sk.recv(n - len(b))
            if not c:
                raise EOFError
            b += c
        return b

    def recv(s):
        msg = b""
        while True:
            a, b = s.rx(2)
            n = b & 127
            if n == 126:
                n = struct.unpack(">H", s.rx(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", s.rx(8))[0]
            msg += s.rx(n)
            if a & 0x80:
                break
        return json.loads(msg)

    def call(s, method, **params):
        s.i += 1
        s.send({"id": s.i, "method": method, "params": params})
        while True:
            r = s.recv()
            if r.get("id") == s.i:
                return r

    def ev(s, js):
        r = s.call("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("result", {}).get("value")


def find_chrome(explicit):
    if explicit:
        return explicit
    cands = {"Windows": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                         r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                         r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
             "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
             "Linux": ["google-chrome", "chromium", "chromium-browser"]}[platform.system()]
    for c in cands:
        if os.path.exists(c) or shutil.which(c):
            return shutil.which(c) or c
    sys.exit("Chrome nao encontrado. Use --chrome CAMINHO")


def search(w, image, captcha_wait):
    w.call("Page.enable")
    w.call("Page.navigate", url="https://www.google.com/imghp?hl=pt-BR")
    time.sleep(3)
    w.ev("""(()=>{const e=[...document.querySelectorAll('[aria-label]')].find(x=>/imagem|image/i.test(x.getAttribute('aria-label'))&&x.tagName==='DIV'); if(e) e.click();})()""")
    time.sleep(1.5)
    doc = w.call("DOM.getDocument", depth=-1)["result"]["root"]["nodeId"]
    node = w.call("DOM.querySelector", nodeId=doc, selector="input[type=file]")["result"]["nodeId"]
    if not node:
        return "ERRO: campo de upload nao encontrado (a pagina do Google mudou?)"
    w.call("DOM.setFileInputFiles", files=[os.path.abspath(image)], nodeId=node)
    t0, warned = time.time(), False
    while time.time() - t0 < captcha_wait + 40:
        time.sleep(3)
        try:
            loc = w.ev("location.href") or ""
        except Exception:
            continue
        if "/sorry/" in loc or "recaptcha" in loc:
            if not warned:
                print("  CAPTCHA: resolva na janela do Chrome; aguardando...", flush=True)
                warned = True
            continue
        if "vsrid" in loc or "/search?" in loc:
            time.sleep(6)
            return w.ev("document.body.innerText") or ""
    return "TIMEOUT"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default="lens_resultados.md")
    ap.add_argument("--chrome")
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--captcha-wait", type=int, default=300)
    ap.add_argument("--runs", type=int, default=2, help="buscas por imagem (o Lens varia; vale o pior caso). Padrao 2")
    ap.add_argument("--keep-open", action="store_true")
    a = ap.parse_args()
    prof = tempfile.mkdtemp(prefix="lens_profile_")
    proc = subprocess.Popen([find_chrome(a.chrome), f"--remote-debugging-port={a.port}", f"--user-data-dir={prof}",
                             "--no-first-run", "--no-default-browser-check", "--window-size=1100,800", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{a.port}/json"))
                page = [t for t in tabs if t["type"] == "page"][0]
                break
            except Exception:
                time.sleep(0.5)
        else:
            sys.exit("nao consegui conectar ao Chrome")
        w = WS(page["webSocketDebuggerUrl"])
        verdicts = {}
        with open(a.out, "w", encoding="utf-8") as out:
            out.write("# Resultados do Google Lens (PISTAS, nao prova)\n\n")
            for img in a.images:
                print(f"> {img}", flush=True)
                best = None
                for run in range(a.runs):  # o Lens muda de resposta entre buscas: vale o PIOR caso (qualquer nome => nomeou)
                    txt = search(w, img, a.captcha_wait)
                    v = analyze(txt)
                    if not v["overview"]:  # sem resumo (timeout/pagina vazia): tenta mais uma vez
                        txt = search(w, img, a.captcha_wait)
                        v = analyze(txt)
                    v["status"] = "nomeou" if v["named"] else ("sem_nome" if v["overview"] else "pendente")
                    print(f"  busca {run + 1}/{a.runs}: {v['status']} {v['names'] or ''}", flush=True)
                    if best is None:
                        best, best_txt = v, txt
                        best["runs"] = []
                    best["runs"].append({"status": v["status"], "names": v["names"]})
                    if v["status"] == "nomeou" and best["status"] != "nomeou":
                        runs = best["runs"]
                        best, best_txt = v, txt
                        best["runs"] = runs
                    elif v["status"] == "pendente" and best["status"] == "sem_nome":
                        best["status"] = "pendente"
                    if v["names"]:
                        best["names"] = sorted(set(best["names"]) | set(v["names"]))
                v, txt = best, best_txt
                verdicts[img] = v
                print(f"  -> {v['status']} {v['names'] or ''}", flush=True)
                lines = [l for l in txt.split("\n") if l.strip()][:80]
                out.write(f"## {img}\n\n**Veredito:** {v['status']} {v['names'] or ''}\n\n```\n" + "\n".join(lines) + "\n```\n\n")
                out.flush()
        vjson = os.path.splitext(a.out)[0] + "_veredito.json"
        json.dump(verdicts, open(vjson, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"resultados em {a.out} | vereditos em {vjson}")
    finally:
        if not a.keep_open:
            try:
                proc.terminate()
            except Exception:
                pass
            shutil.rmtree(prof, ignore_errors=True)


if __name__ == "__main__":
    main()
