# Fluxo detalhado (para humanos e agentes)

Convenção: `SK` = pasta da skill, `W` = pasta de trabalho (ex.: `./trabalho`). Todos os scripts têm `--help`.

## 0. Combinar com o usuário (antes de qualquer ação)
Pergunte/confirme só o que faltar: link da biblioteca; quantos criativos e critério (padrão: **10 mais antigos ativos**);
efeito (`strong` padrão; `mosaic` para figuras públicas); **se quer extensor** (nenhum por padrão) e a duração-alvo;
pasta de trabalho. Antes de baixar, diga: origem (CDN do Facebook), quantidade e pasta de destino.

## 1. Garimpar (precisa de um navegador)
1. Abra o link. A busca deve estar com **Status: Ativos**. A ordem da biblioteca costuma ser por impressões.
2. Execute `scripts/collect_ads.js` na página (console do navegador, ou a ferramenta de JavaScript do agente).
3. `CRP.start({target: 60})` → consulte `CRP.status()` a cada ~10 s até `running:false`.
   - `count` para de subir em ~40–60? É o limite de carregamento do Facebook. Veja TROUBLESHOOTING.md.
4. `CRP.result()` devolve o JSON. Salve em `W/ads.json`.
   Campos: `rank` (ordem de aparição), `library_id`, `start_date` (AAAA-MM-DD), `src`, `poster`, `page_text`.

**Atenção:** "mais antigos" é calculado só entre os anúncios carregados. Informe ao usuário quantos foram carregados
de quantos existem (a página mostra "~N resultados"). Se vários empatam na data mais antiga, o desempate é a ordem de impressões.

## 2. Selecionar e baixar
```bash
python $SK/scripts/fetch_media.py W/ads.json --top 10 --sort oldest --out W/baixados
```
- `--sort oldest|newest|impressions`; `--posters-only` baixa só miniaturas (triagem visual rápida).
- Duplicados (mesmo vídeo em anúncios diferentes) são agrupados; o relatório fica em `baixados/baixados.json`.
- Saída: `<library_id>.mp4` sem metadados. As URLs do CDN **expiram** em horas: baixe logo após coletar.

## 3. Rostos e figuras públicas
```bash
python $SK/scripts/scan_faces.py --out W/analise W/baixados
```
Resultado: `report.json` (cada `Pxx`: segundos em tela, em quais vídeos/intervalos), `crops/Pxx.jpg`, `gallery_*.jpg`.

Para pistas de identidade (opcional):
```bash
python $SK/scripts/lens_search.py --out W/lens.md W/analise/crops/P01.jpg W/analise/crops/P02.jpg
```
- Abre um Chrome visível. **Se pedir CAPTCHA, o usuário resolve**; o script aguarda (até 5 min por imagem).
- Priorize: apresentadores principais, rostos em cortes de arquivo/TV, qualquer rosto com roupas/cenário institucional.
- Recortes que pegam só óculos/objeto geram resultado inútil: refaça com o rosto centralizado.

### Como reportar (modelo)
Para cada criativo: apresentador(es) · pistas do Lens com a fonte ("o resumo de IA do Lens diz X; páginas parecidas: …") ·
nível de risco (alto/médio/baixo/inconclusivo) · trechos de arquivo sensíveis (minutagem). Sempre registre:
*"pista por semelhança visual, não confirmação; quem confirma é uma pessoa"*. Nunca afirme identidade por conta própria.

## 4. Borrão (+ extensor se pedido)
```bash
python $SK/scripts/blur_pipeline.py --out W/finais --style strong W/baixados                         # sem extensor
python $SK/scripts/blur_pipeline.py --out W/finais --style strong --extender EXT.mp4 --target 600 W/baixados   # com extensor
```
- Mostre ao usuário **um** vídeo pronto antes de rodar o lote inteiro se ele ainda não aprovou o estilo.
- `strong` (padrão) derrota reconhecimento por máquina; `mosaic` é o mais seguro e o mais "óbvio"; ambos cobrem todos os rostos.
- O extensor só entra se o usuário pedir. Sem `--extender` o vídeo mantém a duração original.

## 5. Verificar
```bash
python $SK/scripts/verify.py W/finais/*.mp4 --expect-duration 600 --expect-size 1080x1920
python $SK/scripts/verify.py W/finais/ID-EXT10.mp4 --source W/baixados/ID.mp4 --seconds 120
```
- `problems` vazio = duração, tamanho, decodificação e metadados OK.
- `frames_with_detectable_face`: rostos de alta confiança que sobraram. Olhe esses instantes; é comum serem falsos positivos
  (textura, luz, mãos). `frames_with_only_low_confidence_detections` quase sempre é ruído.
- `samples_above_0.363` deve ser 0 (o rosto do final não "bate" mais com o original).
- Sempre olhe alguns frames à mão: início do criativo, meio, emenda com o extensor.

## 6. Entrega
Entregue os caminhos dos arquivos finais e um resumo: quantos vídeos, duração, estilo aplicado, achados de figuras públicas
(com a ressalva) e pendências. Publicar/enviar a terceiros (YouTube etc.) está **fora** desta skill e exige confirmação do usuário.
