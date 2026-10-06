---
name: criativos-pipeline
description: Pipeline completo para trabalhar com criativos em video da Biblioteca de Anuncios da Meta - garimpa os anuncios ativos ha mais tempo (ou mais impressos), baixa sem metadados, mapeia os rostos, consulta o Google Lens com os rostos e, pela regra do projeto (se o Lens citar QUALQUER nome, o video vai para o borrao), borra os rostos (borrao forte ou mosaico), anexa um video extensor ate uma duracao alvo (ex. 10 min) e verifica o resultado. Use quando o usuario pedir para garimpar/baixar criativos da biblioteca, checar se ha figura publica, borrar rostos em video, limpar metadados ou estender videos para uma duracao fixa.
---

# criativos-pipeline

Skill **independente de IA e de sistema operacional**: tudo que ela faz sao comandos de terminal (Python + ffmpeg)
e um trecho de JavaScript para o navegador. Qualquer agente que consiga rodar comandos e abrir uma pagina web
(Claude Code, Codex, Cursor, Gemini CLI, ChatGPT com code-interpreter local, scripts proprios...) consegue executar.
Um humano tambem executa os mesmos comandos a mao. Passo a passo detalhado: `references/WORKFLOW.md`.

## Regras que valem para qualquer agente (leia antes de agir)

1. **Nao identifique pessoas pelo rosto.** A checagem e feita por busca reversa de imagem (`scripts/lens_search.py`).
   Reporte o que a ferramenta devolveu como *pista*, nunca como fato.
2. **REGRA DE DECISAO (definida pelo dono do projeto): se o Lens citar QUALQUER NOME para um rosto — mesmo que seja
   outro nome a cada busca ou um nome errado — o rosto e sensivel e o video vai para o borrao.** O que importa e o Lens
   *nao dar nome nenhum*; se der, e sinal de que outros reconhecedores tambem darao. Nao e preciso "confirmar" quem e.
   Rostos para os quais o Lens nao cita nome ficam como estao. Busca que falhou (`pendente`) ou pessoa nao enviada ao Lens
   (`nao_verificado`) conta como sensivel ate ser refeita. Se o usuario preferir, `blur_pipeline.py` sem `--plan` borra tudo.
3. **CAPTCHA:** nunca tente burlar. Se o Google/Meta pedir, pare e peca ao usuario para resolver na janela.
4. **Peca confirmacao antes de:** baixar arquivos (diga origem, quantidade e pasta), publicar/enviar algo para fora,
   apagar arquivos. Nunca insira credenciais; o fluxo nao exige nenhuma.
5. Criativos de anuncio sao obra de terceiros: avise o usuario que o uso/republicacao e responsabilidade dele
   (direitos autorais, termos da Meta, uso de imagem). Veja `references/SAFETY_AND_LIMITS.md`.

## Entradas minimas a combinar com o usuario

| Dado | Padrao | Observacao |
|---|---|---|
| Link da Biblioteca de Anuncios | (obrigatorio) | Ja filtrada/pesquisada, `active_status=active` |
| Quantos / criterio | 10, **mais antigos ativos** | `--sort oldest` (data de inicio) ou `impressions` |
| Efeito nos rostos | `strong` | `strong` = borrao forte olhos/nariz/boca; `mosaic` = pixelizacao (mais segura); `none` |
| Extensor | **nenhum** | So se o usuario pedir. Informe `--extender arquivo.mp4 --target SEGUNDOS` |
| Pasta de trabalho | `./trabalho` | Tudo fica la |

## Fluxo (6 etapas)

Defina `SK` = pasta desta skill (ex.: `~/.claude/skills/criativos-pipeline`). Todos os scripts aceitam `--help`.

**0. Preparar o ambiente (uma vez)**
```bash
pip install -r $SK/requirements.txt
python $SK/scripts/setup_check.py        # confere python/opencv/ffmpeg/GPU/modelos (baixa modelos se faltarem)
```

**1. Garimpar a biblioteca**
Modo automatico (recomendado, sem copiar/colar): `python $SK/scripts/collect_cdp.py "<link da Biblioteca>" --out trabalho/ads.json --target 100`
abre um Chrome, roda o coletor e rola com a roda do mouse (carrega 100+ anuncios; a rolagem simples trava em ~30-60).
Modo manual: cole `scripts/collect_ads.js` no console da pagina, `CRP.start({target: 100})`, repita `CRP.status()` ate
`running:false` e salve `CRP.result()` em `trabalho/ads.json`.

**2. Selecionar e baixar**
```bash
python $SK/scripts/fetch_media.py trabalho/ads.json --top 10 --sort oldest --out trabalho/baixados
# novo lote DIFERENTE do anterior: --exclude com os ids ja usados (exclui tambem o mesmo video em outros anuncios)
python $SK/scripts/fetch_media.py trabalho/ads.json --top 10 --sort oldest --exclude usados.txt --out trabalho/lote2
```
Gera `<library_id>.mp4` sem metadados, `.jpg` de miniatura e `baixados.json`. Duplicados sao agrupados.
Dica: use `--posters-only` primeiro se quiser triar visualmente antes de baixar os videos.

**3. Mapear rostos, consultar o Lens e decidir onde borrar (regra: "Lens citou nome => borrar")**
```bash
python $SK/scripts/scan_faces.py --out trabalho/analise trabalho/baixados/
python $SK/scripts/lens_search.py --out trabalho/lens.md trabalho/analise/crops/P01.jpg trabalho/analise/crops/P02.jpg ...
python $SK/scripts/triage.py --faces trabalho/analise/report.json --lens trabalho/lens_veredito.json --out trabalho/blur_plan.json
```
`scan_faces.py` agrupa pessoas distintas (crops + onde/quando aparecem). `lens_search.py` abre um Chrome visivel, envia
os recortes ao Google Lens e grava `lens.md` + `lens_veredito.json` (por recorte: `nomeou` | `sem_nome` | `pendente`);
se aparecer CAPTCHA, o usuario resolve na janela. `triage.py` aplica a regra e escreve `blur_plan.json`
(quais videos precisam de borrao e por que). Envie ao Lens pelo menos todas as pessoas com >= 4 s em tela; as mais
curtas tambem contam (`--unchecked blur` e o padrao do triage; use `--min-seconds` so se o usuario aceitar).
Monte o relatorio por criativo (modelo em `references/WORKFLOW.md`), sempre com a ressalva de que sao pistas.

**4. Aplicar o efeito nos rostos (+ extensor se pedido) — passo unico**
```bash
# aplica a regra: borra so os videos do plano (Lens citou nome); os demais saem limpos/convertidos:
python $SK/scripts/blur_pipeline.py --out trabalho/finais --style strong --plan trabalho/blur_plan.json trabalho/baixados/
# borrar TUDO (sem plano):
python $SK/scripts/blur_pipeline.py --out trabalho/finais --style strong trabalho/baixados/
# borrao + extensor ate 10 min (extensor so quando o usuario pedir):
python $SK/scripts/blur_pipeline.py --out trabalho/finais --style strong --plan trabalho/blur_plan.json --extender EXTENSOR.mp4 --target 600 trabalho/baixados/
```
Limpa metadados, converte para 1080x1920, detecta GPU (nvenc/qsv/amf/videotoolbox, senao CPU), pre-renderiza o extensor
uma vez (cache) e o anexa por copia. Para mosaico use `--style mosaic`. Padrao `--min-score 0.5` (prioriza privacidade; pode borrar objetos). Subir para 0.7 reduz falsos alertas mas pode deixar escapar rostos pequenos: so faca isso e confira com `verify.py`.

**5. Verificar**
```bash
python $SK/scripts/verify.py trabalho/finais/*.mp4 --expect-duration 600 --expect-size 1080x1920
python $SK/scripts/verify.py trabalho/finais/ID-EXT10.mp4 --source trabalho/baixados/ID.mp4 --seconds 120   # teste de reconhecimento
```
Confira tambem alguns frames a olho (inicio do criativo, meio, emenda com o extensor).

## Saidas

`trabalho/ads.json`, `baixados/`, `analise/` (report.json, crops, galleries), `lens.md`, `finais/<id>-EXT10.mp4` (ou `-final.mp4`).

## Estilos e o que cada um garante (medido no projeto original)

| Estilo | Reconhecimento facial por maquina (SFace) | Visual |
|---|---|---|
| `mosaic` | 0 acertos em 231 amostras | Quadrado pixelado sobre o rosto |
| `strong` | ~0-1% de acertos | Faixa horizontal esfumada olhos/nariz/boca |
| (borrao fraco, so faixa estreita) | ~90% de acertos — **nao usar** | — |

Para figuras publicas confirmadas, prefira `mosaic`.

## Se algo falhar
`references/TROUBLESHOOTING.md` (carregamento da biblioteca, CAPTCHA, ffmpeg/GPU, duracao fora de 10:00, falsos positivos).
