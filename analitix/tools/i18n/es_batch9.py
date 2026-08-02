# -*- coding: utf-8 -*-
"""Ninth batch: phase 7 — chains, regions, the console and the
elevated scope decisions.

Keys reproduce the .pot msgid byte for byte; make_es_po.py reports any
that miss, because Odoo drops a mismatch without a word.
"""
BATCH9 = {
    '%(user)s changed the %(what)s scope from <b>%(old)s</b> to <b>%(new)s</b> for the whole chain.':
        '%(user)s cambió el alcance de %(what)s de <b>%(old)s</b> a <b>%(new)s</b> para toda la cadena.',

    "<strong>These two settings decide the reach of a\\n                        person's data across your branches</strong>, so only the\\n                        corporate role can change them and every change is\\n                        written to the audit log. A store or regional manager\\n                        cannot move them, by design.":
        '<strong>Estas dos opciones deciden el alcance de los\\n                        datos de una persona entre tus sucursales</strong>, así que solo el\\n                        rol corporativo puede cambiarlas y cada cambio queda\\n                        escrito en la bitácora de auditoría. Un gerente de tienda o regional\\n                        no puede moverlas, por diseño.',

    'A single-store customer never needs one. Create a chain when\\n                there are branches to group, compare and report on together.':
        'Un cliente de una sola tienda nunca necesita una. Crea una cadena cuando\\n                haya sucursales que agrupar, comparar y reportar juntas.',

    'Across the whole chain':
        'En toda la cadena',

    'Analitix Chain':
        'Cadena de Analitix',

    'Analitix Chain Console':
        'Consola de cadena de Analitix',

    'Analitix Daily Store Rollup':
        'Resumen diario por tienda de Analitix',

    'Analitix Region':
        'Región de Analitix',

    'Analitix Regions':
        'Regiones de Analitix',

    'Analitix Scope Restricted':
        'Alcance de Analitix restringido',

    "Analitix: close yesterday's figures per store":
        'Analitix: cerrar las cifras de ayer por tienda',

    'Average':
        'Promedio',

    'Average Ticket':
        'Ticket promedio',

    'Behind Their Region':
        'Por debajo de su región',

    'Chain':
        'Cadena',

    'Chain %(brand)s: %(what)s scope changed from %(old)s to %(new)s':
        'Cadena %(brand)s: el alcance de %(what)s pasó de %(old)s a %(new)s',

    'Chain Console':
        'Consola de cadena',

    'Chain name':
        'Nombre de la cadena',

    "Chain-wide recognition is <strong>on</strong>. A customer\\n                        identified in one branch is now recognised in all of\\n                        them, which builds a picture of one person's movements\\n                        between your properties. Make sure that is what your\\n                        privacy notice tells them.":
        'El reconocimiento en toda la cadena está <strong>encendido</strong>. Un cliente\\n                        identificado en una sucursal ahora se reconoce en todas\\n                        ellas, lo que arma un retrato de los movimientos de una persona\\n                        entre tus locales. Asegúrate de que eso es lo que dice tu\\n                        aviso de privacidad.',

    'Chains':
        'Cadenas',

    'Compare the stores of their regions side by side. No store configuration.':
        'Comparar las tiendas de sus regiones entre sí. Sin configuración de tienda.',

    'Conv. %':
        'Conv. %',

    'Converting more than two points below the average of their own region on the same day — the branches worth a visit.':
        'Convierten más de dos puntos por debajo del promedio de su propia región el mismo día: las sucursales que ameritan una visita.',

    'Corporate / Head Office':
        'Corporativo / Dirección',

    'Daily Rollup':
        'Resumen diario',

    'Each store on its own':
        'Cada tienda por su cuenta',

    'Effective Scope':
        'Alcance efectivo',

    'Effective Store Scope':
        'Alcance efectivo de tiendas',

    'For a chain, give a <b>region</b> rather than a list of\\n                            stores: it already includes the branches that open next\\n                            year. A hand-written list of twenty stores is one nobody\\n                            remembers to extend, and stale access outlives the person\\n                            it was written for. <b>Effective scope</b> shows what the\\n                            two settings actually resolve to.':
        'En una cadena, da una <b>región</b> en vez de una lista de\\n                            tiendas: ya incluye las sucursales que abran el año que\\n                            viene. Una lista de veinte tiendas escrita a mano es una que nadie\\n                            se acuerda de extender, y el acceso viejo sobrevive a la persona\\n                            para la que se escribió. <b>Alcance efectivo</b> muestra a qué\\n                            resuelven de verdad las dos opciones.',

    'How far recognition reaches':
        'Hasta dónde llega el reconocimiento',

    "Informational. What actually grants access is the region on the user's own Analitix scope — a name in this field alone opens nothing, on purpose.":
        'Informativo. Lo que de verdad da acceso es la región en el alcance de Analitix de esa persona: un nombre en este campo, por sí solo, no abre nada. A propósito.',

    'Last 90 Days':
        'Últimos 90 días',

    "Naming a manager here documents who is responsible; it\\n                        grants nothing on its own. Access comes from the region\\n                        on that person's own Analitix scope, so the two can be\\n                        audited separately.":
        'Nombrar aquí a un responsable documenta quién responde; por sí solo\\n                        no otorga nada. El acceso viene de la región en el\\n                        alcance de Analitix de esa persona, para que las dos cosas\\n                        se puedan auditar por separado.',

    'No chains yet.':
        'Todavía no hay cadenas.',

    'No rollups yet.':
        'Todavía no hay resúmenes.',

    'Nothing rolled up yet.':
        'Todavía no hay nada resumido.',

    'Of the walk-outs spotted, how many the team reached in time. The figure that separates a store with a traffic problem from one with a floor problem.':
        'De las fugas detectadas, a cuántas alcanzó a llegar el equipo. La cifra que separa a una tienda con problema de tráfico de una con problema de piso.',

    'One row per store per day, written by the nightly job. This is\\n                what every long-horizon report reads, so that crossing events\\n                can be pruned without losing a figure anybody looks at.':
        'Un renglón por tienda y por día, escrito por el trabajo nocturno. Esto es\\n                lo que leen todos los reportes de horizonte largo, para que los\\n                eventos de cruce se puedan podar sin perder ninguna cifra que alguien mire.',

    "Only the corporate role can change how far recognition reaches across a chain. This decides whether one person's movements are correlated between your branches, which is not a store or regional setting.":
        'Solo el rol corporativo puede cambiar hasta dónde llega el reconocimiento en una cadena. Esto decide si los movimientos de una persona se correlacionan entre tus sucursales, y eso no es una configuración de tienda ni de región.',

    'Optional. A single-store customer leaves this empty and nothing about their installation changes.':
        'Opcional. Un cliente de una sola tienda lo deja vacío y nada de su instalación cambia.',

    'Recognition Scope':
        'Alcance del reconocimiento',

    'Region':
        'Región',

    'Region Count':
        'Número de regiones',

    'Regional Manager':
        'Gerente regional',

    'Regions':
        'Regiones',

    'Scope Last Changed':
        'Alcance cambiado el',

    'Scope Last Changed By':
        'Alcance cambiado por',

    'Scope this user to whole regions. Every store in them is included, including the ones that open next year — which is the point: a list of individual stores goes stale the first time the chain grows and nobody updates it.':
        'Limita a este usuario a regiones completas. Se incluyen todas sus tiendas, también las que abran el año que viene, que es justo el punto: una lista de tiendas sueltas se queda vieja la primera vez que la cadena crece y nadie la actualiza.',

    'Set directly, or filled in from the region. A store belongs to at most one chain.':
        'Se captura directo, o se llena desde la región. Una tienda pertenece a lo sumo a una cadena.',

    'Shared across the chain':
        'Compartida en toda la cadena',

    'Shared by default, and for a reason: if somebody caused an incident at one branch it is reasonable that the others know. It is still a chain-wide statement about a named person, so changing this either way takes the corporate role and is audited.':
        'Compartida por omisión, y por una razón: si alguien provocó un incidente en una sucursal, es razonable que las demás lo sepan. Aun así es una afirmación de alcance de cadena sobre una persona con nombre, así que cambiarla en cualquier sentido exige el rol corporativo y queda auditado.',

    "Store '%(store)s' is in region '%(region)s', which belongs to chain '%(their)s', but the store is assigned to chain '%(ours)s'.":
        'La tienda «%(store)s» está en la región «%(region)s», que pertenece a la cadena «%(their)s», pero la tienda está asignada a la cadena «%(ours)s».',

    'Store Count':
        'Número de tiendas',

    'That chain reference already exists in this company.':
        'Esa referencia de cadena ya existe en esta compañía.',

    'That region reference already exists in this chain.':
        'Esa referencia de región ya existe en esta cadena.',

    'The console reads the nightly daily rollup rather than raw\\n                crossing events, so it keeps working after old events are\\n                pruned. A brand-new installation fills in after the first night.':
        'La consola lee el resumen diario nocturno y no los eventos de cruce\\n                crudos, así que sigue funcionando después de podar los eventos\\n                viejos. Una instalación nueva se llena tras la primera noche.',

    'The only fair way to compare a 60 m² kiosk against a 400 m² flagship. Ranking branches by revenue alone just ranks them by size, which head office already knows.':
        'La única forma justa de comparar un kiosco de 60 m² contra una tienda insignia de 400 m². Ordenar sucursales por ingreso solo las ordena por tamaño, que es algo que dirección ya sabe.',

    "The store this entry was raised at. On a single store, matching happens here and nowhere else. In a chain, the chain's own watch-list scope decides whether the other branches see it — shared by default, because an incident at one branch is worth the others knowing, and changeable only by the corporate role.":
        'La tienda donde se levantó esta entrada. En una sola tienda, la comparación ocurre aquí y en ningún otro lado. En una cadena, el alcance de lista de vigilancia de la propia cadena decide si las demás sucursales la ven: compartida por omisión, porque un incidente en una sucursal amerita que las otras lo sepan, y modificable solo por el rol corporativo.',

    'The stores this user can actually reach: the ones assigned directly plus every store of their regions. The record rules read this one field, so the two ways of granting access can never disagree with each other.':
        'Las tiendas que este usuario puede alcanzar de verdad: las asignadas directamente más todas las de sus regiones. Las reglas de registro leen este único campo, así que las dos formas de dar acceso nunca pueden contradecirse.',

    'The whole chain: cross-branch comparison, chain configuration, and the elevated decisions about how far recognition reaches.':
        'Toda la cadena: comparación entre sucursales, configuración de la cadena y las decisiones elevadas sobre hasta dónde llega el reconocimiento.',

    'There is already a rollup for that store and day.':
        'Ya existe un resumen para esa tienda y ese día.',

    "This store's conversion minus its region's average for the same day. The number a regional manager actually acts on: it removes the week, the weather and the season, which move every branch together, and leaves what is particular to this one.":
        'La conversión de esta tienda menos el promedio de su región el mismo día. El número sobre el que un gerente regional de verdad actúa: quita la semana, el clima y la temporada, que mueven a todas las sucursales por igual, y deja lo que es propio de esta.',

    'True when this user has been given specific stores or regions, and is therefore locked to them.':
        'Verdadero cuando a este usuario se le dieron tiendas o regiones concretas, y por lo tanto queda limitado a ellas.',

    'Units / Ticket':
        'Piezas / ticket',

    'Walk-outs Not Rescued':
        'Fugas no rescatadas',

    'Watch-list Scope':
        'Alcance de la lista de vigilancia',

    "Whether a recognised customer is correlated across branches.\\n'Each store on its own' is the default and the smaller claim: a person seen in one branch is not linked to their visit to another.\\n'Across the whole chain' builds a picture of one individual's movements between your properties. It is a categorically larger thing than store-level recognition, so only the corporate role can switch it and the change is recorded in the audit log.":
        'Si un cliente reconocido se correlaciona o no entre sucursales.\\n«Cada tienda por su cuenta» es lo que viene de fábrica y es la afirmación más chica: a una persona vista en una sucursal no se le liga su visita a otra.\\n«En toda la cadena» arma un retrato de los movimientos de un individuo entre tus locales. Es algo categóricamente más grande que el reconocimiento por tienda, así que solo el rol corporativo puede activarlo y el cambio queda registrado en la bitácora de auditoría.',

    'brand_id':
        'brand_id',

    'e.g. Bajío':
        'p. ej. Bajío',

    'face recognition':
        'reconocimiento facial',

    'watch list':
        'lista de vigilancia',

    'watchlist_scope':
        'watchlist_scope',

    'Δ vs Region':
        'Δ vs región',

}
