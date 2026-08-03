# -*- coding: utf-8 -*-
"""Eighth batch: phase 5, plus everything the earlier batches left over.

This one closes the gap — after it every msgid in the .pot has a Spanish
string. It therefore mixes the watch list with the leftovers of phases 1-4:
the long help texts nobody had reached yet, the two mail bodies, and the
mail.thread fields Odoo generates on any model that gains a chatter.

Keys reproduce the .pot msgid byte for byte; make_es_po.py reports any that
miss, because Odoo drops a mismatch without a word.
"""
BATCH8 = {
    'Help':
        'Ayuda',

    'Implementation Guide':
        'Guía de implementación',

    'User Manual':
        'Manual de usuario',

    '%(detail)s\\n\\nWorth going over. This is a behaviour pattern, not an accusation — most of the time the person simply wants help.':
        '%(detail)s\\n\\nVale la pena echar un ojo. Esto es un patrón de conducta, no una acusación: la mayoría de las veces la persona solo quiere que la atiendan.',

    '%(names)s cannot open watch-list entries, so telling them about a match would be a warning with no explanation attached. Give them the Analitix security role first, or leave them off this list.':
        '%(names)s no puede abrir entradas de la lista de vigilancia, así que avisarles de una coincidencia sería una advertencia sin explicación. Dales primero el rol de seguridad de Analitix, o déjalos fuera de esta lista.',

    '%(tickets)s of them bought something — that is %(rate).1f%% of everyone who walked in.':
        '%(tickets)s de ellas compraron algo: es el %(rate).1f%% de todo el que entró.',

    "%(user)s reviewed a match on %(date)s and reported it as the WRONG PERSON. If this keeps happening, the entry's signature is poor and it should be removed rather than re-enrolled.":
        '%(user)s revisó una coincidencia del %(date)s y reportó que era la PERSONA EQUIVOCADA. Si esto se repite, la firma de la entrada es mala y conviene retirarla en vez de volver a registrarla.',

    '18-24,25-34':
        '18-24,25-34',

    '<div style=\\"font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#333;\\">\\n                    <p style=\\"font-size:16px;margin:0 0 12px 0;\\">\\n                        <strong t-out=\\"object.name\\">Device</strong> stopped reporting.\\n                    </p>\\n                    <table style=\\"border-collapse:collapse;margin:0 0 16px 0;\\">\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">Store</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.store_id.name\\">Store</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">Door</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.door_id.name or \'—\'\\">Door</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">Device UID</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.device_uid\\">uid</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">Last heartbeat</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.last_heartbeat or \'never\'\\">-</t> UTC</td>\\n                        </tr>\\n                    </table>\\n                    <p style=\\"margin:0 0 12px 0;\\">\\n                        While this device is down, the store\'s visitor count and\\n                        conversion rate are incomplete — the numbers on the\\n                        dashboard understate reality and should not be used for\\n                        decisions until it is back.\\n                    </p>\\n                    <p style=\\"margin:0;color:#777;font-size:12px;\\">\\n                        Usual causes, in the order they are usually found: the\\n                        mini-PC lost power, the store\'s internet is down, or the\\n                        camera was unplugged during cleaning.\\n                    </p>\\n                </div>\\n            ':
        '<div style=\\"font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#333;\\">\\n                    <p style=\\"font-size:16px;margin:0 0 12px 0;\\">\\n                        <strong t-out=\\"object.name\\">Dispositivo</strong> dejó de reportar.\\n                    </p>\\n                    <table style=\\"border-collapse:collapse;margin:0 0 16px 0;\\">\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">Tienda</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.store_id.name\\">Tienda</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">Puerta</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.door_id.name or \'—\'\\">Puerta</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">UID del dispositivo</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.device_uid\\">uid</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:4px 12px 4px 0;color:#777;\\">Último latido</td>\\n                            <td style=\\"padding:4px 0;\\"><t t-out=\\"object.last_heartbeat or \'nunca\'\\">-</t> UTC</td>\\n                        </tr>\\n                    </table>\\n                    <p style=\\"margin:0 0 12px 0;\\">\\n                        Mientras este dispositivo esté caído, el conteo de visitantes y la\\n                        tasa de conversión de la tienda están incompletos: los números\\n                        del tablero se quedan cortos frente a la realidad y no deberían\\n                        usarse para decidir hasta que vuelva.\\n                    </p>\\n                    <p style=\\"margin:0;color:#777;font-size:12px;\\">\\n                        Causas habituales, en el orden en que suelen encontrarse: la\\n                        mini-PC se quedó sin corriente, la tienda se quedó sin internet,\\n                        o desconectaron la cámara al hacer la limpieza.\\n                    </p>\\n                </div>\\n            ',

    '<div style=\\"font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#2b2b2b;max-width:620px;\\">\\n                    <p style=\\"font-size:18px;margin:0 0 4px 0;\\">\\n                        <strong t-out=\\"object.store_id.name\\">Store</strong>\\n                    </p>\\n                    <p style=\\"margin:0 0 20px 0;color:#777;font-size:13px;\\">\\n                        <t t-out=\\"object.period_start\\">from</t> – <t t-out=\\"object.period_end\\">to</t>\\n                    </p>\\n\\n                    <t t-foreach=\\"object.summary_lines()\\" t-as=\\"line\\">\\n                        <p style=\\"margin:0 0 10px 0;line-height:1.5;\\" t-out=\\"line\\">Line</p>\\n                    </t>\\n\\n                    <table style=\\"border-collapse:collapse;margin:22px 0;width:100%;\\">\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">Visitors</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.visitors\\">0</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">Sales</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.tickets\\">0</t></td>\\n                        </tr>\\n                        <tr style=\\"background:#fafafa;\\">\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\"><strong>Conversion</strong></td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><strong><t t-out=\\"\'%.1f\' % object.conversion_rate\\">0</t>%</strong></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">Walk-outs spotted</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.lost_sales_detected\\">0</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">Of those, rescued</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.lost_sales_rescued\\">0</t></td>\\n                        </tr>\\n                    </table>\\n\\n                    <div t-if=\\"object.estimated_recovered\\" style=\\"background:#f4f8f4;border-left:3px solid #6aa84f;padding:14px 16px;margin:0 0 18px 0;\\">\\n                        <p style=\\"margin:0 0 6px 0;font-size:17px;\\">\\n                            <strong>≈ <t t-out=\\"object.currency_id.symbol\\"/><t t-out=\\"\'%.2f\' % object.estimated_recovered\\">0</t></strong>\\n                            recovered\\n                        </p>\\n                        <p style=\\"margin:0;color:#666;font-size:13px;\\">\\n                            This is an <strong>estimate</strong>, not a measurement: rescued\\n                            walk-outs multiplied by your own average sale. A rescued walk-out\\n                            is one where we nudged your team and that same visit then bought\\n                            something.\\n                        </p>\\n                    </div>\\n\\n                    <p style=\\"margin:0;color:#777;font-size:12px;\\">\\n                        Questions about any of these numbers? Reply to this e-mail.\\n                    </p>\\n                </div>\\n            ':
        '<div style=\\"font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#2b2b2b;max-width:620px;\\">\\n                    <p style=\\"font-size:18px;margin:0 0 4px 0;\\">\\n                        <strong t-out=\\"object.store_id.name\\">Tienda</strong>\\n                    </p>\\n                    <p style=\\"margin:0 0 20px 0;color:#777;font-size:13px;\\">\\n                        <t t-out=\\"object.period_start\\">desde</t> – <t t-out=\\"object.period_end\\">hasta</t>\\n                    </p>\\n\\n                    <t t-foreach=\\"object.summary_lines()\\" t-as=\\"line\\">\\n                        <p style=\\"margin:0 0 10px 0;line-height:1.5;\\" t-out=\\"line\\">Línea</p>\\n                    </t>\\n\\n                    <table style=\\"border-collapse:collapse;margin:22px 0;width:100%;\\">\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">Visitantes</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.visitors\\">0</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">Ventas</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.tickets\\">0</t></td>\\n                        </tr>\\n                        <tr style=\\"background:#fafafa;\\">\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\"><strong>Conversión</strong></td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><strong><t t-out=\\"\'%.1f\' % object.conversion_rate\\">0</t>%</strong></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">Fugas detectadas</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.lost_sales_detected\\">0</t></td>\\n                        </tr>\\n                        <tr>\\n                            <td style=\\"padding:8px 12px 8px 0;color:#777;\\">De esas, rescatadas</td>\\n                            <td style=\\"padding:8px 0;text-align:right;\\"><t t-out=\\"object.lost_sales_rescued\\">0</t></td>\\n                        </tr>\\n                    </table>\\n\\n                    <div t-if=\\"object.estimated_recovered\\" style=\\"background:#f4f8f4;border-left:3px solid #6aa84f;padding:14px 16px;margin:0 0 18px 0;\\">\\n                        <p style=\\"margin:0 0 6px 0;font-size:17px;\\">\\n                            <strong>≈ <t t-out=\\"object.currency_id.symbol\\"/><t t-out=\\"\'%.2f\' % object.estimated_recovered\\">0</t></strong>\\n                            recuperados\\n                        </p>\\n                        <p style=\\"margin:0;color:#666;font-size:13px;\\">\\n                            Esto es una <strong>estimación</strong>, no una medición: fugas rescatadas\\n                            multiplicadas por tu propia venta promedio. Una fuga rescatada es\\n                            aquella en la que avisamos a tu equipo y esa misma visita después\\n                            compró algo.\\n                        </p>\\n                    </div>\\n\\n                    <p style=\\"margin:0;color:#777;font-size:12px;\\">\\n                        ¿Dudas con alguno de estos números? Responde a este correo.\\n                    </p>\\n                </div>\\n            ',

    '<strong>This entry does nothing yet.</strong> It matches\\n                        nobody until a second authorised person confirms it —\\n                        and the person who added it cannot be the one who\\n                        confirms. One bad afternoon should not be enough to mark\\n                        somebody.':
        '<strong>Esta entrada todavía no hace nada.</strong> No coincide\\n                        con nadie hasta que una segunda persona autorizada la\\n                        confirme, y quien la dio de alta no puede ser quien la\\n                        confirme. Una mala tarde no debería bastar para señalar\\n                        a alguien.',

    '<strong>This is the only feature in Analitix\\n                                that names a specific person.</strong> Switching\\n                                it on does not create a list — entries are added\\n                                by hand after a documented incident, and each\\n                                needs a second authorised person to confirm it.\\n                                Nothing here ever reaches a screen or the sales\\n                                floor at large.':
        '<strong>Esta es la única función de Analitix\\n                                que señala a una persona concreta.</strong> Encenderla\\n                                no crea ninguna lista: las entradas se dan de alta\\n                                a mano tras un incidente documentado, y cada una\\n                                necesita que una segunda persona autorizada la\\n                                confirme. Nada de aquí llega nunca a una pantalla\\n                                ni al piso de venta en general.',

    'A band, not an age. The underlying model outputs an estimate with real error; reporting it to the year would present a guess as a measurement.':
        'Un rango, no una edad. El modelo de fondo entrega una estimación con error real; darla al año presentaría una conjetura como si fuera una medición.',

    'A draft entry matches nothing at all. It becomes active only when a second authorised person confirms it.':
        'Una entrada en borrador no coincide con nada. Solo se activa cuando una segunda persona autorizada la confirma.',

    'A match is a prompt to pay attention. It is never an\\n                        accusation, it never appears on a screen, it never\\n                        reaches the sales floor at large, and it never triggers\\n                        an automatic action. A person is told, quietly, and a\\n                        person decides what to do.':
        'Una coincidencia es una señal para poner atención. Nunca es una\\n                        acusación, nunca aparece en una pantalla, nunca llega al\\n                        piso de venta en general y nunca dispara una acción\\n                        automática. Se le avisa a una persona, en corto, y una\\n                        persona decide qué hacer.',

    'A person matching watch-list entry %(ref)s (%(label)s) has come in.\\n\\n%(reason)s\\n\\nThis is a prompt to pay attention, not an accusation and not an instruction. Confidence %(score).0f%%. Somebody should look, and somebody should decide.':
        'Entró una persona que coincide con la entrada %(ref)s (%(label)s) de la lista de vigilancia.\\n\\n%(reason)s\\n\\nEsto es una señal para poner atención, no una acusación ni una instrucción. Confianza %(score).0f%%. Alguien debe ir a ver, y alguien debe decidir.',

    'A reading captured before the visit was resolved. The resolution job moves it onto the visit; it is held here in the meantime so the reading is never orphaned from the crossing that produced it.':
        'Una lectura capturada antes de resolver la visita. El trabajo de resolución la mueve a la visita; mientras tanto se guarda aquí para que la lectura nunca quede huérfana del cruce que la produjo.',

    'A salesperson attended them, either because the edge saw a staff face beside them or because someone acknowledged the alert.':
        'Un vendedor los atendió, ya sea porque el edge vio una cara de personal a su lado o porque alguien se dio por enterado del aviso.',

    "A salesperson did attend them and they still left. Kept, because 'we attend them and they leave anyway' is a different and more expensive problem than 'nobody goes over'.":
        'Un vendedor sí los atendió y aun así se fueron. Se conserva, porque «los atendemos y se van igual» es un problema distinto y más caro que «nadie se acerca».',

    "A screen that says 'Welcome back, Gustavo' while Gustavo is standing there with somebody has just told that person something about him. When he is not alone the screen stays neutral and the personal greeting goes to the salesperson instead.":
        'Una pantalla que dice «Bienvenido de vuelta, Gustavo» mientras Gustavo está ahí parado con alguien acaba de contarle algo a esa persona sobre él. Cuando no viene solo, la pantalla se queda neutral y el saludo personal se va al vendedor.',

    'A shift still open after this long is closed by the nightly job. Exits do get missed, and an employee who appears to have worked fifty hours makes any payroll reading it wrong.':
        'Un turno que sigue abierto pasado este tiempo lo cierra el trabajo nocturno. Las salidas sí se pierden, y un empleado que parece haber trabajado cincuenta horas deja mal cualquier nómina que lo lea.',

    'A visit still open after this long is closed by the nightly cron. Exits do get missed, and a visit left open forever quietly inflates the occupancy figure until it is nonsense.':
        'Una visita que sigue abierta pasado este tiempo la cierra el cron nocturno. Las salidas sí se pierden, y una visita abierta para siempre infla el aforo en silencio hasta volverlo un disparate.',

    'Activities':
        'Actividades',

    'Activity Exception Decoration':
        'Decoración de la actividad de excepción',

    'Activity State':
        'Estado de la actividad',

    'Activity Type Icon':
        'Icono del tipo de actividad',

    'Added By':
        'Dada de alta por',

    'After this the entry stops matching, automatically. A list that only grows is a list nobody trusts.':
        'A partir de esta fecha la entrada deja de coincidir, sola. Una lista que solo crece es una lista en la que nadie confía.',

    'After this the store is expected to be on a paid plan. Nothing stops working on its own: an expired trial raises an activity for a human, because cutting a customer off automatically over a date is how you lose one who was about to sign.':
        'Después de esta fecha se espera que la tienda esté en un plan de pago. Nada deja de funcionar solo: una prueba vencida levanta una actividad para una persona, porque cortarle el servicio a un cliente automáticamente por una fecha es como se pierde a uno que estaba por firmar.',

    'An entry cannot expire before the date it is due for review.':
        'Una entrada no puede vencer antes de la fecha en que toca revisarla.',

    'An entry stops matching automatically after this. A list that only ever grows is a list nobody trusts and nobody prunes.':
        'Una entrada deja de coincidir automáticamente pasado este plazo. Una lista que solo crece es una lista en la que nadie confía y que nadie poda.',

    'An opaque handle. Deliberately not a name: staff acting on an alert need to know somebody is worth a second look, not to circulate an identity.':
        'Un identificador opaco. A propósito no es un nombre: quien actúa sobre un aviso necesita saber que alguien merece una segunda mirada, no hacer circular una identidad.',

    "An unacknowledged alert becomes 'missed' after this long. Kept honest on purpose: a report that only counted the alerts that went well would be the most flattering and least useful version of the truth.":
        'Un aviso sin acuse se marca «no atendido» pasado este tiempo. Honesto a propósito: un informe que solo contara los avisos que salieron bien sería la versión más halagadora y menos útil de la verdad.',

    'Analitix Watch-list Entry':
        'Entrada de lista de vigilancia de Analitix',

    'Analitix Watch-list Match':
        'Coincidencia de lista de vigilancia de Analitix',

    "Analitix closed this attendance automatically: no exit was seen. The check-out time is the store's maximum shift length, not an observation — correct it if the real time matters.":
        'Analitix cerró esta asistencia automáticamente: no se vio ninguna salida. La hora de salida es la jornada máxima de la tienda, no una observación: corrígela si la hora real importa.',

    'Analitix saw this customer spend %(mins)s minutes at %(zone)s on %(when)s without being served, and leave without buying.':
        'Analitix vio a este cliente pasar %(mins)s minutos en %(zone)s el %(when)s sin que nadie lo atendiera, y salir sin comprar.',

    'Analitix: expire and review watch-list entries':
        'Analitix: vencer y revisar entradas de la lista de vigilancia',

    'At your average sale of %(cur)s%(avg).2f, that is roughly %(cur)s%(recovered).2f you would probably not have taken. It is an estimate, not a measurement.':
        'Con tu venta promedio de %(cur)s%(avg).2f, eso es más o menos %(cur)s%(recovered).2f que probablemente no habrías cobrado. Es una estimación, no una medición.',

    'Attachment Count':
        'Número de adjuntos',

    'Awaiting Confirmation':
        'Pendientes de confirmar',

    'Awaiting confirmation':
        'Pendiente de confirmación',

    "Below the store's usual figure with plenty of stops means people are drawn to this display and then walk away — price, or nobody closing.":
        'Por debajo de la cifra habitual de la tienda y con muchas paradas significa que la gente se acerca a este exhibidor y luego se va: precio, o nadie que cierre.',

    "Ceiling on one purchase unit. Without it, a school group filing through the door becomes a single 'customer' and distorts the day's basket statistics.":
        'Tope de una unidad de compra. Sin él, un grupo escolar que entra en fila se vuelve un solo «cliente» y distorsiona las estadísticas de canasta del día.',

    "Comma-separated, e.g. '18-24,25-34'. Leave empty for any age. Only meaningful where the store captures demographics.":
        'Separadas por comas, p. ej. «18-24,25-34». Vacío para cualquier edad. Solo tiene sentido donde la tienda captura demografía.',

    'Confidence from the edge that this was a live face rather than a photograph held up to the camera. Recorded here so the phases that make consequential decisions can require a floor.':
        'Confianza del edge en que era una cara viva y no una fotografía puesta frente a la cámara. Se registra aquí para que las fases que toman decisiones de peso puedan exigir un mínimo.',

    'Configured but never triggered. Usually the conditions are narrower than the shop realised.':
        'Configuradas y nunca disparadas. Casi siempre las condiciones son más estrechas de lo que la tienda creía.',

    'Confirm':
        'Confirmar',

    'Confirmed By':
        'Confirmada por',

    'Confirmed On':
        'Confirmada el',

    'Confirmed by %(user)s. This entry is now active until %(date)s.':
        'Confirmada por %(user)s. Esta entrada queda activa hasta el %(date)s.',

    'Confirmed incident':
        'Incidente confirmado',

    'Confirming makes this entry live: the person will be recognised on arrival and a small, named group will be told. Is the reason written down, factual and dated?':
        'Confirmar deja esta entrada viva: se reconocerá a la persona al llegar y se le avisará a un grupo pequeño y nombrado. ¿El motivo está escrito, con hechos y con fecha?',

    'Control':
        'Control',

    'Correct match, incident':
        'Coincidencia correcta, con incidente',

    'Correct match, nothing happened':
        'Coincidencia correcta, sin novedad',

    'Cosine similarity above which two sightings are the same person. Stricter than the staff threshold on purpose: a wrong staff match drops one crossing, a wrong visitor match merges two strangers into one visit and corrupts every metric downstream.':
        'Similitud coseno por encima de la cual dos avistamientos son la misma persona. Más estricto que el umbral de personal a propósito: una coincidencia de personal equivocada pierde un cruce, una de visitante equivocada fusiona a dos desconocidos en una visita y corrompe todas las métricas río abajo.',

    'Created by':
        'Creado por',

    'Created on':
        'Creado el',

    'Deliberately far stricter than ordinary re-identification. A wrong re-identification merges two visits; a wrong match here puts an innocent person under suspicion, so this errs heavily towards missing a real match rather than inventing one.':
        'Deliberadamente mucho más estricto que la reidentificación normal. Una reidentificación equivocada fusiona dos visitas; una coincidencia equivocada aquí pone bajo sospecha a una persona inocente, así que esto se inclina fuertemente a perder una coincidencia real antes que a inventar una.',

    'Display Name':
        'Nombre mostrado',

    'Drives sensible defaults and, from phase 4, which screen a trigger is routed to.':
        'Determina valores por omisión razonables y, desde la fase 4, a qué pantalla se enruta un disparo.',

    'Due For Review':
        'Pendientes de revisión',

    'Dwell beyond this with nobody serving them is worth a nudge. Set it long in a browse-heavy shop and short at a counter where waiting means being ignored.':
        'Permanecer más de esto sin que nadie los atienda amerita un aviso. Ponlo largo en una tienda de mirar y corto en un mostrador, donde esperar es sentirse ignorado.',

    'Entries':
        'Entradas',

    'Entries Expire After (days)':
        'Las entradas vencen a los (días)',

    'Entry':
        'Entrada',

    'Entry %(ref)s confirmed by %(user)s':
        'Entrada %(ref)s confirmada por %(user)s',

    'Entry %s removed from the watch list':
        'Entrada %s retirada de la lista de vigilancia',

    'Estimate age band, gender and expression at the entrance. Off by default: it needs a second, front-facing camera per door, and a store that has not installed one should not see empty charts suggesting the system is broken.':
        'Estima rango de edad, género y expresión en la entrada. Apagado por omisión: necesita una segunda cámara frontal por puerta, y una tienda que no la instaló no debería ver gráficas vacías que sugieran que el sistema está roto.',

    'Estimated recovered revenue against what the store paid. The single number the owner is actually asking about.':
        'Ingreso recuperado estimado frente a lo que la tienda pagó. El único número por el que el dueño realmente pregunta.',

    'Estimated recovered revenue at or above the subscription. The number the owner is actually asking about.':
        'Ingreso recuperado estimado igual o superior a la suscripción. El número por el que el dueño realmente pregunta.',

    'Ever Matched':
        'Con alguna coincidencia',

    "Every confidence clears the store's floor. Unreliable readings are kept, not discarded, so a dashboard can leave them out explicitly rather than quietly average a coin flip into the customer's numbers.":
        'Cada confianza supera el mínimo de la tienda. Las lecturas poco fiables se conservan, no se descartan, para que un tablero pueda excluirlas explícitamente en vez de promediar un volado en los números del cliente.',

    'Every sighting lands here, along with what the person who looked made of it.':
        'Aquí cae cada avistamiento, junto con lo que dijo quien fue a ver.',

    'Expired':
        'Vencida',

    'Expired automatically. It no longer matches anything; a person has to review and extend it for that to change.':
        'Vencida automáticamente. Ya no coincide con nada; para que eso cambie, una persona tiene que revisarla y prorrogarla.',

    'Expires On':
        'Vence el',

    'Expiry':
        'Vencimiento',

    'Face vector, encrypted at rest. No photograph is stored here or anywhere else in Analitix.':
        'Vector facial, cifrado en reposo. Aquí no se guarda ninguna fotografía, ni en ningún otro punto de Analitix.',

    "Filled in afterwards by the person who went over. 'Nothing in it' and 'just needed help' are the answers we expect most of the time, and recording them is what lets a store see whether its thresholds are set sensibly.":
        'Lo llena después la persona que fue a ver. «No era nada» y «solo necesitaba ayuda» son las respuestas que esperamos la mayoría de las veces, y registrarlas es lo que le permite a una tienda ver si sus umbrales están razonables.',

    'Filled in by the salesperson, or by phase 4 when a sale is matched to the same visit shortly afterwards.':
        'Lo llena el vendedor, o la fase 4 cuando una venta se asocia a la misma visita poco después.',

    "Filled in by whoever looked. 'Wrong person' is the most important value here: a list with false positives nobody records is a list nobody can fix.":
        'Lo llena quien fue a ver. «Persona equivocada» es el valor más importante de aquí: una lista cuyos falsos positivos nadie registra es una lista que nadie puede corregir.',

    'Followers':
        'Seguidores',

    'Followers (Partners)':
        'Seguidores (contactos)',

    'Font awesome icon e.g. fa-tasks':
        'Icono de Font Awesome, p. ej. fa-tasks',

    'Hard ceiling: no entry can be set to run longer than this without somebody looking at it again.':
        'Tope duro: ninguna entrada puede quedar vigente más tiempo que esto sin que alguien vuelva a mirarla.',

    'Has Message':
        'Tiene mensaje',

    "How close behind a known customer another arrival counts as 'with them' for the greeting rule above.":
        'Qué tan cerca, detrás de un cliente conocido, cuenta otra llegada como «acompañante» para la regla de saludo de arriba.',

    'How close in time counts as arriving together. A wide automatic door lets a couple through side by side in under a second; a narrow one makes them file through three seconds apart.':
        'Qué tan cerca en el tiempo cuenta como llegar juntos. Una puerta automática ancha deja pasar a una pareja hombro con hombro en menos de un segundo; una angosta los hace entrar en fila con tres segundos de diferencia.',

    'How confident the edge is that this was a live face and not a photograph shown to the camera (task 984, point 3).':
        'Qué tan seguro está el edge de que era una cara viva y no una fotografía puesta frente a la cámara (tarea 984, punto 3).',

    'How long an anonymous face signature is kept before it is deleted. This is the retention promise, and it is also what keeps matching fast — a store only ever compares against the people who were there recently, never against its whole history.':
        'Cuánto se conserva una firma facial anónima antes de borrarla. Esta es la promesa de retención, y es también lo que mantiene rápida la comparación: una tienda solo se compara contra quienes estuvieron ahí hace poco, nunca contra toda su historia.',

    'How long an identified signature is kept. It outlives the anonymous window — that is what makes recognition possible — but not forever, and the same expiry job enforces it.':
        'Cuánto se conserva una firma identificada. Sobrevive a la ventana anónima —eso es lo que hace posible el reconocimiento— pero no para siempre, y el mismo trabajo de vencimiento lo hace cumplir.',

    'How long before a new entry is put back in front of a human to confirm it still belongs on the list.':
        'Cuánto tarda una entrada nueva en volver frente a una persona para confirmar que sigue teniendo razón de estar.',

    'How long the salesperson took to acknowledge. The number that tells an owner whether the nudges are actually being read.':
        'Cuánto tardó el vendedor en darse por enterado. El número que le dice al dueño si los avisos de verdad se están leyendo.',

    'How many times this person came back in during the same visit. A high number at a single-door store usually means the virtual line sits across a waiting area rather than in the doorway.':
        'Cuántas veces volvió a entrar esta persona durante la misma visita. Un número alto en una tienda de una sola puerta suele significar que la línea virtual está atravesada en una sala de espera y no en el vano.',

    'How this entry is described internally':
        'Cómo se describe esta entrada internamente',

    "How this entry is described internally — 'the man from the March 4th incident'. Keep it factual: this is read by people who were not there.":
        'Cómo se describe esta entrada internamente: «el señor del incidente del 4 de marzo». Que sea factual: esto lo lee gente que no estuvo ahí.',

    'ID':
        'ID',

    'Icon':
        'Icono',

    'Icon to indicate an exception activity.':
        'Icono para indicar una actividad de excepción.',

    'If checked, new messages require your attention.':
        'Si está marcado, hay mensajes nuevos que requieren tu atención.',

    'If checked, some messages have a delivery error.':
        'Si está marcado, algunos mensajes tienen un error de entrega.',

    'Incident Date':
        'Fecha del incidente',

    'Is Follower':
        'Es seguidor',

    "Kept on purpose: 'the screen never showed it' is exactly what a store needs to be able to see.":
        'Se conservan a propósito: «la pantalla nunca lo mostró» es justo lo que una tienda necesita poder ver.',

    'Label':
        'Etiqueta',

    'Last Updated by':
        'Última modificación por',

    'Last Updated on':
        'Última modificación el',

    'Leave this empty and matches are recorded but\\n                                nobody hears about them. That is a defensible\\n                                state — it is silently telling nobody that is\\n                                not.':
        'Déjalo vacío y las coincidencias se registran pero\\n                                nadie se entera. Ese es un estado defendible:\\n                                lo que no lo es, es no avisarle a nadie en\\n                                silencio.',

    'Leaving and returning inside this gap continues the same visit. A jewellery boutique where people browse for forty minutes and a convenience store where they are in and out in ninety seconds cannot share one number.':
        'Salir y volver dentro de este lapso continúa la misma visita. Una joyería donde la gente mira cuarenta minutos y una tienda de conveniencia donde entran y salen en noventa segundos no pueden compartir un número.',

    "Let measured events change what the shop's screens are showing. Off until the store has mapped a screen to at least one zone — rules that resolve to nowhere are worse than no rules.":
        'Deja que los eventos medidos cambien lo que muestran las pantallas de la tienda. Apagado hasta que la tienda haya mapeado una pantalla a al menos una zona: reglas que no resuelven a ningún lado son peores que ninguna regla.',

    'Link a face signature to a res.partner when the customer hands over their details at the till, so the shop recognises them at the door next time. OFF by default and deliberately so: a store that only bought the analytics should never acquire a biometric customer index by accident.':
        'Liga una firma facial a un res.partner cuando el cliente entrega sus datos en la caja, para que la tienda lo reconozca en la puerta la próxima vez. APAGADO por omisión y a propósito: una tienda que solo compró la analítica jamás debería adquirir por accidente un índice biométrico de clientes.',

    'Mail the owner a plain-language summary each month: visitors, conversion, walk-outs spotted and rescued, and roughly what that was worth. This is the report that shows the subscription paying for itself.':
        'Mándale al dueño un resumen mensual en lenguaje llano: visitantes, conversión, fugas detectadas y rescatadas, y aproximadamente cuánto valió eso. Este es el informe que muestra que la suscripción se paga sola.',

    'Manage the watch list: add, confirm, review and remove entries, and receive match alerts. Not granted to anybody by default.':
        'Gestionar la lista de vigilancia: dar de alta, confirmar, revisar y retirar entradas, y recibir los avisos de coincidencia. No se le concede a nadie por omisión.',

    'Match':
        'Coincidencia',

    'Match Count':
        'Coincidencias',

    'Maximum Without Review (days)':
        'Máximo sin revisión (días)',

    'Message Delivery error':
        'Error de entrega del mensaje',

    'Messages':
        'Mensajes',

    'Minimum gap between alerts of the same kind to the same person. A salesperson buzzed every ninety seconds stops reading them, which is worse than not sending them at all.':
        'Separación mínima entre avisos del mismo tipo a la misma persona. Un vendedor al que le zumba el teléfono cada noventa segundos deja de leerlos, que es peor que no mandarlos.',

    "Minimum gap between two firings of this rule on the same screen. Without it a busy hour turns the shop's signage into a flicker.":
        'Separación mínima entre dos disparos de esta regla en la misma pantalla. Sin ella, una hora concurrida convierte la cartelería de la tienda en un parpadeo.',

    'My Activity Deadline':
        'Fecha límite de mis actividades',

    'Name of the layout to show. Leave empty to send the message below as an overlay instead.':
        'Nombre del layout que se muestra. Déjalo vacío para mandar el mensaje de abajo como sobreimpresión.',

    'New':
        'Nuevo',

    'Next Activity Calendar Event':
        'Evento de calendario de la siguiente actividad',

    'Next Activity Deadline':
        'Fecha límite de la siguiente actividad',

    'Next Activity Summary':
        'Resumen de la siguiente actividad',

    'Next Activity Type':
        'Tipo de la siguiente actividad',

    'No matches recorded.':
        'No hay coincidencias registradas.',

    'No one is on the watch list.':
        'No hay nadie en la lista de vigilancia.',

    "Nobody was on duty in that zone, so this went to the store's fallback. A lot of these means the shift map is wrong.":
        'Nadie estaba de turno en esa zona, así que esto se fue al respaldo de la tienda. Muchos de estos significan que el rol de turnos está mal.',

    'Not reviewed':
        'Sin revisar',

    'Note':
        'Nota',

    'Notice patterns worth a second look: in and out repeatedly, a long stop at an expensive case with nobody nearby, a group that arrives together and scatters. Anonymous and about behaviour, never about people — the named watch list is a separate feature.':
        'Detecta patrones que ameritan una segunda mirada: entrar y salir repetidamente, una parada larga frente a una vitrina cara sin nadie cerca, un grupo que llega junto y se dispersa. Anónimo y sobre conducta, nunca sobre personas: la lista de vigilancia con nombres es una función aparte.',

    "Nudge a salesperson when somebody lingers unserved and then leaves without buying. This is the number that sells the product: not 'you had 400 visitors' but 'eleven people waited at the counter and nine were never spoken to'.":
        'Avísale a un vendedor cuando alguien se demora sin que lo atiendan y luego se va sin comprar. Este es el número que vende el producto: no «tuviste 400 visitantes» sino «once personas esperaron en el mostrador y con nueve nadie habló».',

    'Number of Actions':
        'Número de acciones',

    'Number of errors':
        'Número de errores',

    'Number of messages requiring action':
        'Número de mensajes que requieren atención',

    'Number of messages with delivery error':
        'Número de mensajes con error de entrega',

    "Numeric id of the WhatsApp template to send. Find it in WhatsApp → Templates: it is the last number in the URL when the template is open. Only used when the WhatsApp channel is selected and Odoo's WhatsApp module is installed.":
        'Id numérico de la plantilla de WhatsApp que se manda. Lo encuentras en WhatsApp → Plantillas: es el último número de la URL con la plantilla abierta. Solo se usa cuando el canal de WhatsApp está seleccionado y el módulo WhatsApp de Odoo está instalado.',

    'Of the alerts this person answered, how many ended in a sale. Measured against what they answered rather than what they were sent, because nobody should be marked down for a nudge that arrived while they were with another customer.':
        'De los avisos que esta persona atendió, cuántos terminaron en venta. Se mide contra lo que atendió y no contra lo que le mandaron, porque a nadie hay que bajarle la calificación por un aviso que llegó mientras estaba con otro cliente.',

    'Only a draft entry can be confirmed.':
        'Solo se puede confirmar una entrada en borrador.',

    "Only for the quiet-hour trigger: fire when the store's traffic this hour is under this figure. What counts as quiet is a property of the shop, not of the software.":
        'Solo para el disparo de hora valle: se activa cuando el tráfico de la tienda en esta hora está por debajo de esta cifra. Qué es «hora valle» es propiedad de la tienda, no del software.',

    'Opaque handle for this signature. It is not a name and cannot be traced to one — it exists so a person can be discussed in a log without inventing an identity for them.':
        'Identificador opaco de esta firma. No es un nombre y no puede rastrearse hasta uno: existe para poder hablar de una persona en una bitácora sin inventarle una identidad.',

    'Open a lead for a lost sale. Only ever fires for a customer the shop can actually contact — a lead with no name and no phone is filing clutter that buries the real ones.':
        'Abrir una oportunidad por una venta perdida. Solo se dispara con un cliente al que la tienda de verdad puede contactar: una oportunidad sin nombre ni teléfono es relleno que entierra a las reales.',

    'Optional CRM follow-up. Only created for an identified customer — a lead with no way to contact anybody is filing clutter.':
        'Seguimiento opcional en CRM. Solo se crea para un cliente identificado: una oportunidad sin forma de contactar a nadie es papeleo de relleno.',

    "Past the zone's engagement threshold: this person was looking, not walking through.":
        'Pasó el umbral de interés de la zona: esta persona estaba mirando, no de paso.',

    'Point of Sale Orders':
        'Pedidos del punto de venta',

    'Readings below this are never checked against the list at all. A photograph held up to a camera must not be able to put a real person under suspicion.\\nNote that cameras which do not report a liveness score at all send zero, so with any value above zero here the list matches nothing. That is the safe way round — but if your edge agents do not do liveness, lowering this is a decision to make knowingly rather than a number to nudge until matches appear.':
        'Las lecturas por debajo de esto nunca se comparan contra la lista. Una fotografía puesta frente a una cámara no debe poder poner bajo sospecha a una persona real.\\nOjo: las cámaras que no reportan vitalidad mandan cero, así que con cualquier valor mayor que cero aquí la lista no coincide con nada. Ese es el lado seguro; pero si tus agentes edge no hacen vitalidad, bajarlo es una decisión que hay que tomar a conciencia y no un número que se mueve hasta que aparezcan coincidencias.',

    "Readings below this are stored but flagged unreliable, so a dashboard can leave them out explicitly rather than quietly average a coin flip into the customer's numbers.":
        'Las lecturas por debajo de esto se guardan pero se marcan como poco fiables, para que un tablero pueda excluirlas explícitamente en vez de promediar un volado en los números del cliente.',

    'Reason':
        'Motivo',

    'Recognise people a manager has deliberately added after a documented incident, and tell a named, restricted group when one of them comes in. Off by default, and it should stay off unless the store has a real reason and a person accountable for it.':
        'Reconocer a personas que un gerente dio de alta deliberadamente tras un incidente documentado, y avisarle a un grupo nombrado y restringido cuando alguna entra. Apagado por omisión, y así debería quedarse salvo que la tienda tenga una razón real y una persona que responda por ello.',

    'Recognition':
        'Reconocimiento',

    'Recorded here for the value report, which compares it against the revenue the store recovered.':
        'Se registra aquí para el informe de valor, que lo compara contra los ingresos que la tienda recuperó.',

    'Recording what actually happened is what keeps this list\\n                        honest. <strong>Wrong person</strong> is the most\\n                        important outcome here: a list whose false positives\\n                        nobody writes down is a list nobody can fix.':
        'Registrar lo que de verdad pasó es lo que mantiene honesta esta\\n                        lista. <strong>Persona equivocada</strong> es el\\n                        desenlace más importante de aquí: una lista cuyos falsos\\n                        positivos nadie anota es una lista que nadie puede corregir.',

    'Reject face readings that the edge could not confirm came from a live person rather than a photograph. Meaningful from phase 3 onward, where recognition starts driving real decisions; in phase 2 the only consequence of a match is being counted once instead of twice.':
        'Rechaza lecturas faciales que el edge no pudo confirmar que vinieran de una persona viva y no de una fotografía. Tiene sentido desde la fase 3 en adelante, donde el reconocimiento empieza a mover decisiones reales; en la fase 2 la única consecuencia de una coincidencia es contar una vez en lugar de dos.',

    'Removal Reason':
        'Motivo del retiro',

    'Remove From List':
        'Retirar de la lista',

    'Removed':
        'Retirada',

    'Removed By':
        'Retirada por',

    'Removed from the watch list by %s.':
        '%s retiró esta entrada de la lista de vigilancia.',

    'Repeated incidents':
        'Incidentes repetidos',

    'Rescued means this visit produced a ticket after the alert. It is the figure the monthly value report is built on.':
        '«Rescatada» significa que esta visita sí produjo un ticket después del aviso. Es la cifra sobre la que se construye el informe mensual de valor.',

    "Rescued walk-outs times the store's own average sale. An estimate, labelled as one everywhere it appears: a rescued sale is one where an alert fired and that visit later produced a ticket — correlation, honestly stated, not proof.":
        'Fugas rescatadas por la venta promedio de la propia tienda. Una estimación, etiquetada como tal en todos lados: una venta rescatada es aquella en la que se disparó un aviso y esa visita después produjo un ticket; correlación, dicha con honestidad, no prueba.',

    "Resolved at the moment the rule fires. 'Where it happened' is the usual answer — a bundle offer belongs on the screen the group is standing near, not on the one by the door.":
        'Se resuelve en el momento en que la regla dispara. «Donde pasó» es la respuesta habitual: una oferta de paquete va en la pantalla junto a la que está el grupo, no en la de la puerta.',

    'Responsible User':
        'Usuario responsable',

    'Review Every (days)':
        'Revisar cada (días)',

    'Review On':
        'Revisar el',

    'Review watch-list entry %s':
        'Revisar la entrada %s de la lista de vigilancia',

    'Reviewed and extended by %(user)s to %(date)s.':
        '%(user)s la revisó y la prorrogó hasta %(date)s.',

    'Reviewed — Extend':
        'Revisada — Prorrogar',

    'SMS Delivery error':
        'Error de entrega del SMS',

    'Security':
        'Seguridad',

    'Security / Compliance':
        'Seguridad / Cumplimiento',

    'Send the discreet alert when the threshold above is passed. Turn it off in a fitting room or a waiting area, where lingering is the point rather than a problem.':
        'Manda el aviso discreto cuando se pasa el umbral de arriba. Apágalo en un probador o en una sala de espera, donde demorarse es el punto y no un problema.',

    'Set only for a recognised, identified customer. Most alerts carry no identity at all.':
        'Se llena solo con un cliente reconocido e identificado. La mayoría de los avisos no llevan identidad alguna.',

    'Set only when the customer handed over their details at the till and the store has customer identification switched on. Most signatures never get one and are deleted anonymous.':
        'Se llena solo cuando el cliente entregó sus datos en la caja y la tienda tiene activada la identificación de clientes. La mayoría de las firmas nunca reciben uno y se borran anónimas.',

    'Set when this check-in came from a store camera rather than from a person. Only these are ever closed automatically.':
        'Se marca cuando esta entrada vino de una cámara de la tienda y no de una persona. Solo estas se cierran automáticamente.',

    'Severity':
        'Gravedad',

    "Share of the day's visits made by somebody the store had seen before, within its own retention window. A short window makes this number smaller — it measures what the store chose to remember, not everything that happened.":
        'Proporción de las visitas del día hechas por alguien que la tienda ya había visto, dentro de su propia ventana de retención. Una ventana corta hace este número más chico: mide lo que la tienda eligió recordar, no todo lo que pasó.',

    "Shorter than the zone's engagement threshold: someone pausing at a showcase for eight seconds has looked at it, even if they were only passing through the zone.":
        'Más corto que el umbral de interés de la zona: quien se detiene ocho segundos frente a una vitrina la miró, aunque solo estuviera cruzando la zona.',

    'Shown when no layout is set. Placeholders: {customer}, {store}, {zone}. Remember the customer reads this.':
        'Se muestra cuando no hay layout. Marcadores: {customer}, {store}, {zone}. Recuerda que esto lo lee el cliente.',

    'Similarity behind a face match. Kept so a store seeing odd attributions can re-tune its threshold against real numbers.':
        'Similitud detrás de una coincidencia facial. Se guarda para que una tienda con atribuciones raras pueda reajustar su umbral con números reales.',

    'Somebody stepping out for a moment should not close and reopen their working day.':
        'Que alguien salga un momento no debería cerrarle y reabrirle la jornada.',

    'Someone has been at %(zone)s for %(mins)s minutes and nobody has been over. Worth a look.':
        'Alguien lleva %(mins)s minutos en %(zone)s y nadie se ha acercado. Conviene ir.',

    'Someone lingering this long is looking, not walking past. Below it the dwell is recorded but not treated as interest — a corridor zone would otherwise report everyone who crosses it as engaged.':
        'Quien se demora este tiempo está mirando, no pasando de largo. Por debajo, la permanencia se registra pero no se toma como interés: si no, una zona de pasillo reportaría como interesado a todo el que la cruza.',

    'Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.':
        'Estado según las actividades\\nVencida: la fecha límite ya pasó\\nHoy: la actividad es para hoy\\nPlanificada: actividades futuras.',

    'Stricter than the door threshold: attributing a ticket to the wrong visit corrupts the conversion analysis rather than merely splitting a visit in two.':
        'Más estricto que el umbral de puerta: atribuir un ticket a la visita equivocada corrompe el análisis de conversión, no solo parte una visita en dos.',

    'Subscription paused. Data capture is unaffected — use the capture switch if it should stop too.':
        'Suscripción en pausa. La captura de datos no se toca: usa el interruptor de captura si también debe parar.',

    'Tell the salesperson when a customer they know walks in, with their name and last purchase, so they can greet them properly.':
        'Avísale al vendedor cuando entra un cliente que ya conoce, con su nombre y su última compra, para que pueda saludarlo como corresponde.',

    'That is the right state for most shops. Entries are added by\\n                hand after a documented incident, never automatically, and each\\n                one has to be confirmed by a second authorised person before it\\n                recognises anybody.':
        'Ese es el estado correcto para casi todas las tiendas. Las entradas se dan\\n                de alta a mano tras un incidente documentado, nunca automáticamente, y\\n                cada una tiene que ser confirmada por una segunda persona autorizada\\n                antes de reconocer a nadie.',

    'That watch-list reference already exists.':
        'Esa referencia de lista de vigilancia ya existe.',

    "The anonymous handle this visit was matched to. It expires on the store's retention schedule; the visit itself survives, without any way back to a face.":
        'El identificador anónimo con el que se emparejó esta visita. Vence según el calendario de retención de la tienda; la visita sobrevive, sin ninguna forma de volver a una cara.',

    "The entrance this visit began at. Kept even after the person has moved on, because 'which door brings the customers who buy' is a question the owner will eventually ask.":
        'La entrada por la que empezó esta visita. Se conserva aun después de que la persona siguió su camino, porque «qué puerta trae a los clientes que compran» es una pregunta que el dueño acabará haciendo.',

    'The face vector, encrypted at rest. A list of numbers from which no image can be reconstructed.':
        'El vector facial, cifrado en reposo. Una lista de números a partir de la cual no se puede reconstruir ninguna imagen.',

    "The model's estimate of presented appearance. It is not a statement about anyone's identity, and 'unknown' is a legitimate and common answer rather than a failure.":
        'La estimación del modelo sobre la apariencia presentada. No es una afirmación sobre la identidad de nadie, y «desconocido» es una respuesta legítima y frecuente, no una falla.',

    'The only people told about a match. Named one by one on purpose: a match is not commercial information and does not follow the ordinary zone rota to whoever happens to be on the floor.':
        'Las únicas personas a las que se les avisa de una coincidencia. Nombradas una por una a propósito: una coincidencia no es información comercial y no sigue el rol de turnos de zona hacia quien ande en el piso.',

    'The person who added an entry cannot confirm it. A second authorised person has to agree — that is what makes this a control rather than a formality.':
        'Quien dio de alta una entrada no puede confirmarla. Tiene que estar de acuerdo una segunda persona autorizada: eso es lo que hace de esto un control y no un trámite.',

    "The pseudonymous visit. It expires with its signature; nothing here outlives the shop's retention window.":
        'La visita seudónima. Vence junto con su firma; nada de aquí sobrevive a la ventana de retención de la tienda.',

    'The recurring sale order that bills this store. On Odoo Enterprise this is a subscription with a recurring plan; on Community it is an ordinary order and the recurrence is handled however the customer already handles it.':
        'El pedido recurrente que factura esta tienda. En Odoo Enterprise es una suscripción con plan recurrente; en Community es un pedido normal y la recurrencia se maneja como el cliente ya la maneje.',

    'The single door this unit was formed at. People arriving at two different entrances are never one unit, however close in time — they did not arrive together.':
        'La única puerta en la que se formó esta unidad. Dos personas que llegan por entradas distintas nunca son una unidad, por cerca que sea en el tiempo: no llegaron juntas.',

    "The store's average ticket at the time. An estimate, and labelled as one: the real value of a sale that never happened cannot be known, and quoting it to the cent would be dishonest.":
        'El ticket promedio de la tienda en ese momento. Una estimación, y etiquetada como tal: el valor real de una venta que nunca ocurrió no se puede saber, y darlo al centavo sería deshonesto.',

    'The trial for <b>%(store)s</b> ended on %(date)s. Nothing has been switched off — decide with the customer whether to activate, extend or close it.':
        'La prueba de <b>%(store)s</b> terminó el %(date)s. No se ha apagado nada: decide con el cliente si activar, extender o cerrar.',

    "The unit the ticket belongs to. A family's spend is the family's, not the individual's who happened to hold the card.":
        'La unidad a la que pertenece el ticket. El gasto de una familia es de la familia, no de quien traía la tarjeta.',

    'The visit this crossing belongs to. Empty until the asynchronous resolution job has run, or permanently when the edge sent no face — a counted crossing never depends on a face being readable.':
        'La visita a la que pertenece este cruce. Vacío hasta que corra el trabajo de resolución asíncrona, o para siempre cuando el edge no mandó cara: un cruce contado nunca depende de que una cara sea legible.',

    'The watch-list threshold cannot be looser than ordinary re-identification. Naming a person has to be harder than counting one, not easier.':
        'El umbral de la lista de vigilancia no puede ser más laxo que la reidentificación normal. Señalar a una persona tiene que ser más difícil que contarla, no más fácil.',

    'The watch-list threshold is a cosine similarity: it must sit strictly between 0 and 1.':
        'El umbral de la lista de vigilancia es una similitud coseno: tiene que estar estrictamente entre 0 y 1.',

    'They are not alone — greet them in person rather than letting the screen name them.':
        'No viene sola: salúdala en persona en vez de dejar que la pantalla diga su nombre.',

    'This Was The Wrong Person':
        'Era la persona equivocada',

    'This entry has no face signature, so it could never match anything. Enrol it from the edge tool first.':
        'Esta entrada no tiene firma facial, así que no podría coincidir con nada. Regístrala primero desde la herramienta edge.',

    'This entry is due for review. Does it still belong on the list? Extending is a decision — the default is to let it lapse.':
        'Toca revisar esta entrada. ¿Sigue teniendo razón de estar en la lista? Prorrogarla es una decisión; lo normal es dejarla vencer.',

    'This entry will stop matching. It stays visible, because the record of why somebody was listed is part of the audit trail.':
        'Esta entrada dejará de coincidir. Sigue visible, porque el registro de por qué se listó a alguien es parte del rastro de auditoría.',

    "This entry would stay active beyond the store's maximum of %(days)s days. Somebody has to look at it again before then.":
        'Esta entrada quedaría vigente más allá del máximo de %(days)s días de la tienda. Alguien tiene que volver a mirarla antes de eso.',

    "This person's signature already existed when they walked in — they had been in recently. Within the retention window only; the long-horizon 'how often does this customer come back' question belongs to phase 4.":
        'La firma de esta persona ya existía cuando entró: había estado hace poco. Solo dentro de la ventana de retención; la pregunta de horizonte largo «cada cuánto vuelve este cliente» pertenece a la fase 4.',

    'This signature belongs to a customer the shop can name. It outlives the anonymous retention window — that is the point of it — but not forever: the store sets how long, and the same expiry job enforces it.':
        'Esta firma pertenece a un cliente al que la tienda puede nombrar. Sobrevive a la ventana anónima —de eso se trata— pero no para siempre: la tienda decide cuánto, y el mismo trabajo de vencimiento lo hace cumplir.',

    "Tie each ticket to the visit that produced it. Anonymous: it answers 'does the profile that stops at the window actually buy' without anybody's name. Falls back to the purchase unit when there is no till camera.":
        'Liga cada ticket con la visita que lo produjo. Anónimo: responde «¿el perfil que se para en el aparador de verdad compra?» sin el nombre de nadie. Cae en la unidad de compra cuando no hay cámara en caja.',

    'Treat people who cross the same door together as one buying decision. A store that counts a family of four as four visitors and one ticket reads a 25% conversion rate when the real figure was 100%.':
        'Trata a quienes cruzan juntos la misma puerta como una sola decisión de compra. Una tienda que cuenta a una familia de cuatro como cuatro visitantes y un ticket lee 25% de conversión cuando la cifra real era 100%.',

    'Turn crossings into visits by matching the same anonymous face. Without it a customer who steps out for a phone call and comes back counts as three visitors, and the conversion rate reads a third of the truth.':
        'Convierte cruces en visitas emparejando la misma cara anónima. Sin esto, un cliente que sale a contestar el teléfono y regresa cuenta como tres visitantes, y la tasa de conversión lee un tercio de la verdad.',

    'Turn employee crossings at the staff door into hr.attendance check-ins and check-outs. Off by default: a store that has not agreed this with its team should not start recording their hours because a camera was installed.':
        'Convierte los cruces de empleados en la puerta de personal en entradas y salidas de hr.attendance. Apagado por omisión: una tienda que no lo acordó con su equipo no debería empezar a registrar sus horas porque se instaló una cámara.',

    'Type of the exception activity on record.':
        'Tipo de la actividad de excepción del registro.',

    'Use A Watch List':
        'Usar lista de vigilancia',

    'Watch List':
        'Lista de vigilancia',

    'Watch Person Count':
        'Número de personas en la lista',

    'Watch-list Entry':
        'Entrada de la lista de vigilancia',

    'Watch-list Liveness':
        'Vitalidad para la lista de vigilancia',

    'Watch-list Matches':
        'Coincidencias de la lista de vigilancia',

    'Watch-list Recipients':
        'Quién recibe el aviso',

    'Watch-list Threshold':
        'Umbral de la lista de vigilancia',

    'Watch-list entry %s created (awaiting confirmation)':
        'Entrada %s de la lista de vigilancia creada (pendiente de confirmación)',

    'Watch-list match on %(ref)s at %(score).2f':
        'Coincidencia de lista de vigilancia en %(ref)s con %(score).2f',

    'We spotted %(detected)s people who were about to leave without being served. Your team got to %(rescued)s of them, and those visits ended in a sale.':
        'Detectamos %(detected)s personas que estaban por irse sin que nadie las atendiera. Tu equipo alcanzó a %(rescued)s de ellas, y esas visitas terminaron en venta.',

    'Website Messages':
        'Mensajes del sitio web',

    'Website communication history':
        'Historial de comunicación del sitio web',

    'What happened, factually and dated. Somebody will read this in a year to decide whether the entry still belongs here.':
        'Qué pasó, con hechos y con fecha. Alguien leerá esto dentro de un año para decidir si la entrada sigue teniendo razón de estar aquí.',

    'What happened, factually and dated. This is the record somebody will read in a year when deciding whether the entry still belongs here.':
        'Qué pasó, con hechos y con fecha. Este es el registro que alguien leerá dentro de un año al decidir si la entrada sigue teniendo razón de estar aquí.',

    'What is physically on this display. Only the shop knows, so it is configuration — and without it the attention figures cannot be compared against sales, which is where the insight lives.':
        'Qué hay físicamente en este exhibidor. Solo la tienda lo sabe, así que es configuración; y sin esto las cifras de atención no se pueden comparar contra ventas, que es donde vive el hallazgo.',

    'What the salesperson actually reads, on a phone, mid-shift. Short enough to take in at a glance and act on without opening it.':
        'Lo que el vendedor realmente lee, en el teléfono, a media jornada. Suficientemente corto para captarlo de un vistazo y actuar sin abrirlo.',

    "What the staff call it: 'Window Showcase', 'Solitaire Case', 'New Arrivals Table'.":
        'Como le dice el personal: «Aparador», «Vitrina de solitarios», «Mesa de novedades».',

    "What the staff of this store call it: 'Engagement Rings', 'Fitting Rooms', 'Checkout'.":
        'Como le dice el personal de esta tienda: «Anillos de compromiso», «Probadores», «Caja».',

    "What this store has contracted. It governs which features their users can see and switch on — it is not a licence check in the code, so a billing problem can never switch a customer's cameras off.":
        'Qué contrató esta tienda. Gobierna qué funciones pueden ver y encender sus usuarios: no es una verificación de licencia en el código, así que un problema de cobranza jamás puede apagarle las cámaras a un cliente.',

    'When somebody should look at this again and decide whether it still belongs on the list.':
        'Cuándo alguien debe volver a mirarla y decidir si todavía tiene razón de estar en la lista.',

    "When this signature is deleted. Set from the store's retention window on every sighting, so an active visitor's handle lives as long as their visit and not a minute longer.":
        'Cuándo se borra esta firma. Se fija desde la ventana de retención de la tienda en cada avistamiento, para que el identificador de un visitante activo viva lo que dura su visita y ni un minuto más.',

    'Where':
        'Dónde',

    'Where an alert goes when nobody is rostered on that zone. Without one, alerts for uncovered zones are recorded but never reach a person.':
        'A dónde va un aviso cuando nadie está de turno en esa zona. Sin él, los avisos de zonas sin cubrir se registran pero nunca llegan a una persona.',

    'Which entrance counts for attendance. Leave empty to accept any door — right for a small shop with one way in.':
        'Qué entrada cuenta para asistencia. Déjalo vacío para aceptar cualquier puerta: lo correcto en una tienda con una sola entrada.',

    'Which entrances this person has used. With one door it is always the same door; with several it is the raw material for the cross-door re-identification the multi-entrance stores buy this for.':
        'Qué entradas ha usado esta persona. Con una sola puerta siempre es la misma; con varias es la materia prima de la reidentificación entre puertas por la que las tiendas de varias entradas compran esto.',

    'Which face model produced the pending vector. Vectors from different models are never compared.':
        'Qué modelo facial produjo el vector pendiente. Nunca se comparan vectores de modelos distintos.',

    'Which internal zone this camera watches. Set for zone and checkout cameras; left empty for a door counter, which reports against its door instead.':
        'Qué zona interior vigila esta cámara. Se llena en cámaras de zona y de caja; se deja vacío en un contador de puerta, que reporta contra su puerta.',

    "Which measured event fires this rule. These are the scenarios the product ships with; the conditions below are what make each one this store's own.":
        'Qué evento medido dispara esta regla. Estos son los escenarios que el producto trae de fábrica; las condiciones de abajo son lo que hace que cada uno sea el de esta tienda.',

    'Who Is Told About A Match':
        'Quién se entera de una coincidencia',

    'Who receives the monthly value report. The owner, usually — it is written for somebody who does not open dashboards.':
        'Quién recibe el informe mensual de valor. El dueño, normalmente: está escrito para alguien que no abre tableros.',

    'Why':
        'Por qué',

    'Worth a look near the entrance':
        'Conviene mirar hacia la entrada',

    'Worth a second look':
        'Merece una segunda mirada',

    'Wrong person':
        'Persona equivocada',

    'device_id':
        'device_id',

    'door_id':
        'door_id',

    'sent_discuss':
        'sent_discuss',

    'sent_screen':
        'sent_screen',

    'sent_sound':
        'sent_sound',

    'sent_whatsapp':
        'sent_whatsapp',

    'store_id':
        'store_id',

}
