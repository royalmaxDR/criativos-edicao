# Voz e avatar

O motor de edição só precisa de dois arquivos: `vo.wav` (narração) e `avatar.mp4` (apresentador falando **esse mesmo áudio**). De onde eles vêm é livre — HeyGen foi o usado até aqui.

## Ordem que economiza créditos

1. **Feche a copy antes** de gerar qualquer coisa. Cada regravação custa.
2. **Voz primeiro, sozinha** (barata). Ouça/meça, trate com `voice_fx.py`, e só então gere o avatar.
3. **Avatar por lip-sync do áudio tratado**, não por texto: assim a voz do vídeo é exatamente a que você aprovou e não há segunda geração de fala.
4. **720p, 9:16** basta — o render reenquadra e escala para 1080x1920.
5. **Um avatar por projeto**, reutilizado em todas as variações. Criar avatar novo custa bem mais que gerar vídeo.
6. Teste o estilo com **20–30 s** antes de gerar o vídeo inteiro.

Ordem de grandeza medida (plano Pro do HeyGen): um vídeo de 91 s por lip-sync custou 30 créditos; criar um avatar novo por prompt + um teste descartado elevou um teste curto a 141. Confira o saldo antes e depois e informe o gasto ao usuário.

## Voz

- Escolha uma voz firme e pausada; motor expressivo (no HeyGen, `elevenlabs_v3`) responde melhor à pontuação.
- **A entonação vem do texto**: frases curtas, ponto final onde quer peso, reticências para pausa, vírgula antes da palavra-chave.
- Tratamento: `python scripts/voice_fx.py vo_raw.wav vo.wav --preset imponente` (1 semitom abaixo com timbre preservado, corpo em 110 Hz, presença em 3,2 kHz, compressão 4:1, −14 LUFS).
- Compare com a referência em números: `python scripts/voice_fx.py --stats vo.wav referencia.mp4`. Na referência original o tom mediano era ~142 Hz; uma voz já em ~125 Hz não precisa descer mais — precisa de entonação e corpo.
- Tempos das palavras: `python scripts/transcribe.py vo.wav --out words.json --lang pt`. Confira nomes próprios e números e corrija em `captions.fix`.

## Avatar

- Descreva alguém **condizente com a copy** (idade, roupa, cenário, enquadramento meio-corpo, olhando para a câmera, microfone opcional), **genérico**: sem logotipo, sem uniforme de instituição real, sem semelhança com pessoa conhecida.
- Enquadramento ideal no arquivo gerado: rosto com ~30–40% da largura, olhos no terço superior, espaço acima da cabeça. O render imprime o que detectou (`avatar: … largura 0.32 do quadro`).
- Fundo com profundidade (estante, luminária) rende mais nos closes com difusão.
- Vídeo gravado de verdade também serve: basta estar sincronizado com `vo.wav` (mesmo início).

## Rotas no HeyGen

| Rota | Quando | Como |
|---|---|---|
| **Conector MCP** (Claude e outros agentes com MCP) | o usuário já conectou o HeyGen | ferramentas `create_speech` → baixar o áudio → tratar → enviar o áudio → `create_video_from_avatar` com `audioUrl`, 9:16, 720p → `get_video` até concluir |
| **API REST** | agentes sem MCP | chave em variável de ambiente `HEYGEN_API_KEY` (o usuário configura; nunca no repositório nem no chat). Consulte a documentação atual da API do HeyGen para os endpoints de upload de áudio, geração de vídeo por avatar e consulta de status |
| **Site** | sem integração | o usuário gera pelo painel com o `vo.wav` tratado e salva `avatar.mp4` na pasta do projeto |

O agente não cria conta, não digita senha e não gera chave: isso é do usuário.

## Outras fontes de voz/avatar

ElevenLabs (voz), Azure/Google TTS (voz), D-ID, Synthesia, Hedra, gravação própria. Qualquer uma serve desde que entregue os dois arquivos acima e a licença permita uso em anúncio.
