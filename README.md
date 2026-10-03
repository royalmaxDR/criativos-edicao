# criativos-edicao

Skill de edição de criativos de vídeo para agentes de IA (Claude Code, Codex, Antigravity, Gemini CLI, Cursor…).
Ela **aprende o estilo de edição de um criativo de referência** e **aplica esse estilo em criativos novos** — sem editor de vídeo: tudo é FFmpeg + Python por linha de comando.

## O que faz

**Aprender / analisar / extrair**
- cortes e ritmo, proporção de tela dividida × tela cheia × b-roll, cadência de troca de b-roll
- níveis de zoom e movimentos de câmera (rastreamento do rosto quadro a quadro), retomada de foco
- cada transição em uma tira de 14 frames + palpite do tipo de efeito + se tem whoosh/boom
- cor (vinheta, saturação, contraste, grão) e áudio (base grave, cauda musical, tom e volume da voz, espectrograma)
- transcrição com tempo por palavra (para recriar a copy e as legendas)

**Aplicar**
- tela dividida com emenda esfumada, apresentador em 3 escalas, b-roll com movimento (imagem ou vídeo)
- 12 efeitos de transição com som sincronizado + sistema de plugins para criar outros
- câmera: estouro de escala, recuo/avanço lento, empurrão antes do corte, balanço, microtremor, difusão
- legendas palavra a palavra com destaque, faixa de chamada, cartão final animado
- LUTs `.cube`, tratamento do b-roll, vinheta, grão, filtros do FFmpeg na saída
- trilha: base grave sintetizada ou música própria em loop + efeitos sonoros
- sai com legenda e sem legenda na mesma passada, 1080x1920, metadados limpos

## Começar

```bash
git clone https://github.com/royalmaxDR/criativos-edicao.git criativos-edicao
cd criativos-edicao
python scripts/setup.py
python scripts/selftest.py
```

Instalação completa (Windows, macOS, Linux) e como plugar em cada agente: **[INSTALL.md](INSTALL.md)**.

## Fluxo em 7 passos

```bash
# 1. aprender o estilo de uma referência
python scripts/extract_style.py referencia.mp4 --out referencias/ref1 --transcribe --lang pt
# 2. tratar a narração (gerada no HeyGen/ElevenLabs ou gravada)
python scripts/voice_fx.py vo_raw.wav projetos/p1/vo.wav --preset imponente
# 3. tempos das palavras
python scripts/transcribe.py projetos/p1/vo.wav --out projetos/p1/words.json --lang pt
# 4. avatar: gerar o vídeo do apresentador com o vo.wav (lip-sync) -> projetos/p1/avatar.mp4
# 5. b-roll em domínio público
python scripts/broll_commons.py --out projetos/p1/broll "q01=Dead Sea Scrolls" "q02=gold coins pile"
# 6. plano
python scripts/make_plan.py --words projetos/p1/words.json --voice projetos/p1/vo.wav --avatar projetos/p1/avatar.mp4 \
    --broll projetos/p1/broll --style cinematico_revelacao --name "OFERTA-01 v1" --out projetos/p1/plan.json
# 7. conferir e renderizar
python scripts/render.py projetos/p1/plan.json --check
python scripts/render.py projetos/p1/plan.json --preview 0-12
python scripts/render.py projetos/p1/plan.json --jobs 4
```

Com um agente, basta pedir: *"analise a edição de `referencia.mp4`"* ou *"replique essa edição com esta copy: …"*. O agente segue o `SKILL.md`.

## Estrutura

```
SKILL.md                 procedimento (skill do Claude; também lido pelos outros agentes)
AGENTS.md                resumo e regras para Codex / Antigravity / Gemini / Cursor
INSTALL.md               instalação da equipe
scripts/
  setup.py               instala e confere a máquina          selftest.py   teste de ponta a ponta
  extract_style.py       referência -> style.json + imagens   make_plan.py  narração + estilo -> plan.json
  render.py              plan.json -> vídeo                    fx.py         efeitos de transição (registro plugável)
  look.py                LUT, cor, acabamento                  audio_engine.py  base grave + efeitos sonoros
  voice_fx.py            tratamento e medição da voz           transcribe.py    tempos por palavra
  broll_commons.py       b-roll em domínio público             make_luts.py     gera as LUTs
  assign_broll.py        casa b-roll com a fala e divide planos  sheet.py         folha de contato das imagens
  hook_signal.py         hook encenado: sons sincronizados e queda de sinal
presets/styles/          estilos prontos (cinematico_revelacao, ugc_dinamico, narracao_broll, narracao_dinamica)
plugins/                 efeitos extras (um .py = um efeito)
luts/                    LUTs .cube
models/                  detector de rosto YuNet
docs/                    PLANO.md · ESTILO_REFERENCIA.md · EFEITOS_E_LUTS.md · AVATAR_E_VOZ.md
```

## Ferramentas usadas

| Ferramenta | Papel |
|---|---|
| FFmpeg / ffprobe | decodificar, codificar (NVENC / VideoToolbox / x264), áudio, voz, espectrograma, metadados |
| Python 3.10+ com OpenCV, NumPy, Pillow | composição quadro a quadro, efeitos, textos |
| YuNet (OpenCV Zoo) | detecção de rosto para enquadramento e análise de câmera |
| faster-whisper | transcrição com tempo por palavra |
| Wikimedia Commons (API) | b-roll em domínio público / CC0 |
| HeyGen (ou equivalente) | voz e avatar — externo, conta do usuário |

## O que não vai para o repositório

Vídeos, áudios, criativos de terceiros, avatares, narrações, renders e qualquer chave ou token (veja `.gitignore`). Trabalhe em `projetos/` e `referencias/`, que são ignoradas.

## Limites e cuidados

- A classificação automática de layout e de tipo de transição é um palpite; a decisão é de quem olha as tiras.
- O agente não identifica pessoas reais pelo rosto e não reaproveita áudio/imagem/voz da referência no criativo novo.
- Copy com promessa de cura ou fato inventado tem risco de reprovação nas plataformas: o agente sinaliza antes de narrar.
