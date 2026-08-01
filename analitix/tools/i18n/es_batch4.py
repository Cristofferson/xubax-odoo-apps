# -*- coding: utf-8 -*-
"""Fourth batch: phase 2 — visits, signatures, demographics, purchase units."""
BATCH4 = {
    # ---- models and menus ------------------------------------------
    "Analitix Visit": "Visita de Analitix",
    "Analitix Anonymous Face Signature": "Firma facial anónima de Analitix",
    "Analitix Demographic Reading": "Lectura demográfica de Analitix",
    "Analitix Purchase Unit": "Unidad de compra de Analitix",
    "Visit": "Visita",
    "Visits": "Visitas",
    "Visit Count": "Número de visitas",
    "Crossing Count": "Número de cruces",
    "Demographics": "Demografía",
    "Purchase Unit": "Unidad de compra",
    "Purchase Units": "Unidades de compra",
    "Purchase units": "Unidades de compra",
    "Face Signatures": "Firmas faciales",
    "Signature": "Firma",
    "Visits & Profiling": "Visitas y perfilamiento",
    "Turning crossings into visits": "Convertir cruces en visitas",
    "Anti-spoofing": "Antisuplantación",
    "Where and when": "Dónde y cuándo",
    "Who (anonymously)": "Quién (de forma anónima)",
    "Members": "Integrantes",

    # ---- crons -----------------------------------------------------
    "Analitix: close visits whose exit was missed":
        "Analitix: cerrar visitas cuya salida no se vio",
    "Analitix: expire anonymous face signatures":
        "Analitix: caducar firmas faciales anónimas",

    # ---- visit fields ----------------------------------------------
    "Entry Door": "Puerta de entrada",
    "Exit Door": "Puerta de salida",
    "Entered": "Entró",
    "Exited": "Salió",
    "Duration (min)": "Duración (min)",
    "Minutes": "Minutos",
    "Inside": "Dentro",
    "Left": "Salió",
    "Returning": "Recurrente",
    "Re-entries": "Reingresos",
    "Profile": "Perfil",
    "Pending Profile": "Perfil pendiente",
    "Came With Others": "Vino acompañado",
    "Came Together": "Llegaron juntos",
    "anonymous": "anónimo",

    # ---- signature fields ------------------------------------------
    "First Seen": "Primera vez visto",
    "Last Seen": "Última vez visto",
    "Expires": "Caduca",
    "Sightings": "Avistamientos",
    "Doors Used": "Puertas usadas",
    "Not Expired": "Sin caducar",
    "Seen At Several Doors": "Visto en varias puertas",
    "Liveness": "Detección de vida",
    "Embedding Model": "Modelo de la firma",
    "No live signatures": "No hay firmas vigentes",
    "How many crossings resolved to this signature during its life.":
        "Cuántos cruces se resolvieron a esta firma durante su vida.",
    "This signature reference already exists.":
        "Esta referencia de firma ya existe.",
    "Face signatures must expire: the retention window has to be positive.":
        "Las firmas faciales tienen que caducar: la ventana de retención debe ser "
        "positiva.",
    "Edge confidence that a live person crossed, rather than a photograph held up "
    "to the camera.":
        "Confianza del edge en que cruzó una persona viva y no una fotografía puesta "
        "frente a la cámara.",
    "Time between entering and the last exit seen. Empty while the visit is still "
    "open.":
        "Tiempo entre la entrada y la última salida vista. Vacío mientras la visita "
        "sigue abierta.",

    # ---- store configuration ---------------------------------------
    "Recognise Repeat Faces": "Reconocer caras repetidas",
    "Re-identification Threshold": "Umbral de reidentificación",
    "Signature Retention (min)": "Retención de firmas (min)",
    "Same-visit Gap (min)": "Hueco de la misma visita (min)",
    "Maximum Visit (min)": "Visita máxima (min)",
    "Capture Demographics": "Capturar demografía",
    "Minimum Confidence": "Confianza mínima",
    "Detect Purchase Units": "Detectar unidades de compra",
    "Together Within (s)": "Juntos dentro de (s)",
    "Maximum Unit Size": "Tamaño máximo de la unidad",
    "Require Liveness": "Exigir detección de vida",
    "Minimum Liveness": "Detección de vida mínima",
    "The maximum visit length cannot be shorter than the same-visit gap.":
        "La duración máxima de una visita no puede ser menor que el hueco de la "
        "misma visita.",
    "A purchase unit holds at least one person.":
        "Una unidad de compra tiene al menos una persona.",

    # ---- demographics ----------------------------------------------
    "Age Band": "Rango de edad",
    "Age Confidence": "Confianza de la edad",
    "Gender": "Género",
    "Gender Confidence": "Confianza del género",
    "Emotion": "Emoción",
    "Emotion Confidence": "Confianza de la emoción",
    "Captured": "Capturada",
    "Reliable": "Confiable",
    "Reliable Only": "Solo confiables",
    "Female": "Femenino",
    "Male": "Masculino",
    "Unknown": "Desconocido",
    "Neutral": "Neutral",
    "Happy": "Contento",
    "Sad": "Triste",
    "Angry": "Enojado",
    "Surprised": "Sorprendido",
    "Fearful": "Temeroso",
    "Disgusted": "Disgustado",
    "Child (0-12)": "Niño (0-12)",
    "Teen (13-17)": "Adolescente (13-17)",
    "18-24": "18-24",
    "25-34": "25-34",
    "35-44": "35-44",
    "45-54": "45-54",
    "55-64": "55-64",
    "65+": "65+",
    "No readings yet": "Todavía no hay lecturas",

    # ---- purchase units --------------------------------------------
    "Size": "Tamaño",
    "Alone": "Solo",
    "Pair": "Pareja",
    "Group (3+)": "Grupo (3+)",
    "No purchase units yet": "Todavía no hay unidades de compra",
    "No visits resolved yet": "Todavía no se han resuelto visitas",
    "%(size)s person(s) at %(door)s": "%(size)s persona(s) en %(door)s",
    "unknown door": "puerta desconocida",
    "How many people crossed together. 1 means a lone shopper, which is most of "
    "them.":
        "Cuántas personas cruzaron juntas. 1 significa un comprador solo, que es "
        "la mayoría.",

    # ---- corrected key (the help text changed in phase 2) ----------
    "The tracker id the edge assigned to this person while they were in frame. "
    "Used to tie the crossing to a visit.":
        "El id de seguimiento que el edge le asignó a esta persona mientras estuvo "
        "en cuadro. Sirve para ligar el cruce con una visita.",
}

#: Matched on the whitespace-collapsed msgid, like BATCH3.
BATCH4_LOOSE = {
    "A visit is pseudonymous. It points at an anonymous face signature that expires "
    "on the store's retention schedule, and carries no name and no image.":
        "Una visita es seudónima. Apunta a una firma facial anónima que caduca según "
        "el calendario de retención de la tienda, y no lleva nombre ni imagen.",

    "A crossing is what the camera sees; a visit is what the owner is asking about. "
    "Someone who steps out for a phone call and comes back is <b>one</b> visit — "
    "counting it as three would report a conversion rate a third of the truth.":
        "Un cruce es lo que ve la cámara; una visita es lo que el dueño está "
        "preguntando. Alguien que sale a tomar una llamada y regresa es <b>una</b> "
        "visita: contarlo como tres reportaría una conversión de un tercio de la real.",

    "A couple, a family, three friends — one buying decision. A store that counts a "
    "family of four as four visitors and one ticket reads a 25% conversion rate when "
    "the real figure was 100%.":
        "Una pareja, una familia, tres amigos: una sola decisión de compra. Una tienda "
        "que cuenta a una familia de cuatro como cuatro visitantes y un ticket lee una "
        "conversión del 25% cuando la real era del 100%.",

    "Turn on <b>Capture Demographics</b> on the store and point a front-facing camera "
    "at the entrance. What is stored is a coarse age <i>band</i> and a "
    "presented-appearance estimate — never an identity, and never an image.":
        "Activa <b>Capturar demografía</b> en la tienda y apunta una cámara frontal a "
        "la entrada. Lo que se guarda es un <i>rango</i> de edad amplio y una "
        "estimación de apariencia: nunca una identidad, y nunca una imagen.",

    "Anonymous, expiring handles that let the same person be counted once across a "
    "visit. They carry no name and no image, they are encrypted at rest, and a "
    "scheduled job deletes them on the store's retention window.":
        "Identificadores anónimos y con caducidad que permiten contar una sola vez a "
        "la misma persona durante una visita. No llevan nombre ni imagen, están "
        "cifrados en reposo, y un trabajo programado los borra según la ventana de "
        "retención de la tienda.",

    "Face signatures here are <b>anonymous and expiring</b>: no name, no image, "
    "encrypted at rest, and deleted on the retention window above. Matching never "
    "crosses store boundaries.":
        "Las firmas faciales aquí son <b>anónimas y con caducidad</b>: sin nombre, sin "
        "imagen, cifradas en reposo y borradas según la ventana de retención de "
        "arriba. La comparación nunca cruza los límites de una tienda.",

    "Every confidence clears the store's floor. Leave the rest out rather than "
    "averaging a coin flip into the numbers.":
        "Todas las confianzas superan el piso de la tienda. Deja fuera el resto en vez "
        "de promediar un volado dentro de los números.",
}
