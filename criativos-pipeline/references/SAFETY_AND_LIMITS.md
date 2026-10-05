# Segurança, ética e limites

## O que o pipeline NÃO faz
- **Não identifica pessoas.** `scan_faces.py` só diz "este rosto é o mesmo daquele". `lens_search.py` repassa o que o Google
  Lens encontrou. Nenhum agente deve acrescentar nomes por conta própria a partir de um rosto.
- **Não burla CAPTCHA, login ou bloqueios.** Se aparecer, pare e peça ao usuário.
- **Não envia nada para fora** (YouTube, redes, nuvem). Isso exige pedido e confirmação explícitos do usuário.
- **Não pede nem usa credenciais.**

## Como tratar os resultados do Lens
- É uma busca por **semelhança visual**. O resumo de IA pode errar (ex.: apontar alguém por causa de óculos, roupa ou cenário).
- Use como **pista de risco**. Para um relatório: "o Lens sugere X (fonte)", nunca "esta pessoa é X".
- Se o Lens aponta uma figura pública, a ação segura é **borrar com `mosaic`** (ou descartar o criativo).
- Imagens de pessoas conhecidas em anúncios com promessas milagrosas costumam ser uso indevido de imagem (às vezes deepfake).
  Isso é mais um motivo para não reutilizar esse material sem borrar/substituir.

## Privacidade dos dados
- Os recortes de rosto enviados ao Google Lens saem da sua máquina. Envie apenas o necessário (recortes, não vídeos).
- `lens_search.py` usa um perfil temporário do Chrome e o apaga ao terminar (não usa seu perfil/logins).
- O repositório não contém vídeos, tokens nem dados pessoais. Mantenha assim: **não faça commit** de `trabalho/`, vídeos ou `.env`.

## Direitos e termos
- Criativos de anúncio pertencem aos anunciantes/criadores. Baixar para **análise** é uma coisa; **republicar** é outra
  (direitos autorais, direito de imagem, termos de uso da Meta). A responsabilidade pelo uso é do usuário.
- Borrar o rosto **não** transforma o material em seu. Prefira inspirar-se na estrutura/ideia e produzir conteúdo original ou licenciado.

## Limites técnicos conhecidos
- O detector (YuNet) pode falhar em rostos muito pequenos, de perfil, cobertos ou muito borrados; `--min-score 0.5` já é o mais
  protetivo. **Sempre verifique a olho** os trechos com rosto.
- `strong` esconde olhos/nariz/boca com folga e derrota o SFace nos testes, mas não é garantia contra todo reconhecedor.
  Para casos sensíveis use `mosaic`.
- Os testes de reconhecimento do `verify.py` usam um modelo (SFace), não o Google; é um indicador, não uma garantia.
- "Mais antigos" depende de quantos anúncios a página conseguiu carregar.
