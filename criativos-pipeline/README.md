# criativos-pipeline

Pipeline portátil para **garimpar criativos em vídeo da Biblioteca de Anúncios da Meta, mapear os rostos,
checar figuras públicas, borrar os rostos, (opcionalmente) estender o vídeo até uma duração fixa e verificar o resultado.**

Funciona em Windows, macOS e Linux, com GPU (NVIDIA/Intel/AMD/Apple) ou só CPU, e pode ser operado por **qualquer
agente de IA que execute comandos de terminal** (Claude Code, Codex CLI, Cursor, Gemini CLI, scripts próprios…)
ou por uma pessoa, copiando os comandos.

```
Biblioteca de Anúncios ──► collect_ads.js ──► ads.json ──► fetch_media.py ──► vídeos limpos
                                                                  │
                         scan_faces.py (pessoas distintas) ◄──────┤
                         lens_search.py + triage.py (regra do nome) │
                                                                  ▼
              blur_pipeline.py  (borrão/mosaico + metadados + extensor opcional)  ──► verify.py ──► finais
```

## O que cada parte faz

| Etapa | Script | Função |
|---|---|---|
| 0 | `scripts/setup_check.py` | Confere Python, OpenCV, numpy, ffmpeg, encoder de GPU e modelos; baixa modelos se faltarem |
| 1 | `scripts/collect_ads.js` | Roda **dentro da página** da biblioteca: rola, coleta ID, **data de início**, URL do vídeo e miniatura (PT/EN/ES) |
| 2 | `scripts/fetch_media.py` | Escolhe os N **ativos há mais tempo** (ou mais impressos), remove duplicados, baixa em paralelo e **limpa metadados** |
| 3a | `scripts/scan_faces.py` | Agrupa os rostos em **pessoas distintas** (recorte, quando e quanto tempo aparecem). Não identifica ninguém |
| 3b | `scripts/lens_search.py` | Envia os recortes ao Google Lens num Chrome real e marca cada um como `nomeou`/`sem_nome`/`pendente`; se houver CAPTCHA, você resolve |
| 3c | `scripts/triage.py` | **Regra do projeto:** se o Lens citou *qualquer* nome para um rosto, os vídeos em que ele aparece vão para o borrão (`blur_plan.json`) |
| 4 | `scripts/blur_pipeline.py` | Borra os rostos (`strong`/`mosaic`), limpa metadados, converte p/ 1080×1920 e, **se pedido**, anexa um extensor até a duração alvo |
| 5 | `scripts/verify.py` | Confere duração, tamanho, decodificação, metadados e se ainda há rosto reconhecível |

## Instalação

```bash
git clone <URL-DESTE-REPOSITORIO> criativos-pipeline
cd criativos-pipeline
pip install -r requirements.txt
python scripts/setup_check.py
```
Requisitos: Python 3.9+, **ffmpeg + ffprobe no PATH** (https://ffmpeg.org), um navegador para a etapa 1
e (só para `lens_search.py`) Google Chrome. Os modelos de rosto já vêm em `models/`.

### Usando com cada tipo de agente
- **Claude Code / Claude Desktop (Code):** copie a pasta para `~/.claude/skills/criativos-pipeline` (global) ou
  `<projeto>/.claude/skills/criativos-pipeline`. O `SKILL.md` é carregado automaticamente.
- **Codex CLI / Cursor / Gemini CLI / Aider / outros:** aponte o agente para este repositório e diga:
  *"Leia `SKILL.md` e `references/WORKFLOW.md` e execute o fluxo para este link da Biblioteca: …"*.
  Se o seu agente usa arquivo de instruções do projeto (`AGENTS.md`, `.cursorrules`, `GEMINI.md`), copie/aponte para o `SKILL.md`.
- **Sem agente (manual):** siga o passo a passo abaixo.

## Passo a passo (manual)

1. **Garimpar.** Abra o link da Biblioteca (já filtrado por anunciante/palavra-chave e `Ativos`). Abra o console
   do navegador (F12), cole `scripts/collect_ads.js`, rode `CRP.start({target: 60})` e aguarde
   `CRP.status()` mostrar `running:false`. Rode `copy(CRP.result())` e salve em `trabalho/ads.json`.
2. **Baixar os mais antigos.**
   `python scripts/fetch_media.py trabalho/ads.json --top 10 --sort oldest --out trabalho/baixados`
3. **Mapear rostos.** `python scripts/scan_faces.py --out trabalho/analise trabalho/baixados`
   (abra `analise/gallery_0.jpg` para ver as pessoas distintas).
4. **Lens + triagem (regra: "citou nome ⇒ borrar").**
   `python scripts/lens_search.py --out trabalho/lens.md trabalho/analise/crops/P01.jpg trabalho/analise/crops/P02.jpg ...`
   `python scripts/triage.py --faces trabalho/analise/report.json --lens trabalho/lens_veredito.json --out trabalho/blur_plan.json`
5. **Borrar (e estender, se quiser).**
   - Borrar só onde o Lens citou nome: `python scripts/blur_pipeline.py --out trabalho/finais --style strong --plan trabalho/blur_plan.json trabalho/baixados`
   - Borrar tudo: `python scripts/blur_pipeline.py --out trabalho/finais --style strong trabalho/baixados`
   - Borrão + extensor de 10 min:
     `python scripts/blur_pipeline.py --out trabalho/finais --style strong --extender meu_extensor.mp4 --target 600 trabalho/baixados`
6. **Verificar.**
   `python scripts/verify.py trabalho/finais/*.mp4 --expect-duration 600 --expect-size 1080x1920`

## Referência de opções do `blur_pipeline.py`

| Opção | Padrão | O que faz |
|---|---|---|
| `--style strong\|mosaic\|none` | `strong` | `strong` = borrão horizontal forte em olhos/nariz/boca; `mosaic` = pixelização; `none` = só extensor/limpeza |
| `--extender ARQ` | — | Vídeo a anexar após o criativo (**só use se o usuário pedir**) |
| `--target SEG` | `600` | Duração final; o extensor é cortado para fechar exatamente |
| `--size LxA` | `1080x1920` | Resolução de saída (9:16, com faixas pretas se preciso) |
| `--encoder` | `auto` | `h264_nvenc`/`h264_qsv`/`h264_amf`/`h264_videotoolbox`/`libx264` |
| `--cq` | `28` | Qualidade/tamanho (maior = arquivo menor) |
| `--workers` | auto | Vídeos em paralelo (3 com GPU; metade dos núcleos na CPU) |
| `--min-score` | `0.5` | Confiança mínima do detector de rosto. Menor = mais proteção (mais falsos alertas) |
| `--step` / `--hold` | `2` / `0.6` | Detectar a cada N quadros; segundos que o efeito persiste sem detecção |
| `--plan ARQ` | — | `blur_plan.json` do `triage.py`: borra só os vídeos sinalizados (os demais saem sem efeito, mas limpos/convertidos/estendidos) |
| `--suffix` | `EXT10`/`final` | Sufixo do arquivo de saída |

### Como funciona por dentro (resumo)
- **Detecção:** YuNet (OpenCV Zoo) a cada 2 quadros; um *tracker* simples mantém o efeito por 0,6 s se o rosto some.
- **Efeito `strong`:** borrão de caixa horizontal + gaussiano numa faixa olhos→boca, com máscara elíptica esfumada, calculado
  numa versão reduzida do recorte (5× mais rápido, sem perda visível).
- **Extensor rápido:** é re-renderizado **uma única vez** (cache em `<saida>/.cache`, GOP de 1 s) e anexado
  **por cópia de stream** (`concat`), então só o criativo (curto) passa pela codificação.
- **Metadados:** removidos em todas as etapas (`-map_metadata -1`, `-fflags +bitexact`).
- **Desempenho medido (RTX 3060, 12 núcleos):** 7 criativos de 2–3 min → 10 min cada em ~3 min no total.

## Segurança e limites
Leia `references/SAFETY_AND_LIMITS.md`. Em resumo: o pipeline **não identifica pessoas**; a regra é **"o Lens citou algum nome ⇒ borrar"**
(borrar tudo é o modo conservador); CAPTCHA nunca é burlado; criativos de terceiros têm direitos autorais; o Lens fornece **pistas**, não provas.

## Estrutura
```
SKILL.md                 instruções para o agente (formato Agent Skills)
README.md                este arquivo
requirements.txt
scripts/                 setup_check.py collect_ads.js fetch_media.py scan_faces.py lens_search.py namecheck.py triage.py blur_pipeline.py verify.py
models/                  yunet.onnx (detector) e sface.onnx (comparador) — ver models/README.md
references/              WORKFLOW.md  SAFETY_AND_LIMITS.md  TROUBLESHOOTING.md
```

## Licença
Código: MIT (`LICENSE`). Modelos: licenças originais do OpenCV Zoo (ver `models/README.md`).
