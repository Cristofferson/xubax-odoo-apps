# La presentación de venta

`slides.html` compone las quince láminas; `build_deck.py` las monta a sangre en
`ANALITIX.pptx`.

    /home/ubuntu/pw_venv/bin/python  →  captura #s1..#s15 a n01..n15.jpg
    /tmp/pptx_venv/bin/python build_deck.py

## Por qué las láminas son imágenes

La primera versión se armó con cajas de texto de PowerPoint: editable, y con
aspecto de plantilla — Arial, el mismo encuadre quince veces y una banda negra
cortando cada foto. PowerPoint no da control sobre degradados, retículas ni
tipografía condensada, y sin eso no hay diseño. Para cambiar un texto se edita
el HTML y se vuelve a correr, que toma menos que pelearse con las guías.

## El sistema visual

* **Se lee como el registro de una cámara**: la hora enorme en cada lámina de
  la historia, y una línea roja fina que es la misma línea virtual que el
  producto dibuja en la puerta.
* **Ritmo alternado** oscuro / claro. Quince láminas oscuras seguidas es lo que
  hacía que la primera versión se sintiera plantilla.
* **Bebas Neue** para cifras y titulares (voz de letrero de tienda) e **Inter**
  para lo que hay que leer. `apt install fonts-bebas-neue fonts-inter-variable`.
* 🚨 El rojo es el **del logo, `#F70814`** — no el dorado, que venía de la ficha
  de apps.odoo.com y no es la marca.

## Trampas

🪤 Los renders de la historia van en la variante **`bare`** (sin el titular
quemado) o el título de la lámina compite con el texto de dentro de la foto.
🪤 La lámina de hardware usa las fotos **limpias** de `tools/demo/crop/`, sin el
overlay del producto: ahí se habla de la mini PC, no de lo que el sistema pinta,
y los rótulos chocaban con el texto.
🪤 Los tickets van **dentro** de la barra de visitantes, no encima: son un
subconjunto, y apilarlos hacía que la columna midiera visitantes+tickets.
🪤 Exportar a JPEG 2560 px con `subsampling=0`: a 3200 px el .pptx pesaba 27 MB,
y con submuestreo de color el texto fino se ensucia.

Las cifras (62 salidas, 40 rescatadas, la curva por hora) son las **reales** de
la BD `retail`. Si cambian los datos demo, hay que rehacerlas.

Para revisar sin PowerPoint: `soffice --headless --convert-to pdf ANALITIX.pptx`
