# Instalação (equipe)

Tempo: ~10 minutos. Depois de instalar, rode os dois comandos do fim desta página — se aparecer `SELFTEST OK`, está pronto.

## 1. Ferramentas obrigatórias

| Ferramenta | Para quê | Versão |
|---|---|---|
| **Python** | roda todos os scripts | 3.10 ou mais novo (testado em 3.12) |
| **FFmpeg + ffprobe** (build completa) | ler/gravar vídeo, áudio, voz, espectrograma | 6 ou mais novo (testado na 9.0 "full build") |
| **Git** | baixar e atualizar esta skill | qualquer |

### Windows 10/11 (PowerShell)

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install Git.Git
```

Feche e reabra o terminal. A build `Gyan.FFmpeg` é a completa: já traz NVENC, `rubberband` (voz), `libass`, `lut3d`, `xfade` e o filtro `frei0r` (os plugins frei0r em si são um pacote à parte, opcional).

### macOS (Terminal, com [Homebrew](https://brew.sh))

```bash
brew install python@3.12 ffmpeg git
```

A fórmula padrão do Homebrew pode vir sem `rubberband`. Não é obrigatório (o `voice_fx.py` usa um método alternativo), mas para a voz ficar idêntica instale uma build completa, por exemplo `brew install ffmpeg-full` quando disponível no seu Homebrew, ou baixe uma build estática em <https://evermeet.cx/ffmpeg/>. Em Mac a codificação usa VideoToolbox automaticamente.

### Linux (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv ffmpeg git fonts-dejavu-core
```

## 2. Baixar a skill e instalar as dependências

```bash
git clone https://github.com/royalmaxDR/criativos-edicao.git criativos-edicao
cd criativos-edicao
python scripts/setup.py
```

O `setup.py` instala os pacotes Python (`opencv-python`, `numpy`, `pillow`, `requests`, `faster-whisper`), baixa o detector de rosto YuNet (OpenCV Zoo, licença MIT) e a fonte Anton (Google Fonts, licença OFL), gera as LUTs e confere o FFmpeg. Itens marcados `[--]` são opcionais; `[FALTA]` precisa resolver.

Se preferir isolar em ambiente virtual: `python -m venv .venv` e ative (`.venv\Scripts\activate` no Windows, `source .venv/bin/activate` no macOS/Linux) antes do `setup.py`.

## 3. Testar

```bash
python scripts/setup.py --check
python scripts/selftest.py
```

O autoteste cria mídia sintética, monta o plano nos 3 estilos e renderiza 8 s de cada. Não precisa de internet nem de conta em nenhum serviço.

## 4. Opcionais

| Item | Para quê | Como |
|---|---|---|
| GPU NVIDIA + driver recente | render 3–5x mais rápido (NVENC) | driver em <https://www.nvidia.com/drivers>; detectado sozinho |
| CUDA 12 + cuBLAS/cuDNN | transcrição pela GPU | sem isso o `transcribe.py` usa CPU sozinho (1 min de áudio ≈ 20 s) |
| `yt-dlp`, `gdown` | baixar referências do YouTube / Google Drive | `pip install yt-dlp gdown` |
| HeyGen (voz + avatar) | narração e apresentador por IA | conta do usuário; conector MCP ou chave de API — veja `docs/AVATAR_E_VOZ.md` |
| Separador de música (Demucs) | isolar a trilha de uma referência para estudo | `pip install demucs` (~2,5 GB com PyTorch) |
| Plugins frei0r | mais filtros via `look.ffmpeg_vf` | Linux: `sudo apt install frei0r-plugins`; macOS: `brew install frei0r`; Windows: baixar as DLLs em <https://frei0r.dyne.org> e apontar a variável `FREI0R_PATH` para a pasta (não testado nesta máquina) |
| DaVinci Resolve (grátis) | criar/exportar LUTs `.cube` próprias | <https://www.blackmagicdesign.com/products/davinciresolve> |

## 5. Usar a skill no seu agente

A pasta inteira é a skill. O arquivo `SKILL.md` é o procedimento; `AGENTS.md` é o resumo para agentes que leem esse nome.

| Agente | Onde colocar |
|---|---|
| **Claude Code** | copie/clonar a pasta em `~/.claude/skills/criativos-edicao/` (todas as sessões) ou `.claude/skills/criativos-edicao/` dentro do projeto |
| **Claude (app, aba Skills)** | compacte a pasta em `.zip` e envie em Configurações → Capacidades → Skills |
| **OpenAI Codex (CLI / IDE)** | abra o Codex com esta pasta como diretório de trabalho — ele lê `AGENTS.md`; ou copie a pasta para `~/.codex/skills/criativos-edicao/` |
| **Google Antigravity** | copie a pasta para `.agent/skills/criativos-edicao/` no workspace (ou a pasta global de skills do Antigravity); `AGENTS.md` também é lido na raiz |
| **Gemini CLI** | abra na pasta e peça para seguir `AGENTS.md`; ou crie um `GEMINI.md` com a linha `Siga AGENTS.md e SKILL.md` |
| **Cursor / Windsurf / outros** | abra a pasta; `AGENTS.md` é lido na raiz. Em agentes sem suporte, cole como primeira mensagem: "Leia AGENTS.md e SKILL.md desta pasta e siga-os." |

Os caminhos de skills mudam entre versões dos agentes — se o seu não achar a skill, confira a documentação da versão instalada; o conteúdo da pasta não muda.

## Problemas comuns

- **`ffmpeg` não encontrado** depois de instalar no Windows: feche e reabra o terminal (o PATH só atualiza em terminal novo).
- **Render lento / "encoder: x264"**: sem GPU compatível. Funciona igual; use `--jobs` igual ao número de núcleos ÷ 2.
- **Erro do NVENC com muitos processos**: placas antigas limitam sessões simultâneas → `--jobs 2`.
- **Legenda com fonte diferente**: `fonts/Anton-Regular.ttf` não baixou (sem internet no `setup.py`). Rode de novo ou aponte `captions.font` para um `.ttf`.
- **Acentos quebrados no terminal do Windows**: `chcp 65001` antes de rodar, ou use o Windows Terminal.
