---
name: criativos-pipeline
description: Pipeline completo para trabalhar com criativos em video da Biblioteca de Anuncios da Meta - garimpa os anuncios ativos ha mais tempo (ou mais impressos), baixa sem metadados, mapeia os rostos, ajuda a checar figuras publicas (busca reversa de imagem), borra todos os rostos (borrao forte ou mosaico), anexa um video extensor ate uma duracao alvo (ex. 10 min) e verifica o resultado. Use quando o usuario pedir para garimpar/baixar criativos da biblioteca, checar se ha figura publica, borrar rostos em video, limpar metadados ou estender videos para uma duracao fixa.
---

# criativos-pipeline

Skill **independente de IA e de sistema operacional**: tudo que ela faz sao comandos de terminal (Python + ffmpeg)
e um trecho de JavaScript para o navegador. Qualquer agente que consiga rodar comandos e abrir uma pagina web
(Claude Code, Codex, Cursor, Gemini CLI, ChatGPT com code-interpreter local, scripts proprios...) consegue executar.
Um humano tambem executa os mesmos comandos a mao. Passo a passo detalhado: `references/WORKFLOW.md`.

## Regras que valem para qualquer agente (leia antes de agir)

1. **Nao identifique pessoas pelo rosto.** Quem decide se alguem e figura publica e uma busca reversa de imagem
   (`scripts/lens_search.py`) ou o proprio usuario. Reporte o que a ferramenta devolveu como *pista*, nunca como fato.
2. **Padrao seguro:** borre *todos* os rostos (`--style strong` ou `mosaic`). Assim a checagem de figura publica
   deixa de ser necessaria para a saida final (ela continua util para relatorio).
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

**1. Garimpar a biblioteca (navegador)**
Abra o link da biblioteca, execute `scripts/collect_ads.js` na pagina (console, ou a ferramenta de JavaScript do agente),
depois `CRP.start({target: 60})`, repita `CRP.status()` ate `running:false` e salve `CRP.result()` em `trabalho/ads.json`.
Para "ativos ha mais tempo" colete bastante (o Facebook trava em ~40-60 por carga; veja TROUBLESHOOTING).

**2. Selecionar e baixar**
```bash
python $SK/scripts/fetch_media.py trabalho/ads.json --top 10 --sort oldest --out trabalho/baixados
```
Gera `<library_id>.mp4` sem metadados, `.jpg` de miniatura e `baixados.json`. Duplicados sao agrupados.
Dica: use `--posters-only` primeiro se quiser triar visualmente antes de baixar os videos.

**3. Mapear rostos e (opcional) checar figuras publicas**
```bash
python $SK/scripts/scan_faces.py --out trabalho/analise trabalho/baixados/*.mp4
python $SK/scripts/lens_search.py --out trabalho/lens.md trabalho/analise/crops/P01.jpg ...   # opcional
```
`scan_faces.py` agrupa pessoas distintas (crops + onde/quando aparecem). `lens_search.py` abre um Chrome visivel,
envia os recortes ao Google Lens e salva as pistas; se aparecer CAPTCHA, o usuario resolve na janela.
Monte o relatorio por criativo (modelo em `references/WORKFLOW.md`), sempre com a ressalva de que sao pistas.

**4. Aplicar o efeito nos rostos (+ extensor se pedido) — passo unico**
```bash
# so borrao:
python $SK/scripts/blur_pipeline.py --out trabalho/finais --style strong trabalho/baixados/
# borrao + extensor ate 10 min (extensor so quando o usuario pedir):
python $SK/scripts/blur_pipeline.py --out trabalho/finais --style strong --extender EXTENSOR.mp4 --target 600 trabalho/baixados/
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
