# -*- coding: utf-8 -*-
"""Arma el .pptx a partir de las láminas compuestas en slides.html.

Por qué las láminas son imágenes y no cajas de texto de PowerPoint: la primera
versión sí era editable y se veía como una plantilla —Arial, el mismo encuadre
quince veces, una banda negra cortando cada foto—. PowerPoint no da control
sobre degradados, retículas ni tipografía condensada, y sin eso no hay diseño.
Componiendo en HTML sí lo hay.

El intercambio se asume a conciencia: para cambiar un texto se edita
`slides.html` y se vuelve a correr esto, que toma menos que pelearse con las
guías de PowerPoint. Por eso el generador vive en el repositorio y no solo el
archivo final.
"""
import glob
import os

from pptx import Presentation
from pptx.util import Inches

D = os.path.dirname(os.path.abspath(__file__))
ANCHO, ALTO = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width, prs.slide_height = ANCHO, ALTO
en_blanco = prs.slide_layouts[6]

laminas = sorted(glob.glob(os.path.join(D, "n[0-9][0-9].jpg")))
assert laminas, "no hay láminas: corre primero el render de slides.html"

for archivo in laminas:
    s = prs.slides.add_slide(en_blanco)
    # A sangre: la lámina ES la imagen, 16:9 exacto, sin recorte ni margen.
    s.shapes.add_picture(archivo, 0, 0, width=ANCHO, height=ALTO)

salida = os.path.join(D, "ANALITIX.pptx")
prs.save(salida)
print("%d láminas → %s (%.1f MB)" % (
    len(laminas), salida, os.path.getsize(salida) / 1e6))
