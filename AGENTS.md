# AGENTS.md — instruções para qualquer agente de IA (Codex, Antigravity, Gemini CLI, Cursor, Claude Code…)

Este repositório é uma **skill de edição de criativos de vídeo**. Você, agente, opera os scripts de `scripts/` pela linha de comando.
**Leia `SKILL.md` inteiro antes de agir** — ele é a fonte única do procedimento. Este arquivo só resume e diz como se comportar.

## O que você faz aqui

1. **Aprender o estilo** de um criativo de referência: `python scripts/extract_style.py ref.mp4 --out referencias/nome --transcribe`, ler `REPORT.md`, **abrir as imagens** (`sheet_*.jpg`, `trans_*.jpg`, `spec.png`) e corrigir os palpites em `style.json`.
2. **Aplicar o estilo** numa copy nova: narração → `voice_fx.py` → `transcribe.py` → avatar → b-roll → `make_plan.py` → revisar `plan.json` → `render.py --check` → `--preview` → render final.

## Regras de operação

- Trabalhe dentro de uma pasta de projeto (`projetos/<nome>/`), nunca na raiz. Mídia não é versionada (veja `.gitignore`).
- Antes do primeiro uso na máquina: `python scripts/setup.py`; se algo estiver em FALTA, siga `INSTALL.md` e pare para avisar o usuário quando precisar de instalação com privilégio de administrador.
- Sempre `--check` e `--preview` antes do render inteiro. Extraia uma tira de frames e **olhe** antes de dizer que ficou bom.
- Se você não enxerga imagens, diga isso: use os palpites do `style.json` e peça ao usuário para conferir as tiras.
- Geração de voz e avatar depende de serviço externo (HeyGen, ElevenLabs etc.). Use o conector/API que o usuário já tiver configurado; **não crie contas, não digite senhas, não peça chaves no chat** — peça que o usuário configure a variável de ambiente ou o conector. Veja `docs/AVATAR_E_VOZ.md`.
- Não identifique pessoas reais pelo rosto. Não reaproveite áudio, imagem ou voz do criativo de referência no criativo novo.
- Copy com promessa de cura, fato inventado ou especialista fictício: sinalize e confirme com o usuário antes de narrar.
- Relate o que fez de verdade: arquivos gerados, duração, o que foi só prévia, o que não conferiu, créditos gastos.

## Comandos de referência

```bash
python scripts/setup.py --check
python scripts/selftest.py
python scripts/extract_style.py ref.mp4 --out referencias/ref1 --transcribe --lang pt
python scripts/voice_fx.py vo_raw.wav vo.wav --preset imponente
python scripts/transcribe.py vo.wav --out words.json --lang pt
python scripts/broll_commons.py --out broll "q01=Dead Sea Scrolls" "q02=gold coins pile"
python scripts/make_plan.py --words words.json --voice vo.wav --avatar avatar.mp4 --broll broll --style cinematico_revelacao --name "OFERTA-01 v1" --out plan.json
python scripts/render.py plan.json --check
python scripts/render.py plan.json --preview 0-12
python scripts/render.py plan.json --jobs 4
```

## Onde está cada coisa

- `SKILL.md` procedimento completo · `INSTALL.md` instalação por sistema · `docs/PLANO.md` formato do plano
- `docs/ESTILO_REFERENCIA.md` o estilo aprendido, em detalhe · `docs/EFEITOS_E_LUTS.md` efeitos, LUTs, plugins e ferramentas externas
- `docs/AVATAR_E_VOZ.md` voz e avatar · `presets/styles/` estilos prontos · `plugins/` efeitos extras · `luts/` LUTs `.cube`
