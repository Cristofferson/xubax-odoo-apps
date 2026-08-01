# -*- coding: utf-8 -*-
"""Third batch: strings whose msgid carries XML indentation.

These are keyed on their whitespace-normalised form (see make_es_po.py), so the
translation does not have to reproduce a view's indentation byte for byte —
which is exactly the kind of transcription error Odoo swallows in silence.
"""
BATCH3 = {
    "<b>Copy these keys now.</b> Odoo keeps only a hash of them, so this screen is "
    "the one and only time they can be read. Paste each into its device's agent "
    "configuration before you leave the site. If one is lost, rotate it from the "
    "device form.":
        "<b>Copia estas llaves ahora.</b> Odoo solo guarda un hash de ellas, así que "
        "esta pantalla es la única vez que se pueden leer. Pega cada una en la "
        "configuración del agente de su dispositivo antes de irte del sitio. Si se "
        "pierde alguna, rótala desde la ficha del dispositivo.",

    "<b>Empty means every store</b> of the companies this user already belongs to. "
    "That is the right setting for a customer who runs one store, and it needs no "
    "configuration.":
        "<b>Vacío significa todas las tiendas</b> de las compañías a las que este "
        "usuario ya pertenece. Es lo correcto para un cliente con una sola tienda, y "
        "no requiere configurar nada.",

    "On a shared instance hosting several customers, fill this in. Once it has any "
    "value the user sees <b>only</b> those stores — no group, company switch or "
    "manager role widens it.":
        "En una instancia compartida con varios clientes, llena este campo. En cuanto "
        "tiene algún valor, el usuario ve <b>solo</b> esas tiendas: ningún grupo, "
        "cambio de compañía ni rol de gerente lo amplía.",

    "A signature is a list of numbers produced from a face by the enrolment tool. No "
    "photograph is stored here or anywhere else in Analitix, and no image can be "
    "rebuilt from it. It is encrypted in the database and its only use is to keep "
    "this employee out of the visitor count.":
        "Una firma es una lista de números que la herramienta de registro produce a "
        "partir de un rostro. Aquí no se guarda ninguna fotografía, ni en ninguna otra "
        "parte de Analitix, y de la firma no se puede reconstruir ninguna imagen. Está "
        "cifrada en la base de datos y su único uso es mantener a este empleado fuera "
        "del conteo de visitantes.",

    "Devices appear here grouped by status. A critical device that stops sending "
    "heartbeats raises an activity and an e-mail to the store's technical contacts, "
    "because while it is down that store's conversion figures are incomplete.":
        "Los dispositivos aparecen aquí agrupados por estado. Un dispositivo crítico "
        "que deja de mandar latidos genera una actividad y un correo a los contactos "
        "técnicos de la tienda, porque mientras esté caído las cifras de conversión de "
        "esa tienda están incompletas.",

    "Employees cross the door all day. Left in the count they can be a third of the "
    "\\\"visitors\\\", which drags the conversion rate down and keeps it there.":
        "Los empleados cruzan la puerta todo el día. Si se dejan en el conteo pueden "
        "ser un tercio de los \\\"visitantes\\\", lo que jala la tasa de conversión "
        "hacia abajo y la deja ahí.",

    "Enrol your team from the edge enrolment tool. Their crossings then stop counting "
    "as visitors, whichever door they use — without it, a small store's conversion "
    "rate reads far lower than the truth.":
        "Registra a tu equipo desde la herramienta de registro del edge. Sus cruces "
        "dejan de contar como visitantes, sin importar por qué puerta pasen: sin esto, "
        "la conversión de una tienda pequeña se lee muy por debajo de la real.",

    "Everything that differs between customer stores lives on this screen. Add one "
    "line per entrance — one, three, seven — and Analitix creates the store, its "
    "doors, a counting device for each and their API keys in a single pass.":
        "Todo lo que cambia de una tienda cliente a otra vive en esta pantalla. Agrega "
        "una línea por entrada (una, tres, siete) y Analitix crea la tienda, sus "
        "puertas, un dispositivo de conteo para cada una y sus llaves de API de una "
        "sola pasada.",

    "Face matching, signage triggers and CRM writes run here instead of on the ingest "
    "request, so a slow integration can never hold up a store's counting. A growing "
    "backlog here means the Odoo scheduler is not running.":
        "La comparación facial, los disparos a pantallas y las escrituras al CRM corren "
        "aquí y no en la petición de ingesta, para que una integración lenta nunca "
        "detenga el conteo de una tienda. Una cola que crece aquí significa que el "
        "planificador de Odoo no está corriendo.",

    "JSON handed to the agent when it calls <code>/analitix/api/v1/config</code>: line "
    "coordinates, camera index, zone polygons. Retune a camera from here instead of "
    "going back to the store with a laptop.":
        "JSON que se le entrega al agente cuando llama a "
        "<code>/analitix/api/v1/config</code>: coordenadas de la línea, índice de "
        "cámara, polígonos de zona. Reajusta una cámara desde aquí en vez de volver a "
        "la tienda con una laptop.",

    "Odoo stores only a hash of the API key, so it cannot be read back — it is shown "
    "once when issued or rotated. If a key is lost, rotate it and reconfigure the "
    "device.":
        "Odoo solo guarda un hash de la llave de API, así que no se puede volver a "
        "leer: se muestra una vez al emitirla o rotarla. Si se pierde una llave, rótala "
        "y reconfigura el dispositivo.",

    "Odoo's chatter records who <i>changed</i> something. This records who "
    "<i>looked</i>: reads of sensitive data, report exports, key rotations, use of the "
    "kill switch and rejected credentials. Entries can never be edited or deleted, by "
    "anybody.":
        "El chatter de Odoo registra quién <i>cambió</i> algo. Esto registra quién "
        "<i>miró</i>: consultas de datos sensibles, exportaciones de reportes, "
        "rotaciones de llaves, uso del interruptor de emergencia y credenciales "
        "rechazadas. Las entradas no las puede editar ni borrar nadie, nunca.",

    "Once a store's devices start reporting and POS orders exist, this is where "
    "visitors meet sales: conversion, average ticket, units per ticket, revenue per "
    "visitor and density per m².":
        "En cuanto los dispositivos de una tienda empiezan a reportar y hay pedidos de "
        "TPV, aquí es donde los visitantes se cruzan con las ventas: conversión, ticket "
        "promedio, unidades por ticket, ingreso por visitante y densidad por m².",

    "One line per entrance. A store may have as many as it actually has — the rest of "
    "Analitix follows this list.":
        "Una línea por entrada. Una tienda puede tener tantas como realmente tenga: "
        "todo lo demás en Analitix sigue esta lista.",

    "This door's crossings are recorded but do not count as visitors. Traffic here "
    "still shows on the door report; it simply stays out of the store's conversion "
    "rate.":
        "Los cruces de esta puerta se registran pero no cuentan como visitantes. El "
        "tráfico sigue apareciendo en el reporte por puerta; simplemente se queda fuera "
        "de la tasa de conversión de la tienda.",

    "Traffic broken down per entrance, with each door's share of the store's total. "
    "Conversion is deliberately absent here: a ticket belongs to the store, not to the "
    "door the customer walked through, so a per-door conversion rate would be a "
    "fiction.":
        "Tráfico desglosado por entrada, con la participación de cada puerta en el "
        "total de la tienda. La conversión no aparece aquí a propósito: un ticket "
        "pertenece a la tienda, no a la puerta por la que entró el cliente, así que una "
        "conversión por puerta sería una ficción.",

    "Use <b>Configuration → New Store Setup</b> to create a store with all its doors "
    "and their device keys in one pass.":
        "Usa <b>Configuración → Alta de tienda nueva</b> para crear una tienda con "
        "todas sus puertas y las llaves de sus dispositivos de una sola pasada.",

    "How POS sales are attributed to this store for conversion: • Specific POS "
    "registers: only orders from the registers below. Use this when several stores "
    "share one company. • Whole company: every POS order of the company. Use this when "
    "the company runs a single store.":
        "Cómo se atribuyen las ventas de TPV a esta tienda para la conversión: • Cajas "
        "de TPV específicas: solo los pedidos de las cajas de abajo. Úsalo cuando "
        "varias tiendas comparten una compañía. • Toda la compañía: todos los pedidos "
        "de TPV de la compañía. Úsalo cuando la compañía tiene una sola tienda.",

    "%(key)s This is the only time it is shown. Odoo stores only a hash of it; if it "
    "is lost, rotate again.":
        "%(key)s Esta es la única vez que se muestra. Odoo solo guarda un hash; si se "
        "pierde, hay que rotarla otra vez.",

    "Door: %(door)s Device UID : %(uid)s API key : %(key)s":
        "Puerta: %(door)s UID del dispositivo : %(uid)s Llave de API : %(key)s",

    "<span class=\\\"text-muted d-block small\\\">Inside now</span>":
        "<span class=\\\"text-muted d-block small\\\">Dentro ahora</span>",
    "<span class=\\\"text-muted d-block small\\\">Visitors today</span>":
        "<span class=\\\"text-muted d-block small\\\">Visitantes hoy</span>",
}
