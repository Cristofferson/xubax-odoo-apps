# -*- coding: utf-8 -*-
"""Fifth batch: phase 3 — zones, lost sales, displays, alerts, identification."""
BATCH5 = {
    # ---- models and menus ------------------------------------------
    "Analitix Discreet Alert": "Aviso discreto de Analitix",
    "Analitix Store Zone": "Zona de tienda de Analitix",
    "Analitix Zone Coverage": "Cobertura de zona de Analitix",
    "Analitix Zone Dwell": "Permanencia por zona de Analitix",
    "Analitix Display / Point of Interest": "Exhibidor / punto de interés de Analitix",
    "Analitix Display Attention": "Atención al exhibidor de Analitix",
    "Analitix — Display Attention vs Sales":
        "Analitix — Atención al exhibidor contra ventas",
    "Analitix Lost Sale": "Venta perdida de Analitix",
    "Analitix Visit ↔ Ticket": "Visita ↔ ticket de Analitix",
    "Analitix Behaviour Signal": "Señal de comportamiento de Analitix",
    "Alert": "Aviso",
    "Alerts": "Avisos",
    "All Alerts": "Todos los avisos",
    "My Alerts": "Mis avisos",
    "Zone": "Zona",
    "Zones": "Zonas",
    "Zone Count": "Número de zonas",
    "Zone Dwell": "Permanencia por zona",
    "Zone Type": "Tipo de zona",
    "Display": "Exhibidor",
    "Displays": "Exhibidores",
    "Display Performance": "Desempeño del exhibidor",
    "Lost Sale": "Venta perdida",
    "Lost Sales": "Ventas perdidas",
    "Lost sales": "Ventas perdidas",
    "Ticket Attribution": "Atribución de tickets",
    "Behaviour Signal": "Señal de comportamiento",
    "Behaviour Signals": "Señales de comportamiento",
    "Behaviour signals": "Señales de comportamiento",
    "Shift Coverage": "Cobertura por turno",
    "Cameras": "Cámaras",
    "Floor & Alerts": "Piso y avisos",
    "Tickets and customers": "Tickets y clientes",
    "Context": "Contexto",

    # ---- crons -----------------------------------------------------
    "Analitix: mark unacknowledged alerts as missed":
        "Analitix: marcar como no atendidos los avisos sin acuse",
    "Analitix: scan for unusual behaviour":
        "Analitix: buscar comportamientos inusuales",
    "Analitix: settle open lost sales":
        "Analitix: cerrar las ventas perdidas abiertas",

    # ---- alert -----------------------------------------------------
    "Alert Cooldown (min)": "Enfriamiento entre avisos (min)",
    "Count As Missed After (min)": "Contar como no atendido tras (min)",
    "Fallback Recipient": "Destinatario de respaldo",
    "WhatsApp Template ID": "ID de la plantilla de WhatsApp",
    "Recipient": "Destinatario",
    "Salesperson": "Vendedor",
    "Message": "Mensaje",
    "Sent": "Enviado",
    "Escalated": "Escalado",
    "Acknowledged": "Con acuse",
    "Acknowledged At": "Acuse el",
    "Response (s)": "Respuesta (s)",
    "Outcome": "Resultado",
    "On it": "Voy",
    "Mine": "Míos",
    "Not Acknowledged": "Sin acuse",
    "Missed": "No atendido",
    "Attended": "Atendido",
    "Ended in a sale": "Terminó en venta",
    "Not attended": "No atendido",
    "WhatsApp": "WhatsApp",
    "No alerts": "No hay avisos",
    "Avg response": "Respuesta prom.",
    "Possible lost sale": "Posible venta perdida",
    "Known customer arrived": "Llegó un cliente conocido",
    "Unusual behaviour": "Comportamiento inusual",
    "Customer looks unhappy": "El cliente se ve molesto",
    "Watch-list match": "Coincidencia con la lista de vigilancia",
    "Nobody was rostered on that zone. A lot of these means the shift map is "
    "wrong.":
        "No había nadie asignado a esa zona. Muchos de estos significan que el "
        "rol de turnos está mal.",

    # ---- zone ------------------------------------------------------
    "Entrance area": "Zona de entrada",
    "Display / counter": "Exhibidor / mostrador",
    "Fitting rooms": "Probadores",
    "Checkout": "Caja",
    "General floor": "Piso general",
    "Exit area": "Zona de salida",
    "Engaged After (s)": "Interesado tras (s)",
    "Possible Lost Sale After (s)": "Posible venta perdida tras (s)",
    "Nudge On Long Dwell": "Avisar por permanencia larga",
    "Nudges On Long Dwell": "Avisa por permanencia larga",
    "Dwell Records": "Registros de permanencia",
    "Visits Today": "Visitas hoy",
    "Avg Dwell (s)": "Permanencia prom. (s)",
    "Avg dwell": "Permanencia prom.",
    "Dwell": "Permanencia",
    "Dwell (s)": "Permanencia (s)",
    "Seconds": "Segundos",
    "Engaged": "Interesado",
    "Served": "Atendido",
    "Was Served": "Fue atendido",
    "Nobody Went Over": "Nadie se acercó",
    "Divide the floor": "Divide el piso",
    "m²": "m²",
    "e.g. Engagement Rings": "p. ej. Anillos de compromiso",
    "Another zone of this store already uses that reference.":
        "Otra zona de esta tienda ya usa esa referencia.",
    "The lost-sale threshold cannot be shorter than the engagement one.":
        "El umbral de venta perdida no puede ser menor que el de interés.",
    "Time in the zone. Grows while the visitor is still there.":
        "Tiempo en la zona. Crece mientras el visitante sigue ahí.",
    "The nudge this dwell produced, if it produced one.":
        "El aviso que produjo esta permanencia, si produjo alguno.",

    # ---- shift coverage --------------------------------------------
    "Every day": "Todos los días",
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sábado",
    "Sunday": "Domingo",
    "From": "Desde",
    "To": "Hasta",
    "Store local time. 0 to 24 covers the whole day.":
        "Hora local de la tienda. De 0 a 24 cubre todo el día.",
    "The shift must end after it starts.":
        "El turno debe terminar después de empezar.",
    "Shift hours are a 24-hour clock: 'From' between 0 and 24, 'To' above it.":
        "Las horas del turno son reloj de 24 horas: 'Desde' entre 0 y 24, "
        "'Hasta' por encima.",

    # ---- displays --------------------------------------------------
    "Counts As A Stop After (s)": "Cuenta como parada tras (s)",
    "Products On It": "Productos que tiene encima",
    "What is physically on it": "Qué tiene encima físicamente",
    "Stops": "Paradas",
    "Stops Today": "Paradas hoy",
    "Avg Stop (s)": "Parada prom. (s)",
    "Avg stop": "Parada prom.",
    "Attention": "Atención",
    "Attention (s)": "Atención (s)",
    "Units / Stop": "Unidades / parada",
    "Units / stop": "Unidades / parada",
    "Started": "Inició",
    "Map your displays": "Mapea tus exhibidores",
    "No Products Attached": "Sin productos asignados",
    "No display data yet": "Todavía no hay datos de exhibidores",
    "Draws A Crowd, Sells Little": "Atrae gente, vende poco",
    "Sells Well, Few Visitors": "Vende bien, pocos visitantes",
    "e.g. Window Showcase": "p. ej. Vitrina del aparador",
    "Another display of this store already uses that reference.":
        "Otro exhibidor de esta tienda ya usa esa referencia.",
    "People stop and walk away. Almost always price, or nobody closing.":
        "La gente se detiene y se va. Casi siempre es precio, o que nadie cierra.",
    "It converts everyone who finds it and it is in a cold corner. Move it.":
        "Convierte a todo el que lo encuentra y está en un rincón frío. Muévelo.",

    # ---- lost sale -------------------------------------------------
    "Detect Lost Sales": "Detectar ventas perdidas",
    "Create CRM Leads": "Crear iniciativas de CRM",
    "Detected": "Detectada",
    "Estimated": "Estimado",
    "Estimated Value": "Valor estimado",
    "Open": "Abierta",
    "Rescued": "Rescatada",
    "Rescued By": "Rescatada por",
    "Lost": "Perdida",
    "Lead": "Iniciativa",
    "No lost sales detected": "No se han detectado ventas perdidas",
    "%(zone)s: customer unattended for %(mins)s min":
        "%(zone)s: cliente sin atender desde hace %(mins)s min",
    "%(zone)s · %(when)s": "%(zone)s · %(when)s",
    "Unattended at %(zone)s — %(store)s":
        "Sin atender en %(zone)s — %(store)s",
    "the store": "la tienda",
    "store": "tienda",
    "a display": "un exhibidor",

    # ---- ticket attribution ----------------------------------------
    "Attribute Tickets To Visits": "Atribuir tickets a visitas",
    "Till Match Threshold": "Umbral de coincidencia en caja",
    "Ticket": "Ticket",
    "Matched": "Emparejado",
    "How": "Cómo",
    "Confidence": "Confianza",
    "Face at the till": "Cara en la caja",
    "Through the purchase unit": "Por la unidad de compra",
    "Through The Purchase Unit": "Por la unidad de compra",
    "Through the customer record": "Por la ficha del cliente",
    "Set by hand": "Puesto a mano",
    "Matched By Face": "Emparejado por cara",
    "No tickets attributed yet": "Todavía no hay tickets atribuidos",
    "This ticket is already attributed to a visit.":
        "Este ticket ya está atribuido a una visita.",

    # ---- identification --------------------------------------------
    "Identify Returning Customers": "Identificar clientes recurrentes",
    "Identified Retention (days)": "Retención de identificados (días)",
    "Nudge On Known Customer": "Avisar cuando llegue un cliente conocido",
    "Identified": "Identificado",
    "Identified On": "Identificado el",
    "Customer": "Cliente",
    "%(name)s just came in": "%(name)s acaba de entrar",
    "Face signature linked to customer %s":
        "Firma facial ligada al cliente %s",

    # ---- behaviour signals -----------------------------------------
    "Flag Unusual Behaviour": "Marcar comportamientos inusuales",
    "Behaviour Window (min)": "Ventana de comportamiento (min)",
    "Re-entries Before Flagging": "Reingresos antes de marcar",
    "Unattended Stop (s)": "Parada sin atender (s)",
    "Zones Before Dispersal": "Zonas antes de considerar dispersión",
    "Signal": "Señal",
    "In and out repeatedly": "Entra y sale repetidamente",
    "Long stop, nobody nearby": "Parada larga, nadie cerca",
    "Arrived together, scattered": "Llegaron juntos y se dispersaron",
    "Nothing in it": "No era nada",
    "Customer just needed help": "El cliente solo necesitaba ayuda",
    "Turned out to matter": "Sí resultó ser algo",
    "Not Reviewed": "Sin revisar",
    "Nothing flagged": "Nada marcado",
    "Worth a look": "Vale la pena echar un ojo",
    "Someone has come in and out several times":
        "Alguien ha entrado y salido varias veces",
    "A group came in together and split up":
        "Un grupo entró junto y se separó",
    "Long stop at %(zone)s with nobody nearby":
        "Parada larga en %(zone)s sin nadie cerca",
    "%(n)s re-entries during one visit.":
        "%(n)s reingresos durante una misma visita.",
    "%(mins)s minutes at %(zone)s, unattended.":
        "%(mins)s minutos en %(zone)s, sin atender.",
    "%(size)s people arrived together and are now in %(zones)s different zones.":
        "%(size)s personas llegaron juntas y ahora están en %(zones)s zonas "
        "distintas.",

    # ---- misc ------------------------------------------------------
    "Device '%(dev)s' points at a zone of another store.":
        "El dispositivo '%(dev)s' apunta a una zona de otra tienda.",
}

#: Matched on the whitespace-collapsed msgid.
BATCH5_LOOSE = {

    "Every one is recorded with who received it and whether they reacted, "
    "because a nudge nobody measures is a nudge nobody improves.":
        "Cada uno queda registrado con quién lo recibió y si reaccionó, porque "
        "un aviso que nadie mide es un aviso que nadie mejora.",

    "\"Twelve minutes inside\" tells an owner nothing. \"Eleven of those twelve "
    "in front of the engagement rings, and nobody spoke to them\" tells them "
    "exactly where the money went.":
        "\"Doce minutos adentro\" no le dice nada al dueño. \"Once de esos doce "
        "frente a los anillos de compromiso, y nadie le habló\" le dice "
        "exactamente por dónde se fue el dinero.",

    "Somebody lingered past the zone's threshold, nobody served them, and they "
    "left without buying. <b>All three conditions</b> — each one on its own is "
    "ordinary, and together they are a specific, actionable event.":
        "Alguien se quedó más allá del umbral de la zona, nadie lo atendió, y se "
        "fue sin comprar. <b>Las tres condiciones</b>: cada una por separado es "
        "de lo más común, y juntas son un hecho concreto sobre el que se puede "
        "actuar.",

    "Deliberately conservative: a false alarm costs a salesperson a trip and, "
    "repeated, their trust in the whole system, after which no alert works at "
    "all.":
        "Conservador a propósito: una falsa alarma le cuesta al vendedor un "
        "viaje y, si se repite, su confianza en todo el sistema, después de lo "
        "cual ningún aviso sirve.",

    "The estimated value is the store's recent average ticket. It is an "
    "estimate and labelled as one: what a sale that never happened would have "
    "been worth cannot be known, and quoting it to the cent would be dishonest.":
        "El valor estimado es el ticket promedio reciente de la tienda. Es una "
        "estimación y se etiqueta como tal: cuánto habría valido una venta que "
        "nunca ocurrió no se puede saber, y darlo al centavo sería deshonesto.",

    "Zones answer \"where do people go\". Displays answer \"what do they stop "
    "at\", which is finer and more commercially useful. Attach the products "
    "that sit on each one and the ranking becomes actionable rather than merely "
    "interesting.":
        "Las zonas responden \"a dónde va la gente\". Los exhibidores responden "
        "\"en qué se detienen\", que es más fino y más útil comercialmente. "
        "Asigna los productos que tiene encima cada uno y el ranking pasa de "
        "interesante a accionable.",

    "Attention on its own is a vanity metric. Attention crossed with the sales "
    "of the products actually on this display is what produces the two findings "
    "worth acting on: <b>lots of attention and few sales</b> (price, or nobody "
    "closing) and <b>few visitors but good sales</b> (it converts everyone who "
    "finds it — move it somewhere warmer). Only the shop knows what is on it, "
    "so this list is configuration.":
        "La atención por sí sola es una métrica de vanidad. La atención cruzada "
        "con las ventas de los productos que de verdad están en este exhibidor "
        "es lo que produce los dos hallazgos que valen: <b>mucha atención y "
        "pocas ventas</b> (precio, o que nadie cierra) y <b>pocos visitantes "
        "pero buenas ventas</b> (convierte a todo el que lo encuentra: muévelo a "
        "un lugar más concurrido). Solo la tienda sabe qué tiene encima, así "
        "que esta lista es configuración.",

    "Long dwell here raises no nudge. Right for a fitting room or a checkout "
    "queue, where lingering is the shape of the activity rather than a sign "
    "that somebody is being ignored.":
        "Aquí una permanencia larga no genera aviso. Es lo correcto en un "
        "probador o en la fila de la caja, donde quedarse es la forma normal de "
        "la actividad y no señal de que alguien está siendo ignorado.",

    "Who gets the discreet nudge for this zone, and when. Whoever covers the "
    "counter at 11:00 is not whoever covers it at 19:00 — if nobody is rostered "
    "at the moment an alert fires, it escalates to the store's fallback rather "
    "than evaporating.":
        "Quién recibe el aviso discreto de esta zona, y cuándo. Quien cubre el "
        "mostrador a las 11:00 no es quien lo cubre a las 19:00: si no hay nadie "
        "asignado en el momento en que salta un aviso, escala al responsable de "
        "respaldo de la tienda en vez de evaporarse.",

    "This is a <b>behaviour</b> signal, not an accusation and not a person. It "
    "carries no identity, it expires with the visit it came from, and most of "
    "the time the honest outcome is \"nothing in it\" or \"they just needed "
    "help\" — recording those is what lets a store see whether its thresholds "
    "are set sensibly.":
        "Esta es una señal de <b>comportamiento</b>, no una acusación ni una "
        "persona. No lleva identidad, caduca con la visita de la que salió, y "
        "la mayor parte de las veces el resultado honesto es \"no era nada\" o "
        "\"solo necesitaba ayuda\": registrar esos es lo que le permite a una "
        "tienda ver si sus umbrales están bien puestos.",

    "Patterns worth a second look — in and out repeatedly, a long stop at an "
    "expensive case with nobody nearby, a group that arrives together and "
    "scatters. <b>Anonymous, and about behaviour rather than people.</b> The "
    "named watch list is a separate feature with its own controls.":
        "Patrones que ameritan una segunda mirada: entrar y salir varias veces, "
        "una parada larga frente a una vitrina cara sin nadie cerca, un grupo "
        "que entra junto y se dispersa. <b>Anónimo, y sobre comportamiento, no "
        "sobre personas.</b> La lista de vigilancia con nombres es una función "
        "aparte, con sus propios controles.",

    "Which visit produced which ticket — anonymously. It answers questions no "
    "aggregate can: does the profile that stops at the window actually buy, "
    "does a group spend more than a lone shopper. None of it needs anybody's "
    "name.":
        "Qué visita produjo qué ticket, de forma anónima. Responde preguntas "
        "que ningún agregado puede: ¿el perfil que se detiene en el aparador de "
        "verdad compra?, ¿un grupo gasta más que alguien que viene solo? Nada de "
        "eso necesita el nombre de nadie.",

    "Attention beside the sales of the products on each display. A product "
    "sitting on two displays counts on both — honest, because the data "
    "genuinely cannot say which one closed the sale, and splitting it would "
    "invent a precision that does not exist.":
        "La atención junto a las ventas de los productos de cada exhibidor. Un "
        "producto que está en dos exhibidores cuenta en ambos, y eso es honesto: "
        "los datos genuinamente no pueden decir cuál cerró la venta, y repartirla "
        "inventaría una precisión que no existe.",

    "Customer identification is on. Face signatures of customers who hand over "
    "their details at the till become persistent and named. Every later "
    "<b>read</b> of that list is written to the audit log, and the signatures "
    "still expire on the retention above.":
        "La identificación de clientes está activa. Las firmas faciales de los "
        "clientes que entregan sus datos en la caja se vuelven persistentes y "
        "con nombre. Cada <b>consulta</b> posterior de esa lista queda escrita "
        "en la bitácora de auditoría, y las firmas siguen caducando según la "
        "retención de arriba.",

    "Attention here cannot be compared against sales until somebody says what "
    "is on the display.":
        "La atención aquí no se puede comparar contra las ventas hasta que "
        "alguien diga qué tiene encima el exhibidor.",

    "The nudge worked: this visit produced a ticket afterwards. This is the "
    "figure the monthly value report is built on.":
        "El aviso funcionó: esta visita produjo un ticket después. Es la cifra "
        "sobre la que se construye el reporte mensual de valor.",
}
