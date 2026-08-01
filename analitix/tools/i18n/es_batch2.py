# -*- coding: utf-8 -*-
"""Second batch: the long help texts and dialogs.

Keys must reproduce the .pot's msgid byte for byte — a key that does not match
is dropped by Odoo without a word, so make_es_po.py reports any that miss.
"""
BATCH2 = {
    "%(key)s\\n\\nThis is the only time it is shown. Odoo stores only a hash of it; "
    "if it is lost, rotate again.":
        "%(key)s\\n\\nEsta es la única vez que se muestra. Odoo solo guarda un hash; "
        "si se pierde, hay que rotarla otra vez.",

    "<span class=\\\"text-muted d-block small\\\">Inside now</span>":
        "<span class=\\\"text-muted d-block small\\\">Dentro ahora</span>",
    "<span class=\\\"text-muted d-block small\\\">Visitors today</span>":
        "<span class=\\\"text-muted d-block small\\\">Visitantes hoy</span>",

    "A critical device is one whose silence makes this store's numbers wrong: any "
    "door counter, or the checkout camera. When it goes offline the technical "
    "contacts are alerted. Clear the flag for a spare or experimental unit so it "
    "does not page anyone at 3 a.m.":
        "Un dispositivo crítico es aquel cuyo silencio deja mal los números de esta "
        "tienda: cualquier contador de puerta o la cámara de caja. Cuando se cae, se "
        "avisa a los contactos técnicos. Quita la marca en un equipo de repuesto o de "
        "pruebas para que no despierte a nadie a las 3 de la mañana.",

    "A device that has not sent a heartbeat for this long is marked offline. Raise "
    "it on stores with a flaky connection so a 90-second outage does not page the "
    "technician every night.":
        "Un dispositivo que no manda latido durante este tiempo se marca fuera de "
        "línea. Súbelo en tiendas con conexión inestable para que un corte de 90 "
        "segundos no despierte al técnico cada noche.",

    "A revoked device is refused by the ingest endpoint immediately, without waiting "
    "for anyone to reach the hardware.":
        "Un dispositivo revocado es rechazado por el endpoint de ingesta de inmediato, "
        "sin esperar a que alguien llegue al equipo.",

    "Clear this for a staff or service door: it stays measured, but its traffic stops "
    "distorting the conversion rate.":
        "Desmárcalo en una puerta de personal o de servicio: se sigue midiendo, pero "
        "su tráfico deja de distorsionar la tasa de conversión.",

    "Cleared when the crossing was matched to an employee, or when it came through a "
    "door configured not to count visitors. The row is kept either way — excluded "
    "traffic is still traffic, and hiding it would make an audit impossible.":
        "Se desmarca cuando el cruce se asoció a un empleado, o cuando entró por una "
        "puerta configurada para no contar visitantes. El registro se conserva en "
        "ambos casos: el tráfico excluido sigue siendo tráfico, y esconderlo haría "
        "imposible una auditoría.",

    "Configure stores, doors and devices, enrol staff signatures and use the capture "
    "kill switch.":
        "Configurar tiendas, puertas y dispositivos, registrar firmas de empleados y "
        "usar el interruptor de emergencia de la captura.",

    "Cosine similarity above which a crossing is attributed to a known employee and "
    "excluded from the visitor count. Higher is stricter: fewer customers wrongly "
    "dropped, more staff wrongly counted.":
        "Similitud coseno a partir de la cual un cruce se atribuye a un empleado "
        "conocido y se excluye del conteo. Más alto es más estricto: se descartan "
        "menos clientes por error, pero se cuentan más empleados por error.",

    "Cosine similarity of the staff match, kept so a threshold can be re-tuned "
    "against real data instead of guesswork.":
        "Similitud coseno de la coincidencia con el empleado. Se guarda para poder "
        "reajustar el umbral con datos reales y no a ojo.",

    "Create the counting device and issue its API key now. Clear it for a door whose "
    "hardware is not installed yet.":
        "Crea el dispositivo de conteo y emite su llave de API ahora. Desmárcalo si "
        "el equipo de esa puerta todavía no está instalado.",

    "Cut this device off now? It will be refused by the ingest endpoint until a new "
    "key is issued. Use this for stolen or decommissioned hardware.":
        "¿Cortar este dispositivo ahora? El endpoint de ingesta lo rechazará hasta "
        "que se emita una llave nueva. Úsalo con equipo robado o dado de baja.",

    "Data capture PAUSED by %(user)s. The ingest endpoint will reject this store's "
    "devices until capture is resumed.":
        "Captura de datos PAUSADA por %(user)s. El endpoint de ingesta rechazará los "
        "dispositivos de esta tienda hasta que se reanude.",

    "Device '%(dev)s' points at a door of another store. A device belongs to exactly "
    "one store.":
        "El dispositivo '%(dev)s' apunta a la puerta de otra tienda. Un dispositivo "
        "pertenece a exactamente una tienda.",

    "Device <b>%(dev)s</b> of store <b>%(store)s</b> stopped reporting. While it is "
    "down, this store's visitor count and conversion are incomplete.":
        "El dispositivo <b>%(dev)s</b> de la tienda <b>%(store)s</b> dejó de reportar. "
        "Mientras esté caído, el conteo de visitantes y la conversión de esta tienda "
        "están incompletos.",

    "Employee crossings that were identified and kept out of the visitor count. Shown "
    "so the exclusion is auditable rather than invisible.":
        "Cruces de empleados que se identificaron y se dejaron fuera del conteo de "
        "visitantes. Se muestran para que la exclusión sea auditable y no invisible.",

    "Encrypted embedding awaiting asynchronous matching. Cleared once the job has run, "
    "so the high-volume table does not become a biometric store.":
        "Firma cifrada en espera de comparación asíncrona. Se borra en cuanto corre el "
        "trabajo, para que la tabla de mayor volumen no se convierta en un almacén "
        "biométrico.",

    "Enrolled but never recognised. Usually means the enrolment was poor or the "
    "employee changed appearance.":
        "Registrado pero nunca reconocido. Casi siempre significa que el registro "
        "quedó mal o que el empleado cambió de aspecto.",

    "Entrances minus exits over the period, never negative. On the default 'today' "
    "period this estimates who is inside right now.":
        "Entradas menos salidas del periodo, nunca negativo. Con el periodo por "
        "omisión ('hoy') estima cuánta gente hay dentro en este momento.",

    "Events still queued on the device itself, reported in its heartbeat. A backlog "
    "that keeps growing means the store's link is down or Odoo is refusing the data — "
    "the count is not lost yet, but it will be if the buffer overflows.":
        "Eventos que siguen en cola dentro del propio dispositivo, reportados en su "
        "latido. Una cola que no deja de crecer significa que el enlace de la tienda "
        "está caído o que Odoo está rechazando los datos: el conteo todavía no se "
        "pierde, pero se perderá si se desborda el búfer.",

    "Free-form JSON handed to the agent by the config endpoint: line coordinates, "
    "camera index, zone polygons. Kept here so an implementer can retune a camera "
    "from Odoo instead of going back to the store with a laptop.":
        "JSON libre que el endpoint de configuración le entrega al agente: coordenadas "
        "de la línea, índice de cámara, polígonos de zona. Vive aquí para que el "
        "implementador reajuste una cámara desde Odoo en vez de volver a la tienda "
        "con una laptop.",

    "Free-form name the staff of this store would use: 'North Entrance', 'Mall Door', "
    "'Service Door'.":
        "Nombre libre, el que usaría el personal de esta tienda: 'Entrada Norte', "
        "'Puerta de la Plaza', 'Puerta de Servicio'.",

    "Grace band before 'offline': the device is late but not yet presumed down. Shown "
    "amber on the technical dashboard.":
        "Margen antes de 'fuera de línea': el dispositivo va retrasado pero todavía no "
        "se da por caído. Aparece en ámbar en el tablero técnico.",

    "How POS sales are attributed to this store for conversion:\\n"
    "• Specific POS registers: only orders from the registers below. Use this when "
    "several stores share one company.\\n"
    "• Whole company: every POS order of the company. Use this when the company runs "
    "a single store.":
        "Cómo se atribuyen las ventas de TPV a esta tienda para calcular la "
        "conversión:\\n"
        "• Cajas de TPV específicas: solo los pedidos de las cajas de abajo. Úsalo "
        "cuando varias tiendas comparten una misma compañía.\\n"
        "• Toda la compañía: todos los pedidos de TPV de la compañía. Úsalo cuando la "
        "compañía tiene una sola tienda.",

    "How far from its own baseline a device may drift before it is flagged. 5.0 means "
    "'five times the usual hourly volume'.":
        "Cuánto puede alejarse un dispositivo de su propia línea base antes de que se "
        "marque. 5.0 significa 'cinco veces el volumen normal por hora'.",

    "How many records the action touched. A single read of one entry and a bulk export "
    "of the whole list are very different events.":
        "Cuántos registros tocó la acción. Consultar una sola entrada y exportar la "
        "lista completa son cosas muy distintas.",

    "How often each edge agent of this store reports it is alive. The agent reads this "
    "value from the config endpoint, so changing it here re-tunes the fleet without "
    "touching any device.":
        "Cada cuánto reporta cada agente edge de esta tienda que sigue vivo. El agente "
        "lee este valor del endpoint de configuración, así que cambiarlo aquí reajusta "
        "toda la flota sin tocar ningún equipo.",

    "Include this door's crossings in the store's visitor total. Turn it off for a "
    "staff-only or emergency door whose traffic is not customers — it stays measured, "
    "it just stops distorting the conversion rate.":
        "Incluir los cruces de esta puerta en el total de visitantes de la tienda. "
        "Desactívalo en una puerta de solo personal o de emergencia cuyo tráfico no "
        "son clientes: se sigue midiendo, simplemente deja de distorsionar la tasa de "
        "conversión.",

    "Informational, but it drives sensible defaults: a service door is where staff "
    "traffic concentrates, an emergency exit normally produces exits only.":
        "Es informativo, pero define valores por omisión razonables: en una puerta de "
        "servicio se concentra el tráfico del personal, y una salida de emergencia "
        "normalmente solo produce salidas.",

    "Ingest anomaly: %(count)s events in the last hour against a usual %(base).1f. "
    "Check the device for a fault or tampering — its data is suspect until reviewed.":
        "Anomalía de ingesta: %(count)s eventos en la última hora contra un valor "
        "normal de %(base).1f. Revisa el dispositivo por falla o manipulación: sus "
        "datos son sospechosos hasta que alguien los revise.",

    "Issue a new key? The current one stops working immediately, and the new one is "
    "shown only once.":
        "¿Emitir una llave nueva? La actual deja de funcionar de inmediato, y la nueva "
        "se muestra una sola vez.",

    "JSON arguments for the handler. Kept as text so a job survives a module upgrade "
    "that changes the models it refers to.":
        "Argumentos JSON para el manejador. Se guardan como texto para que un trabajo "
        "sobreviva a una actualización del módulo que cambie los modelos a los que "
        "hace referencia.",

    "Keep employee crossings out of visitors and conversion. Turn it off only while "
    "calibrating: with it off, a store whose team walks in and out all day reads a "
    "conversion rate far below the truth.":
        "Mantener los cruces de empleados fuera de los visitantes y de la conversión. "
        "Desactívalo solo mientras calibras: apagado, una tienda cuyo equipo entra y "
        "sale todo el día marca una conversión muy por debajo de la real.",

    "Last characters of the active key, so a technician can tell which credential a "
    "device is carrying without being able to use it.":
        "Últimos caracteres de la llave activa, para que un técnico sepa qué credencial "
        "trae un dispositivo sin poder usarla.",

    "Lower runs first. Time-sensitive work — a welcome message that is worthless if it "
    "arrives after the customer has walked past the screen — belongs below 10.":
        "Lo más bajo corre primero. El trabajo sensible al tiempo (una bienvenida que "
        "no sirve de nada si llega después de que el cliente ya pasó frente a la "
        "pantalla) va por debajo de 10.",

    "Master switch for this store's data capture. Turning it off stops the ingest "
    "endpoint from accepting anything at all — no code deployment, no trip to the "
    "store. Use it for an incident, a malfunction, or when the customer asks to pause "
    "the system.":
        "Interruptor maestro de la captura de datos de esta tienda. Apagarlo hace que "
        "el endpoint de ingesta deje de aceptar absolutamente todo: sin desplegar "
        "código y sin ir a la tienda. Úsalo ante un incidente, una falla grave, o "
        "cuando el cliente pida pausar el sistema.",

    "No devices were created. Add them from the store's Devices tab when the hardware "
    "is on site.":
        "No se creó ningún dispositivo. Agrégalos desde la pestaña Dispositivos de la "
        "tienda cuando el equipo esté en el sitio.",

    "People who entered during the selected period (default: today, in the store's "
    "timezone). Staff crossings excluded.":
        "Personas que entraron durante el periodo seleccionado (por omisión hoy, en la "
        "zona horaria de la tienda). Se excluyen los cruces de empleados.",

    "Pick the POS registers whose tickets belong to this store, or switch to 'Whole "
    "company'. Without either, conversion has no sales side and every hour will read "
    "0%.":
        "Elige las cajas de TPV cuyos tickets pertenecen a esta tienda, o cambia a "
        "'Toda la compañía'. Sin una de las dos, la conversión no tiene lado de ventas "
        "y todas las horas marcarán 0%.",

    "Queued more than fifteen minutes ago and still not run. Usually means the Odoo "
    "cron is not running.":
        "En cola desde hace más de quince minutos y todavía sin ejecutarse. Casi "
        "siempre significa que el cron de Odoo no está corriendo.",

    "Register '%(reg)s' already belongs to store '%(store)s'. A register can feed only "
    "one store, otherwise its tickets would be counted twice.":
        "La caja '%(reg)s' ya pertenece a la tienda '%(store)s'. Una caja solo puede "
        "alimentar a una tienda; si no, sus tickets se contarían dos veces.",

    "Registers whose tickets count toward this store's conversion. Only used when "
    "'Match sales by' is 'Specific POS registers'.":
        "Cajas cuyos tickets cuentan para la conversión de esta tienda. Solo se usan "
        "cuando 'Atribuir ventas por' es 'Cajas de TPV específicas'.",

    "Restrict this user to these stores. Leave empty to give access to every store of "
    "the companies they already belong to — right for a single-store customer, wrong "
    "for a shared instance.":
        "Limitar a este usuario a estas tiendas. Déjalo vacío para darle acceso a todas "
        "las tiendas de las compañías a las que ya pertenece: correcto para un cliente "
        "de una sola tienda, incorrecto en una instancia compartida.",

    "Revenue divided by visitors: what each walk-in is worth. Moves when either "
    "conversion or ticket value moves, so it is the single number to watch if you only "
    "watch one.":
        "Ingresos divididos entre visitantes: cuánto vale cada persona que entra. Se "
        "mueve cuando se mueve la conversión o el valor del ticket, así que es el "
        "número a vigilar si solo vas a vigilar uno.",

    "Rolling average of this device's hourly volume, learned from its own history. "
    "Used to notice that a device suddenly reports ten times its usual traffic — a "
    "fault or a tampered agent.":
        "Promedio móvil del volumen por hora de este dispositivo, aprendido de su "
        "propio historial. Sirve para notar que un dispositivo de pronto reporta diez "
        "veces su tráfico normal: una falla o un agente manipulado.",

    "Selling area only, excluding storage and offices. Optional: use it when density "
    "should be measured over the sellable floor.":
        "Solo el área de venta, sin bodega ni oficinas. Opcional: úsalo cuando la "
        "densidad deba medirse sobre el piso vendible.",

    "Short internal code for this store (e.g. 'MOR-01'). Used in device UIDs and in "
    "chain-wide reports.":
        "Código interno corto de esta tienda (p. ej. 'MOR-01'). Se usa en los UID de "
        "dispositivo y en los reportes de toda la cadena.",

    "Signatures are scoped to a store: an employee of store A is not silently excluded "
    "from store B's counts. Enrol them in both if they genuinely work in both.":
        "Las firmas están acotadas a una tienda: un empleado de la tienda A no queda "
        "excluido en silencio del conteo de la tienda B. Regístralo en ambas si "
        "realmente trabaja en las dos.",

    "Stable identifier the agent sends in every payload, e.g. 'mor01-north-counter'. "
    "It identifies the device in logs; it does not authenticate it — the API key does.":
        "Identificador estable que el agente manda en cada envío, p. ej. "
        "'mor01-north-counter'. Identifica al dispositivo en las bitácoras; no lo "
        "autentica: eso lo hace la llave de API.",

    "Stop capturing data for this store right now? Devices will be refused until you "
    "resume. Their local buffers keep the events, so nothing is lost while it is "
    "paused.":
        "¿Dejar de capturar datos de esta tienda ahora mismo? Los dispositivos serán "
        "rechazados hasta que reanudes. Sus búferes locales conservan los eventos, así "
        "que no se pierde nada mientras está en pausa.",

    "The employee's face embedding, encrypted at rest. It is a vector of numbers from "
    "which no image can be reconstructed.":
        "La firma facial del empleado, cifrada en reposo. Es un vector de números del "
        "que no se puede reconstruir ninguna imagen.",

    "The tracker id the edge assigned to this person while they were in frame. Phase 2 "
    "uses it to tie the crossing to a visitor.":
        "El id de seguimiento que el edge le asignó a esta persona mientras estuvo en "
        "cuadro. La Fase 2 lo usa para ligar el cruce con un visitante.",

    "This signature carries no usable vector. Re-enrol the employee from the edge "
    "enrolment tool.":
        "Esta firma no trae ningún vector utilizable. Vuelve a registrar al empleado "
        "desde la herramienta de registro del edge.",

    "Tickets divided by visitors entering. The headline number: out of everyone who "
    "walked in, how many bought.":
        "Tickets divididos entre los visitantes que entraron. El número principal: de "
        "toda la gente que entró, cuánta compró.",

    "Tickets in an hour with no crossings: almost always a counter that was down. "
    "Worth checking before trusting the day.":
        "Tickets en una hora sin ningún cruce: casi siempre es un contador que estaba "
        "caído. Conviene revisarlo antes de confiar en el día.",

    "Timezone of the physical store. Opening hours, daily resets and the owner's "
    "reports follow this, not the reader's timezone — a chain's HQ in another timezone "
    "still sees each store's real day.":
        "Zona horaria de la tienda física. El horario, los cortes diarios y los "
        "reportes del dueño siguen esta zona, no la de quien mira: un corporativo en "
        "otra zona horaria sigue viendo el día real de cada tienda.",

    "Total floor area in square meters. Enables the density KPIs (revenue and visitors "
    "per m²).":
        "Superficie total en metros cuadrados. Habilita los KPI de densidad (ingresos y "
        "visitantes por m²).",

    "Unique identifier minted by the edge agent before sending. It is what makes a "
    "network retry safe: the same crossing arriving twice is stored once.":
        "Identificador único que el agente edge genera antes de enviar. Es lo que hace "
        "seguro un reintento de red: el mismo cruce que llega dos veces se guarda una "
        "sola vez.",

    "User who gets the Odoo activity for device incidents in this store. Leave empty "
    "to fall back to the store's creator.":
        "Usuario que recibe la actividad de Odoo por incidentes de dispositivo en esta "
        "tienda. Déjalo vacío para que recaiga en quien creó la tienda.",

    "What percentage of the store's entrances that hour came through this door. Tells "
    "the owner which entrance actually carries the traffic — often not the one they "
    "assumed.":
        "Qué porcentaje de las entradas de la tienda en esa hora pasó por esta puerta. "
        "Le dice al dueño qué entrada carga de verdad con el tráfico, que muchas veces "
        "no es la que suponía.",

    "What this device is for. Later phases route zone dwell, demographics and purchase "
    "attribution by role.":
        "Para qué sirve este dispositivo. Las fases siguientes enrutan la permanencia "
        "por zona, la demografía y la atribución de compra según esta función.",

    "When Odoo stored it. Compared against 'Time' it shows how far behind a store's "
    "link is running.":
        "Cuándo lo guardó Odoo. Comparado con 'Hora' muestra qué tan atrasado va el "
        "enlace de la tienda.",

    "When the crossing happened at the store, as reported by the edge — not when Odoo "
    "received it. After an outage a device replays hours of buffered events, and they "
    "must land on the hour they actually belong to or the day's curve is wrong.":
        "Cuándo ocurrió el cruce en la tienda, según lo reporta el edge, no cuándo lo "
        "recibió Odoo. Tras un corte, un dispositivo reenvía horas de eventos en búfer "
        "y tienen que caer en la hora a la que de verdad pertenecen o la curva del día "
        "queda mal.",

    "Which entrance this device watches. Required for counters; left empty for devices "
    "that watch a zone or the checkout instead.":
        "Qué entrada vigila este dispositivo. Obligatorio en los contadores; se deja "
        "vacío en los dispositivos que vigilan una zona o la caja.",

    "Which face model produced this vector. Embeddings from different models are not "
    "comparable, so matching only ever compares signatures sharing this value.":
        "Qué modelo facial produjo este vector. Las firmas de modelos distintos no son "
        "comparables, así que la comparación solo se hace entre firmas que comparten "
        "este valor.",

    "Who is warned when a critical device of this store goes offline. While it is down "
    "the store's counting and conversion are not trustworthy and the customer is "
    "paying for data nobody captures.":
        "A quién se le avisa cuando un dispositivo crítico de esta tienda se cae. "
        "Mientras esté caído, el conteo y la conversión de la tienda no son confiables "
        "y el cliente está pagando por datos que nadie está capturando.",
}
