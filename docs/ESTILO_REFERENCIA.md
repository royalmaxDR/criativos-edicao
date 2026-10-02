# O estilo aprendido com o criativo de referência

Referência: anúncio vertical de 104 s, apresentador + b-roll, tom de mistério/revelação. Analisado quadro a quadro (rastreamento do rosto, nitidez, diferença entre frames, tiras de 14 frames por transição, espectrograma). Este documento é a "memória" do estilo; o preset `cinematico_revelacao` e os padrões do `render.py` saem daqui.

## Estrutura

- **Dois layouts que se alternam**: tela dividida (apresentador nos ~50% de cima, b-roll embaixo) e apresentador em tela cheia. Cerca de metade do tempo em cada.
- **Emenda da tela dividida**: não é uma linha; é uma faixa esfumada (~8% da altura) e escurecida, com a legenda bem em cima dela.
- **Ritmo**: ~22 blocos, média 4,7 s. Dentro da tela dividida o b-roll troca a cada 1–2,5 s. ~10 transições fortes por minuto.
- **Três escalas em tela cheia** (largura do rosto ÷ largura do quadro): 0,46 aberto · 0,52 médio · 0,56–0,60 close. Na tela dividida, 0,46 com o rosto a 20–24% da altura.
- **Sequência típica**: abre em tela dividida (gancho ilustrado) → corte para médio → close na frase de impacto → volta para dividida com b-roll novo.

## Texto na tela

- Legenda palavra a palavra: 1–3 palavras, maiúsculas, fonte condensada pesada, branca com contorno preto, **caixa vermelha atrás da palavra-chave**. Na emenda (tela dividida) ou no terço inferior (tela cheia).
- Faixa verde no topo "TOQUE NO BOTÃO ABAIXO" com setas, só nos trechos de chamada.
- Cartão final preto de ~4,5 s: "CLIQUE EM SAIBA MAIS" com setas animadas descendo e só a trilha.

## Transições (medidas frame a frame, 30 fps; k = frame relativo ao corte)

**A — prisma + zoom-blur** (~8 frames; usada em cheia→cheia e dividida→cheia)
k−3 desfoque leve · k−2, k−1 borrão de movimento vertical longo + separação de cor vertical + tinta arco-íris a ~20% · k0 **um frame limpo** · k1 borrão diagonal + RGB separado · k2 zoom ~1,9x girado com desfoque pesado · k3 1,28x · k4 1,09x · depois o foco "assenta" em ~0,4 s.

**B — estrobo solarizado** (~7 frames)
k−1 brilho estourado com tinta roxa · k0 duotone roxo solarizado sobre fundo escuro · k1–k2 negativo verde com contorno brilhante, zoom 1,55x girado −9° · k3 superexposição quente · k4 negativo P&B · k5 P&B lavado. A escala "pula" a cada frame.

**C — glitch RGB / datamosh** (~5 frames)
2 frames de ruído leve → 3 frames de fatias horizontais deslocadas, RGB separado e blocos de cor.

**D — rasgo horizontal** (cheia→dividida)
~4 frames de barras brancas horizontais deslocando faixas, e em seguida uma varredura de luz quente atravessa o b-roll (~0,5 s).

**bsw — troca de b-roll**
0,2 s de zoom-blur (1,18x → 1, desfoque forte → 0), sem cortar o apresentador.

Proporção certa: os efeitos são **rápidos e escuros**. Arco-íris em tela cheia ou solarização clara ficam amadores; a referência usa a cor como tempero (14–22%) e deixa o fundo escuro.

## Câmera

- **Tela dividida**: balanço lateral lento (±3,5% da largura, período ~9 s) + "respiração" de escala de ~1%.
- **Entrada em tela cheia**: estouro de escala de +10% que decai em ~0,1 s (`z = alvo × (1 + 0,10 × e^(−t/0,11))`).
- **Durante o bloco**: close recua ~5%; médio avança ~3,5%.
- **Antes de voltar para a dividida**: empurrão de +13% nos últimos 0,17 s.
- **Sempre**: microtremor de câmera na mão (passeio aleatório suavizado) e difusão suave nos closes (imagem + 16% dela mesma desfocada).

## Cor e acabamento

Vinheta forte · b-roll dessaturado e azulado (≈62% da cor + tinta fria) · contraste levemente acima · leve aberração cromática (2 px) · grão fino.

## Áudio

- **Base grave contínua** (30–220 Hz) com um pulso a cada ~8 s; volume ~0,03 RMS contra ~0,17 da voz (a base se sente, não se ouve por cima).
- **Efeitos nas transições**: whoosh (ruído filtrado subindo de 0,5 a 7 kHz, ~0,4 s) um pouco antes do corte + boom grave (50 Hz, decaimento ~0,9 s) no corte. Estalos digitais no glitch e no estrobo.
- **Voz**: tom mediano ~142 Hz (faixa 107–176), firme e pausada, −14 LUFS. A imponência vem da entonação e do corpo em ~110 Hz, não de tom muito baixo.
- Cauda final: ~4,5 s só de trilha sobre o cartão.

## Como isso vira parâmetro

| Observação | Onde está |
|---|---|
| layouts e ritmo | `presets/styles/cinematico_revelacao.json` → `pacing`, `fx` |
| escalas de zoom | `shots.levels` (ou `face_w` por segmento) |
| câmera | `camera` no plano (padrões do `render.py`) |
| transições | `scripts/fx.py` (`A`, `B`, `C`, `D`, `bsw`) |
| cor | `look` no plano + `luts/frio_misterio.cube` |
| trilha | `scripts/audio_engine.py` (`drone`, `whoosh`, `boom`, `crackle`) |
| voz | `scripts/voice_fx.py --preset imponente` |
