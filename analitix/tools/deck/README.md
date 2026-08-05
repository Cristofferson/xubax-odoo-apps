# La presentación de venta

`ANALITIX.pptx` se genera con `build_deck.py`. Se guarda el generador y no solo
el archivo porque las cifras salen de la demo de retail: cuando esos datos
cambien, la presentación se rehace en un minuto en vez de editarse a mano lámina
por lámina, que es como una presentación acaba diciendo algo distinto de lo que
enseña el sistema.

    python3 -m venv /tmp/pptx_venv && /tmp/pptx_venv/bin/pip install python-pptx
    # las imágenes se esperan en /tmp/ppt/ (ver la lista abajo)
    /tmp/pptx_venv/bin/python build_deck.py

**Imágenes que consume**, todas ya versionadas en el repo:

| Origen | Cuáles |
|---|---|
| `tools/demo/overlay.html?bare=1&lang=es` | door, floor, frustrated, walkout, install, cameras |
| `static/description/screenshots/` | alert-discuss |
| `tools/deck/img/` | chart-hora, chart-salidas (de `charts.html`) |
| tema del sitio | `analitix-logo-blanco.png` |

🚨 Los renders van en la variante **`bare`**, sin el titular quemado: si no, el
título de la lámina compite con el texto de dentro de la foto.

🚨 Las cifras (62 salidas, 40 rescatadas, la curva por hora) son las **reales**
de la BD `retail`. Si se tocan los datos demo, hay que rehacer `charts.html`.

Para revisar el resultado sin PowerPoint:

    soffice --headless --convert-to pdf ANALITIX.pptx
    pdftoppm -png -r 60 ANALITIX.pdf lam
