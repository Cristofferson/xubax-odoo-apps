# -*- coding: utf-8 -*-
"""Sixth batch: the alert-channel rework (Discuss, chime, signage screen)."""
BATCH6 = {
    # ---- channel switches ------------------------------------------
    "Odoo Mobile App": "App móvil de Odoo",
    "Odoo Chat (Discuss)": "Chat interno de Odoo (Discuss)",
    "Audible Chime": "Timbre audible",
    "Signage Screen": "Pantalla de señalización",
    "Screen Duration (s)": "Duración en pantalla (s)",
    "Signage Display Group": "Grupo de pantallas de señalización",
    "Alert channels": "Canales de aviso",
    "Alert routing": "Enrutamiento de avisos",
    "Discreet — only the salesperson notices":
        "Discretos — solo lo nota el vendedor",
    "Not discreet — the customer may notice":
        "No discretos — el cliente puede notarlo",
    "<b>These two can be perceived by the customer.</b>":
        "<b>Estos dos los puede percibir el cliente.</b>",

    # ---- delivery record -------------------------------------------
    "Channels": "Canales",
    "Delivered": "Entregado",
    "Sent To App": "Enviado a la app",
    "Sent To Chat": "Enviado al chat",
    "Sent To WhatsApp": "Enviado a WhatsApp",
    "Chimed": "Sonó",
    "Shown On Screen": "Mostrado en pantalla",
    "Never Reached Anybody": "Nunca llegó a nadie",
    "app": "app",
    "chat": "chat",
    "chime": "timbre",
    "screen": "pantalla",
    "not delivered": "no entregado",

    # ---- help texts ------------------------------------------------
    "Push notification and activity on the salesperson's phone. Discreet: only "
    "they see it.":
        "Notificación push y actividad en el teléfono del vendedor. Discreto: "
        "solo lo ve él.",
    "For staff who do not keep the Odoo app open on the floor. Needs Odoo's "
    "WhatsApp module and a template.":
        "Para el personal que no trae abierta la app de Odoo en el piso. "
        "Requiere el módulo de WhatsApp de Odoo y una plantilla.",
    "How long an alert stays on the signage screen.":
        "Cuánto tiempo permanece un aviso en la pantalla de señalización.",
    "Recorded but delivered on no channel — usually no recipient, or a channel "
    "switched on but not configured.":
        "Registrado pero sin entregar por ningún canal: normalmente porque no "
        "hay destinatario, o porque un canal está encendido pero sin configurar.",
    "At least one channel accepted it. False means the alert was recorded but "
    "never reached anybody — usually no recipient, or a channel that is "
    "switched on but not configured.":
        "Al menos un canal lo aceptó. Falso significa que el aviso quedó "
        "registrado pero no llegó a nadie: normalmente porque no hay "
        "destinatario, o porque un canal está encendido pero sin configurar.",
    "Which channels actually delivered this alert.":
        "Por qué canales se entregó realmente este aviso.",
    "Direct message in Odoo's internal chat. Discreet, and it lands in the same "
    "place the team already talks to each other — which on a floor where "
    "everyone keeps Discuss open is often read faster than a push notification. "
    "Odoo's own client chimes for a new message, so this is audible on the "
    "salesperson's device without being audible in the shop.":
        "Mensaje directo en el chat interno de Odoo. Es discreto, y cae en el "
        "mismo lugar donde el equipo ya se habla — que en un piso donde todos "
        "traen Discuss abierto muchas veces se lee más rápido que una "
        "notificación push. El propio cliente de Odoo suena al llegar un "
        "mensaje, así que esto es audible en el dispositivo del vendedor sin "
        "ser audible en la tienda.",
    "Ask the receiving device to play a sound. NOT DISCREET: if the "
    "salesperson's phone is not on silent, or the alert lands on a back-office "
    "computer, the customer may hear it and understand that they are being "
    "discussed. Off by default for that reason, and worth testing on the actual "
    "devices before enabling.":
        "Pide al dispositivo que reciba el aviso que reproduzca un sonido. NO "
        "ES DISCRETO: si el teléfono del vendedor no está en silencio, o si el "
        "aviso cae en una computadora de trastienda, el cliente puede oírlo y "
        "entender que están hablando de él. Por eso viene apagado, y conviene "
        "probarlo en los equipos reales antes de encenderlo.",
    "Show the alert on the Xibo screen mapped to the zone. NOT DISCREET AT ALL: "
    "whatever appears there is visible to the customer standing in front of it. "
    "Use it for a message written for the customer to read, never for one about "
    "them — 'ask about our finance options', not 'unattended for three "
    "minutes'. Requires the Xibo connector.":
        "Muestra el aviso en la pantalla Xibo asignada a la zona. NO ES NADA "
        "DISCRETO: lo que aparezca ahí lo ve el cliente que está parado "
        "enfrente. Úsalo para un mensaje escrito para que el cliente lo lea, "
        "nunca para uno sobre él: «pregunta por nuestros planes de "
        "financiamiento», no «sin atender desde hace tres minutos». Requiere "
        "el conector de Xibo.",
    "Name of the Xibo display group covering this zone. Only used when the "
    "store has the signage channel switched on. Remember that anything sent "
    "here is visible to the customer standing in front of it.":
        "Nombre del grupo de pantallas de Xibo que cubre esta zona. Solo se usa "
        "cuando la tienda tiene encendido el canal de señalización. Recuerda "
        "que todo lo que se manda aquí lo ve el cliente que está enfrente.",
}

BATCH6_LOOSE = {
    "A <b>chime</b> is heard by whoever is nearby if the phone is not on "
    "silent, or if the alert lands on a back-office computer. Test it on the "
    "actual devices before you rely on it.":
        "Un timbre lo oye quien esté cerca si el teléfono no está en silencio, "
        "o si el aviso cae en una computadora de trastienda. Pruébalo en los "
        "equipos reales antes de confiarte.",

    "A <b>screen</b> message is read by the customer standing in front of it. "
    "Use it for something written <i>for</i> them — \"ask about our finance "
    "options\" — never for something <i>about</i> them.":
        "Un mensaje en pantalla lo lee el cliente que está parado enfrente. "
        "Úsalo para algo escrito para él —«pregunta por nuestros planes de "
        "financiamiento»— nunca para algo sobre él.",

    "Nudges to the salesperson covering a zone. Three channels are "
    "<b>discreet</b> — only they notice: the Odoo mobile app, Odoo's internal "
    "chat, and WhatsApp.":
        "Avisos al vendedor que cubre una zona. Tres canales son discretos "
        "—solo los nota él—: la app móvil de Odoo, el chat interno de Odoo y "
        "WhatsApp.",

    "Two more are available and <b>off by default</b> because the customer may "
    "perceive them: an audible chime, and a message on the signage screen. "
    "Switch them on knowingly — the store form spells out what each one costs "
    "in discretion.":
        "Hay dos más, apagados por omisión porque el cliente puede percibirlos: "
        "un timbre audible y un mensaje en la pantalla de señalización. "
        "Enciéndelos a sabiendas: la ficha de la tienda explica lo que cuesta "
        "cada uno en discreción.",
}
