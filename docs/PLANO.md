# Formato do plano (`plan.json`)

O plano descreve o vídeo inteiro. Caminhos relativos valem a partir da pasta do plano (ou da raiz da skill, para `luts/…`). Só `segments` é obrigatório; o resto tem padrão.

```json
{
  "name": "OFERTA-01 v1",
  "size": [1080, 1920],
  "fps": 30,
  "avatar": "avatar.mp4",
  "voice": "vo.wav",
  "words": "words.json",
  "segments": [
    {"s": 0.00, "e": 2.10, "layout": "split", "broll": "broll/q01_0.jpg", "say": "Em 1947,"},
    {"s": 2.10, "e": 4.10, "layout": "split", "broll": "broll/clip.mp4"},
    {"s": 4.10, "e": 6.30, "layout": "full", "zoom": 1.18},
    {"s": 6.30, "e": 9.00, "layout": "full", "face_w": 0.57, "shot": "close"},
    {"s": 9.00, "e": 12.0, "layout": "broll", "broll": "gen:wave"}
  ],
  "fx": [[2.10, "bsw"], [4.10, "C"], [6.30, "A"], [9.00, "D"]],
  "banners": [{"s": 87.5, "e": 91.2, "text": "TOQUE NO BOTÃO ABAIXO", "color": [18, 150, 40], "arrows": true}],
  "captions": {"mode": "both", "style": "box", "keywords": ["1947", "pergaminho"], "fix": {"Fecha": "Feche"}},
  "end_card": {"dur": 4.3, "lines": [["CLIQUE ABAIXO", [255, 255, 255], 120], ["SAIBA MAIS", [40, 220, 70], 150]], "chevrons": true},
  "look": {"lut": "luts/frio_misterio.cube", "lut_strength": 0.6, "broll_grade": "frio"},
  "audio": {"bed": "synth", "sfx": true}
}
```

## Campos

**Raiz**

| Campo | Padrão | Significado |
|---|---|---|
| `name` | `CRIATIVO` | nome dos arquivos de saída |
| `size`, `fps` | `[1080, 1920]`, `30` | qualquer tamanho; tudo escala a partir de 1920 de altura |
| `avatar` | — | vídeo do apresentador (opcional: sem ele, tudo vira layout `broll`) |
| `avatar_face` | detectado | `[x, y, largura]` do rosto em frações do quadro do avatar, se o detector errar |
| `voice` | — | narração final (define a duração) |
| `words` | — | tempos das palavras (`transcribe.py`); sem isso não há legenda |
| `speech_end` | duração de `voice` | fim da fala; depois entra o cartão final |
| `fx_intensity` | `1.0` | força do desfoque de retomada após as transições |
| `seed` | `21` | muda o tremor, o glitch e os sorteios (mesma seed = mesmo vídeo) |

**`segments`** — contíguos, do 0 ao fim da fala.

| Campo | Significado |
|---|---|
| `s`, `e` | início e fim em segundos |
| `layout` | `split` (apresentador em cima, b-roll embaixo), `full` (apresentador em tela cheia), `broll` (b-roll em tela cheia) |
| `broll` | imagem, vídeo, ou `gen:wave` (ondas sonoras animadas) — para `split` e `broll` |
| `zoom` | tela cheia: multiplicador sobre o enquadramento do avatar (1.0 aberto, 1.18 médio, 1.42 close) |
| `face_w` | alternativa ao `zoom`: largura do rosto ÷ largura do quadro (0.46 aberto, 0.52 médio, 0.57 close) — é a medida que o `extract_style.py` devolve, então serve para copiar a referência com qualquer avatar |
| `shot` | `wide` / `medium` / `close`: muda o comportamento da câmera (close = recuo lento + difusão; os outros = avanço lento) |
| `kb` | b-roll: `1` aproxima (padrão), `-1` afasta, `0` parado |
| `grade` | b-roll: tratamento só neste segmento (`frio`, `quente`, `pb`, `none`). `kb: 0` + `grade: none` com um vídeo = trecho original intacto (ex.: manter o hook de outro criativo) |
| `cap_y` | altura da legenda só neste segmento (fração da altura) |
| `say` | texto falado no trecho (só anotação para quem revisa) |

**`fx`** — `[tempo, nome]`; o tempo é o do corte. Nomes: veja `SKILL.md` ou `docs/EFEITOS_E_LUTS.md`.

**`captions`**

| Campo | Padrão | |
|---|---|---|
| `mode` | `both` | `both` gera com e sem legenda na mesma passada; `on`; `off` |
| `style` | `box` | `box` = caixa colorida atrás da palavra-chave; `color` = palavra-chave colorida; `plain` |
| `keywords` | `[]` | palavras que recebem o destaque (sem nenhuma no grupo, destaca a última) |
| `fix` | `{}` | correção de grafia: `{"errada": "certa"}` |
| `max_chars`, `max_words` | `14`, `2` | tamanho de cada grupo na tela |
| `size`, `font` | `74`, Anton | tamanho (para 1920 de altura) e `.ttf` |
| `box_color`, `key_color` | vermelho, amarelo | RGB |
| `y_split`, `y_full` | `0.484`, `0.672` | altura da legenda em cada layout |
| `uppercase` | `true` | |

**`camera`** (frações; os padrões são os medidos na referência)

`split_zoom` 1.30 · `split_face_y` 0.20 · `pan` 0.035 (balanço lateral, fração da largura) · `pan_period` 9 s · `breath` 0.012 · `overshoot` 0.10 (estouro de escala na entrada) · `overshoot_tau` 0.11 s · `pull_out` 0.05 (recuo no close) · `push_in` 0.035 · `anticipation` 0.13 (empurrão nos últimos 0,17 s antes de ir para a tela dividida) · `shake` 1.6 · `diffusion` 0.16.

**`look`**

`lut` (.cube) · `lut_strength` 0–1 · `broll_grade` `frio` / `quente` / `pb` / `none` · `vignette` 0.72 · `chroma` 2 px · `contrast` 1.07 · `lift` 12 · `grain` 3.2 · `ffmpeg_vf` (cadeia de filtros do FFmpeg aplicada na saída).

**`audio`**

`bed`: `synth` (base grave sintetizada), caminho de um arquivo de música, ou `none` · `bed_loop` `[início, fim]` do trecho usado em loop · `bed_rms` 0.036 (volume da base; a voz fica em ~0.17) · `sfx` liga os sons das transições · `sfx_gain` · `voice_gain`.

**`end_card`** — `null` para não ter. `lines`: `[texto, [R, G, B], tamanho]`.

**`banners`** — faixa no topo entre `s` e `e`.
