# -*- coding: utf-8 -*-
"""Twelfth batch: the camera that heartbeats but sees nothing."""
BATCH12 = {
    "A device that is heartbeating normally but has counted nobody for this long is reported as seeing nothing. Judged against the device's own usual hourly rate, never against a clock — a counter that reports nothing at four in the morning is working correctly.\\nThis is the failure the offline check cannot see: the agent is up, the dashboard is green, and the shop simply stops being counted. Raise it on a store with long quiet spells; lower it on a busy one, where two hours of nobody is already impossible.":
        'Un dispositivo que late con normalidad pero no ha contado a nadie durante este tiempo se reporta como que no está viendo. Se juzga contra el ritmo horario habitual del propio dispositivo, nunca contra un reloj: un contador que no reporta nada a las cuatro de la mañana está funcionando bien.\\nEsta es la falla que la revisión de caída no puede ver: el agente está arriba, el tablero en verde, y la tienda simplemente deja de contarse. Súbelo en una tienda con rachas largas de calma; bájalo en una concurrida, donde dos horas sin nadie ya es imposible.',

    'Analitix: camera alive but seeing nothing':
        'Analitix: cámara viva pero sin ver nada',

    'Device %s heartbeating but reporting no crossings':
        'El dispositivo %s late pero no reporta ningún cruce',

    "Device <b>%(dev)s</b> of store <b>%(store)s</b> is reporting in normally and has not counted a single person for %(min)s minutes. Its own history says it should be seeing about %(rate).1f an hour.<br/><br/>Nothing is offline, so nothing else will flag this. Look at the camera itself: a lens that was knocked, a view that something now blocks, or a virtual line that no longer sits across the doorway.<br/><br/><b>While it lasts, this store's figures are wrong rather than missing</b> — the conversion rate reads high because the tickets keep arriving and the visitors do not.":
        'El dispositivo <b>%(dev)s</b> de la tienda <b>%(store)s</b> está reportando con normalidad y no ha contado a una sola persona en %(min)s minutos. Su propio historial dice que debería estar viendo alrededor de %(rate).1f por hora.<br/><br/>Nada está fuera de línea, así que nada más va a marcar esto. Mira la cámara en sí: un lente que se movió, una vista que ahora algo tapa, o una línea virtual que ya no cruza el vano.<br/><br/><b>Mientras dure, las cifras de esta tienda están mal, no ausentes</b>: la tasa de conversión se lee alta porque los tickets siguen llegando y los visitantes no.',

    "Device is HEARTBEATING BUT SEEING NOTHING — no crossing for %(min)s minutes, against a usual %(rate).1f an hour. The agent is alive, so this is not an outage: check the camera, the lens and the virtual line. This store's numbers are wrong rather than missing while it lasts.":
        'El dispositivo LATE PERO NO VE NADA — ningún cruce en %(min)s minutos, contra un habitual de %(rate).1f por hora. El agente está vivo, así que esto no es una caída: revisa la cámara, el lente y la línea virtual. Mientras dure, los números de esta tienda están mal, no ausentes.',

    'Seeing Nothing After (min)':
        'Sin ver nada tras (min)',

    'Seeing Nothing Since':
        'Sin ver nada desde',

    'Seeing again — crossings are arriving from this device.':
        'Vuelve a ver — están llegando cruces de este dispositivo.',

    'Set when the device is heartbeating perfectly and has not reported a single crossing for far longer than it normally goes quiet. The agent is alive; the camera is not seeing.':
        'Se marca cuando el dispositivo late perfectamente y no ha reportado un solo cruce durante mucho más de lo que suele estar callado. El agente está vivo; la cámara no está viendo.',

}
