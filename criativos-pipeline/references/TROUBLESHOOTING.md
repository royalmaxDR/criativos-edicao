# Solução de problemas

## Biblioteca de Anúncios
| Sintoma | Causa / solução |
|---|---|
| Só 30–60 anúncios carregam | **Use `scripts/collect_cdp.py`** (rolagem real com a roda do mouse: carregou 110 na prática). Com o console, o Facebook carrega em lotes e às vezes para. Rode `CRP.start({target: 200, stallTicks: 60})` de novo, role a página manualmente, ou refine a busca (um anunciante/página por vez, `Mais recentes`). O mais antigo só é garantido entre os carregados |
| `start_date` vem `null` | Idioma/formato novo. Veja o texto em `page_text` e acrescente o mês em `MONTHS` / um padrão em `parseDate` (`collect_ads.js`) |
| `src` vazio | Anúncio de imagem/carrossel (só vídeos são coletados) ou vídeo ainda não carregou: role até ele e rode `CRP.status()` |
| Download dá 403/expirado | As URLs do CDN expiram. Colete de novo e baixe imediatamente |
| Pede login | Navegue sem login (a biblioteca pública não exige); se pedir, é o usuário quem decide |

## Google Lens / CAPTCHA
| Sintoma | Solução |
|---|---|
| Página "tráfego incomum" | É CAPTCHA. **Resolva na janela do Chrome**; `lens_search.py` aguarda. Não tente automatizar |
| `campo de upload não encontrado` | A página do Google mudou. Abra `google.com/imghp`, clique no ícone de câmera e envie manualmente, ou ajuste o seletor em `search()` |
| Resultado fala só de óculos/produtos | O recorte pegou só parte do rosto. Gere um recorte maior (`scan_faces.py` salva o melhor frame) |
| Chrome não abre | Informe `--chrome "caminho/chrome"`; em Linux instale `chromium` |

## Borrão / extensor / ffmpeg
| Sintoma | Solução |
|---|---|
| `'ffmpeg' não encontrado` | Instale ffmpeg e ponha no PATH, ou defina `FFMPEG` e `FFPROBE` com o caminho completo |
| Encoder de GPU falha | Use `--encoder libx264` (CPU, mais lento). `setup_check.py` mostra o que foi detectado |
| Duração final ≠ 10:00 (`verify.py`) | Extensor menor que o alvo (o script avisa) ou `--target` diferente. Sem extensor o vídeo mantém a duração original |
| Arquivos muito grandes | Suba `--cq` (ex.: 32). 360p de origem não ganha com bitrate alto |
| Borrão em objetos (mãos, terra) | Falsos positivos do detector. Suba `--min-score 0.6/0.7` **e confira com `verify.py`** (pode deixar escapar rostos pequenos) |
| Rosto sem borrão em alguns quadros | Rosto de perfil/pequeno. Baixe `--min-score` (0.4), use `--step 1` e aumente `--hold` (ex.: 1.0) |
| `Referenced QT chapter track not found` | Aviso inofensivo do ffprobe/ffmpeg em arquivos do Facebook |
| Muito lento em CPU | Reduza `--workers` ao nº de núcleos/2, use `--step 3`, ou use GPU |
| Windows: caminho com acento/espaço | Sempre entre aspas. Os scripts usam caminhos absolutos internamente |
