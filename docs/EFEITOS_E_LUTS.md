# Efeitos, LUTs, plugins e ferramentas externas

## Efeitos embutidos (`scripts/fx.py`)

| Nome | Efeito | Som | Origem |
|---|---|---|---|
| `A` | prisma + zoom-blur com retomada de foco | whoosh + boom | referência |
| `B` | estrobo solarizado (roxo → negativo verde → estouro quente → negativo P&B) | estalo + boom | referência |
| `C` | glitch RGB / datamosh | estalo + boom | referência |
| `D` | rasgo horizontal + varredura de luz | whoosh | referência |
| `bsw` | troca de b-roll com zoom-blur de 0,2 s | whoosh curto | referência |
| `flash` | clarão branco | batida | extra |
| `dip` | mergulho no preto | — | extra |
| `whip` | chicote lateral com borrão de movimento | whoosh | extra |
| `punch` | soco de zoom (+16% que assenta) | batida | extra |
| `shake` | tremor de impacto | boom | extra |
| `leak` | vazamento de luz quente | — | extra |
| `vhs` | linhas, salto vertical, cor deslocada | estalo | extra |
| `duotone` | pisca em azul/laranja (exemplo de plugin) | batida | `plugins/` |

Listar o que está carregado na sua máquina:

```bash
python -c "import sys; sys.path.insert(0,'scripts'); import fx; fx.load_plugins(); [print(k, '-', v['desc']) for k, v in fx.REG.items()]"
```

## Criar um efeito novo

Veja `plugins/README.md`. Em resumo: um arquivo `.py` em `plugins/` com uma função decorada por `@effect`. Fluxo recomendado quando a referência tem um efeito que não existe aqui:

1. Abra a tira `trans_NN_T.jpg` e descreva frame a frame (k−3 … k+5) o que muda: escala, rotação, desfoque, cor, deslocamento.
2. Escreva a função com um `dict` de intensidade por `k`.
3. Renderize `--preview` em volta do corte, tire uma tira igual e compare lado a lado com a da referência. Ajuste até bater.

## LUTs

- Formato: `.cube` 3D (qualquer tamanho: 17, 33, 65). Salve em `luts/` e aponte em `look.lut`. `lut_strength` mistura com a imagem original.
- Próprias (geradas por `python scripts/make_luts.py`, sem licença de terceiros):

| Arquivo | Clima |
|---|---|
| `teal_orange.cube` | sombras azul-esverdeadas, pele quente — "cinema" |
| `frio_misterio.cube` | frio, dessaturado, contraste alto — revelação / segredo |
| `quente_filme.cube` | quente, pretos levantados — depoimento / nostalgia |
| `noir.cube` | quase P&B, contraste forte — denúncia / notícia |
| `sepia_antigo.cube` | sépia — documento histórico |
| `bleach.cube` | pouco croma, muito contraste — tensão |

- Criar a sua: edite `LOOKS` em `scripts/make_luts.py`, ou exporte um `.cube` do DaVinci Resolve (página Color → clique direito no clipe → Generate LUT), Photoshop (Exportar → Tabelas de consulta de cores) ou de qualquer pacote de LUTs **com licença de uso comercial**.
- A LUT é aplicada na imagem antes dos efeitos e dos textos. Para aplicar em tudo (inclusive legenda), use `look.ffmpeg_vf`: `"lut3d=file=luts/noir.cube"`.

## Filtros do FFmpeg na saída (`look.ffmpeg_vf`)

Qualquer cadeia `-vf` roda sobre o quadro final. Exemplos testáveis:

| Objetivo | Valor |
|---|---|
| mais saturação e contraste | `eq=saturation=1.15:contrast=1.05` |
| nitidez | `unsharp=5:5:0.8` |
| curva de filme | `curves=preset=medium_contrast` |
| balanço de cor | `colorbalance=rs=0.05:bs=-0.05` |
| LUT em tudo | `lut3d=file=luts/teal_orange.cube` |
| barras de cinema | `drawbox=y=0:h=ih*0.08:t=fill:c=black,drawbox=y=ih*0.92:h=ih*0.08:t=fill:c=black` |

## Transições entre dois vídeos prontos (fora do motor)

Para juntar dois clipes já renderizados com transição do próprio FFmpeg (`xfade`, 40+ tipos: `fade`, `wipeleft`, `circleopen`, `pixelize`, `radial`, `zoomin`…):

```bash
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:v][1:v]xfade=transition=pixelize:duration=0.4:offset=9.6[v];[0:a][1:a]acrossfade=d=0.4[a]" -map "[v]" -map "[a]" saida.mp4
```

`offset` = duração do primeiro clipe menos a duração da transição.

## Ferramentas e plugins externos que encaixam no fluxo

| Ferramenta | Para quê | Como entra |
|---|---|---|
| **frei0r** (plugins de vídeo livres) | glow, distorções, glitch, cartoon | `look.ffmpeg_vf: "frei0r=<plugin>:<params>"` — exige o pacote de plugins instalado |
| **gl-transitions** (transições GLSL abertas) | dezenas de transições de shader | porte a fórmula para um plugin `@effect`, ou use um FFmpeg compilado com o filtro `gltransition` |
| **DaVinci Resolve** (grátis) | criar LUTs e conferir cor | exportar `.cube` → `luts/` |
| **Demucs** | separar voz e música de uma referência para estudar a trilha | `pip install demucs` → `demucs -n htdemucs --two-stems vocals ref.wav` |
| **Real-ESRGAN / Topaz** | aumentar b-roll pequeno | rodar antes e apontar o arquivo ampliado em `broll` |
| **rembg** | recortar pessoa/objeto do fundo | `pip install rembg` → PNG com transparência (use como b-roll sobre fundo próprio) |
| **MoviePy / Remotion / Motion Canvas** | motion graphics mais elaborados | renderize o clipe à parte e use como b-roll de vídeo (`"broll": "clipe.mp4"`) |
| **Pexels / Pixabay / Wikimedia Commons** | b-roll gratuito | `broll_commons.py` cobre o Commons; para os outros, confira a licença de cada arquivo |
| **Freesound / Pixabay Audio / YouTube Audio Library** | trilhas e efeitos sonoros com licença | `audio.bed: "arquivo.mp3"` |
| **ElevenLabs / HeyGen / Azure TTS** | narração | veja `docs/AVATAR_E_VOZ.md` |

Regra para qualquer item externo: só entra no criativo material com licença que permita uso comercial, e a origem fica anotada na pasta do projeto.
