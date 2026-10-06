#!/usr/bin/env python3
"""Detecta se o resultado do Google Lens NOMEIA alguem (regra de decisao: qualquer nome => borrar).

A regra do projeto NAO e "confirmar quem e a pessoa", e sim: se o Lens cita um nome de pessoa para o rosto,
mesmo que seja o nome errado ou diferente a cada busca, esse rosto e tratado como sensivel e vai para o borrao.

Heuristica (conservadora = prefere marcar a deixar passar):
  - le o bloco "Visao geral criada por IA" (e as primeiras correspondencias);
  - procura um NOME PROPRIO (2+ palavras capitalizadas) logo depois de um cargo/papel (ator, bispo, jornalista, papa...)
    ou de uma expressao de identificacao ("parece retratar", "aparenta ser", "e o/a", "looks like"...).
Uso como modulo: from namecheck import analyze ; analyze(texto) -> {"named": bool, "names": [...], "evidence": "...", "reason": "..."}
Uso em CLI:      python namecheck.py lens_resultados.md   (imprime um veredito por secao)
"""
import json, re, sys

CAP = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõçñ]+"
PARTICLE = r"(?:de|da|do|dos|das|di|del|van|von|y)"
NAME_RE = rf"({CAP}(?:[ 	]+(?:{PARTICLE}[ 	]+)?(?:{CAP}|[A-Z]\.))" + r"{1,3})"
CUE = (r"(?:ator|atriz|jornalista|bispo|arcebispo|cardeal|papa|padre|pastor|pastora|irm[ãa]|frei|apresentador|apresentadora|"
       r"pol[ií]tico|prefeito|presidente|senador|deputado|governador|cantor|cantora|m[ée]dico|doutor|dr\.?|sr\.?|sra\.?|"
       r"empres[áa]rio|bilion[áa]rio|influenciador|influenciadora|youtuber|escritor|escritora|professor|professora|"
       r"actor|actress|journalist|bishop|archbishop|cardinal|pope|priest|nun|sister|mayor|president|singer|host|"
       r"preacher|televangelist|pastor|doctor|dr\.?|sir|ministro)")
IDCUE = (r"(?:pessoa\s*:|parece (?:mostrar|retratar|ser)|mostrar o|mostrar a|parece retratar|aparenta ser|parece ser|[ée] o\b|[ée] a\b|retrata|mostra o|mostra a|identificad[oa] como|"
         r"appears to be|looks like|is the|depicts|shows)")
STOP = {"Instagram", "YouTube", "Facebook", "Google", "Amazon", "TikTok", "Pinterest", "Wikipedia", "Wikipédia", "Mercado",
        "Livre", "Shopee", "Biblioteca", "Bíblia", "Bible", "Vou", "Mostrar", "Visão", "Correspondências", "Feedback",
        "Resultados", "Ajuda", "Traduzir", "Modo", "Tudo", "Brasil", "Jesus", "Cristo", "Deus", "Santa", "São", "Igreja",
        "Catholic", "Church", "Meta", "Lens", "Imagem", "Detalhes", "Pessoa", "Rosto", "Legenda", "Contexto", "Identidade",
        "Vestimenta", "Cenário", "Função", "Atuação", "Identificação", "Características", "Expressão", "Mitra", "Pesquisa",
        "Boston", "Roma", "Vaticano", "Universal", "Reino", "Nasa", "Sacerdote", "Católico", "Católica", "Stock", "iStock", "Getty", "Images", "Shutterstock", "Colégio", "Wikimedia",
        "Fit", "Women", "Men", "Sport", "Size", "Small", "Running", "Vest", "Gym", "Pink", "Black", "Blue", "Kit", "Store", "Shop",
        "Armação", "Óculos", "Grau", "Masculino", "Feminino", "Premium", "Video", "Footage", "Royalty", "Free"}


def overview_block(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    start = next((i for i, l in enumerate(lines) if re.search(r"Vis[aã]o geral criada por IA|AI Overview", l, re.I)), None)
    if start is None:
        return None, lines
    block = []
    for l in lines[start + 1:start + 22]:
        if re.match(r"(Mostrar (mais|tudo)|Correspond[êe]ncias visuais|Show (more|all)|Visual matches|A IA pode cometer|AI can make|"
                    r"Instagram|YouTube|Facebook|TikTok|Amazon|Mercado Livre|Shopee|Wikip|Pinterest|X$|LinkedIn|Reddit|Getty|iStock)", l):
            break
        block.append(l)
    return " \n".join(block), lines


def _clean(name, role_first=False):
    orig = name
    toks = name.split()
    had_role = False
    while toks and re.fullmatch(CUE, toks[0], re.I):  # tira cargo/papel do inicio ("Bispo Edir Macedo" -> "Edir Macedo")
        toks = toks[1:]
        had_role = True
    name = " ".join(toks)
    good = [t for t in toks if t not in STOP]
    # com cargo/papel colado ("Frei Gilson", "Padre Marcelo", "Papa Francisco") basta UM nome; sem cargo exige 2+
    if len(good) < (1 if (had_role or role_first) else 2) or (toks and toks[0] in STOP):
        return None
    return (name if len(good) >= 2 else orig).strip()  # nome unico: mantem o cargo ("Frei Gilson")


def analyze(text):
    block, lines = overview_block(text)
    if block is None:
        return {"named": False, "names": [], "evidence": "", "reason": "sem resumo de IA no resultado (inconclusivo)",
                "overview": False}
    names, evid = [], ""
    cue = re.compile(rf"\b(?:{CUE}|{IDCUE})", re.I)
    for m in re.finditer(NAME_RE, block):  # nomes proprios: capitalizacao e CASE-SENSITIVE
        raw = m.group(1)
        role_first = bool(re.fullmatch(CUE, raw.split()[0], re.I))  # "Irma Anna Maria...", "Bispo Edir Macedo"
        n = _clean(raw, role_first)
        if not n or n in names:
            continue
        window = block[max(0, m.start() - 70):m.start()]
        if role_first or cue.search(window):  # cargo colado ao nome, ou logo apos cargo/"parece ser"/"Pessoa:"
            names.append(n)
            evid = evid or block[max(0, m.start() - 90):m.end() + 40].replace("\n", " ").strip()
    return {"named": bool(names), "names": names, "evidence": evid[:300],
            "reason": "nome citado pelo Lens" if names else "o resumo de IA nao cita nome de pessoa", "overview": True}


def split_sections(md):
    parts = re.split(r"^## (.+)$", md, flags=re.M)
    return list(zip(parts[1::2], parts[2::2]))


def verdicts_from_md(md):
    out = {}
    for k, v in split_sections(md):
        r = analyze(v)
        r["status"] = "nomeou" if r["named"] else ("sem_nome" if r["overview"] else "pendente")
        out[k.strip()] = r
    return out


if __name__ == "__main__":
    # python namecheck.py lens.md [--write lens_veredito.json]   (regera vereditos a partir do .md)
    src = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    out = verdicts_from_md(src) if split_sections(src) else {"(texto)": analyze(src)}
    if "--write" in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index("--write") + 1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: {"status": v.get("status"), "names": v["names"]} for k, v in out.items()}, ensure_ascii=False, indent=1))
