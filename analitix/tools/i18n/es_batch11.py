# -*- coding: utf-8 -*-
"""Eleventh batch: the customer-facing plan names and the
sustained-expression nudge.
"""
BATCH11 = {
    '<strong>The only signal here that judges a mood\\n                                rather than a fact.</strong> A lost sale rests on\\n                                things anybody can check — they waited, nobody\\n                                came, they did not buy. This rests on a face, read\\n                                by a model that is wrong often. The nudge is\\n                                worded as «go over and ask», never as «this\\n                                customer is angry», and it says so to the\\n                                salesperson. Needs the front-facing cameras.':
        '<strong>La única señal de aquí que juzga un ánimo\\n                                en vez de un hecho.</strong> Una venta perdida se apoya en\\n                                cosas que cualquiera puede verificar: se demoró, nadie\\n                                se acercó, no compró. Esta se apoya en una cara, leída\\n                                por un modelo que se equivoca seguido. El aviso está\\n                                redactado como «acércate y pregunta», nunca como «este\\n                                cliente está enojado», y así se lo dice al\\n                                vendedor. Necesita las cámaras frontales.',

    'Complete':
        'Completo',

    "Consecutive readings above the store's confidence floor that came back sad, angry or fearful. Resets to zero the moment one does not — which is the whole point: a person who frowns once and then does not is not unhappy, they were reading a price tag.":
        'Lecturas por encima del mínimo de confianza de la tienda que salieron tristes, enojadas o con miedo, una tras otra. Se reinicia a cero en cuanto una no lo está — que es justamente el punto: alguien que frunce el ceño una vez y luego no, no está incómodo, estaba leyendo una etiqueta de precio.',

    'Deliberately higher than the general demographic floor. A wrong age band skews a chart; a wrong reading here sends somebody to manage a mood the customer never had.':
        'A propósito más alto que el mínimo general de demografía. Un rango de edad equivocado ensucia una gráfica; una lectura equivocada aquí manda a alguien a atender un estado de ánimo que el cliente nunca tuvo.',

    'Expression Confidence Floor':
        'Confianza mínima de expresión',

    'Expression Nudge':
        'Aviso de expresión',

    'How many consecutive negative readings, in the same zone and the same visit, before anybody is told. One frame is a person blinking; three in a row while they stand at a counter is worth somebody walking over.':
        'Cuántas lecturas negativas seguidas, en la misma zona y la misma visita, antes de avisarle a alguien. Un solo cuadro es una persona parpadeando; tres seguidas mientras está parada en un mostrador sí ameritan que alguien se acerque.',

    'Last Expression':
        'Última expresión',

    'Momentary expression at the moment of the reading. A single frame means nothing on its own, and nothing acts on this one: a face is read at the door, once. What can raise a nudge is a negative reading that *persists* while somebody stands in a zone, which arrives on the dwell report and is measured there.':
        'Expresión momentánea al instante de la lectura. Un solo cuadro no significa nada por sí mismo, y sobre este no actúa nada: la cara se lee en la puerta, una vez. Lo que sí puede levantar un aviso es una lectura negativa que *persiste* mientras alguien está parado en una zona, que llega en el reporte de permanencia y se mide ahí.',

    'Negative In A Row':
        'Negativas seguidas',

    'Nudge On Sustained Unhappiness':
        'Avisar por incomodidad sostenida',

    'Raised at most once per visit and zone. Somebody who is having a bad afternoon should not generate a nudge every thirty seconds.':
        'Se levanta a lo sumo una vez por visita y zona. A alguien que está teniendo una mala tarde no hay que zumbarle el teléfono al vendedor cada treinta segundos.',

    'Readings Before Nudging':
        'Lecturas antes de avisar',

    'Service':
        'Atención',

    'Somebody has been at %(zone)s for %(mins)s minutes and has not looked comfortable while they waited.\\n\\nThis is a reading of a face, not a fact — the camera is wrong about this often enough that it is worth saying so. Treat it the way you would treat any customer who looks like they are waiting: go over and ask.':
        'Alguien lleva %(mins)s minutos en %(zone)s y no se ha visto cómodo mientras esperaba.\\n\\nEsto es la lectura de una cara, no un hecho: la cámara se equivoca en esto lo bastante seguido como para que valga la pena decirlo. Trátalo como tratarías a cualquier cliente que se ve esperando: acércate y pregunta.',

    'Someone at %s may want a hand':
        'Alguien en %s podría necesitar una mano',

    'Sustained unhappiness':
        'Incomodidad sostenida',

    "Tell the salesperson covering a zone when somebody standing there has looked unhappy for several readings in a row. Off by default: it is the most easily misused signal in the product, because it judges a person's mood rather than an observable fact. Needs the front-facing cameras and demographics.":
        'Avísale al vendedor que cubre una zona cuando alguien parado ahí lleva varias lecturas seguidas viéndose incómodo. Apagado por omisión: es la señal más fácil de usar mal de todo el producto, porque juzga el ánimo de una persona en vez de un hecho observable. Necesita las cámaras frontales y demografía.',

    "The most recent expression the edge reported for this person while they stood here. Kept as the latest reading only: a history of somebody's face is not something this product needs in order to say 'go over'.":
        'La expresión más reciente que reportó el edge mientras esta persona estuvo aquí. Se guarda solo la última: un historial de la cara de alguien no es algo que este producto necesite para decir «acércate».',

}
