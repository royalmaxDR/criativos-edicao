# Histórico do projeto (para retomar sem depender da conversa)

Resumo do que foi construído e decidido. Os dados específicos da conta (links do canal, IDs de avatar e voz, pastas locais) ficam em `projetos/REGISTRO.md`, que **não** vai para o repositório.

## Linha do tempo

1. **Criativo base (FDC).** Análise quadro a quadro de um anúncio vertical de 104 s (apresentador + b-roll). Dela saíram o estilo `cinematico_revelacao`, os efeitos A/B/C/D/bsw, a câmera e a trilha → `docs/ESTILO_REFERENCIA.md`.
2. **Teste FDC e ANJO-SM.** Primeiras recriações com avatar, voz tratada e b-roll em domínio público. O motor do ANJO virou o `render.py` genérico (plano em JSON).
3. **Skill.** Extrator de estilo, gerador de plano, render, efeitos plugáveis, LUTs, instalação para a equipe; publicada no GitHub (privado).
4. **SL.** Reedição de um criativo com pastor + react: corte de trecho mantendo a voz, versão HD, hook encenado da porta (cena gerada + sons sincronizados + lip-sync), 3 variações de avatar e, por fim, versão sem o hook da porta (abre com a mulher do react).
5. **NASA e CHAMP.** Copies reescritas (sem promessa de cura), versão só com imagens e versão com avatar.
6. **CV42 e CV47.** Recriação com avatar e voz do banco no lugar do apresentador original.
7. **Tradução.** 9 criativos recriados em inglês nativo (voz nativa, lip-sync refeito, textos fixos traduzidos).
8. **IMG6209.** Reedição com os avatares do original e depois com avatar novo.

## Decisões que valem para tudo

- **Figuras públicas:** não se identifica ninguém pelo rosto (nem por busca reversa); decide-se por contexto (nome, logotipo, traje, legenda). Borrão só em figura pública; react, UGC e avatar ficam sem filtro. Resposta curta e ambígua do dono = processar e subir sem borrão.
- **Pessoa real:** não se recria aparência nem voz de pessoa real identificável (sósia, clone de voz, lip-sync em outra língua), nem "sem dizer o nome". Voz de anúncio de terceiros não é clonada: escolhe-se no banco a mais próxima em tom.
- **Copy:** sem promessa de cura/saúde, sem fato falso sobre pessoa real, sem valor ou prazo garantido. Trocar só a palavra mantendo a promessa não resolve; a troca mínima tem de mudar a promessa. Gancho, tensão e urgência podem ser fortes. Sempre avisar os trechos com risco de reprovação.
- **Entrega:** sempre com e sem legenda; mandar os arquivos finais no chat; no canal sobem "sem extensão" e "com extensão" (10 min intercalada), como não listado; lembrar de desativar comentários. Nunca excluir vídeo do canal sem aprovação.
- **Custo:** reutilizar avatar da conta antes de criar; subir a narração uma vez e gerar vários avatares; informar créditos gastos e saldo.
- **Velocidade:** `--jobs` = metade das threads; nunca dois renders com NVENC ao mesmo tempo; refazer só o trecho que mudou e emendar com `splice.py`.

## O que cada criativo ensinou

| Criativo | Lição que virou recurso |
|---|---|
| FDC (base) | presets de transição, câmera, trilha grave sintetizada |
| ANJO-SM | render por pedaços paralelos; b-roll do Commons com registro de origem |
| SL | `cut_ranges.py`, zoom máximo para fonte mole, `hook_signal.py`, `sync`/`grade` por segmento |
| NASA / CHAMP | `narracao_dinamica`, `assign_broll.py`, regras de copy |
| CV42 / CV47 | escolha de voz por medida de tom; trocar apresentador real por avatar |
| Versões EN | tradução nativa reaproveitando imagens com mapa de palavras do idioma novo |
| IMG6209 | recorte sincronizado para esconder legendas queimadas; avatar novo por prompt |

## Pendências conhecidas

Ficam listadas no fim de `projetos/REGISTRO.md` (dependem da conta e do canal).
