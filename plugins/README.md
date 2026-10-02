# Plugins de efeito

Todo arquivo `.py` desta pasta (que não comece com `_`) é carregado pelo `render.py`. Cada um registra um ou mais efeitos:

```python
import numpy as np
from fx import effect

@effect("meu_efeito", pre=0.07, post=0.20, focus=(0.1, 0.3, 3, 2), sfx=(("whoosh", -0.1, 0.15),), desc="o que faz")
def meu_efeito(img, k, c):
    ...
    return img
```

## Parâmetros do `@effect`

| Parâmetro | Significado |
|---|---|
| `nome` | o que vai no plano: `[12.4, "meu_efeito"]` |
| `pre`, `post` | janela em segundos antes/depois do corte em que a função é chamada |
| `focus` | `(início_s, fim_s, sigma, potência)`: desfoque que assenta depois do corte (retomada de foco). Omitir = sem |
| `sfx` | sons disparados: `(som, atraso_s, ganho[, {parâmetros}])`. Sons: `whoosh` (`d`), `boom` (`d`, `f0`), `crackle` (`d`), `hit` (`d`), `riser` (`d`) |
| `desc` | descrição que aparece nas listagens |

## A função

- `img`: quadro `float32` BGR `(H, W, 3)`, 0–255, já composto. Devolva no mesmo formato (pode passar de 255; o render corta).
- `k`: frame relativo ao corte em passos de 1/30 s. `k = 0` é o primeiro frame depois do corte; negativos são antes.
- `c`: utilitários —
  `c.W`, `c.H`, `c.S` (escala em relação a 1920 de altura), `c.dt` (segundos desde o corte), `c.layout` (`split`/`full`/`broll`), `c.intensity`
  `c.px(v)` converte pixels de 1920p para o tamanho atual · `c.warp(img, escala, ângulo)` · `c.shift(img, dx, dy)` · `c.chroma(img, d)` separação RGB · `c.blur(img, sigma)` · `c.gray(img)`
  `c.xx`, `c.yy` coordenadas · `c.VIG` vinheta · `c.RAIN` arco-íris diagonal · `c.rng` (`random.Random` do frame) · `c.nrng` (`numpy` `RandomState` do frame)

Use sempre `c.rng`/`c.nrng` em vez de `random`/`np.random`: o render é dividido em processos e precisa dar o mesmo resultado em todos.

## Receita

O jeito mais simples é um dicionário "força por frame":

```python
a = {-1: 0.4, 0: 1.0, 1: 0.8, 2: 0.5, 3: 0.2}.get(k)
if a is None:
    return img
return img * (1 - a) + efeito(img) * a
```

Teste: `python scripts/render.py plan.json --preview 11-14` e tire uma tira de frames em volta do corte.
