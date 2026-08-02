# -*- coding: utf-8 -*-
"""Seventh batch: phase 4 — signage, welcome, attendance, billing, ROI."""
BATCH7 = {
    # ---- models, menus, sections -----------------------------------
    "Analitix Signage Rule": "Regla de señalización de Analitix",
    "Analitix Signage Firing": "Disparo de señalización de Analitix",
    "Analitix Monthly Value Report": "Reporte mensual de valor de Analitix",
    "Analitix — Customer Context": "Analitix — Contexto del cliente",
    "Analitix — Floor Coaching": "Analitix — Coaching de piso",
    "Analitix — Visit Frequency": "Analitix — Frecuencia de visita",
    "Analitix — Staff Attendance Bridge":
        "Analitix — Puente de asistencia del personal",
    "Signage Rule": "Regla de señalización",
    "Signage Rules": "Reglas de señalización",
    "Signage rules": "Reglas de señalización",
    "Signage Rule Count": "Número de reglas de señalización",
    "Signage Firings": "Disparos de señalización",
    "Monthly Value": "Valor mensual",
    "Monthly value report": "Reporte mensual de valor",
    "Monthly Reports": "Reportes mensuales",
    "Floor Coaching": "Coaching de piso",
    "Visit Frequency": "Frecuencia de visita",
    "Action & Billing": "Acción y facturación",
    "Screens": "Pantallas",
    "Staff attendance": "Asistencia del personal",
    "Attendance": "Asistencia",
    "Subscription": "Suscripción",
    "Traffic and sales": "Tráfico y ventas",
    "What the system did": "Lo que hizo el sistema",
    "What to show": "Qué mostrar",
    "Where and who": "Dónde y quién",
    "Conditions": "Condiciones",
    "Days": "Días",
    "Rule": "Regla",
    "Trigger": "Disparador",
    "Firings": "Disparos",
    "Content": "Contenido",

    # ---- crons and templates ---------------------------------------
    "Analitix: send the monthly value report":
        "Analitix: enviar el reporte mensual de valor",
    "Analitix: flag trials that have ended":
        "Analitix: marcar las pruebas que ya terminaron",
    "Analitix: close shifts nobody was seen leaving":
        "Analitix: cerrar turnos en los que no se vio la salida",
    "Analitix: monthly value report": "Analitix: reporte mensual de valor",
    "{{ object.store_id.name }} — how last month went":
        "{{ object.store_id.name }} — cómo estuvo el mes pasado",

    # ---- signage rule ----------------------------------------------
    "Drive The Screens": "Manejar las pantallas",
    "Someone is about to leave empty-handed":
        "Alguien está por irse con las manos vacías",
    "A group walked in": "Entró un grupo",
    "Visitor profile matches": "El perfil del visitante coincide",
    "Quiet hour / peak hour": "Hora valle / hora pico",
    "A known customer arrived": "Llegó un cliente conocido",
    "Show It On": "Mostrarlo en",
    "Show it on": "Mostrarlo en",
    "The screen covering where it happened":
        "La pantalla que cubre donde pasó",
    "The screen by the exit": "La pantalla de la salida",
    "The screen facing the street": "La pantalla que da a la calle",
    "A specific screen": "Una pantalla específica",
    "Specific Zone": "Zona específica",
    "Screen Zone": "Zona de la pantalla",
    "Screen": "Pantalla",
    "Xibo Layout": "Layout de Xibo",
    "Xibo layout name": "Nombre del layout de Xibo",
    "Xibo display group": "Grupo de pantallas de Xibo",
    "Duration (s)": "Duración (s)",
    "Cooldown (min)": "Enfriamiento (min)",
    "Only In Zones": "Solo en las zonas",
    "Age Bands": "Rangos de edad",
    "Group Of At Least": "Grupo de al menos",
    "From Hour": "Desde la hora",
    "To Hour": "Hasta la hora",
    "Quiet Below (visitors/h)": "Valle por debajo de (visitantes/h)",
    "Never Fired": "Nunca se disparó",
    "Did Not Reach The Screen": "No llegó a la pantalla",
    "Make the screens react": "Haz que las pantallas reaccionen",
    "Mon": "Lun", "Tue": "Mar", "Wed": "Mié", "Thu": "Jue",
    "Fri": "Vie", "Sat": "Sáb", "Sun": "Dom",
    "Leave empty for any.": "Déjalo vacío para cualquiera.",
    "Leave empty for the whole store.": "Déjalo vacío para toda la tienda.",
    "0 for any. Set 2 to target couples and families.":
        "0 para cualquiera. Pon 2 para apuntar a parejas y familias.",
    "Used when the destination is a specific screen.":
        "Se usa cuando el destino es una pantalla específica.",
    "e.g. Finance offer at the exit":
        "p. ej. Oferta de financiamiento en la salida",
    "Welcome back, {customer}": "Bienvenido de nuevo, {customer}",
    "No screen is mapped to this zone.":
        "No hay ninguna pantalla asignada a esta zona.",
    "The Xibo connector is not installed.":
        "El conector de Xibo no está instalado.",
    "No Xibo display group named '%s'.":
        "No existe un grupo de pantallas de Xibo llamado '%s'.",
    "No Xibo layout named '%s'.": "No existe un layout de Xibo llamado '%s'.",
    "No Xibo server is configured.":
        "No hay ningún servidor de Xibo configurado.",

    # ---- welcome ---------------------------------------------------
    "Greet By Name Only If Alone": "Saludar por su nombre solo si viene solo",
    "Arrived-together Window (s)": "Ventana de llegada juntos (s)",
    "Welcome back, %(name)s": "Bienvenido de nuevo, %(name)s",
    "Welcome back, %(name)s — happy %(occasion)s!":
        "¡Bienvenido de nuevo, %(name)s — feliz %(occasion)s!",
    "%s is a returning customer.": "%s es un cliente recurrente.",
    "Today is their %s.": "Hoy es su %s.",
    "Last bought %(products)s on %(date)s (%(total).2f).":
        "Su última compra fue %(products)s el %(date)s (%(total).2f).",
    "Open opportunity: %(name)s (%(stage)s).":
        "Oportunidad abierta: %(name)s (%(stage)s).",
    "something": "algo",
    "there": "por ahí",

    # ---- attendance ------------------------------------------------
    "Log Staff Attendance": "Registrar la asistencia del personal",
    "Staff Door": "Puerta del personal",
    "Ignore Repeats Within (min)": "Ignorar repeticiones dentro de (min)",
    "Maximum Shift (h)": "Turno máximo (h)",
    "Opened By Analitix": "Abierta por Analitix",

    # ---- subscription ----------------------------------------------
    "Plan": "Plan",
    "Counting": "Conteo",
    "Counting + Insight": "Conteo + Análisis",
    "Insight + Floor": "Análisis + Piso",
    "Full": "Completo",
    "Billing Status": "Estado de facturación",
    "Trial": "Prueba",
    "Trial Ends": "La prueba termina",
    "Live Since": "En vivo desde",
    "Monthly Fee": "Cuota mensual",
    "Cancelled": "Cancelada",
    "Trial started, ending %s.": "Prueba iniciada, termina el %s.",
    "Subscription active.": "Suscripción activa.",
    "Subscription cancelled.": "Suscripción cancelada.",
    "Analitix trial ended: %s": "Terminó la prueba de Analitix: %s",

    # ---- value report ----------------------------------------------
    "Send The Monthly Report": "Enviar el reporte mensual",
    "Send To The Owner": "Enviar al dueño",
    "Report Recipients": "Destinatarios del reporte",
    "Sales": "Ventas",
    "Average Sale": "Venta promedio",
    "Alerts Sent": "Avisos enviados",
    "Alerts Acted On": "Avisos atendidos",
    "Alerts Missed": "Avisos no atendidos",
    "Walk-outs Spotted": "Salidas detectadas",
    "Walk-outs Rescued": "Salidas rescatadas",
    "Spotted": "Detectadas",
    "Recovered": "Recuperado",
    "Rescue %": "Rescate %",
    "Estimated Recovered": "Recuperado estimado",
    "× Subscription": "× la suscripción",
    "Previous Conversion %": "Conversión % anterior",
    "Change": "Cambio",
    "Draft": "Borrador",
    "Not Sent": "Sin enviar",
    "Paid For Itself": "Se pagó solo",
    "No reports yet": "Todavía no hay reportes",
    "This store already has a report for that month.":
        "Esta tienda ya tiene un reporte de ese mes.",
    "%(visitors)s people came into the shop.":
        "Entraron %(visitors)s personas a la tienda.",
    "That is better than last month (%(prev).1f%%).":
        "Es mejor que el mes pasado (%(prev).1f%%).",
    "That is down from last month (%(prev).1f%%).":
        "Está por debajo del mes pasado (%(prev).1f%%).",
    "%(missed)s alerts went unanswered. Each one was somebody waiting.":
        "%(missed)s avisos quedaron sin atender. Cada uno era alguien esperando.",

    # ---- coaching / recurrence -------------------------------------
    "Answered": "Atendidos",
    "Answered %": "Atendidos %",
    "Converted %": "Convertidos %",
    "Ended In A Sale": "Terminó en venta",
    "Avg Response (s)": "Respuesta prom. (s)",
    "Nothing to coach on yet": "Todavía no hay nada que analizar",
    "Known": "Conocidos",
    "Known Customers": "Clientes conocidos",
    "Returning %": "Recurrentes %",
    "No frequency data yet": "Todavía no hay datos de frecuencia",
}

BATCH7_LOOSE = {
    "A store has several screens and they are not interchangeable. Every rule "
    "resolves <b>where</b> before <b>what</b>: a bundle offer belongs on the "
    "screen the group is standing near, not on the one by the door.":
        "Una tienda tiene varias pantallas y no son intercambiables. Cada regla "
        "resuelve <b>dónde</b> antes que <b>qué</b>: una promoción de paquete va "
        "en la pantalla junto a la que está parado el grupo, no en la de la "
        "puerta.",

    "The scenarios that ship are examples. Every shop wants its own, and an "
    "owner who has to call us to change three minutes into five will stop "
    "asking.":
        "Los escenarios que vienen de fábrica son ejemplos. Cada tienda quiere "
        "los suyos, y un dueño que tenga que llamarnos para cambiar tres "
        "minutos por cinco va a dejar de pedirlo.",

    "Whatever this rule shows is <b>read by the customer</b>. Write it for them "
    "— an offer, a suggestion, a welcome — never about them.":
        "Lo que muestre esta regla <b>lo lee el cliente</b>. Escríbelo para él "
        "—una oferta, una sugerencia, una bienvenida— nunca sobre él.",

    "A screen saying \"Welcome back, Gustavo\" while Gustavo is standing there "
    "with somebody has just told that person something about him. With this on, "
    "the screen stays neutral when he is not alone and the personal greeting "
    "goes to the salesperson instead.":
        "Una pantalla que dice «Bienvenido de nuevo, Gustavo» mientras Gustavo "
        "está ahí parado con alguien acaba de decirle algo sobre él a esa "
        "persona. Con esto activo, la pantalla se queda neutral cuando no viene "
        "solo y el saludo personal se le manda al vendedor.",

    "This records your team's working hours from the cameras. It writes into "
    "Odoo's own attendance, never overwrites a manual correction, and should be "
    "agreed with the people it measures before it is switched on.":
        "Esto registra las horas de trabajo de tu equipo a partir de las "
        "cámaras. Escribe en la asistencia nativa de Odoo, nunca sobrescribe una "
        "corrección hecha a mano, y conviene acordarlo con las personas a las "
        "que mide antes de encenderlo.",

    "The plan governs which features this store's users <b>see and can switch "
    "on</b>. It is not a licence check in the code: a billing problem on our "
    "side must never be able to turn a customer's cameras off.":
        "El plan define qué funciones <b>ven y pueden encender</b> los usuarios "
        "de esta tienda. No es una verificación de licencia en el código: un "
        "problema de facturación de nuestro lado nunca debe poder apagarle las "
        "cámaras a un cliente.",

    "Once a month, in plain language: how many people came in, how many bought, "
    "how many were about to walk out unserved, how many your team caught, and "
    "roughly what that was worth.":
        "Una vez al mes, en lenguaje llano: cuánta gente entró, cuánta compró, "
        "cuánta estaba por irse sin que la atendieran, a cuánta alcanzó tu "
        "equipo, y aproximadamente cuánto valió eso.",

    "This is what an owner reads instead of a dashboard, and it is what makes "
    "the subscription obviously worth keeping — or obviously not, which is "
    "information too.":
        "Esto es lo que un dueño lee en vez de un tablero, y es lo que vuelve "
        "evidente que vale la pena mantener la suscripción — o que no, que "
        "también es información.",

    "<b>Recovered revenue is an estimate.</b> It is rescued walk-outs "
    "multiplied by this store's own average sale, and a rescued walk-out is one "
    "where an alert fired and that same visit later produced a ticket — "
    "correlation, stated honestly, not proof that the nudge caused the sale. "
    "Inflating this figure is the fastest way to lose the customer who "
    "eventually checks it.":
        "<b>El ingreso recuperado es una estimación.</b> Son las salidas "
        "rescatadas multiplicadas por la venta promedio de esta misma tienda, y "
        "una salida rescatada es aquella en la que saltó un aviso y esa misma "
        "visita después produjo un ticket: correlación, dicha con honestidad, no "
        "prueba de que el aviso causó la venta. Inflar esta cifra es la forma "
        "más rápida de perder al cliente que algún día la revise.",

    "How many nudges each salesperson received, how fast they answered, and how "
    "many of the ones they answered ended in a sale.":
        "Cuántos avisos recibió cada vendedor, qué tan rápido los atendió, y "
        "cuántos de los que atendió terminaron en venta.",

    "Conversion is measured against what they <b>answered</b>, not what they "
    "were sent: nobody should be marked down for a nudge that arrived while "
    "they were serving another customer.":
        "La conversión se mide contra lo que <b>atendió</b>, no contra lo que se "
        "le mandó: a nadie hay que bajarle la calificación por un aviso que "
        "llegó mientras atendía a otro cliente.",

    "How much of your traffic is people coming back. Bounded by the store's own "
    "retention window — it measures what the shop chose to remember, not "
    "everything that happened.":
        "Qué parte de tu tráfico es gente que regresa. Acotado por la ventana de "
        "retención de la propia tienda: mide lo que la tienda decidió recordar, "
        "no todo lo que pasó.",

    "Every condition is optional and they are all combined. Leave one empty and "
    "it stops narrowing anything.":
        "Todas las condiciones son opcionales y se combinan entre sí. Deja una "
        "vacía y deja de acotar nada.",
}
