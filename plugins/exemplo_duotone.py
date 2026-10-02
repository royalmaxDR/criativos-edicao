# -*- coding: utf-8 -*-
"""Exemplo de plugin: efeito novo registrado com @effect. Copie este arquivo, mude o nome e a funcao.
Use no plano como  [12.40, "duotone"]  dentro de "fx"."""
import numpy as np
from fx import effect


@effect("duotone", pre=0.04, post=0.20, focus=(0.1, 0.3, 3, 2), sfx=(("hit", 0.0, 0.2),),
        desc="pisca em duas cores (azul escuro / laranja) por 6 frames e volta")
def duotone(img, k, c):
    a = {-1: 0.4, 0: 1.0, 1: 1.0, 2: 0.8, 3: 0.55, 4: 0.3, 5: 0.12}.get(k)      # forca do efeito em cada frame em volta do corte
    if a is None:
        return img
    y = c.gray(img)[..., None] / 255.0                                           # luminancia 0..1
    duo = np.float32([90, 30, 10]) * (1 - y) + np.float32([40, 150, 255]) * y    # sombra azul (BGR) -> alta luz laranja
    return img * (1 - a) + duo * a
