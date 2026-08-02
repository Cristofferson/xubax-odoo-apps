# -*- coding: utf-8 -*-
"""Build analitix/i18n/es.po from the exported .pot.

One es.po covers es, es_419 and es_MX by Odoo's language cascade, so the
Spanish-speaking customers this product targets get a translated UI without
three near-identical files drifting apart.

Only entries whose msgid appears in the .pot are written — an entry that does
not match exactly is ignored in silence by Odoo, which is the worst possible
failure mode for a translation.
"""
import re
import sys

# Import the batches from this script's own directory, not from wherever it
# happens to be invoked: a stale copy elsewhere on sys.path would silently
# win and translate against msgids that no longer exist.
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from es_batch2 import BATCH2
from es_batch3 import BATCH3
from es_batch4 import BATCH4, BATCH4_LOOSE
from es_batch5 import BATCH5, BATCH5_LOOSE
from es_batch6 import BATCH6, BATCH6_LOOSE
from es_batch7 import BATCH7, BATCH7_LOOSE
from es_batch8 import BATCH8
from es_batch9 import BATCH9
from es_batch10 import BATCH10

TRANSLATIONS = {
    # ---- module, models, menus -------------------------------------
    "Analitix": "Analitix",
    "Analitix Audit Log": "Bitácora de auditoría de Analitix",
    "Analitix Background Job": "Trabajo en segundo plano de Analitix",
    "Analitix Crossing Event": "Evento de cruce de Analitix",
    "Analitix Edge Device": "Dispositivo edge de Analitix",
    "Analitix Staff Face Signature": "Firma facial de empleado de Analitix",
    "Analitix Store": "Tienda de Analitix",
    "Analitix Store Door": "Puerta de tienda de Analitix",
    "Analitix Stores": "Tiendas de Analitix",
    "Analitix — Embedding Encryption Service":
        "Analitix — Servicio de cifrado de firmas",
    "Analitix — Hourly Door Traffic": "Analitix — Tráfico por puerta y hora",
    "Analitix — Hourly Store Conversion": "Analitix — Conversión por tienda y hora",
    "Analitix — New Store Setup": "Analitix — Alta de tienda nueva",
    "Analitix — New Store Setup Door": "Analitix — Puerta del alta de tienda",
    "Analitix — Read-Audited Model": "Analitix — Modelo con lectura auditada",
    "Analysis": "Análisis",
    "Operations": "Operación",
    "Configuration": "Configuración",
    "Conversion": "Conversión",
    "Door Traffic": "Tráfico por puerta",
    "Stores": "Tiendas",
    "Doors": "Puertas",
    "Devices": "Dispositivos",
    "Device Health": "Salud de dispositivos",
    "Crossing Events": "Eventos de cruce",
    "Background Jobs": "Trabajos en segundo plano",
    "Background Job": "Trabajo en segundo plano",
    "Audit Log": "Bitácora de auditoría",
    "Staff Signatures": "Firmas de empleados",
    "Staff Signature": "Firma de empleado",
    "New Store Setup": "Alta de tienda nueva",

    # ---- crons -----------------------------------------------------
    "Analitix: apply event retention policy":
        "Analitix: aplicar la política de retención de eventos",
    "Analitix: check device health": "Analitix: revisar la salud de los dispositivos",
    "Analitix: clean finished jobs": "Analitix: limpiar trabajos terminados",
    "Analitix: critical device offline": "Analitix: dispositivo crítico fuera de línea",
    "Analitix: refresh ingest baselines and flag anomalies":
        "Analitix: recalcular líneas base de ingesta y marcar anomalías",
    "Analitix: run background jobs": "Analitix: ejecutar trabajos en segundo plano",

    # ---- groups ----------------------------------------------------
    "Manager": "Gerente",
    "Technician / Implementer": "Técnico / Implementador",
    "See this store's traffic and conversion dashboards.":
        "Ver los tableros de tráfico y conversión de esta tienda.",
    "Device health, ingest diagnostics and the job queue, without access to sales figures.":
        "Salud de dispositivos, diagnóstico de ingesta y cola de trabajos, sin acceso "
        "a las cifras de venta.",

    # ---- store -----------------------------------------------------
    "Store": "Tienda",
    "Store Name": "Nombre de la tienda",
    "Reference": "Referencia",
    "Company": "Compañía",
    "Timezone": "Zona horaria",
    "Total m²": "m² totales",
    "Sales-floor m²": "m² de piso de venta",
    "Store m²": "m² de la tienda",
    "Floor Area": "Superficie",
    "Match sales by": "Atribuir ventas por",
    "Specific POS registers": "Cajas de TPV específicas",
    "Whole company": "Toda la compañía",
    "POS Registers": "Cajas de TPV",
    "Register Count": "Número de cajas",
    "Sales Matching": "Atribución de ventas",
    "Notes": "Notas",
    "Occupancy": "Aforo",
    "Inside Now": "Dentro ahora",
    "Visitors In": "Visitantes que entraron",
    "Visitors Out": "Visitantes que salieron",
    "Visitors Today": "Visitantes hoy",
    "Visitors": "Visitantes",
    "Last Event": "Último evento",
    "Health": "Salud",
    "Healthy": "Sana",
    "Degraded": "Degradada",
    "Down": "Caída",
    "Paused": "Pausada",
    "Devices Offline": "Dispositivos fuera de línea",
    "Monitoring": "Monitoreo",
    "Thresholds": "Umbrales",
    "Who Gets Told": "A quién se avisa",
    "Technical Contacts": "Contactos técnicos",
    "Technical Owner": "Responsable técnico",
    "Heartbeat Interval (s)": "Intervalo de latido (s)",
    "Degraded After (min)": "Degradado tras (min)",
    "Offline After (min)": "Fuera de línea tras (min)",
    "Capture Enabled": "Captura activa",
    "Capture Paused": "Captura pausada",
    "Pause Reason": "Motivo de la pausa",
    "Paused By": "Pausada por",
    "Paused On": "Pausada el",
    "Pause Capture": "Pausar captura",
    "Resume Capture": "Reanudar captura",
    "Staff Exclusion": "Exclusión de empleados",
    "Exclude Staff From Counts": "Excluir empleados del conteo",
    "Staff Match Threshold": "Umbral de coincidencia de empleado",
    "Set up your first store": "Da de alta tu primera tienda",
    "Needs Attention": "Requiere atención",
    "Capture is paused. Nothing is being recorded for this store.":
        "La captura está pausada. No se está registrando nada de esta tienda.",
    "Why it is paused…": "Por qué está pausada…",
    "Anything the next implementer should know about this site…":
        "Lo que el siguiente implementador deba saber de este sitio…",
    "e.g. Anello Morelia Centro": "p. ej. Anello Morelia Centro",
    "e.g. MOR-01": "p. ej. MOR-01",

    # ---- door ------------------------------------------------------
    "Door": "Puerta",
    "Door Name": "Nombre de la puerta",
    "Door Count": "Número de puertas",
    "Door Type": "Tipo de puerta",
    "Counts Visitors": "Cuenta visitantes",
    "Counts As Visitor": "Cuenta como visitante",
    "Counted as Visitors": "Contados como visitantes",
    "Main entrance": "Entrada principal",
    "Main Entrance": "Entrada principal",
    "Secondary entrance": "Entrada secundaria",
    "Mall / gallery entrance": "Entrada a plaza / galería",
    "Service / staff entrance": "Entrada de servicio / personal",
    "Emergency exit": "Salida de emergencia",
    "Share %": "Participación %",
    "Share of Store %": "Participación de la tienda %",
    "No door traffic yet": "Todavía no hay tráfico por puerta",
    "e.g. North Entrance": "p. ej. Entrada Norte",
    "Short code used in device UIDs, e.g. 'N' for the north door.":
        "Código corto usado en los UID de dispositivo, p. ej. 'N' para la puerta norte.",
    "Short code, e.g. 'MOR-01'. Device UIDs are derived from it.":
        "Código corto, p. ej. 'MOR-01'. Los UID de dispositivo se derivan de él.",

    # ---- device ----------------------------------------------------
    "Device": "Dispositivo",
    "Device Count": "Número de dispositivos",
    "Device UID": "UID del dispositivo",
    "Device Credentials": "Credenciales del dispositivo",
    "Credentials": "Credenciales",
    "Placement": "Ubicación",
    "Hardware": "Hardware",
    "Role": "Función",
    "Critical": "Crítico",
    "Kind": "Tipo",
    "Status": "Estado",
    "Online": "En línea",
    "Offline": "Fuera de línea",
    "Never seen": "Nunca visto",
    "Disabled": "Deshabilitado",
    "Late": "Retrasado",
    "Offline Since": "Fuera de línea desde",
    "Last Heartbeat": "Último latido",
    "Agent Version": "Versión del agente",
    "Edge Backlog": "Cola en el dispositivo",
    "Edge Configuration": "Configuración del edge",
    "Edge Track": "Rastro del edge",
    "API Key": "Llave de API",
    "API Key Hash": "Hash de la llave de API",
    "Key Issued On": "Llave emitida el",
    "Key Revoked": "Llave revocada",
    "Rotate API Key": "Rotar la llave de API",
    "Revoke": "Revocar",
    "Revoked": "Revocada",
    "New API key — copy it now": "Nueva llave de API — cópiala ahora",
    "Ingest Volume": "Volumen de ingesta",
    "Events / Hour": "Eventos / hora",
    "Normal Events / Hour": "Eventos / hora normales",
    "Anomaly Factor": "Factor de anomalía",
    "Door counter (in/out line)": "Contador de puerta (línea entrada/salida)",
    "Demographics (frontal camera)": "Demografía (cámara frontal)",
    "Zone camera": "Cámara de zona",
    "Checkout camera": "Cámara de caja",
    "Other": "Otro",
    "Depth camera + edge PC": "Cámara de profundidad + mini-PC",
    "Depth camera + edge PC (Orbbec / RealSense)":
        "Cámara de profundidad + mini-PC (Orbbec / RealSense)",
    "DIY edge (YOLO + ByteTrack)": "Edge propio (YOLO + ByteTrack)",
    "CCTV — Hikvision": "CCTV — Hikvision",
    "CCTV — Hikvision (ISAPI people counting)":
        "CCTV — Hikvision (conteo de personas ISAPI)",
    "CCTV — Dahua": "CCTV — Dahua",
    "IR beam counter": "Contador de barrera infrarroja",
    "Every device is reporting": "Todos los dispositivos están reportando",
    "e.g. North door counter": "p. ej. Contador de la puerta norte",
    "Leave empty to derive it from the store and door codes.":
        "Déjalo vacío para derivarlo de los códigos de tienda y puerta.",
    "The only store this device may ever post data for.":
        "La única tienda para la que este dispositivo puede enviar datos.",
    "SHA-256 of the device key. The key itself is never stored.":
        "SHA-256 de la llave del dispositivo. La llave misma nunca se almacena.",
    "auto": "automático",
    "device(s)": "dispositivo(s)",
    "door(s) ·": "puerta(s) ·",

    # ---- events / analytics ----------------------------------------
    "Crossing Event": "Evento de cruce",
    "Crossings": "Cruces",
    "Event UUID": "UUID del evento",
    "Direction": "Dirección",
    "Entrance": "Entrada",
    "Entrances": "Entradas",
    "Exit": "Salida",
    "Exits": "Salidas",
    "In": "Entrada",
    "Out": "Salida",
    "People": "Personas",
    "Time": "Hora",
    "Received": "Recibido",
    "Hour": "Hora",
    "Hour of Day": "Hora del día",
    "Day": "Día",
    "Week": "Semana",
    "Month": "Mes",
    "Today": "Hoy",
    "Yesterday": "Ayer",
    "This Week": "Esta semana",
    "This Month": "Este mes",
    "Last 7 Days": "Últimos 7 días",
    "Last 30 Days": "Últimos 30 días",
    "When": "Cuándo",
    "Visitor Counting": "Conteo de visitantes",
    "Match Score": "Puntaje de coincidencia",
    "Pending Embedding": "Firma pendiente",
    "Staff": "Empleados",
    "Staff (Excluded)": "Empleados (excluidos)",
    "Staff Crossings": "Cruces de empleados",
    "Employee": "Empleado",
    "Tickets": "Tickets",
    "POS Tickets": "Tickets de TPV",
    "Units": "Unidades",
    "Units Sold": "Unidades vendidas",
    "Revenue": "Ingresos",
    "Currency": "Moneda",
    "Conversion %": "Conversión %",
    "ATV": "Ticket promedio",
    "Avg Ticket (ATV)": "Ticket promedio (ATV)",
    "UPT": "Unidades por ticket",
    "Units / Ticket (UPT)": "Unidades / ticket (UPT)",
    "Revenue / Visitor": "Ingreso / visitante",
    "Rev / Visitor": "Ingreso / visitante",
    "Revenue / m²": "Ingreso / m²",
    "Visitors / m²": "Visitantes / m²",
    "Visitors / Ticket": "Visitantes / ticket",
    "Visitors / Unit": "Visitantes / unidad",
    "Had Traffic": "Con tráfico",
    "Sales Without Visitors": "Ventas sin visitantes",
    "No data yet": "Todavía no hay datos",
    "Revenue per ticket: what an average sale is worth.":
        "Ingreso por ticket: cuánto vale una venta promedio.",
    "Units per ticket: basket size.": "Unidades por ticket: tamaño de la canasta.",
    "Hides closed hours, which would otherwise drag every average toward zero.":
        "Oculta las horas cerradas, que si no arrastran todos los promedios hacia cero.",

    # ---- staff signature -------------------------------------------
    "Encrypted Signature": "Firma cifrada",
    "Dimensions": "Dimensiones",
    "Dim": "Dim",
    "Model": "Modelo",
    "Enrolled": "Registrada",
    "Enrolled By": "Registrada por",
    "Last Match": "Última coincidencia",
    "Matches": "Coincidencias",
    "Never Matched": "Nunca coincidió",
    "No staff enrolled yet": "Todavía no hay empleados registrados",
    "Set when this crossing was attributed to a known employee.":
        "Se llena cuando el cruce se atribuyó a un empleado conocido.",
    "The enrolment payload carried no vector.":
        "El registro no traía ningún vector.",

    # ---- jobs ------------------------------------------------------
    "Pending": "Pendiente",
    "Running": "Ejecutándose",
    "Done": "Hecho",
    "Failed": "Falló",
    "Queued": "En cola",
    "Priority": "Prioridad",
    "Scheduled At": "Programado para",
    "Started At": "Iniciado el",
    "Finished At": "Terminado el",
    "Attempts": "Intentos",
    "Max Attempts": "Intentos máximos",
    "Duration (ms)": "Duración (ms)",
    "Payload": "Contenido",
    "Retry": "Reintentar",
    "Error": "Error",
    "State": "Estado",
    "The queue is empty": "La cola está vacía",
    "Not before this moment. Retries push it into the future.":
        "No antes de este momento. Los reintentos lo empujan hacia adelante.",
    "No handler is registered for job kind '%s'.":
        "No hay ningún manejador registrado para el tipo de trabajo '%s'.",

    # ---- audit -----------------------------------------------------
    "Action": "Acción",
    "Detail": "Detalle",
    "Records": "Registros",
    "Record ID": "ID del registro",
    "User": "Usuario",
    "IP": "IP",
    "Read sensitive data": "Consultó datos sensibles",
    "Exported a report": "Exportó un reporte",
    "Rotated a device key": "Rotó la llave de un dispositivo",
    "Revoked a device key": "Revocó la llave de un dispositivo",
    "Used the capture kill switch": "Usó el interruptor de emergencia",
    "Ingest anomaly detected": "Anomalía de ingesta detectada",
    "Rejected API credential": "Credencial de API rechazada",
    "Elevated-control decision": "Decisión de control elevado",
    "Watch-list entry created": "Alta en la lista de vigilancia",
    "Watch-list entry confirmed": "Alta confirmada en la lista de vigilancia",
    "Sensitive Reads": "Consultas sensibles",
    "Security Events": "Eventos de seguridad",
    "Nothing logged yet": "Todavía no hay nada registrado",
    "Consulted %s record(s)": "Consultó %s registro(s)",
    "Edge device %s pulled staff signatures":
        "El dispositivo edge %s descargó las firmas de empleados",
    "Rejected API key from %s": "Llave de API rechazada desde %s",
    "Key rotated for device %s": "Llave rotada del dispositivo %s",
    "Key revoked for device %s": "Llave revocada del dispositivo %s",
    "Capture paused: %s": "Captura pausada: %s",
    "Capture resumed": "Captura reanudada",
    "Volume anomaly: %(c)s vs baseline %(b).1f/h":
        "Anomalía de volumen: %(c)s contra una base de %(b).1f/h",
    "Audit entries cannot be deleted. Use the retention cron if the trail has to be "
    "pruned on a documented schedule.":
        "Las entradas de auditoría no se pueden borrar. Usa el cron de retención si "
        "la bitácora debe podarse con un calendario documentado.",
    "Audit entries cannot be modified. A trail that can be edited by the people it "
    "records is not a trail.":
        "Las entradas de auditoría no se pueden modificar. Una bitácora que pueden "
        "editar las personas a las que registra no es una bitácora.",

    # ---- wizard ----------------------------------------------------
    "Setup": "Configuración",
    "Wizard": "Asistente",
    "Create Device": "Crear dispositivo",
    "Create Store": "Crear tienda",
    "Open Store": "Abrir tienda",
    "Close": "Cerrar",
    "Code": "Código",
    "Add at least one door. A store with no entrance has nothing to count.":
        "Agrega al menos una puerta. Una tienda sin entrada no tiene nada que contar.",
    "Store created by %(user)s with %(doors)s door(s).":
        "Tienda creada por %(user)s con %(doors)s puerta(s).",
    "%s counter": "Contador de %s",
    "Door: %(door)s\\n  Device UID : %(uid)s\\n  API key    : %(key)s\\n":
        "Puerta: %(door)s\\n  UID del dispositivo : %(uid)s\\n"
        "  Llave de API        : %(key)s\\n",

    # ---- messages and constraints ----------------------------------
    "Device back online.": "El dispositivo volvió a estar en línea.",
    "Device OFFLINE — no heartbeat for %(min)s minutes (threshold %(limit)s).":
        "Dispositivo FUERA DE LÍNEA — sin latido durante %(min)s minutos "
        "(umbral %(limit)s).",
    "API key REVOKED by %s. This device can no longer send data.":
        "Llave de API REVOCADA por %s. Este dispositivo ya no puede enviar datos.",
    "API key rotated by %s. The previous key stopped working immediately.":
        "Llave de API rotada por %s. La anterior dejó de funcionar de inmediato.",
    "Data capture RESUMED by %s.": "Captura de datos REANUDADA por %s.",
    "'Offline After' must be at least as long as 'Degraded After'.":
        "'Fuera de línea tras' debe ser al menos tan largo como 'Degradado tras'.",
    "A crossing must involve at least one person.":
        "Un cruce debe involucrar al menos a una persona.",
    "Another door of this store already uses that reference.":
        "Otra puerta de esta tienda ya usa esa referencia.",
    "Another store of this company already uses that reference.":
        "Otra tienda de esta compañía ya usa esa referencia.",
    "The heartbeat interval must be a positive number of seconds.":
        "El intervalo de latido debe ser un número positivo de segundos.",
    "The staff match threshold is a cosine similarity: it must sit strictly "
    "between 0 and 1.":
        "El umbral de coincidencia de empleado es una similitud coseno: debe estar "
        "estrictamente entre 0 y 1.",
    "This API key is already assigned to another device.":
        "Esta llave de API ya está asignada a otro dispositivo.",
    "This Device UID is already in use.": "Este UID de dispositivo ya está en uso.",
    "This event was already received (duplicate UUID).":
        "Este evento ya se había recibido (UUID duplicado).",
    "[Analitix] {{ object.store_id.name }} — {{ object.name }} is offline":
        "[Analitix] {{ object.store_id.name }} — {{ object.name }} está fuera de línea",

    # ---- kanban / misc ---------------------------------------------
    "<span class=\\\"text-muted d-block small\\\">Inside now</span>":
        "<span class=\\\"text-muted d-block small\\\">Dentro ahora</span>",
    "<span class=\\\"text-muted d-block small\\\">Visitors today</span>":
        "<span class=\\\"text-muted d-block small\\\">Visitantes hoy</span>",
    "Sequence": "Secuencia",
    "Active": "Activo",
    "Archived": "Archivado",
    "Name": "Nombre",
    "Type": "Tipo",
    "Events": "Eventos",
    "Action Needed": "Requiere acción",
}

TRANSLATIONS.update(BATCH2)
TRANSLATIONS.update(BATCH4)
TRANSLATIONS.update(BATCH5)
TRANSLATIONS.update(BATCH6)
TRANSLATIONS.update(BATCH7)
TRANSLATIONS.update(BATCH8)
TRANSLATIONS.update(BATCH9)
TRANSLATIONS.update(BATCH10)

#: Same translations, keyed on the whitespace-collapsed msgid. View strings carry
#: the XML's line breaks and indentation inside the msgid, and transcribing that
#: by hand is exactly the mistake Odoo swallows without a word — so those are
#: matched on a normalised form instead.
NORMALISED = {}


def squash(text):
    """Normalise a msgid for loose matching.

    Collapses literal ``\\n`` escapes and runs of whitespace, and drops the
    backslashes the .pot puts in front of embedded quotes — otherwise a
    translation of a sentence containing a quoted phrase never matches, and
    Odoo drops it without a word.
    """
    return " ".join(
        text.replace("\\n", " ").replace('\\"', '"').split())


for _key, _value in (list(BATCH3.items()) + list(BATCH4_LOOSE.items())
                     + list(BATCH5_LOOSE.items())
                     + list(BATCH6_LOOSE.items())
                     + list(BATCH7_LOOSE.items())):
    NORMALISED[squash(_key)] = _value

HEADER = '''# Translation of Odoo Server.
# This file contains the translation of the following modules:
# \t* analitix
#
# One file for every Spanish locale: Odoo cascades es -> es_419 -> es_MX, so
# es.po reaches every Spanish-speaking customer without three near-identical
# files drifting apart.
#
msgid ""
msgstr ""
"Project-Id-Version: Odoo Server 19.0\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: 2026-08-01 22:23+0000\\n"
"PO-Revision-Date: 2026-08-01 22:23+0000\\n"
"Last-Translator: XUBAX\\n"
"Language-Team: Spanish\\n"
"Language: es\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
'''


def po_quote(text):
    """Render a python string as one or more PO string literals."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    # msgids in the pot already carry literal \n as two characters; keep them.
    return '"%s"' % escaped


def main():
    pot = open("i18n/analitix.pot", encoding="utf-8").read()
    blocks = pot.split("\n\n")
    out = [HEADER]
    matched = set()
    for block in blocks:
        if not block.strip() or block.startswith("# Translation of"):
            continue
        found = re.search(r'^msgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', block, re.M)
        if not found:
            continue
        raw = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', found.group(1)))
        if not raw:
            continue
        translation = TRANSLATIONS.get(raw) or NORMALISED.get(squash(raw))
        if not translation:
            continue
        matched.add(raw)
        comments = "\n".join(
            line for line in block.splitlines() if line.startswith("#"))
        out.append("%s\nmsgid %s\nmsgstr %s\n" % (
            comments, po_quote(raw), po_quote(translation)))

    body = "\n".join(out)
    # Three files from one source, so they cannot drift apart. Odoo does cascade
    # es -> es_419 -> es_MX, but the cascade only fires for languages that are
    # actually installed, and a Mexican database with only es_MX active has been
    # seen to miss a Spain-only es.po. Writing all three costs nothing and
    # removes the failure mode entirely.
    for locale in ("es", "es_419", "es_MX"):
        with open("i18n/%s.po" % locale, "w", encoding="utf-8") as handle:
            handle.write(body.replace('"Language: es\\n"', '"Language: %s\\n"' % locale))

    unknown = {k for k in TRANSLATIONS if k not in matched}
    _seen = {squash(m) for m in matched}
    unknown |= {k for k in BATCH3 if squash(k) not in _seen}
    unknown |= {k for k in BATCH4_LOOSE if squash(k) not in _seen}
    unknown |= {k for k in BATCH5_LOOSE if squash(k) not in _seen}
    unknown |= {k for k in BATCH6_LOOSE if squash(k) not in _seen}
    unknown |= {k for k in BATCH7_LOOSE if squash(k) not in _seen}
    print("translated %d of the .pot's entries" % len(matched))
    if unknown:
        # An entry whose msgid is not in the .pot is ignored silently by Odoo,
        # so surfacing them here is the only way to notice a typo.
        print("WARNING - %d translations match no msgid:" % len(unknown))
        for item in sorted(unknown):
            print("   ", item[:90])
    return 0 if not unknown else 1


if __name__ == "__main__":
    sys.exit(main())
