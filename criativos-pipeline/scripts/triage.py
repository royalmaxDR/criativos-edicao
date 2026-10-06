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
    ap.add_argument("--registry", help="registro_figuras.json: acumula as pessoas sinalizadas de TODOS os lotes. Quem foi nomeado pelo "
                    "Lens em qualquer lote continua borrado nos proximos, mesmo que a nova busca venha sem nome")
    ap.add_argument("--batch", default="lote", help="nome do lote (rotulo no registro)")
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
    videos, plist, flagged = {}, {}, []
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
        if sensitive and pr.get("embedding"):
            flagged.append({"id": pid, "names": names, "emb": pr["embedding"]})
        for vid in pr["appearances"]:
            e = videos.setdefault(vid, {"blur": False, "reasons": [], "flagged_persons": []})
            if sensitive:
                e["flagged_persons"].append(pid)
                e["blur"] = True
                for span in pr["appearances"][vid]:  # "6-8s" -> janela [6, 8] em segundos
                    m = re.match(r"(\d+)-(\d+)s", span)
                    if m:
                        e.setdefault("windows", []).append([int(m.group(1)), int(m.group(2))])
                e["reasons"].append({"person": pid, "status": status, "names": names, "when": pr["appearances"][vid]})
    if a.registry:
        import numpy as np
        reg = json.load(open(a.registry, encoding="utf-8")) if os.path.exists(a.registry) else []
        for r in reg:  # formato antigo (uma assinatura) -> lista de assinaturas
            if "emb" in r:
                r["embs"] = [r.pop("emb")]

        def sim(x, y):
            return float(np.dot(np.array(x, dtype=np.float32), np.array(y, dtype=np.float32)))

        for f in flagged:
            hit = next((r for r in reg if max(sim(f["emb"], e) for e in r["embs"]) >= 0.5), None)
            if hit:  # mesma pessoa ja registrada: soma nomes e guarda a nova assinatura (cobre mais angulos/idades da imagem)
                hit["names"] = sorted(set(hit["names"]) | set(f["names"]))
                if a.batch not in hit.setdefault("seen_in", []):
                    hit["seen_in"].append(a.batch)
                if len(hit["embs"]) < 12 and max(sim(f["emb"], e) for e in hit["embs"]) < 0.93:
                    hit["embs"].append(f["emb"])
            else:
                reg.append({"id": f"{a.batch}:{f['id']}", "names": f["names"], "embs": [f["emb"]], "seen_in": [a.batch]})
        json.dump(reg, open(a.registry, "w", encoding="utf-8"), ensure_ascii=False)
        flagged = [{"id": r["id"], "names": r["names"], "emb": e} for r in reg for e in r["embs"]]
        print(f"registro: {len(reg)} pessoa(s) sinalizadas ({len(flagged)} assinaturas) acumuladas em {a.registry}")
    plan = {"rule": "Lens citou nome => borrar o ROSTO dessa pessoa (modo persons) / o video inteiro (modo video)",
            "videos": videos, "persons": plist, "flagged_embeddings": flagged}
    json.dump(plan, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nb = sum(1 for v in videos.values() if v["blur"])
    print(f"{nb} de {len(videos)} videos tem figura sensivel; {len(flagged)} pessoa(s) a borrar (so o rosto delas) -> {a.out}")
    for vid, e in sorted(videos.items()):
        why = "; ".join(f"{r['person']}={r['status']}{' ' + ','.join(r['names']) if r['names'] else ''}" for r in e["reasons"])
        print(f"  {'BORRAR' if e['blur'] else 'ok    '} {vid}  {why}")
    pend = [p for p, d in plist.items() if d["status"] in ("pendente", "nao_verificado") and d["sensitive"]]
    if pend:
        print(f"\nAtencao: {len(pend)} pessoa(s) sem resposta do Lens ({', '.join(pend)}); estao sendo tratadas como sensiveis. "
              "Refaca a busca (lens_search.py) para libera-las.")


if __name__ == "__main__":
    main()
