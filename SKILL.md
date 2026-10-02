---
name: criativos-edicao
description: Aprende, analisa e extrai o estilo de edição de qualquer criativo de vídeo (cortes, tela dividida, zooms, movimentos de câmera, foco, transições, cor, trilha) e aplica esse estilo em criativos novos ou modelagens — narração, avatar, b-roll, legendas palavra a palavra, efeitos, LUTs e trilha, tudo por script (FFmpeg + Python). Use quando o usuário pedir "analise a edição deste criativo", "extraia o estilo", "replique essa edição com outra copy", "recrie este criativo", "modele este vídeo", "gere uma versão sem legenda", "aplique LUT/transição/efeito" ou "edite um criativo".
---

# Edição de criativos: extrair o estilo de uma referência → aplicar em vídeos novos

Tudo roda local, por linha de comando, a partir da pasta desta skill. Não usa CapCut, Premiere nem After Effects.
Primeira vez numa máquina: `python scripts/setup.py` e depois `python scripts/selftest.py` (deve terminar com `SELFTEST OK`). Instalação detalhada: `INSTALL.md`.

## Mapa

| Etapa | Script | Entra | Sai |
|---|---|---|---|
| 1. Aprender o estilo | `scripts/extract_style.py ref.mp4 --out pasta [--transcribe]` | criativo de referência | `style.json`, `REPORT.md`, folhas de contato, tiras das transições, espectrograma |
| 2. Narração | (HeyGen/ElevenLabs/gravação) + `scripts/voice_fx.py` | copy | `vo.wav` tratado |
| 3. Tempos das palavras | `scripts/transcribe.py vo.wav --out words.json --lang pt` | narração | `words.json` |
| 4. Apresentador | HeyGen (ou vídeo gravado) com o **mesmo áudio** | `vo.wav` | `avatar.mp4` |
| 5. B-roll | `scripts/broll_commons.py` (domínio público) ou arquivos próprios | buscas | `broll/*.jpg` + `_fontes.json` |
| 6. Plano | `scripts/make_plan.py --words … --style …` | tudo acima | `plan.json` (rascunho) |
| 7. Render | `scripts/render.py plan.json [--preview 0-12]` | plano | `NOME LEGENDA.mp4` + `NOME SEM LEGENDA.mp4` |
| Hook encenado (opcional) | HeyGen `text_to_video` (9:16, 10 s) + `scripts/hook_signal.py cena.mp4 fala.wav --door T --speech-at T --glitch T1,T2` | cena gerada + fala | hook 1080x1920 com porta batendo, chiado/queda de sinal, pronto para emendar |

Um pedido de "replique a edição com esta copy" = etapas 2 a 7. Um pedido de "analise a edição" = etapa 1.
Um pedido de "recrie este criativo" = etapa 1 (com `--transcribe` para pegar a copy) + 2 a 7.

## 1. Aprender o estilo de uma referência

```bash
python scripts/extract_style.py referencia.mp4 --out referencias/nome --transcribe --lang pt
```

O script mede; **quem decide é você, olhando as imagens**. Ordem de leitura:

1. `REPORT.md` — ritmo, proporção de layouts, níveis de zoom (largura do rosto ÷ largura do quadro), cor, áudio, tabela de transições.
2. `sheet_NN.jpg` — 1 frame por segundo. Confirme o layout de cada bloco (tela dividida / tela cheia / só b-roll), o estilo da legenda (posição, fonte, cor de destaque, palavras por tela), faixas e cartão final.
3. `trans_NN_T.jpg` — 14 frames em volta de cada transição. Compare com a tabela de efeitos abaixo. Os palpites (`kind_guess`) erram: glitch e rasgo costumam sair como `A` ou `B`.
4. `spec.png` — faixa escura contínua embaixo = base grave; riscos verticais em alta frequência = whoosh; manchas graves = boom.

Depois grave o que confirmou em `style.json` (campos `layout` em `segments` e `kind` em `transitions` têm prioridade sobre os palpites) e descreva o estilo em 5–10 linhas para o usuário **antes** de produzir. Se a referência usa um efeito que não existe aqui, crie um plugin (seção "Estender").

O estilo já extraído do criativo de referência original está em `docs/ESTILO_REFERENCIA.md` e pronto para uso como `--style cinematico_revelacao`.

## 2–5. Insumos do criativo novo

- **Copy.** Se vier com promessa de cura, "adeus aos remédios", fato histórico inventado ou especialista fictício apresentado como real: avise o usuário, proponha a versão adaptada e só siga com o texto que ele confirmar. Aponte sempre os trechos com risco de reprovação.
- **Voz.** Gere com a mesma voz do projeto (pontuação forte dá entonação) e trate: `python scripts/voice_fx.py vo_raw.wav vo.wav --preset imponente`. Para comparar com a referência: `python scripts/voice_fx.py --stats vo.wav referencia.mp4` (tom mediano e volume).
- **Avatar.** Gere o vídeo do apresentador com **o áudio já tratado** (lip-sync por áudio), 9:16, 720p basta. Um avatar condizente com a copy (idade, roupa, cenário), genérico, sem logotipo e sem imitar pessoa real. Detalhes e economia de créditos: `docs/AVATAR_E_VOZ.md`.
- **B-roll.** Uma imagem ou vídeo por ideia falada. `broll_commons.py` só baixa domínio público/CC0 e registra a origem em `_fontes.json`. Olhe `_previa.jpg` e escolha. Não use footage de TV, filme ou pessoa pública.

## 6. Plano

```bash
python scripts/make_plan.py --words words.json --voice vo.wav --avatar avatar.mp4 --broll broll --style cinematico_revelacao --name "OFERTA-01 v1" --out plan.json
python scripts/make_plan.py --list-styles
```

`--style` aceita um preset de `presets/styles/` **ou** o `style.json` de uma referência extraída. O rascunho corta nos limites de frase e distribui o b-roll em ordem; **revise antes de renderizar**:

- cada segmento tem `say` (o que é dito ali) → troque `broll` para a imagem que ilustra aquela fala;
- closes (`shot: close`) nas frases de impacto; plano aberto no CTA;
- `captions.keywords`: palavras que recebem o destaque; `captions.fix`: correções de grafia do reconhecimento;
- `banners`: faixa verde só nos trechos de chamada para ação.

Formato completo do plano: `docs/PLANO.md`.

## 7. Render

```bash
python scripts/render.py plan.json --check          # valida arquivos, tempos e nomes de efeito
python scripts/render.py plan.json --preview 0-12   # trecho curto para conferir
python scripts/render.py plan.json --jobs 4         # vídeo inteiro, em pedaços paralelos
```

Sempre confira a prévia com uma tira de frames antes do render inteiro:
`ffmpeg -ss 6.8 -i "NOME LEGENDA PREVIA 0-12.mp4" -vf "fps=15,scale=200:-1,tile=10x1" -frames:v 1 -update 1 chk.jpg`
Saída: 1080x1920, 30 fps, H.264 + AAC, metadados limpos. `captions.mode`: `both` (com e sem legenda numa passada), `on`, `off`.
Usa GPU (NVENC/VideoToolbox) quando existe; senão libx264. Um vídeo de 95 s leva ~6–8 min com `--jobs 3` numa GPU intermediária.

## Efeitos disponíveis (`fx` no plano: `[tempo_do_corte, "nome"]`)

| Nome | O que faz | Som |
|---|---|---|
| `A` | prisma + zoom-blur: borrão vertical com separação de cor, 1 frame limpo, zoom 1,9x girado que assenta com retomada de foco | whoosh + boom |
| `B` | estrobo solarizado: duotone roxo, negativo verde com contorno, estouro quente, negativo P&B | estalo + boom |
| `C` | glitch RGB/datamosh: fatias deslocadas, separação de cor, blocos coloridos, ruído | estalo + boom |
| `D` | rasgo horizontal: barras brancas deslocando faixas + varredura de luz quente no b-roll | whoosh |
| `bsw` | troca de b-roll dentro do mesmo layout (zoom-blur de 0,2 s, automático) | whoosh curto |
| `flash` `dip` `whip` `punch` `shake` `leak` `vhs` | clarão, mergulho no preto, chicote lateral, soco de zoom, tremor, vazamento de luz, VHS | variados |

Uso típico do estilo cinematográfico: dividida→cheia `C`/`A`/`B`; cheia→cheia `A`/`B`; cheia→dividida `D`; dividida→dividida `bsw`.
Efeitos saturados demais ficam amadores: a referência usa arco-íris a 14–22% e solarização sobre fundo escuro. `fx_intensity` no plano controla a força do desfoque de retomada.

## Estender (LUTs, efeitos, transições, outras ferramentas)

- **LUT:** qualquer `.cube` em `luts/` → `"look": {"lut": "luts/teal_orange.cube", "lut_strength": 0.7}`. `python scripts/make_luts.py` gera 6 looks próprios. A LUT entra antes dos textos (legenda e cartão não mudam de cor).
- **Efeito novo:** copie `plugins/exemplo_duotone.py`, registre com `@effect("nome", …)`; é carregado sozinho. Guia: `plugins/README.md`.
- **Filtros do FFmpeg na saída:** `"look": {"ffmpeg_vf": "eq=saturation=1.15:contrast=1.05"}` ou qualquer cadeia `-vf` (inclusive `frei0r=…` se o pacote de plugins frei0r estiver instalado).
- **Trilha própria:** `"audio": {"bed": "musica.mp3", "bed_loop": [0.9, 4.5], "bed_rms": 0.04}`. Só música com licença.
- Lista de ferramentas e plugins externos compatíveis: `docs/EFEITOS_E_LUTS.md`.

## Regras fixas

- **Não identificar pessoas pelo rosto.** Decidir "é figura pública" só por contexto observável (legenda com nome, logotipo de emissora, traje oficial). Borrão só em figura pública; react, UGC e apresentador/avatar ficam sem filtro.
- Trilha, footage e voz da referência servem para **análise**, não para reaproveitar no criativo novo. A base grave é sintetizada; b-roll vem de domínio público ou do próprio usuário.
- Não baixar vídeos à toa (disco); não excluir nada do usuário sem aprovação; não digitar senhas nem fazer login por ele; segredos nunca vão para o repositório.
- Relatar com precisão: o que foi renderizado, o que foi só prévia, o que não foi conferido, e quantos créditos de avatar/voz foram gastos.
- Entregar sempre os dois arquivos (com e sem legenda) quando o usuário não disser o contrário, e avisar os trechos da copy com risco de reprovação.

## Armadilhas já vividas

- `ffmpeg drawtext` falha em silêncio sem fonte → os textos são desenhados com Pillow.
- `tile` de vários frames precisa de `-frames:v 1 -update 1`.
- faster-whisper sem cuBLAS cai para CPU sozinho (mais lento, mesmo resultado).
- Áudio mais longo que o vídeo do avatar: o render segura o último frame do avatar; confira o fim.
- Render longo num processo só estoura limite de tempo de agentes: por isso o render é dividido (`--jobs`).
- Rosto do avatar fora do centro: informe `"avatar_face": [x, y, largura]` (frações do quadro) no plano se o detector errar; o render imprime o que detectou.
- Voz "mais imponente" não é só baixar o tom: meça com `--stats`; em geral é entonação (pontuação, motor expressivo) + corpo em 110 Hz + compressão.

## Hook encenado gerado por IA (aprendido no SL)

- Peça a cena **do ponto de vista do próprio celular** e escreva "nenhum celular aparece no quadro"; sem isso o modelo mostra um celular em primeiro plano.
- Divida a cena por segundos no prompt (0–3 entra e bate a porta; 3–5 vem até a câmera e pega; 5–10 selfie tremida falando). 10 s em 768p, `promptEnhancement: quality`.
- O áudio gerado pela cena vem mudo para nós (`--scene-gain 0`): fala, porta, respiração e chiado são montados pelo `hook_signal.py`.
- Fala de pânico: motor expressivo com marcas (`[panicked, fast, out of breath]`) e `speed 1.2`; corte pausas com `silenceremove`. A fala começa logo depois da batida da porta.
- Para legenda no hook, renderize o hook como segmento `broll` com `kb: 0`, `grade: none`, sem vinheta/grão, e emende antes do corpo; o corpo abre com efeito `C` (continua a "queda de sinal").
- Fonte mole (vídeo de 720p ampliado): zoom máximo ~1,45x, `diffusion: 0`, `look.ffmpeg_vf: "unsharp=5:5:0.75:5:5:0"`, grão 1,6.
- Voz: meça a referência (`voice_fx.py --stats`) e escolha no banco a voz pública mais próxima em tom; nunca clone voz de anúncio de terceiros. No SL: referência ~93 Hz → Yuri (106 Hz) com `--preset imponente` (≈100 Hz).
- Lip-sync: suba a cena e a fala alinhada no tempo (silêncio antes, `adelay`) e use `create_lipsync` em modo `precision`, `enableDynamicDuration: false`. A fala começa logo depois da porta; o rosto só aparece depois, então o sincronismo vale onde importa.
- Porta: impactos reais do banco de efeitos do HeyGen (`search_audio_sounds`, tipo `sound_effects`) via `--door-sfx arquivo:pico:ganho`, com ganho alto e `--voice-gain 0.7` para a batida soar mais forte que a voz; chiado com `--static-sfx`.

