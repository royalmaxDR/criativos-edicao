#!/usr/bin/env python3
"""Triagem: cruza as PESSOAS (scan_faces.py) com os VEREDITOS do Lens (lens_search.py) e decide QUAIS VIDEOS BORRAR.

REGRA DO PROJETO: se o Lens citar qualquer nome para um rosto (mesmo que errado ou diferente a cada busca), aquele
rosto e tratado como sensivel -> todo video em que ele aparece vai para o borrao. Se o Lens nao der nome nenhum,
o rosto fica como esta.

Estados por pessoa:
  nomeou          o Lens citou um nome                        -> borrar os videos dela
  sem_nome        o Lens respondeu e nao citou nome           -> nao borra
  pendente        a busca falhou/sem resumo                   -> tratada como sensivel (borra) ate repetir a busca
  nao_verificado  a pessoa nao foi enviada ao Lens            -> borra (padrao) ou ignora (--unchecked ignore)

Uso:
  python triage.py --faces analise/report.json --lens lens_veredito.json --out blur_plan.json
  # depois: python blur_pipeline.py --plan blur_plan.json ...
Opcoes: --unchecked blur|ignore   --min-seconds N (pessoas com menos de N s em tela nao exigem busca)
"""
import argparse, json, os, re, sys


def pid_of(path):
    m = re.search(r"(P\d+)", os.path.basename(path))
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--faces", required=True, help="analise/report.json (scan_faces.py)")
    ap.add_argument("--lens", required=True, nargs="+", help="um ou mais *_veredito.json (lens_search.py); varios = vale o pior caso")
    ap.add_argument("--out", default="blur_plan.json")
    ap.add_argument("--unchecked", choices=["blur", "ignore"], default="blur")
    ap.add_argument("--min-seconds", type=float, default=0.0)
    a = ap.parse_args()

    persons = json.load(open(a.faces, encoding="utf-8"))
    verd = {}
    rank = {"nomeou": 3, "pendente": 2, "sem_nome": 1}
    for lf in a.lens:
        for img, v in json.load(open(lf, encoding="utf-8")).items():
            p = pid_of(img)
            if p:  # varios recortes/arquivos da mesma pessoa: vale o pior caso (nomeou > pendente > sem_nome)
                if p not in verd or rank[v["status"]] > rank[verd[p]["status"]]:
                    nm = sorted(set(v.get("names", [])) | set(verd.get(p, {}).get("names", [])))
                    verd[p] = dict(v, names=nm)
    videos, plist = {}, {}
    for pr in persons:
        pid = pr["id"]
        v = verd.get(pid)
        if v:
            status, names = v["status"], v.get("names", [])
        elif pr["seconds_on_screen"] < a.min_seconds:
            status, names = "ignorado_curto", []
        else:
            status, names = "nao_verificado", []
        sensitive = status in ("nomeou", "pendente") or (status == "nao_verificado" and a.unchecked == "blur")
        plist[pid] = {"status": status, "names": names, "seconds_on_screen": pr["seconds_on_screen"], "sensitive": sensitive}
        for vid in pr["appearances"]:
            e = videos.setdefault(vid, {"blur": False, "reasons": []})
            if sensitive:
                e["blur"] = True
                e["reasons"].append({"person": pid, "status": status, "names": names, "when": pr["appearances"][vid]})
    plan = {"rule": "Lens citou nome => borrar o video", "videos": videos, "persons": plist}
    json.dump(plan, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nb = sum(1 for v in videos.values() if v["blur"])
    print(f"{nb} de {len(videos)} videos precisam de borrao -> {a.out}")
    for vid, e in sorted(videos.items()):
        why = "; ".join(f"{r['person']}={r['status']}{' ' + ','.join(r['names']) if r['names'] else ''}" for r in e["reasons"])
        print(f"  {'BORRAR' if e['blur'] else 'ok    '} {vid}  {why}")
    pend = [p for p, d in plist.items() if d["status"] in ("pendente", "nao_verificado") and d["sensitive"]]
    if pend:
        print(f"\nAtencao: {len(pend)} pessoa(s) sem resposta do Lens ({', '.join(pend)}); estao sendo tratadas como sensiveis. "
              "Refaca a busca (lens_search.py) para libera-las.")


if __name__ == "__main__":
    main()
