# -*- coding: utf-8 -*-
# Demo comercial "Asesorías ISO" para Odoo 19 Community.
#
# Este archivo es un SCRIPT ORM idempotente (no es un módulo importable).
# Lo ejecutan:
#   1) hooks.post_init_hook, al instalar iso_demo en una base nueva;
#   2) scripts/rebuild_demo.ps1 (odoo shell), para reconstruir o mover fechas;
#   3) una acción de servidor (safe_eval), que omite el bloque [solo-python].
# Para que funcione en safe_eval: sin imports fuera del bloque, sin closures,
# sin "with", sin asignar atributos (usar write) y sin nombres con "__".
# Cada registro creado queda con un XML-ID del módulo iso_demo, por lo que se
# puede ejecutar varias veces: actualiza en vez de duplicar.
# [solo-python]
import datetime
from odoo.exceptions import UserError
# [/solo-python]

# ------------------------------------------------------------------ parámetros
SHIFT_WEEKS = 11          # semanas que se adelanta el calendario (0 = inicio 01/11/2026)
LANG = 'es_CL'
MOD = 'iso_demo'
PRICE = 6000000           # CLP netos del contrato ISO 9001
COST = {'S': 38000, 'D': 24000}   # costo hora CLP: Consultor Senior / Consultor ISO
PROJECT_NAME = 'Implementación ISO 9001:2015 – Empresa ABC'
STAGES = ['Diagnóstico', 'Planificación', 'Implementación', 'Capacitación', 'Auditoría interna', 'Certificación']

_ctx = env.context
_run = _ctx.get('iso_phases')
_pwd = _ctx.get('iso_demo_password')
if _ctx.get('iso_shift_weeks') is not None:
    SHIFT_WEEKS = int(_ctx.get('iso_shift_weeks'))
SHIFT = datetime.timedelta(weeks=SHIFT_WEEKS)
OUT = []
LOAD = {}


# -------------------------------------------------------------------- helpers
def want(phase):
    return _run is None or phase in _run


def C(records):
    return records.with_context(tracking_disable=True, mail_create_nosubscribe=True,
                                mail_auto_subscribe_no_notify=True, mail_activity_quick_update=True,
                                mail_notrack=True)


def R(xid):
    return env.ref(MOD + '.' + xid, raise_if_not_found=False)


def bind(xid, rec):
    env['ir.model.data'].create({'module': MOD, 'name': xid, 'model': rec._name, 'res_id': rec.id, 'noupdate': True})


def upsert(xid, model, vals, adopt=None):
    rec = R(xid)
    if not rec and adopt:
        cands = env[model].with_context(active_test=False).search(adopt, order='id')
        if cands:
            used = env['ir.model.data'].search([('model', '=', model), ('res_id', 'in', cands.ids)]).mapped('res_id')
            free = [c for c in cands if c.id not in used]
            if free:
                rec = free[0]
                bind(xid, rec)
    if rec:
        C(rec).write(vals)
        return rec
    rec = C(env[model]).create(vals)
    bind(xid, rec)
    return rec


def Y(m):
    return 2027 if m <= 6 else 2026


def D(m, d):
    return datetime.date(Y(m), m, d) - SHIFT


def DL(m, d):
    return '%s 21:00:00' % D(m, d)


def DT(m, d, hh, mm):
    return '%s %02d:%02d:00' % (D(m, d), hh, mm)


def fmt(date):
    return '%02d/%02d/%04d' % (date.day, date.month, date.year)


def prev_workday(d):
    d = d - datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d = d - datetime.timedelta(days=1)
    return d


def money(n):
    return '$ ' + f"{int(n):,}".replace(',', '.')


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# ------------------------------------------------- XLSX mínimo (sin librerías)
CRC_TABLE = []
for _n in range(256):
    _c = _n
    for _k in range(8):
        _c = ((_c >> 1) ^ 0xEDB88320) if (_c & 1) else (_c >> 1)
    CRC_TABLE.append(_c)


def crc32(data):
    c = 0xFFFFFFFF
    for b in data:
        c = CRC_TABLE[(c ^ b) & 0xFF] ^ (c >> 8)
    return c ^ 0xFFFFFFFF


def u16(n):
    return n.to_bytes(2, 'little')


def u32(n):
    return n.to_bytes(4, 'little')


def zip_store(files):
    out = b''
    central = b''
    stamp = u16(24576) + u16(23873)
    for name, text in files:
        data = text.encode('utf-8')
        fn = name.encode('utf-8')
        sizes = u32(crc32(data)) + u32(len(data)) + u32(len(data))
        offset = len(out)
        out += b'PK\x03\x04' + u16(20) + u16(0) + u16(0) + stamp + sizes + u16(len(fn)) + u16(0) + fn + data
        central += (b'PK\x01\x02' + u16(20) + u16(20) + u16(0) + u16(0) + stamp + sizes + u16(len(fn))
                    + u16(0) + u16(0) + u16(0) + u16(0) + u32(0) + u32(offset) + fn)
    end = b'PK\x05\x06' + u16(0) + u16(0) + u16(len(files)) + u16(len(files)) + u32(len(central)) + u32(len(out)) + u16(0)
    return out + central + end


XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
NS_MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'
XLSX_STYLES = (
    XML_HEAD + '<styleSheet xmlns="' + NS_MAIN + '">'
    '<fonts count="2"><font><sz val="10"/><name val="Calibri"/></font>'
    '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
    '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E79"/><bgColor indexed="64"/></patternFill></fill></fills>'
    '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
    '<border><left style="thin"><color rgb="FFBFBFBF"/></left><right style="thin"><color rgb="FFBFBFBF"/></right>'
    '<top style="thin"><color rgb="FFBFBFBF"/></top><bottom style="thin"><color rgb="FFBFBFBF"/></bottom><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
    '<alignment horizontal="center" vertical="center" wrapText="1"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">'
    '<alignment vertical="top" wrapText="1"/></xf></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
)


def xlsx_bytes(sheet, headers, rows, widths):
    cols = ''
    i = 0
    for w in widths:
        i += 1
        cols += '<col min="%d" max="%d" width="%s" customWidth="1"/>' % (i, i, w)
    cells = ''
    i = 0
    for h in headers:
        cells += '<c r="%s1" t="inlineStr" s="1"><is><t>%s</t></is></c>' % (chr(65 + i), esc(h))
        i += 1
    body = '<row r="1" ht="30" customHeight="1">%s</row>' % cells
    n = 1
    for row in rows:
        n += 1
        cells = ''
        i = 0
        for v in row:
            ref = '%s%d' % (chr(65 + i), n)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cells += '<c r="%s" s="2"><v>%s</v></c>' % (ref, v)
            else:
                cells += '<c r="%s" t="inlineStr" s="2"><is><t>%s</t></is></c>' % (ref, esc(v))
            i += 1
        body += '<row r="%d">%s</row>' % (n, cells)
    last = '%s%d' % (chr(64 + len(headers)), n)
    sheet_xml = (XML_HEAD + '<worksheet xmlns="' + NS_MAIN + '"><dimension ref="A1:' + last + '"/>'
                 '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                 '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/><cols>' + cols + '</cols><sheetData>' + body
                 + '</sheetData><autoFilter ref="A1:' + last + '"/></worksheet>')
    content_types = (XML_HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                     '</Types>')
    rels = (XML_HEAD + '<Relationships xmlns="' + NS_PKG + '"><Relationship Id="rId1" Type="' + NS_REL
            + '/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    workbook = (XML_HEAD + '<workbook xmlns="' + NS_MAIN + '" xmlns:r="' + NS_REL + '"><sheets><sheet name="'
                + esc(sheet) + '" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wb_rels = (XML_HEAD + '<Relationships xmlns="' + NS_PKG + '"><Relationship Id="rId1" Type="' + NS_REL
               + '/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="' + NS_REL
               + '/styles" Target="styles.xml"/></Relationships>')
    return zip_store([
        ('[Content_Types].xml', content_types), ('_rels/.rels', rels), ('xl/workbook.xml', workbook),
        ('xl/_rels/workbook.xml.rels', wb_rels), ('xl/styles.xml', XLSX_STYLES), ('xl/worksheets/sheet1.xml', sheet_xml),
    ])


# ----------------------------------------------------------- PDF (HTML → PDF)
PDF_CSS = (
    "body{font-family:'DejaVu Sans',Arial,sans-serif;font-size:11px;color:#222;margin:0}"
    "table.hdr{width:100%;border-collapse:collapse;margin-bottom:14px}"
    "table.hdr td{border:1px solid #1F4E79;padding:8px;vertical-align:middle}"
    "td.brand{width:27%;background:#1F4E79;color:#fff;font-size:15px;font-weight:bold}"
    "td.brand span{font-size:9px;font-weight:normal}"
    "td.ttl{font-size:15px;font-weight:bold;text-align:center;color:#1F4E79}"
    "td.ttl span{font-size:10px;font-weight:normal;color:#444}"
    "td.meta{width:23%;font-size:9.5px;line-height:1.5}"
    "h2{font-size:13px;color:#1F4E79;border-bottom:1px solid #1F4E79;padding-bottom:2px;margin:16px 0 6px}"
    "p{margin:4px 0 6px;line-height:1.45}li{margin:2px 0;line-height:1.4}"
    "table.d{width:100%;border-collapse:collapse;margin:6px 0 10px}"
    "table.d th{background:#1F4E79;color:#fff;font-size:10px;padding:5px;border:1px solid #1F4E79;text-align:left}"
    "table.d td{font-size:10px;padding:5px;border:1px solid #bbb;vertical-align:top}"
    "table.flow{width:100%;border-collapse:separate;border-spacing:4px;margin:8px 0 12px}"
    "table.flow td{background:#DCE6F1;border:1px solid #1F4E79;text-align:center;font-size:10px;font-weight:bold;padding:10px 4px}"
    "table.flow td.arrow{background:none;border:none;font-size:16px;color:#1F4E79;padding:0;width:16px}"
    "p.foot{margin-top:22px;font-size:8.5px;color:#777;border-top:1px solid #ccc;padding-top:5px}"
)


def pdf_html(spec):
    h = '<html><head><meta charset="utf-8"/><style>' + PDF_CSS + '</style></head><body>'
    h += ('<table class="hdr"><tr><td class="brand">Asesorías ISO<br/><span>Consultoría en sistemas de gestión</span></td>'
          '<td class="ttl">' + esc(spec['title']) + '<br/><span>Empresa ABC SpA · ISO 9001:2015</span></td>'
          '<td class="meta">Código: ' + esc(spec['code']) + '<br/>Versión: ' + esc(spec['version'])
          + '<br/>Fecha: ' + fmt(spec['date']) + '</td></tr></table>')
    for b in spec['blocks']:
        kind = b[0]
        if kind == 'h':
            h += '<h2>' + esc(b[1]) + '</h2>'
        elif kind == 'p':
            h += '<p>' + esc(b[1]) + '</p>'
        elif kind == 'ul':
            h += '<ul>'
            for item in b[1]:
                h += '<li>' + esc(item) + '</li>'
            h += '</ul>'
        elif kind == 'flow':
            h += '<table class="flow"><tr>'
            first = True
            for item in b[1]:
                if not first:
                    h += '<td class="arrow">&#9654;</td>'
                h += '<td>' + esc(item) + '</td>'
                first = False
            h += '</tr></table>'
        elif kind == 't':
            h += '<table class="d"><thead><tr>'
            for head in b[1]:
                h += '<th>' + esc(head) + '</th>'
            h += '</tr></thead><tbody>'
            for row in b[2]:
                h += '<tr>'
                for cell in row:
                    h += '<td>' + esc(cell) + '</td>'
                h += '</tr>'
            h += '</tbody></table>'
    h += ('<p class="foot">Documento de demostración elaborado por Asesorías ISO para Empresa ABC SpA. '
          'Información documentada controlada: la versión vigente es la publicada en el proyecto.</p></body></html>')
    return h


# ------------------------------------------------------- datos: proyecto ABC
# (n, nombre, etapa, responsable, horas, mes, día, estado D=hecha/O=abierta, prioridad, etiquetas, descripción, entregable)
MAIN_TASKS = [
    (1, 'Reunión Kick-Off', 0, 'S', 2, 11, 2, 'D', '2', 'R', 'Reunión de inicio con Gerencia de Operaciones y Encargado de Calidad: objetivos del proyecto, alcance preliminar, equipo de trabajo, canales de comunicación y calendario de hitos.', 'Acta de inicio firmada.'),
    (2, 'Solicitar antecedentes al cliente', 0, 'D', 1, 11, 3, 'D', '1', 'D', 'Solicitar organigrama, procedimientos vigentes, registros de los últimos 12 meses, reclamos de clientes y evaluaciones de proveedores.', 'Lista de antecedentes recibidos.'),
    (3, 'Levantar procesos actuales', 0, 'D', 6, 11, 6, 'D', '2', '', 'Entrevistar a los dueños de proceso (Comercial, Operaciones, Compras, RR.HH. y Bodega) y documentar el flujo actual de cada proceso.', 'Diagramas de flujo de la situación actual.'),
    (4, 'Definir alcance del sistema de gestión', 0, 'S', 2, 11, 6, 'D', '2', 'E', 'Determinar los límites y la aplicabilidad del sistema de gestión de la calidad según la cláusula 4.3, incluyendo sitios, procesos y exclusiones justificadas.', 'Declaración de alcance.'),
    (5, 'Ejecutar Gap Analysis', 0, 'S', 5, 11, 11, 'D', '3', 'E', 'Comparar el estado actual del sistema de gestión de Empresa ABC contra los requisitos aplicables de ISO 9001:2015. Registrar cumplimiento, cumplimiento parcial, brechas identificadas, evidencia disponible, responsable y recomendación.', '02_Gap_Analysis_ISO9001.xlsx'),
    (6, 'Identificar brechas', 0, 'D', 2, 11, 12, 'D', '2', '', 'Consolidar las brechas detectadas en el Gap Analysis por cláusula y proceso, vinculando cada una con su evidencia.', 'Listado de 12 brechas.'),
    (7, 'Clasificar brechas por criticidad', 0, 'S', 1, 11, 13, 'D', '1', '', 'Priorizar las brechas según su impacto en la conformidad del servicio y el esfuerzo de cierre (alta, media, baja).', 'Brechas priorizadas: 3 altas, 5 medias y 4 bajas.'),
    (8, 'Elaborar informe de diagnóstico', 0, 'S', 3, 11, 18, 'D', '2', 'E', 'Redactar el informe de diagnóstico con el nivel de cumplimiento por cláusula, las brechas priorizadas y las recomendaciones.', '01_Informe_Diagnostico_ISO9001.pdf'),
    (9, 'Reunión de revisión con cliente', 0, 'S', 2, 11, 20, 'D', '2', 'R', 'Presentar los resultados del diagnóstico a la Gerencia de Empresa ABC y acordar prioridades para la planificación.', 'Acta de reunión con acuerdos.'),
    (10, 'Crear plan de implementación', 1, 'S', 3, 11, 25, 'D', '2', 'E', 'Definir fases, actividades, responsables, plazos y horas para cerrar las brechas del diagnóstico.', '03_Plan_Implementacion_ISO9001.pdf'),
    (11, 'Definir responsables', 1, 'D', 1, 11, 25, 'D', '1', '', 'Asignar dueños de proceso y contrapartes del cliente para cada actividad del plan (matriz RACI).', ''),
    (12, 'Construir matriz de requisitos ISO 9001', 1, 'D', 3, 11, 27, 'D', '2', 'D', 'Construir la matriz de requisitos de ISO 9001:2015 (cláusulas 4 a 10) con el proceso responsable y la evidencia esperada.', 'Matriz de requisitos.'),
    (13, 'Definir cronograma', 1, 'D', 2, 11, 30, 'D', '1', '', 'Calendarizar las actividades con hitos, dependencias y fechas de entrega comprometidas con el cliente.', ''),
    (14, 'Planificar documentación', 1, 'D', 2, 12, 1, 'D', '1', 'D', 'Definir el listado maestro de documentos a elaborar: manual, procedimientos, instructivos y formatos.', ''),
    (15, 'Identificar riesgos del proyecto', 1, 'S', 2, 12, 2, 'D', '2', 'K', 'Identificar riesgos de plazo, disponibilidad del cliente y alcance, con sus medidas de mitigación.', ''),
    (16, 'Validar plan con cliente', 1, 'S', 1, 12, 4, 'D', '2', 'R', 'Revisar y aprobar el plan de implementación con la Gerencia de Operaciones.', 'Plan aprobado por el cliente.'),
    (17, 'Diseñar mapa de procesos', 2, 'D', 4, 12, 9, 'D', '2', 'E', 'Diseñar el mapa de procesos estratégicos, operativos y de apoyo, con sus interacciones (cláusula 4.4).', '04_Mapa_Procesos.pdf'),
    (18, 'Definir procedimientos', 2, 'D', 6, 12, 11, 'D', '2', 'D', 'Redactar los procedimientos obligatorios y operacionales: ventas, compras, operaciones y control de calidad.', ''),
    (19, 'Crear documentación', 2, 'D', 8, 12, 18, 'O', '2', 'D', 'Elaborar manual de calidad, política, instructivos de trabajo y formatos asociados a cada procedimiento.', 'Manual de calidad e instructivos.'),
    (20, 'Implementar control documental', 2, 'D', 4, 12, 16, 'D', '2', 'ED', 'Implementar el control de la información documentada (cláusula 7.5): codificación, aprobación, distribución y listado maestro.', '05_Procedimiento_Control_Documentos.pdf'),
    (21, 'Implementar gestión de riesgos', 2, 'D', 4, 12, 23, 'O', '3', 'EK', 'Implementar la metodología de riesgos y oportunidades (cláusula 6.1) y los planes de tratamiento por proceso.', '06_Matriz_Riesgos.xlsx'),
    (22, 'Implementar tratamiento de no conformidades', 2, 'D', 3, 12, 30, 'O', '2', '', 'Implementar el procedimiento de no conformidades y acciones correctivas (cláusula 10.2).', ''),
    (23, 'Validar procesos', 2, 'S', 3, 1, 6, 'O', '2', '', 'Verificar en terreno que los procesos operan según los procedimientos aprobados y registrar las desviaciones.', ''),
    (24, 'Revisar registros', 2, 'D', 2, 1, 8, 'O', '1', 'V', 'Revisar que los registros exigidos por el sistema se generan, completan y conservan correctamente.', ''),
    (25, 'Revisar evidencias', 2, 'S', 3, 1, 13, 'O', '2', 'V', 'Revisar las evidencias de implementación por proceso antes de la auditoría interna.', ''),
    (26, 'Ejecutar acciones pendientes', 2, 'D', 3, 1, 15, 'O', '1', '', 'Cerrar las acciones pendientes del plan de implementación detectadas en las revisiones.', ''),
    (27, 'Preparar material de capacitación', 3, 'D', 3, 12, 14, 'D', '1', 'C', 'Preparar presentaciones, casos prácticos y evaluaciones para las capacitaciones del equipo de Empresa ABC.', ''),
    (28, 'Capacitación introducción ISO 9001', 3, 'D', 2, 12, 17, 'D', '2', 'C', 'Capacitación de 2 horas sobre principios de calidad, estructura de la norma y rol de cada área.', 'Lista de asistencia y evaluación.'),
    (29, 'Capacitación gestión documental', 3, 'D', 2, 1, 7, 'O', '2', 'C', 'Capacitación sobre uso del listado maestro, codificación y control de registros.', ''),
    (30, 'Capacitación auditoría interna', 3, 'S', 3, 1, 14, 'O', '2', 'C', 'Formación de auditores internos: planificación, ejecución, redacción de hallazgos y seguimiento.', ''),
    (31, 'Registrar asistencia', 3, 'D', 1, 1, 15, 'O', '0', 'V', 'Registrar la asistencia de cada sesión como evidencia de competencia (cláusula 7.2).', ''),
    (32, 'Evaluar capacitación', 3, 'D', 1, 1, 22, 'O', '1', '', 'Evaluar la eficacia de las capacitaciones mediante prueba escrita y seguimiento en el puesto de trabajo.', ''),
    (33, 'Crear plan de auditoría', 4, 'S', 2, 12, 18, 'D', '2', 'EA', 'Definir objetivo, alcance, criterios, equipo auditor y agenda de la auditoría interna (cláusula 9.2).', '07_Plan_Auditoria_Interna.pdf'),
    (34, 'Preparar checklist', 4, 'S', 2, 1, 15, 'O', '1', 'A', 'Preparar listas de verificación por proceso con los requisitos aplicables de ISO 9001:2015.', ''),
    (35, 'Ejecutar auditoría interna', 4, 'S', 6, 1, 22, 'O', '3', 'A', 'Ejecutar la auditoría interna en terreno: entrevistas, revisión de registros y observación de procesos.', '08_Informe_Auditoria_Interna.pdf'),
    (36, 'Registrar observaciones', 4, 'S', 1, 1, 25, 'O', '1', 'A', 'Registrar las observaciones y oportunidades de mejora detectadas durante la auditoría.', ''),
    (37, 'Registrar hallazgos', 4, 'S', 1, 1, 25, 'O', '2', 'A', 'Registrar los hallazgos con su evidencia objetiva, cláusula asociada y clasificación. Los hallazgos detectados en la revisión documental previa ya están registrados como tareas de esta etapa, con sus acciones correctivas como subtareas.', '09_Registro_Hallazgos.xlsx'),
    (38, 'Registrar no conformidades', 4, 'S', 1, 1, 26, 'O', '1', 'A', 'Registrar las no conformidades mayores y menores con su análisis de causa raíz.', ''),
    (39, 'Definir acciones correctivas', 4, 'S', 2, 1, 28, 'O', '2', 'A', 'Definir acciones correctivas, responsables y plazos para cada hallazgo.', '10_Plan_Acciones_Correctivas.xlsx'),
    (40, 'Asignar responsables', 4, 'D', 1, 1, 29, 'O', '1', '', 'Asignar responsables del cliente para cada acción correctiva y comunicar los plazos.', ''),
    (41, 'Verificar evidencias', 4, 'D', 1, 2, 3, 'O', '1', 'V', 'Verificar las evidencias de implementación de cada acción correctiva.', ''),
    (42, 'Verificar cierre de hallazgos', 4, 'S', 1, 2, 5, 'O', '2', 'A', 'Verificar la eficacia de las acciones y cerrar formalmente los hallazgos.', ''),
    (43, 'Revisión final del sistema', 5, 'S', 2, 2, 9, 'O', '2', '', 'Revisión integral del sistema de gestión antes de la auditoría de certificación.', ''),
    (44, 'Preparar documentación para auditor externo', 5, 'D', 2, 2, 11, 'O', '1', 'D', 'Preparar la carpeta documental para el organismo certificador.', ''),
    (45, 'Revisar evidencias finales', 5, 'D', 1, 2, 12, 'O', '1', 'V', 'Revisar que las evidencias de los últimos tres meses estén completas y disponibles.', ''),
    (46, 'Preparar equipo del cliente', 5, 'D', 1, 2, 15, 'O', '1', '', 'Preparar a los dueños de proceso para las entrevistas del auditor externo.', ''),
    (47, 'Simulación de auditoría', 5, 'S', 2, 2, 17, 'O', '2', 'A', 'Simular la auditoría de certificación con el equipo del cliente.', ''),
    (48, 'Acompañamiento auditoría de certificación', 5, 'D', 2, 2, 23, 'O', '3', 'A', 'Acompañar a Empresa ABC durante las etapas 1 y 2 de la auditoría de certificación.', ''),
    (49, 'Resolver observaciones finales', 5, 'D', 1, 2, 25, 'O', '1', '', 'Apoyar el cierre de las observaciones del organismo certificador.', ''),
    (50, 'Cerrar proyecto', 5, 'D', 1, 2, 26, 'O', '1', '', 'Cierre formal del proyecto: lecciones aprendidas, entrega documental y encuesta de satisfacción.', 'Acta de cierre.'),
]

# tarea bloqueada: [tareas que la bloquean]
DEPS = {6: [5], 7: [6], 8: [7], 9: [8], 10: [9], 13: [10], 16: [13, 15], 17: [16], 18: [17], 19: [18], 20: [18],
        23: [18], 25: [19], 29: [20], 30: [33], 34: [33], 35: [34, 23], 39: [35], 42: [39], 43: [42], 47: [43],
        48: [47], 49: [48], 50: [49]}

# (mes, día, quién, tarea, horas, descripción) -> total 74 h (Senior 25 h, Consultor ISO 49 h)
MAIN_TS = [
    (11, 2, 'S', 1, 2.0, 'Reunión de inicio con Gerencia de Operaciones: objetivos, alcance preliminar y equipo del proyecto'),
    (11, 3, 'D', 2, 1.0, 'Solicitud de antecedentes: organigrama, procedimientos vigentes y registros del último año'),
    (11, 4, 'D', 3, 3.0, 'Entrevistas con Operaciones y Comercial; levantamiento de procesos actuales'),
    (11, 5, 'D', 3, 3.0, 'Entrevistas con Compras, RR.HH. y Bodega; diagramas de flujo de la situación actual'),
    (11, 6, 'S', 4, 2.0, 'Definición del alcance del sistema de gestión y exclusiones (cláusula 4.3)'),
    (11, 9, 'S', 5, 3.0, 'Gap Analysis cláusulas 4 a 7: revisión documental y entrevistas'),
    (11, 10, 'S', 5, 2.5, 'Gap Analysis cláusulas 8 a 10: operación, desempeño y mejora'),
    (11, 10, 'D', 5, 1.5, 'Apoyo en recopilación de evidencias para el Gap Analysis'),
    (11, 11, 'D', 6, 2.0, 'Consolidación de las 12 brechas identificadas por cláusula y proceso'),
    (11, 12, 'S', 7, 1.0, 'Clasificación de brechas por criticidad: 3 altas, 5 medias y 4 bajas'),
    (11, 16, 'S', 8, 2.0, 'Redacción del informe de diagnóstico ISO 9001'),
    (11, 17, 'S', 8, 1.0, 'Revisión final y emisión del informe de diagnóstico'),
    (11, 19, 'S', 9, 2.0, 'Presentación de resultados del diagnóstico a Gerencia'),
    (11, 23, 'S', 10, 2.0, 'Elaboración del plan de implementación por fases'),
    (11, 24, 'S', 10, 1.0, 'Ajustes al plan según disponibilidad del cliente'),
    (11, 24, 'D', 11, 0.5, 'Matriz de responsables por proceso (RACI)'),
    (11, 25, 'D', 12, 1.5, 'Matriz de requisitos ISO 9001: cláusulas 4 a 7'),
    (11, 26, 'D', 12, 1.5, 'Matriz de requisitos ISO 9001: cláusulas 8 a 10'),
    (11, 27, 'D', 13, 1.5, 'Cronograma detallado con hitos y dependencias'),
    (11, 30, 'D', 14, 1.5, 'Listado maestro de documentos a elaborar'),
    (12, 1, 'S', 15, 1.5, 'Identificación de riesgos del proyecto y medidas de mitigación'),
    (12, 3, 'S', 16, 1.0, 'Reunión de validación del plan con Gerencia de Operaciones'),
    (12, 7, 'D', 17, 2.0, 'Taller de mapa de procesos con dueños de proceso'),
    (12, 9, 'D', 17, 2.0, 'Mapa de procesos versión 1.0 y caracterizaciones'),
    (12, 10, 'D', 18, 3.0, 'Procedimientos de ventas y compras'),
    (12, 11, 'D', 18, 3.0, 'Procedimientos de operaciones y control de calidad'),
    (12, 14, 'D', 20, 2.0, 'Procedimiento de control de documentos y registros'),
    (12, 15, 'D', 20, 2.0, 'Implementación del listado maestro y codificación documental'),
    (12, 14, 'D', 19, 2.0, 'Redacción del manual de calidad y política'),
    (12, 16, 'D', 19, 2.0, 'Instructivos de trabajo operacionales'),
    (12, 18, 'D', 19, 2.0, 'Formatos y registros asociados a los procedimientos'),
    (12, 16, 'D', 21, 1.5, 'Matriz de riesgos y oportunidades por proceso'),
    (12, 17, 'D', 21, 1.5, 'Planes de tratamiento para riesgos altos'),
    (12, 17, 'D', 22, 2.0, 'Procedimiento de no conformidades y acciones correctivas (borrador)'),
    (12, 17, 'S', 23, 2.0, 'Revisión cruzada de los procesos de ventas y compras'),
    (12, 18, 'D', 24, 1.0, 'Revisión de registros de capacitación e inducción'),
    (12, 10, 'D', 27, 1.5, 'Material de capacitación: introducción a ISO 9001'),
    (12, 11, 'D', 27, 1.5, 'Material de capacitación: gestión documental y casos prácticos'),
    (12, 15, 'D', 28, 2.0, 'Capacitación introducción ISO 9001 (18 asistentes)'),
    (12, 16, 'D', 31, 1.0, 'Registro de asistencia y evaluaciones de la primera sesión'),
    (12, 18, 'S', 33, 2.0, 'Programa y plan de auditoría interna: alcance, criterios y equipo auditor'),
]

TAGDEF = [('E', 'Entregable', 10), ('R', 'Reunión cliente', 4), ('D', 'Documentación', 2), ('C', 'Capacitación', 3),
          ('A', 'Auditoría', 1), ('V', 'Evidencia', 7), ('K', 'Riesgos', 9), ('H', 'Hallazgo', 1),
          ('N', 'No conformidad menor', 9), ('O', 'Observación', 3), ('P', 'En proceso', 4), ('Q', 'Pendiente', 8)]
NORMS = [('9001', 'ISO 9001:2015', 10), ('45001', 'ISO 45001:2018', 2), ('27001', 'ISO 27001:2022', 11), ('14001', 'ISO 14001:2015', 7)]

PROJECT_DESC = ('<p>Implementación del sistema de gestión de la calidad de Empresa ABC SpA conforme a ISO 9001:2015, '
                'desde el diagnóstico hasta el acompañamiento en la auditoría de certificación.</p>'
                '<p><strong>Norma:</strong> ISO 9001:2015 · <strong>Presupuesto:</strong> 120 h (Consultor Senior 50 h, '
                'Consultor ISO 70 h) · <strong>Contrato:</strong> ' + money(PRICE) + ' + IVA en tres hitos (40 % / 40 % / 20 %).</p>')


def finding_html(rows):
    h = '<table class="table table-bordered"><tbody>'
    for label, value in rows:
        h += '<tr><td><strong>' + esc(label) + '</strong></td><td>' + esc(value) + '</td></tr>'
    return h + '</tbody></table>'


FINDINGS = [
    ('h01', 'Hallazgo 01 · Registros de capacitación incompletos', 1, 20, 'HNP', [
        ('Descripción', 'Registros de capacitación incompletos para personal incorporado durante el último trimestre.'),
        ('Clasificación', 'No conformidad menor'), ('Cláusula', 'ISO 9001:2015, 7.2 Competencia'),
        ('Origen', 'Revisión documental previa a la auditoría interna'),
        ('Evidencia', '6 de 14 colaboradores ingresados en el último trimestre sin registro de inducción firmado.'),
        ('Acción correctiva', 'Regularizar registros y establecer control mensual de evidencias.'),
        ('Responsable', 'Encargado de Calidad (Empresa ABC)'), ('Estado', 'En proceso')],
     [('Regularizar los registros de capacitación pendientes', 1, 8), ('Establecer control mensual de evidencias de capacitación', 1, 15)]),
    ('h02', 'Hallazgo 02 · Revisión anual de proveedores críticos sin evidencia uniforme', 1, 27, 'HOQ', [
        ('Descripción', 'No existe evidencia uniforme de revisión anual de proveedores críticos.'),
        ('Clasificación', 'Observación'), ('Cláusula', 'ISO 9001:2015, 8.4 Control de proveedores externos'),
        ('Origen', 'Revisión documental previa a la auditoría interna'),
        ('Evidencia', 'Solo 3 de 8 proveedores críticos cuentan con evaluación vigente, en formatos distintos.'),
        ('Acción correctiva', 'Crear checklist de evaluación y calendario anual.'),
        ('Responsable', 'Jefe de Compras (Empresa ABC)'), ('Estado', 'Pendiente')],
     [('Crear checklist de evaluación de proveedores críticos', 1, 22), ('Definir y publicar calendario anual de evaluación de proveedores', 1, 29)]),
]

# ------------------------------------------------------------ datos: cartera
# tareas: (clave, nombre, etapa, quién, horas plan, horas ejecutadas, mes, día, estado, prioridad,
#          mes fin trabajo, día fin trabajo, bloque de horas, nombre anterior)
PORT = [
    {'key': 'b', 'name': 'Implementación ISO 45001:2018 – Cliente B', 'partner': 'partner_b', 'pm': 'D', 'norm': '45001',
     'start': (12, 1), 'end': (3, 31), 'hours': 90, 'code': 'ISO45001-CLIENTE-B', 'status': 'on_track', 'progress': 13,
     'update': 'Proyecto recién iniciado. Kick-off realizado y levantamiento de peligros y riesgos (IPER) en curso junto al Gap Analysis.',
     'tasks': [
         ('01', 'Reunión Kick-Off', 0, 'S', 2, 2, 12, 1, 'D', '2', 12, 1, 2, None),
         ('02', 'Solicitar antecedentes de SST al cliente', 0, 'D', 2, 2, 12, 3, 'D', '1', 12, 2, 2, None),
         ('03', 'Levantamiento de peligros y riesgos (IPER)', 0, 'D', 10, 5, 12, 22, 'O', '3', 12, 18, 2.5, 'Diagnóstico inicial'),
         ('04', 'Gap Analysis ISO 45001', 0, 'S', 8, 3, 12, 23, 'O', '2', 12, 16, 3, None),
         ('05', 'Informe de diagnóstico SST', 0, 'S', 6, 0, 1, 8, 'O', '2', 0, 0, 0, None),
         ('06', 'Revisión de avance con cliente', 0, 'S', 2, 0, 1, 12, 'O', '1', 0, 0, 0, None),
         ('07', 'Plan de implementación ISO 45001', 1, 'S', 6, 0, 1, 20, 'O', '2', 0, 0, 0, None),
         ('08', 'Matriz de requisitos legales SST', 1, 'D', 8, 0, 1, 27, 'O', '2', 0, 0, 0, None),
         ('09', 'Procedimiento de investigación de incidentes', 2, 'D', 12, 0, 2, 17, 'O', '1', 0, 0, 0, None),
         ('10', 'Plan de preparación y respuesta ante emergencias', 2, 'D', 12, 0, 2, 26, 'O', '2', 0, 0, 0, None),
         ('11', 'Capacitación comité paritario', 3, 'D', 6, 0, 3, 10, 'O', '1', 0, 0, 0, None),
         ('12', 'Auditoría interna ISO 45001', 4, 'S', 10, 0, 3, 19, 'O', '2', 0, 0, 0, None),
         ('13', 'Acompañamiento auditoría de certificación', 5, 'S', 6, 0, 3, 30, 'O', '2', 0, 0, 0, None),
     ]},
    {'key': 'c', 'name': 'Implementación ISO 27001:2022 – Cliente C', 'partner': 'partner_c', 'pm': 'D', 'norm': '27001',
     'start': (9, 14), 'end': (1, 29), 'hours': 160, 'code': 'ISO27001-CLIENTE-C', 'status': 'at_risk', 'progress': 60,
     'update': 'Implementación en curso. La evaluación y tratamiento de riesgos está atrasada por baja disponibilidad del área de TI del cliente; se reprogramaron dos sesiones.',
     'tasks': [
         ('01', 'Gap Analysis ISO 27001 (Anexo A)', 0, 'S', 12, 12, 9, 25, 'D', '2', 9, 25, 3, None),
         ('02', 'Inventario de activos de información', 0, 'D', 14, 14, 10, 9, 'D', '2', 10, 9, 2, None),
         ('03', 'Declaración de aplicabilidad (SoA)', 1, 'S', 10, 10, 10, 16, 'D', '3', 10, 16, 2.5, None),
         ('04', 'Metodología de evaluación de riesgos', 1, 'S', 8, 8, 10, 23, 'D', '2', 10, 22, 2, None),
         ('05', 'Política de seguridad de la información', 2, 'D', 10, 10, 10, 30, 'D', '2', 10, 29, 2.5, None),
         ('06', 'Evaluación y tratamiento de riesgos', 2, 'D', 20, 18, 12, 11, 'O', '3', 12, 4, 3, None),
         ('07', 'Procedimiento de control de accesos', 2, 'D', 14, 10, 12, 22, 'O', '2', 11, 19, 2.5, 'Implementación inicial'),
         ('08', 'Gestión de incidentes de seguridad', 2, 'D', 14, 8, 1, 8, 'O', '2', 11, 27, 2, None),
         ('09', 'Plan de continuidad del negocio', 2, 'D', 12, 0, 1, 15, 'O', '2', 0, 0, 0, None),
         ('10', 'Revisión de avance con cliente', 2, 'S', 4, 2, 12, 21, 'O', '1', 12, 14, 1, None),
         ('11', 'Concientización en seguridad de la información', 3, 'D', 10, 4, 1, 12, 'O', '1', 12, 2, 2, None),
         ('12', 'Auditoría interna ISO 27001', 4, 'S', 16, 0, 1, 20, 'O', '2', 0, 0, 0, None),
         ('13', 'Preparación auditoría de certificación (Etapas 1 y 2)', 5, 'S', 16, 0, 1, 28, 'O', '2', 0, 0, 0, None),
     ]},
    {'key': 'd', 'name': 'Implementación ISO 14001:2015 – Cliente D', 'partner': 'partner_d', 'pm': 'S', 'norm': '14001',
     'start': (7, 6), 'end': (12, 30), 'hours': 100, 'code': 'ISO14001-CLIENTE-D', 'status': 'on_track', 'progress': 82,
     'update': 'Auditoría interna en ejecución. Quedan por cerrar tres no conformidades ambientales antes de la revisión por la dirección.',
     'tasks': [
         ('01', 'Revisión ambiental inicial', 0, 'S', 10, 10, 7, 17, 'D', '2', 7, 17, 2.5, None),
         ('02', 'Matriz de aspectos e impactos ambientales', 1, 'D', 12, 12, 8, 7, 'D', '3', 8, 7, 3, None),
         ('03', 'Identificación de requisitos legales ambientales', 1, 'D', 8, 8, 8, 21, 'D', '2', 8, 21, 2, None),
         ('04', 'Procedimiento de gestión de residuos', 2, 'D', 12, 12, 9, 11, 'D', '2', 9, 11, 3, None),
         ('05', 'Control operacional y plan de emergencias ambientales', 2, 'D', 12, 13, 10, 2, 'D', '2', 10, 2, 3, None),
         ('06', 'Capacitación en gestión ambiental', 3, 'D', 8, 8, 10, 16, 'D', '1', 10, 16, 4, None),
         ('07', 'Plan y checklist de auditoría ISO 14001', 4, 'S', 4, 4, 11, 6, 'D', '2', 11, 6, 2, None),
         ('08', 'Ejecución de auditoría interna ISO 14001', 4, 'S', 12, 10, 12, 18, 'O', '3', 12, 15, 2.5, 'Auditoría interna inicial'),
         ('09', 'Tratamiento de no conformidades ambientales', 4, 'D', 8, 3, 12, 23, 'O', '2', 12, 18, 1.5, None),
         ('10', 'Revisión de avance con cliente', 4, 'S', 2, 2, 12, 11, 'D', '1', 12, 11, 2, None),
         ('11', 'Revisión por la dirección', 5, 'S', 4, 0, 12, 22, 'O', '2', 0, 0, 0, None),
         ('12', 'Acompañamiento auditoría de certificación', 5, 'S', 8, 0, 12, 29, 'O', '3', 0, 0, 0, None),
     ]},
]
TS_LABELS = ['Sesión de trabajo con el cliente', 'Elaboración de documentación', 'Revisión y ajustes',
             'Levantamiento de información', 'Reunión de seguimiento']


def spread(prefix, project, task, employee, hours, end, chunk):
    d = end
    i = 0
    left = hours
    while left > 0.001:
        h = chunk if left >= chunk else left
        while d.weekday() >= 5 or LOAD.get((employee.id, d), 0) + h > 7.5:
            d = prev_workday(d)
        i += 1
        upsert('%s_%02d' % (prefix, i), 'account.analytic.line', {
            'date': d, 'name': '%s · %s' % (TS_LABELS[i % 5], task.name), 'employee_id': employee.id,
            'project_id': project.id, 'task_id': task.id, 'unit_amount': h})
        LOAD[(employee.id, d)] = LOAD.get((employee.id, d), 0) + h
        left -= h
        d = prev_workday(d)
    return i


# ----------------------------------------------------------- datos: documentos
def docs_spec():
    gap = [
        ('4.1', 'Comprensión de la organización y su contexto', 'Cumple', 85, 'Análisis FODA y planificación estratégica vigente', 'Sin brecha relevante', '-', 'Gerencia General', 'Mantener revisión anual'),
        ('4.2', 'Necesidades y expectativas de las partes interesadas', 'Cumple parcialmente', 50, 'Listado informal de clientes clave', 'No se identifican los requisitos de todas las partes interesadas', 'Baja', 'Encargado de Calidad', 'Elaborar matriz de partes interesadas'),
        ('4.3', 'Alcance del sistema de gestión de la calidad', 'No cumple', 20, 'Sin documento', 'Alcance del sistema no definido ni documentado', 'Media', 'Gerencia de Operaciones', 'Documentar alcance y exclusiones'),
        ('4.4', 'Sistema de gestión de la calidad y sus procesos', 'Cumple parcialmente', 55, 'Diagramas parciales de Operaciones', 'No existe mapa de procesos ni se describen sus interacciones', 'Media', 'Encargado de Calidad', 'Diseñar mapa de procesos y caracterizaciones'),
        ('5.2', 'Política de la calidad', 'Cumple parcialmente', 70, 'Política publicada en casa matriz', 'Política no comunicada a todo el personal', 'Baja', 'Gerencia General', 'Difundir y evidenciar su comprensión'),
        ('5.3', 'Roles, responsabilidades y autoridades', 'Cumple', 90, 'Organigrama y perfiles de cargo', 'Sin brecha relevante', '-', 'Recursos Humanos', 'Mantener actualizado'),
        ('6.1', 'Acciones para abordar riesgos y oportunidades', 'No cumple', 25, 'Sin registros', 'No existe metodología de gestión de riesgos', 'Media', 'Gerencia de Operaciones', 'Implementar matriz de riesgos por proceso'),
        ('6.2', 'Objetivos de la calidad y planificación', 'Cumple parcialmente', 50, 'Indicadores comerciales mensuales', 'Objetivos sin metas ni seguimiento formal', 'Media', 'Gerencia de Operaciones', 'Definir objetivos medibles por proceso'),
        ('7.2', 'Competencia', 'Cumple parcialmente', 45, 'Registros de inducción incompletos', 'Registros de capacitación incompletos para personal nuevo', 'Alta', 'Recursos Humanos', 'Regularizar registros y establecer control mensual'),
        ('7.5', 'Información documentada', 'No cumple', 30, 'Documentos sin codificación ni control de versión', 'Sin procedimiento de control de documentos; circulan versiones obsoletas', 'Alta', 'Encargado de Calidad', 'Implementar listado maestro y codificación documental'),
        ('8.2', 'Requisitos para los productos y servicios', 'Cumple', 85, 'Contratos y órdenes de servicio', 'Sin brecha relevante', '-', 'Comercial', 'Mantener'),
        ('8.4', 'Control de procesos, productos y servicios externos', 'Cumple parcialmente', 40, 'Evaluaciones aisladas de proveedores', 'Evaluación de proveedores críticos sin evidencia uniforme', 'Alta', 'Compras', 'Crear checklist de evaluación y calendario anual'),
        ('8.5', 'Producción y provisión del servicio', 'Cumple', 80, 'Instructivos operacionales', 'Instructivos sin control de versión', 'Baja', 'Operaciones', 'Incorporar los instructivos al listado maestro'),
        ('9.2', 'Auditoría interna', 'No cumple', 0, 'Sin registros', 'Nunca se han realizado auditorías internas', 'Media', 'Encargado de Calidad', 'Formar auditores internos y programar auditoría'),
        ('10.2', 'No conformidad y acción correctiva', 'Cumple parcialmente', 50, 'Registro de reclamos de clientes', 'No se analiza la causa raíz de las no conformidades', 'Baja', 'Encargado de Calidad', 'Implementar procedimiento de acciones correctivas'),
    ]
    risks = [
        ('Comercial', 'Pérdida de clientes por incumplimiento de plazos de entrega', 'Planificación de rutas sin holguras', 3, 4, 12, 'Alto', 'Tablero de cumplimiento de entregas y reunión semanal', 'Gerente de Operaciones', fmt(D(1, 15)), 'En implementación'),
        ('Operaciones', 'Errores de despacho por uso de instructivos obsoletos', 'Documentos sin control de versión', 4, 3, 12, 'Alto', 'Listado maestro y retiro de copias obsoletas', 'Encargado de Calidad', fmt(D(12, 30)), 'En implementación'),
        ('Compras', 'Falla de proveedor crítico de transporte', 'Proveedores sin evaluación periódica', 2, 5, 10, 'Alto', 'Evaluación anual y proveedor alternativo homologado', 'Jefe de Compras', fmt(D(1, 29)), 'Planificado'),
        ('Recursos Humanos', 'Personal nuevo sin la competencia requerida', 'Inducción sin registro ni evaluación', 3, 3, 9, 'Medio', 'Control mensual de registros de capacitación', 'Jefe de RR.HH.', fmt(D(1, 15)), 'En implementación'),
        ('Bodega', 'Daño de mercadería en almacenamiento', 'Falta de inspecciones periódicas', 2, 3, 6, 'Medio', 'Inspección semanal con lista de verificación', 'Jefe de Bodega', fmt(D(1, 22)), 'Planificado'),
        ('Tecnología', 'Pérdida de información de servicio al cliente', 'Respaldos manuales', 2, 4, 8, 'Medio', 'Respaldo automático diario y prueba trimestral', 'Encargado de TI', fmt(D(2, 5)), 'Planificado'),
        ('Dirección', 'Oportunidad: nuevos contratos que exigen certificación ISO 9001', 'Licitaciones con requisito de certificación', 4, 4, 16, 'Oportunidad', 'Certificar dentro del plazo del proyecto', 'Gerencia General', fmt(D(2, 26)), 'En curso'),
        ('Servicio al cliente', 'Reclamos sin respuesta dentro del plazo', 'No se mide el tiempo de respuesta', 3, 2, 6, 'Medio', 'Indicador de tiempo de respuesta y escalamiento', 'Jefe de Servicio al Cliente', fmt(D(1, 22)), 'Planificado'),
    ]
    h1 = 'Registros de capacitación incompletos para personal incorporado durante el último trimestre.'
    h2 = 'No existe evidencia uniforme de revisión anual de proveedores críticos.'
    return [
        {'file': '01_Informe_Diagnostico_ISO9001.pdf', 'task': 8, 'kind': 'pdf', 'code': 'INF-DIAG-01',
         'title': 'Informe de Diagnóstico ISO 9001:2015', 'version': '1.0', 'date': D(11, 17), 'blocks': [
             ('h', '1. Objetivo y alcance'),
             ('p', 'Evaluar el grado de cumplimiento del sistema de gestión de Empresa ABC SpA respecto de los requisitos de ISO 9001:2015 e identificar las brechas que deben cerrarse antes de la certificación. El diagnóstico cubrió los procesos Comercial, Operaciones, Compras, Bodega y Recursos Humanos de la casa matriz en Santiago.'),
             ('h', '2. Metodología'),
             ('p', 'Se realizaron 9 entrevistas a dueños de proceso, se revisaron 46 documentos y registros, y se verificaron en terreno 3 procesos operativos. Cada requisito se calificó como Cumple, Cumple parcialmente o No cumple.'),
             ('h', '3. Resultado global'),
             ('p', 'Nivel de cumplimiento global: 56 %. Se identificaron 12 brechas: 3 de criticidad alta, 5 de criticidad media y 4 de criticidad baja.'),
             ('t', ['Cláusula', 'Requisito', 'Cumplimiento', 'Estado'], [
                 ('4', 'Contexto de la organización', '60 %', 'Cumple parcialmente'), ('5', 'Liderazgo', '70 %', 'Cumple parcialmente'),
                 ('6', 'Planificación', '45 %', 'Cumple parcialmente'), ('7', 'Apoyo', '50 %', 'Cumple parcialmente'),
                 ('8', 'Operación', '72 %', 'Cumple parcialmente'), ('9', 'Evaluación del desempeño', '40 %', 'No cumple'),
                 ('10', 'Mejora', '55 %', 'Cumple parcialmente')]),
             ('h', '4. Brechas de criticidad alta'),
             ('t', ['N°', 'Cláusula', 'Brecha', 'Recomendación'], [
                 ('B-01', '7.5', 'No existe un procedimiento formal de control de documentos; circulan versiones no vigentes.', 'Implementar listado maestro y codificación documental.'),
                 ('B-02', '8.4', 'La evaluación de proveedores críticos no es sistemática ni deja evidencia uniforme.', 'Definir criterios y calendario anual de evaluación.'),
                 ('B-03', '7.2', 'Registros de competencia y capacitación incompletos para personal nuevo.', 'Regularizar registros y establecer control mensual.')]),
             ('h', '5. Conclusiones'),
             ('p', 'Empresa ABC cuenta con procesos operativos estables y con el compromiso de la gerencia. Las principales brechas se concentran en información documentada, evaluación del desempeño y gestión de riesgos. Se estima un plazo de 4 meses y 120 horas de consultoría para alcanzar la certificación.')]},
        {'file': '02_Gap_Analysis_ISO9001.xlsx', 'task': 5, 'kind': 'xlsx', 'sheet': 'Gap Analysis',
         'headers': ['Cláusula', 'Requisito ISO 9001:2015', 'Estado', '% cumplimiento', 'Evidencia disponible', 'Brecha identificada', 'Criticidad', 'Responsable', 'Recomendación'],
         'rows': gap, 'widths': [9, 38, 20, 13, 34, 44, 11, 22, 40]},
        {'file': '03_Plan_Implementacion_ISO9001.pdf', 'task': 10, 'kind': 'pdf', 'code': 'PLAN-IMP-01',
         'title': 'Plan de Implementación ISO 9001:2015', 'version': '1.1', 'date': D(11, 24), 'blocks': [
             ('h', '1. Objetivo'),
             ('p', 'Establecer las fases, actividades, responsables, plazos y horas necesarias para cerrar las 12 brechas identificadas en el diagnóstico y preparar a Empresa ABC SpA para la auditoría de certificación.'),
             ('h', '2. Fases, plazos y horas'),
             ('t', ['Fase', 'Actividades principales', 'Inicio', 'Término', 'Horas', 'Responsable'], [
                 ('Diagnóstico', 'Kick-off, levantamiento de procesos, Gap Analysis e informe', fmt(D(11, 2)), fmt(D(11, 20)), '24', 'Consultor Senior'),
                 ('Planificación', 'Plan, matriz de requisitos, cronograma y riesgos', fmt(D(11, 23)), fmt(D(12, 4)), '14', 'Consultor Senior'),
                 ('Implementación', 'Mapa de procesos, procedimientos, control documental y riesgos', fmt(D(12, 7)), fmt(D(1, 15)), '40', 'Consultor ISO'),
                 ('Capacitación', 'Introducción a ISO 9001, gestión documental y auditores internos', fmt(D(12, 14)), fmt(D(1, 22)), '12', 'Consultor ISO'),
                 ('Auditoría interna', 'Plan, ejecución, hallazgos y acciones correctivas', fmt(D(1, 18)), fmt(D(2, 5)), '18', 'Consultor Senior'),
                 ('Certificación', 'Revisión final, simulación y acompañamiento', fmt(D(2, 8)), fmt(D(2, 26)), '12', 'Consultor ISO'),
                 ('Total', '', '', '', '120', '')]),
             ('h', '3. Hitos de facturación'),
             ('t', ['Hito', 'Condición de cumplimiento', '%', 'Monto neto'], [
                 ('1. Inicio y Diagnóstico', 'Informe de diagnóstico aprobado por el cliente', '40 %', money(PRICE * 0.4)),
                 ('2. Implementación y Capacitación', 'Documentación implementada y capacitaciones realizadas', '40 %', money(PRICE * 0.4)),
                 ('3. Auditoría interna y Certificación', 'Hallazgos cerrados y acompañamiento en auditoría externa', '20 %', money(PRICE * 0.2))]),
             ('h', '4. Supuestos'),
             ('ul', ['El cliente designa un Encargado de Calidad con dedicación mínima de 8 horas semanales.',
                     'Los dueños de proceso participan en los talleres y revisan los documentos dentro de 3 días hábiles.',
                     'Las horas adicionales a las 120 presupuestadas se acuerdan previamente por escrito.'])]},
        {'file': '04_Mapa_Procesos.pdf', 'task': 17, 'kind': 'pdf', 'code': 'MP-SGC-01',
         'title': 'Mapa de Procesos', 'version': '1.0', 'date': D(12, 9), 'blocks': [
             ('h', 'Cadena de valor'),
             ('flow', ['Requisitos del cliente', 'Gestión comercial', 'Planificación del servicio', 'Operaciones y distribución', 'Servicio al cliente', 'Satisfacción del cliente']),
             ('h', 'Procesos estratégicos'),
             ('t', ['Proceso', 'Dueño', 'Entradas', 'Salidas', 'Indicador'], [
                 ('Planificación estratégica', 'Gerencia General', 'Contexto, partes interesadas', 'Objetivos y presupuesto anual', 'Cumplimiento de objetivos'),
                 ('Gestión de la calidad', 'Encargado de Calidad', 'Requisitos ISO 9001, hallazgos', 'Sistema de gestión mantenido', 'Hallazgos cerrados en plazo'),
                 ('Revisión por la dirección', 'Gerencia General', 'Indicadores, auditorías, reclamos', 'Decisiones y acciones de mejora', 'Acciones implementadas')]),
             ('h', 'Procesos operativos'),
             ('t', ['Proceso', 'Dueño', 'Entradas', 'Salidas', 'Indicador'], [
                 ('Gestión comercial', 'Gerente Comercial', 'Solicitudes de clientes', 'Contratos y órdenes de servicio', 'Tasa de cierre de cotizaciones'),
                 ('Planificación del servicio', 'Jefe de Operaciones', 'Órdenes de servicio', 'Programa de despachos', 'Cumplimiento del programa'),
                 ('Operaciones y distribución', 'Gerente de Operaciones', 'Programa de despachos', 'Servicio entregado', 'Entregas a tiempo'),
                 ('Servicio al cliente', 'Jefe de Servicio al Cliente', 'Consultas y reclamos', 'Respuestas y soluciones', 'Tiempo de respuesta')]),
             ('h', 'Procesos de apoyo'),
             ('t', ['Proceso', 'Dueño', 'Entradas', 'Salidas', 'Indicador'], [
                 ('Compras y proveedores', 'Jefe de Compras', 'Requerimientos internos', 'Bienes y servicios conformes', 'Proveedores evaluados'),
                 ('Recursos humanos', 'Jefe de RR.HH.', 'Necesidades de personal', 'Personal competente', 'Cumplimiento del plan de capacitación'),
                 ('Mantención', 'Jefe de Mantención', 'Plan de mantención', 'Equipos disponibles', 'Disponibilidad de flota'),
                 ('Tecnología', 'Encargado de TI', 'Requerimientos de sistemas', 'Sistemas e información disponibles', 'Respaldos exitosos')])]},
        {'file': '05_Procedimiento_Control_Documentos.pdf', 'task': 20, 'kind': 'pdf', 'code': 'PR-SGC-01',
         'title': 'Procedimiento de Control de Documentos', 'version': '1.0', 'date': D(12, 15), 'blocks': [
             ('h', '1. Objetivo'),
             ('p', 'Establecer la metodología para elaborar, revisar, aprobar, distribuir y actualizar la información documentada del sistema de gestión de la calidad, conforme a la cláusula 7.5 de ISO 9001:2015.'),
             ('h', '2. Alcance'),
             ('p', 'Aplica a todos los documentos y registros del sistema de gestión: manual, política, procedimientos, instructivos, formatos y documentos de origen externo.'),
             ('h', '3. Responsabilidades'),
             ('t', ['Rol', 'Responsabilidad'], [
                 ('Encargado de Calidad', 'Administrar el listado maestro, asignar códigos y retirar las versiones obsoletas.'),
                 ('Dueño de proceso', 'Elaborar y revisar los documentos de su proceso.'),
                 ('Gerencia de Operaciones', 'Aprobar los documentos antes de su publicación.')]),
             ('h', '4. Desarrollo'),
             ('t', ['N°', 'Actividad', 'Responsable', 'Registro'], [
                 ('1', 'Identificar la necesidad de crear o modificar un documento.', 'Dueño de proceso', 'Solicitud de cambio'),
                 ('2', 'Asignar código y versión según la tabla de codificación.', 'Encargado de Calidad', 'Listado maestro'),
                 ('3', 'Elaborar y revisar el documento.', 'Dueño de proceso', 'Borrador revisado'),
                 ('4', 'Aprobar y publicar la versión vigente.', 'Gerencia de Operaciones', 'Documento aprobado'),
                 ('5', 'Retirar las copias obsoletas e informar a los usuarios.', 'Encargado de Calidad', 'Registro de distribución')]),
             ('h', '5. Codificación'),
             ('ul', ['PR-XXX-NN: procedimientos.', 'IT-XXX-NN: instructivos de trabajo.', 'FO-XXX-NN: formatos y registros.',
                     'XXX corresponde a la sigla del proceso y NN al número correlativo.']),
             ('h', '6. Control de cambios'),
             ('t', ['Versión', 'Fecha', 'Descripción', 'Aprobó'], [
                 ('1.0', fmt(D(12, 15)), 'Emisión inicial.', 'Gerente de Operaciones')])]},
        {'file': '06_Matriz_Riesgos.xlsx', 'task': 21, 'kind': 'xlsx', 'sheet': 'Matriz de riesgos',
         'headers': ['Proceso', 'Riesgo u oportunidad', 'Causa', 'Probabilidad (1-5)', 'Impacto (1-5)', 'Nivel', 'Clasificación', 'Tratamiento', 'Responsable', 'Plazo', 'Estado'],
         'rows': risks, 'widths': [18, 44, 34, 13, 11, 8, 14, 44, 24, 12, 18]},
        {'file': '07_Plan_Auditoria_Interna.pdf', 'task': 33, 'kind': 'pdf', 'code': 'PLAN-AUD-01',
         'title': 'Plan de Auditoría Interna', 'version': '1.0', 'date': D(12, 18), 'blocks': [
             ('h', '1. Objetivo'),
             ('p', 'Verificar la conformidad y la eficacia del sistema de gestión de la calidad de Empresa ABC SpA respecto de los requisitos de ISO 9001:2015 y de la documentación interna, antes de la auditoría de certificación.'),
             ('h', '2. Alcance y criterios'),
             ('p', 'Todos los procesos del mapa de procesos en la casa matriz de Santiago. Criterios: ISO 9001:2015, manual de calidad, procedimientos e instructivos vigentes y requisitos legales aplicables.'),
             ('h', '3. Equipo auditor'),
             ('ul', ['Auditor líder: Valentina Rojas, Consultor Senior.', 'Auditor: Diego Muñoz, Consultor ISO.',
                     'Auditores internos en formación: dos representantes de Empresa ABC.']),
             ('h', '4. Agenda'),
             ('t', ['Fecha', 'Horario', 'Proceso', 'Cláusulas', 'Auditor', 'Auditado'], [
                 (fmt(D(1, 20)), '09:00 - 09:30', 'Reunión de apertura', '-', 'Equipo auditor', 'Gerencia'),
                 (fmt(D(1, 20)), '09:30 - 11:30', 'Dirección y gestión de la calidad', '4, 5, 6, 9.3', 'Valentina Rojas', 'Gerencia General'),
                 (fmt(D(1, 20)), '11:30 - 13:00', 'Gestión comercial', '8.2', 'Diego Muñoz', 'Gerente Comercial'),
                 (fmt(D(1, 20)), '14:30 - 17:00', 'Operaciones y distribución', '8.1, 8.5, 8.6, 8.7', 'Valentina Rojas', 'Gerente de Operaciones'),
                 (fmt(D(1, 21)), '09:00 - 10:30', 'Compras y proveedores', '8.4', 'Diego Muñoz', 'Jefe de Compras'),
                 (fmt(D(1, 21)), '10:30 - 12:00', 'Recursos humanos', '7.1, 7.2, 7.3', 'Valentina Rojas', 'Jefe de RR.HH.'),
                 (fmt(D(1, 21)), '12:00 - 13:00', 'Control documental y mejora', '7.5, 10', 'Diego Muñoz', 'Encargado de Calidad'),
                 (fmt(D(1, 21)), '16:00 - 17:00', 'Reunión de cierre', '-', 'Equipo auditor', 'Gerencia')])]},
        {'file': '08_Informe_Auditoria_Interna.pdf', 'task': 35, 'kind': 'pdf', 'code': 'INF-AUD-01',
         'title': 'Informe de Auditoría Interna (preliminar)', 'version': '0.1', 'date': D(12, 18), 'blocks': [
             ('h', '1. Estado del informe'),
             ('p', 'Versión preliminar. Contiene los hallazgos levantados en la revisión documental previa a la auditoría interna. Se completará con los resultados de la auditoría en terreno programada para el ' + fmt(D(1, 20)) + ' y el ' + fmt(D(1, 21)) + '.'),
             ('h', '2. Hallazgos preliminares'),
             ('t', ['N°', 'Descripción', 'Clasificación', 'Cláusula', 'Acción comprometida', 'Responsable', 'Estado'], [
                 ('H-01', h1, 'No conformidad menor', '7.2', 'Regularizar registros y establecer control mensual de evidencias.', 'Encargado de Calidad', 'En proceso'),
                 ('H-02', h2, 'Observación', '8.4', 'Crear checklist de evaluación y calendario anual.', 'Jefe de Compras', 'Pendiente')]),
             ('h', '3. Fortalezas observadas'),
             ('ul', ['Compromiso visible de la Gerencia de Operaciones con el proyecto.',
                     'Procedimientos operacionales claros y conocidos por el personal.',
                     'Listado maestro de documentos implementado y en uso.']),
             ('h', '4. Próximos pasos'),
             ('p', 'Ejecutar la auditoría en terreno según el plan PLAN-AUD-01, registrar los hallazgos definitivos y actualizar el plan de acciones correctivas antes de la revisión final del sistema.')]},
        {'file': '09_Registro_Hallazgos.xlsx', 'task': 37, 'kind': 'xlsx', 'sheet': 'Hallazgos',
         'headers': ['N°', 'Fecha de detección', 'Origen', 'Proceso', 'Cláusula', 'Descripción', 'Clasificación', 'Evidencia objetiva', 'Responsable', 'Estado'],
         'rows': [
             ('H-01', fmt(D(12, 18)), 'Revisión documental previa a auditoría interna', 'Recursos Humanos', '7.2', h1, 'No conformidad menor', '6 de 14 colaboradores ingresados en el último trimestre sin registro de inducción firmado', 'Encargado de Calidad', 'En proceso'),
             ('H-02', fmt(D(12, 18)), 'Revisión documental previa a auditoría interna', 'Compras', '8.4', h2, 'Observación', 'Solo 3 de 8 proveedores críticos cuentan con evaluación vigente, en formatos distintos', 'Jefe de Compras', 'Pendiente')],
         'widths': [8, 16, 30, 20, 10, 50, 22, 50, 22, 14]},
        {'file': '10_Plan_Acciones_Correctivas.xlsx', 'task': 39, 'kind': 'xlsx', 'sheet': 'Acciones correctivas',
         'headers': ['Hallazgo', 'Causa raíz', 'Acción correctiva', 'Responsable', 'Fecha compromiso', 'Estado', 'Verificación de eficacia'],
         'rows': [
             ('H-01', 'El proceso de inducción no define quién archiva el registro firmado', 'Regularizar los registros de capacitación pendientes', 'Encargado de Calidad', fmt(D(1, 8)), 'En proceso (4 de 6 regularizados)', 'Revisión de carpetas de personal'),
             ('H-01', 'El proceso de inducción no define quién archiva el registro firmado', 'Establecer control mensual de evidencias de capacitación', 'Encargado de Calidad', fmt(D(1, 15)), 'En proceso', 'Auditoría interna'),
             ('H-02', 'No existen criterios ni frecuencia definidos para evaluar proveedores', 'Crear checklist de evaluación de proveedores críticos', 'Jefe de Compras', fmt(D(1, 22)), 'Pendiente', 'Revisión del checklist aplicado'),
             ('H-02', 'No existen criterios ni frecuencia definidos para evaluar proveedores', 'Definir y publicar calendario anual de evaluación', 'Jefe de Compras', fmt(D(1, 29)), 'Pendiente', 'Auditoría interna')],
         'widths': [10, 46, 46, 22, 16, 30, 30]},
    ]


# ======================================================================= fases
# ------------------------------------------------------------------- idioma
if want('lang'):
    lang = env['res.lang'].with_context(active_test=False).search([('code', '=', LANG)], limit=1)
    if lang and not lang.active:
        env['base.language.install'].create({'lang_ids': [(6, 0, lang.ids)], 'overwrite': False}).lang_install()
        OUT.append('idioma %s instalado' % LANG)
    if lang:
        env['ir.default'].set('res.partner', 'lang', LANG)

# ------------------------------------------------- contabilidad chilena (CLP)
if want('accounting'):
    company = env.company
    clp = env['res.currency'].with_context(active_test=False).search([('name', '=', 'CLP')], limit=1)
    chile = env.ref('base.cl')
    if company.chart_template != 'cl' or company.currency_id != clp:
        moves = env['account.move'].search([('company_id', '=', company.id)])
        alien = [m.name for m in moves if m.partner_id.name != 'Empresa ABC SpA']
        if alien:
            raise UserError('Hay asientos contables ajenos a la demo (%s); no se cambia el plan contable.' % ', '.join(alien))
        pays = env['account.payment'].search([('company_id', '=', company.id)])
        if pays:
            pays.filtered(lambda p: p.state not in ('draft', 'canceled')).action_draft()
            pays.unlink()
        moves = env['account.move'].search([('company_id', '=', company.id)])
        if moves:
            moves.filtered(lambda m: m.state == 'posted').button_draft()
            moves.with_context(force_delete=True).unlink()
        clp.write({'active': True})
        company.write({'country_id': chile.id, 'currency_id': clp.id})
        lists = env['product.pricelist'].with_context(active_test=False).search([('currency_id', '!=', clp.id)])
        if lists:
            lists.write({'currency_id': clp.id})
        env['account.chart.template'].try_loading('cl', company=company, install_demo=False)
        OUT.append('contabilidad: plan chileno y CLP cargados; IVA venta por defecto = %s' % company.account_sale_tax_id.display_name)

# ---------------------------------------- compañía, usuarios, clientes, etapas
def demo_user(xid, name, login, groups, job, cost):
    user = R(xid) or env['res.users'].with_context(active_test=False).search([('login', '=', login)], limit=1)
    vals = {'name': name, 'lang': LG, 'tz': 'America/Santiago', 'group_ids': [(4, env.ref(g).id) for g in groups]}
    if 'tour_enabled' in env['res.users']._fields:
        vals['tour_enabled'] = False
    if user:
        user.write(vals)
        if not R(xid):
            bind(xid, user)
    else:
        vals = dict(vals, login=login, email=login)
        if _pwd:
            vals['password'] = _pwd
        user = env['res.users'].with_context(no_reset_password=True).create(vals)
        bind(xid, user)
    employee = env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
    evals = {'job_title': job, 'hourly_cost': cost, 'work_email': login}
    if employee:
        employee.write(evals)
    else:
        env['hr.employee'].create(dict(evals, name=name, user_id=user.id))
    return user


if want('masters'):
    company = env.company
    chile = env.ref('base.cl')
    rm = env['res.country.state'].search([('country_id', '=', chile.id), ('code', 'in', ['CL-RM', 'RM'])], limit=1)
    LG = LANG if env['res.lang'].search([('code', '=', LANG)], limit=1) else 'en_US'
    PF = env['res.partner']._fields
    rut = env.ref('l10n_cl.it_RUT', raise_if_not_found=False)
    company.write({'name': 'Asesorías ISO'})
    cvals = {'street': 'Av. Apoquindo 1234, Oficina 1203', 'city': 'Las Condes, Santiago', 'state_id': rm.id, 'zip': '7550000',
             'country_id': chile.id, 'phone': '+56 2 2500 2000', 'email': 'contacto@asesoriasiso.demo',
             'website': 'https://www.asesoriasiso.demo', 'lang': LG}
    if 'l10n_cl_sii_taxpayer_type' in PF:
        cvals['l10n_cl_sii_taxpayer_type'] = '1'
        cvals['l10n_cl_activity_description'] = 'Consultoría en sistemas de gestión'
    company.partner_id.write(cvals)

    base_user = env.ref('base.group_user')
    for gx in ['project.group_project_task_dependencies', 'project.group_project_milestone']:
        grp = env.ref(gx, raise_if_not_found=False)
        if grp and grp not in base_user.implied_ids:
            base_user.write({'implied_ids': [(4, grp.id)]})

    demo_user('user_senior', 'Valentina Rojas - Consultor Senior', 'valentina.rojas@asesoriasiso.demo',
              ['project.group_project_manager', 'hr_timesheet.group_hr_timesheet_approver'], 'Consultor Senior ISO', COST['S'])
    demo_user('user_consultor', 'Diego Muñoz - Consultor ISO', 'diego.munoz@asesoriasiso.demo',
              ['project.group_project_user', 'hr_timesheet.group_hr_timesheet_user'], 'Consultor ISO', COST['D'])
    demo_user('user_gerencia', 'Carolina Fuentes - Gerencia', 'carolina.fuentes@asesoriasiso.demo',
              ['project.group_project_manager', 'hr_timesheet.group_timesheet_manager', 'sales_team.group_sale_manager',
               'account.group_account_manager', 'account.group_account_user', 'analytic.group_analytic_accounting',
               'hr.group_hr_user'], 'Gerente General', 0)
    admin_vals = {'lang': LG, 'group_ids': [(4, env.ref('analytic.group_analytic_accounting').id),
                                            (4, env.ref('account.group_account_user').id)]}
    if 'tour_enabled' in env['res.users']._fields:
        admin_vals['tour_enabled'] = False
    env.ref('base.user_admin').write(admin_vals)

    def_ind = env['res.partner.industry']
    ind = {}
    for ikey, iname in [('abc', 'Other Services'), ('b', 'Construction'), ('c', 'IT/Communication'), ('d', 'Manufacturing')]:
        ind[ikey] = def_ind.search([('name', '=', iname)], limit=1)
    avals = {'name': 'Empresa ABC SpA', 'is_company': True, 'street': 'Av. Providencia 1234, Oficina 601',
             'city': 'Santiago', 'state_id': rm.id, 'zip': '7500000', 'country_id': chile.id, 'phone': '+56 2 2400 1000',
             'email': 'contacto@empresaabc.demo', 'website': 'https://www.empresaabc.demo', 'lang': LG,
             'industry_id': ind['abc'].id,
             'comment': '<p><strong>Nombre comercial:</strong> Empresa ABC. Empresa mediana de servicios de logística y '
                        'distribución con 180 colaboradores y casa matriz en Santiago. Cliente del servicio de '
                        'implementación ISO 9001:2015.</p>'}
    if 'l10n_cl_sii_taxpayer_type' in PF:
        avals['l10n_cl_sii_taxpayer_type'] = '1'
        avals['l10n_cl_activity_description'] = 'Servicios de logística y distribución'
        avals['vat'] = '77777777-7'
        if rut:
            avals['l10n_latam_identification_type_id'] = rut.id
    abc = upsert('partner_abc', 'res.partner', avals, adopt=[('name', '=', 'Empresa ABC SpA'), ('is_company', '=', True)])
    upsert('contact_abc_gop', 'res.partner', {'name': 'Marcela Soto', 'parent_id': abc.id, 'type': 'contact',
           'function': 'Gerente de Operaciones', 'email': 'marcela.soto@empresaabc.demo', 'phone': '+56 9 5550 1001', 'lang': LG})
    upsert('contact_abc_cal', 'res.partner', {'name': 'Rodrigo Pizarro', 'parent_id': abc.id, 'type': 'contact',
           'function': 'Encargado de Calidad', 'email': 'rodrigo.pizarro@empresaabc.demo', 'phone': '+56 9 5550 1002', 'lang': LG})
    for pkey, pname, street, phone, cname, cfunc, cmail in [
            ('b', 'Cliente B SpA', 'Av. Vicuña Mackenna 4321', '+56 2 2400 2000', 'Felipe Araya', 'Jefe de Prevención de Riesgos', 'felipe.araya@clienteb.demo'),
            ('c', 'Cliente C Ltda.', 'Av. Nueva Tajamar 555, Piso 9', '+56 2 2400 3000', 'Daniela Vergara', 'Gerente de Tecnología', 'daniela.vergara@clientec.demo'),
            ('d', 'Cliente D S.A.', 'Camino a Melipilla 9876', '+56 2 2400 4000', 'Ignacio Cárdenas', 'Jefe de Medio Ambiente', 'ignacio.cardenas@cliented.demo')]:
        partner = upsert('partner_' + pkey, 'res.partner', {
            'name': pname, 'is_company': True, 'street': street, 'city': 'Santiago', 'state_id': rm.id,
            'country_id': chile.id, 'phone': phone, 'email': 'contacto@cliente%s.demo' % pkey, 'lang': LG,
            'industry_id': ind[pkey].id}, adopt=[('name', '=', pname), ('is_company', '=', True)])
        upsert('contact_%s' % pkey, 'res.partner', {'name': cname, 'parent_id': partner.id, 'type': 'contact',
               'function': cfunc, 'email': cmail, 'lang': LG})

    for code, tname, color in TAGDEF:
        upsert('tag_' + code, 'project.tags', {'name': tname, 'color': color}, adopt=[('name', '=', tname)])
    for code, tname, color in NORMS:
        upsert('norm_' + code, 'project.tags', {'name': tname, 'color': color}, adopt=[('name', '=', tname)])
    seq = 0
    for sname in STAGES:
        seq += 1
        upsert('stage_%d' % seq, 'project.task.type', {'name': sname, 'sequence': seq, 'fold': False},
               adopt=[('name', '=', sname), ('user_id', '=', False)])
    OUT.append('maestros: compañía, 3 usuarios demo, 4 clientes con contactos, etiquetas y 6 etapas')

# ------------------------------------------------- proyecto principal ISO 9001
if want('project'):
    USR = {'S': R('user_senior'), 'D': R('user_consultor')}
    EMP = {'S': env['hr.employee'].search([('user_id', '=', USR['S'].id)], limit=1),
           'D': env['hr.employee'].search([('user_id', '=', USR['D'].id)], limit=1)}
    stage_ids = [R('stage_%d' % i).id for i in range(1, 7)]
    abc = R('partner_abc')
    proj = upsert('proj_abc', 'project.project', {
        'name': PROJECT_NAME, 'partner_id': abc.id, 'user_id': USR['D'].id, 'date_start': D(11, 1), 'date': D(2, 28),
        'allocated_hours': 120, 'allow_timesheets': True, 'allow_task_dependencies': True, 'allow_milestones': True,
        'label_tasks': 'Tareas',
        'tag_ids': [(6, 0, [R('norm_9001').id])], 'type_ids': [(6, 0, stage_ids)], 'description': PROJECT_DESC,
    }, adopt=[('name', '=', PROJECT_NAME)])
    proj.account_id.write({'code': 'ISO9001-EMPRESA-ABC'})
    MS = []
    for mkey, mname, mm, md, reached in [('ms_1', 'Hito 1 · Inicio y Diagnóstico (40 %)', 11, 20, True),
                                         ('ms_2', 'Hito 2 · Implementación y Capacitación (40 %)', 1, 22, False),
                                         ('ms_3', 'Hito 3 · Auditoría interna y Certificación (20 %)', 2, 26, False)]:
        MS.append(upsert(mkey, 'project.milestone', {'name': mname, 'project_id': proj.id, 'deadline': D(mm, md), 'is_reached': reached}))
    MS_BY_STAGE = [MS[0], MS[1], MS[1], MS[1], MS[2], MS[2]]
    T = {}
    for (num, name, st, who, alloc, m, d, status, prio, tg, desc, ent) in MAIN_TASKS:
        html = '<p>' + esc(desc) + '</p>'
        if ent:
            html += '<p><strong>Entregable:</strong> ' + esc(ent) + '</p>'
        T[num] = upsert('task_abc_%02d' % num, 'project.task', {
            'name': name, 'project_id': proj.id, 'stage_id': stage_ids[st], 'user_ids': [(6, 0, [USR[who].id])],
            'allocated_hours': alloc, 'date_deadline': DL(m, d), 'priority': prio,
            'tag_ids': [(6, 0, [R('tag_' + c).id for c in tg])], 'description': html, 'milestone_id': MS_BY_STAGE[st].id,
        }, adopt=[('project_id', '=', proj.id), ('name', '=', name)])
    for blocked, blockers in DEPS.items():
        C(T[blocked]).write({'depend_on_ids': [(6, 0, [T[b].id for b in blockers])]})
    for row in MAIN_TASKS:
        if row[7] == 'D':
            C(T[row[0]]).write({'state': '1_done'})
    for fkey, fname, fm, fd, ftags, frows, factions in FINDINGS:
        finding = upsert('task_abc_' + fkey, 'project.task', {
            'name': fname, 'project_id': proj.id, 'parent_id': False,
            'stage_id': stage_ids[4], 'user_ids': [(6, 0, [USR['D'].id])], 'allocated_hours': 0,
            'date_deadline': DL(fm, fd), 'priority': '2', 'tag_ids': [(6, 0, [R('tag_' + c).id for c in ftags])],
            'description': finding_html(frows), 'milestone_id': MS[2].id})
        k = 0
        for aname, am, ad in factions:
            k += 1
            upsert('task_abc_%s_a%d' % (fkey, k), 'project.task', {
                'name': aname, 'project_id': proj.id, 'parent_id': finding.id, 'stage_id': stage_ids[4],
                'user_ids': [(6, 0, [USR['D'].id])], 'allocated_hours': 0, 'date_deadline': DL(am, ad), 'priority': '1',
                'milestone_id': MS[2].id,
                'description': '<p>Acción correctiva del ' + esc(fname.split(' · ')[0]) + '. La ejecuta el cliente; el consultor verifica la evidencia de cierre.</p>'})
    n = 0
    for (m, d, who, num, hours, text) in MAIN_TS:
        n += 1
        upsert('ts_abc_%02d' % n, 'account.analytic.line', {
            'date': D(m, d), 'name': text, 'employee_id': EMP[who].id, 'project_id': proj.id, 'task_id': T[num].id,
            'unit_amount': hours}, adopt=[('project_id', '=', proj.id)])
    env.flush_all()
    lines = env['account.analytic.line'].search([('project_id', '=', proj.id)])
    done = sum(lines.mapped('unit_amount'))
    plan = sum([T[k].allocated_hours for k in T])
    plan_s = sum([row[4] for row in MAIN_TASKS if row[3] == 'S'])
    if abs(done - 74) > 0.001 or abs(plan - 120) > 0.001 or plan_s != 50:
        raise UserError('Horas del proyecto principal fuera de objetivo: plan %s, senior %s, ejecutadas %s' % (plan, plan_s, done))
    OUT.append('proyecto ISO 9001: %d tareas + %d hallazgos con acciones correctivas, %s h plan, %s h ejecutadas en %d registros' % (len(T), len(FINDINGS), plan, done, len(lines)))

# ------------------------------------------------------------------- cartera
if want('portfolio'):
    USR = {'S': R('user_senior'), 'D': R('user_consultor')}
    EMP = {'S': env['hr.employee'].search([('user_id', '=', USR['S'].id)], limit=1),
           'D': env['hr.employee'].search([('user_id', '=', USR['D'].id)], limit=1)}
    stage_ids = [R('stage_%d' % i).id for i in range(1, 7)]
    main = R('proj_abc')
    for line in env['account.analytic.line'].search([('project_id', '=', main.id)]):
        LOAD[(line.employee_id.id, line.date)] = LOAD.get((line.employee_id.id, line.date), 0) + line.unit_amount
    for P in PORT:
        pr = upsert('proj_' + P['key'], 'project.project', {
            'name': P['name'], 'partner_id': R(P['partner']).id, 'user_id': USR[P['pm']].id,
            'date_start': D(P['start'][0], P['start'][1]), 'date': D(P['end'][0], P['end'][1]),
            'allocated_hours': P['hours'], 'allow_timesheets': True, 'allow_milestones': True, 'label_tasks': 'Tareas',
            'tag_ids': [(6, 0, [R('norm_' + P['norm']).id])], 'type_ids': [(6, 0, stage_ids)],
            'description': '<p>Proyecto de implementación y certificación ' + esc(P['name'].split(' – ')[0].replace('Implementación ', ''))
                           + ' gestionado por Asesorías ISO.</p>',
        }, adopt=[('name', '=', P['name'])])
        pr.account_id.write({'code': P['code']})
        total = 0
        count = 0
        for (key, name, st, who, alloc, exe, m, d, status, prio, wm, wd, chunk, old) in P['tasks']:
            names = [name, old] if old else [name]
            task = upsert('task_%s_%s' % (P['key'], key), 'project.task', {
                'name': name, 'project_id': pr.id, 'stage_id': stage_ids[st], 'user_ids': [(6, 0, [USR[who].id])],
                'allocated_hours': alloc, 'date_deadline': DL(m, d), 'priority': prio,
                'description': '<p>' + esc(name) + '. Actividad de la fase ' + STAGES[st] + ' del proyecto '
                               + esc(P['name']) + '.</p>',
            }, adopt=[('project_id', '=', pr.id), ('name', 'in', names)])
            if status == 'D':
                C(task).write({'state': '1_done'})
            if exe:
                count += spread('ts_%s_%s' % (P['key'], key), pr, task, EMP[who], exe, D(wm, wd), chunk)
                total += exe
        upsert('update_' + P['key'], 'project.update', {
            'name': 'Reporte de avance', 'project_id': pr.id, 'status': P['status'], 'progress': P['progress'],
            'user_id': USR[P['pm']].id, 'date': D(12, 18), 'description': '<p>' + esc(P['update']) + '</p>'})
        OUT.append('cartera %s: %d tareas, %s h plan, %s h ejecutadas en %d registros' % (P['code'], len(P['tasks']), P['hours'], total, count))

# ---------------------------------------------------------------- documentos
if want('docs'):
    proj = R('proj_abc')
    made = 0
    for spec in docs_spec():
        if spec['kind'] == 'pdf':
            data = env['ir.actions.report']._run_wkhtmltopdf(
                [pdf_html(spec)], specific_paperformat_args={'data-report-margin-top': 14, 'data-report-header-spacing': 0})
            mime = 'application/pdf'
        else:
            data = xlsx_bytes(spec['sheet'], spec['headers'], spec['rows'], spec['widths'])
            mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        code = spec['file'][:2]
        task = R('task_abc_%02d' % spec['task'])
        for xid, rec in [('doc_%s_project' % code, proj), ('doc_%s_task' % code, task)]:
            upsert(xid, 'ir.attachment', {'name': spec['file'], 'type': 'binary', 'raw': data, 'mimetype': mime,
                                          'res_model': rec._name, 'res_id': rec.id},
                   adopt=[('res_model', '=', rec._name), ('res_id', '=', rec.id), ('name', '=', spec['file'])])
        made += 1
    OUT.append('documentos: %d entregables (PDF/XLSX) adjuntos al proyecto y a su tarea' % made)

# --------------------------------------------- venta, hitos, factura y pago
if want('sales'):
    company = env.company
    proj = R('proj_abc')
    abc = R('partner_abc')
    tax = company.account_sale_tax_id
    tmpl = upsert('product_iso9001', 'product.template', {
        'name': 'Implementación Sistema de Gestión ISO 9001:2015', 'type': 'service', 'default_code': 'ISO9001-IMPL',
        'list_price': PRICE, 'sale_ok': True, 'purchase_ok': False, 'service_tracking': 'no', 'service_type': 'milestones',
        'invoice_policy': 'delivery', 'taxes_id': [(6, 0, tax.ids)],
        'description_sale': 'Servicio de diagnóstico, planificación, implementación, capacitación, auditoría interna y preparación para certificación ISO 9001:2015.'})
    product = tmpl.product_variant_id
    C(proj).write({'allow_billable': True, 'partner_id': abc.id})
    sovals = {'partner_id': abc.id, 'client_order_ref': 'ISO-ABC-2026'}
    if R('user_gerencia'):
        sovals['user_id'] = R('user_gerencia').id
    term = env.ref('account.account_payment_term_30days', raise_if_not_found=False)
    if term:
        sovals['payment_term_id'] = term.id
    order = upsert('sale_abc', 'sale.order', sovals, adopt=[('partner_id', '=', abc.id), ('client_order_ref', '=', 'ISO-ABC-2026')])
    if order.state in ('draft', 'sent'):
        order._compute_currency_id()
        lvals = {'product_id': product.id, 'product_uom_qty': 1, 'price_unit': PRICE, 'tax_ids': [(6, 0, tax.ids)],
                 'name': 'Implementación Sistema de Gestión ISO 9001:2015\nServicio de diagnóstico, planificación, implementación, capacitación, auditoría interna y preparación para certificación ISO 9001:2015.',
                 'analytic_distribution': {str(proj.account_id.id): 100}}
        if order.order_line:
            order.order_line[0].write(lvals)
        else:
            order.write({'order_line': [(0, 0, lvals)]})
        if 'project_id' in order._fields:
            order.write({'project_id': proj.id})
        order.action_confirm()
        order.write({'date_order': DT(10, 28, 15, 0)})
    line = order.order_line[0]
    C(proj).write({'sale_line_id': line.id})
    for mkey, pct in [('ms_1', 0.4), ('ms_2', 0.4), ('ms_3', 0.2)]:
        R(mkey).write({'sale_line_id': line.id, 'quantity_percentage': pct})
    env.flush_all()
    inv = R('invoice_abc_h1')
    if not inv:
        inv = order._create_invoices()
        bind('invoice_abc_h1', inv)
        inv.write({'invoice_date': D(11, 23)})
        inv.invoice_line_ids.filtered(lambda l: l.display_type == 'product').write({'name': '40% Implementación ISO 9001 – Inicio y Diagnóstico'})
        inv.action_post()
    if inv.state == 'posted' and inv.payment_state in ('not_paid', 'partial'):
        bank = env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1)
        env['account.payment.register'].with_context(active_model='account.move', active_ids=inv.ids).create(
            {'payment_date': D(12, 4), 'journal_id': bank.id}).action_create_payments()
    OUT.append('venta %s (%s): %s neto, total %s | factura %s: neto %s, total %s, estado de pago %s | entregado %s, facturado %s' % (
        order.name, order.state, money(order.amount_untaxed), money(order.amount_total), inv.name, money(inv.amount_untaxed),
        money(inv.amount_total), inv.payment_state, line.qty_delivered, line.qty_invoiced))

# ------------------------- reportes de avance, actividades, chatter y filtros
def activity(xid, rec, type_xid, summary, user, date, text):
    vals = {'summary': summary, 'user_id': user.id, 'date_deadline': date, 'note': '<p>' + esc(text) + '</p>',
            'activity_type_id': env.ref(type_xid).id}
    act = R(xid)
    if act:
        C(act).write(vals)
    else:
        act = C(env['mail.activity']).create(dict(vals, res_model_id=env['ir.model']._get_id(rec._name), res_id=rec.id))
        bind(xid, act)
    return act


def message(xid, rec, author, when, body):
    vals = {'body': body, 'author_id': author.id, 'email_from': author.email_formatted, 'date': when}
    msg = R(xid)
    if msg:
        msg.write(vals)
    else:
        msg = env['mail.message'].create(dict(vals, model=rec._name, res_id=rec.id, message_type='comment',
                                              subtype_id=env.ref('mail.mt_comment').id))
        bind(xid, msg)
    return msg


def favorite(xid, name, model, domain, context, default_action=None):
    vals = {'name': name, 'model_id': model, 'domain': domain, 'context': context, 'user_ids': [(6, 0, [])],
            'is_default': bool(default_action), 'action_id': default_action or False}
    return upsert(xid, 'ir.filters', vals)


if want('extras'):
    senior = R('user_senior')
    consultor = R('user_consultor')
    proj = R('proj_abc')
    WHO = {'S': senior.partner_id, 'D': consultor.partner_id, 'G': R('contact_abc_gop'), 'Q': R('contact_abc_cal')}
    TK = {}
    for row in MAIN_TASKS:
        TK[row[0]] = R('task_abc_%02d' % row[0])
    upsert('update_abc', 'project.update', {
        'name': 'Reporte de avance semanal', 'project_id': proj.id, 'status': 'on_track', 'progress': 62,
        'user_id': consultor.id, 'date': D(12, 18),
        'description': '<p><strong>Avance:</strong> 74 de 120 h ejecutadas (62 %). Diagnóstico y Planificación cerrados; '
                       'Implementación al 70 %; Capacitación iniciada; Auditoría interna planificada.</p>'
                       '<p><strong>Punto de atención:</strong> organigrama actualizado pendiente del cliente para cerrar el manual de calidad.</p>'
                       '<p><strong>Próximos pasos:</strong> cerrar documentación, capacitación de gestión documental y preparación de checklist de auditoría.</p>'})

    activity('act_01', TK[19], 'mail.mail_activity_data_todo', 'Cliente debe enviar organigrama actualizado', consultor, D(12, 21),
             'Necesario para cerrar el capítulo de roles y responsabilidades del manual de calidad.')
    activity('act_02', TK[21], 'mail.mail_activity_data_meeting', 'Revisar matriz de riesgos con Gerencia', senior, D(12, 24),
             'Validar los riesgos altos y sus planes de tratamiento con la Gerencia de Operaciones.')
    activity('act_03', TK[29], 'mail.mail_activity_data_call', 'Confirmar participantes capacitación', consultor, D(12, 23),
             'Confirmar con el Encargado de Calidad la lista de asistentes y la sala.')
    activity('act_04', R('task_abc_h01'), 'mail.mail_activity_data_todo', 'Validar acciones correctivas antes de auditoría', senior, D(1, 12),
             'Revisar la evidencia de regularización de registros antes de la auditoría interna.')
    activity('act_05', proj, 'mail.mail_activity_data_todo', 'Enviar reporte de avance quincenal a Empresa ABC', consultor, D(12, 28),
             'Incluir horas consumidas, hitos y puntos de atención.')
    activity('act_06', R('task_b_06'), 'mail.mail_activity_data_meeting', 'Agendar revisión de avance con Cliente B', senior, D(12, 22),
             'Presentar resultados preliminares del levantamiento de peligros y riesgos.')
    activity('act_07', R('task_d_09'), 'mail.mail_activity_data_todo', 'Solicitar evidencia de cierre de no conformidades', consultor, D(12, 25),
             'Tres no conformidades ambientales pendientes de evidencia.')

    for (xid, rec, who, m, d, hh, mm, body) in [
            ('msg_01', TK[5], 'S', 11, 10, 20, 30, '<p>Gap Analysis consolidado y adjunto (<em>02_Gap_Analysis_ISO9001.xlsx</em>). Resultado: 12 brechas, 3 de criticidad alta: control de documentos (7.5), evaluación de proveedores (8.4) y competencia del personal (7.2).</p>'),
            ('msg_02', TK[5], 'G', 11, 11, 14, 10, '<p>Recibido, muchas gracias. Lo revisaremos con el Encargado de Calidad y enviaremos nuestros comentarios antes de la reunión de revisión.</p>'),
            ('msg_03', TK[5], 'D', 11, 11, 18, 45, '<p>Evidencias de las cláusulas 7 y 8 cargadas en el proyecto. Falta el organigrama actualizado, ya solicitado a RR.HH.</p>'),
            ('msg_04', TK[8], 'S', 11, 17, 21, 0, '<p>Informe de diagnóstico emitido en versión 1.0 (<em>01_Informe_Diagnostico_ISO9001.pdf</em>). Nivel de cumplimiento global: 56 %.</p>'),
            ('msg_05', TK[9], 'G', 11, 19, 19, 30, '<p>Informe revisado y aprobado por Gerencia. Pueden avanzar con el plan de implementación priorizando las tres brechas críticas.</p>'),
            ('msg_06', TK[16], 'G', 12, 3, 17, 20, '<p>Plan de implementación aprobado. Confirmamos la disponibilidad de los dueños de proceso para los talleres de las próximas semanas.</p>'),
            ('msg_07', TK[28], 'D', 12, 15, 20, 0, '<p>Capacitación de introducción a ISO 9001 realizada con 18 asistentes de Operaciones, Bodega y Comercial. Evaluación promedio: 6,3.</p>'),
            ('msg_08', TK[19], 'D', 12, 16, 15, 0, '<p>Manual de calidad en borrador (80 %). Para cerrar el capítulo de roles y responsabilidades necesitamos el organigrama actualizado y los perfiles de cargo vigentes.</p>'),
            ('msg_09', TK[19], 'Q', 12, 17, 13, 40, '<p>RR.HH. está actualizando el organigrama por la reestructuración de Bodega. Lo enviamos a más tardar el lunes.</p>'),
            ('msg_10', R('task_abc_h01'), 'D', 12, 18, 16, 10, '<p>En la revisión de registros se detectó que 6 de 14 colaboradores ingresados en el último trimestre no tienen registro de inducción firmado. Se registra como no conformidad menor (cláusula 7.2).</p>'),
            ('msg_11', R('task_abc_h01'), 'Q', 12, 21, 14, 0, '<p>RR.HH. ya regularizó 4 de los 6 registros. Los 2 restantes corresponden al turno de noche y quedarán firmados esta semana.</p>'),
            ('msg_12', R('task_abc_h02'), 'D', 12, 18, 16, 25, '<p>Solo 3 de 8 proveedores críticos tienen evaluación vigente y en formatos distintos. Se registra como observación (cláusula 8.4) y se propone un checklist único con calendario anual.</p>'),
            ('msg_13', proj, 'S', 11, 20, 21, 30, '<p>Hito 1 <strong>Inicio y Diagnóstico</strong> alcanzado. Se emite la factura por el 40 % del contrato.</p>'),
            ('msg_14', proj, 'D', 12, 18, 21, 0, '<p>Reporte semanal: Implementación al 70 % (28 de 40 h). Primera capacitación realizada con 18 asistentes. Punto de atención: organigrama actualizado pendiente del cliente.</p>')]:
        message(xid, rec, WHO[who], DT(m, d, hh, mm), body)

    # Fechas coherentes en el historial: los avisos automáticos (creación, validación) y las notas
    # que dejó la primera versión del módulo se alinean con el calendario de la demo.
    MM = env['mail.message']
    for pkey in ['abc', 'b', 'c', 'd']:
        pr = R('proj_' + pkey)
        ptasks = env['project.task'].search([('project_id', '=', pr.id)])
        MM.search([('message_type', '!=', 'comment'), '|', '&', ('model', '=', 'project.task'), ('res_id', 'in', ptasks.ids),
                   '&', ('model', '=', 'project.project'), ('res_id', '=', pr.id)]).write(
            {'date': '%s 13:00:00' % (pr.date_start - datetime.timedelta(days=3))})
    found = env['project.task'].search(['|', ('id', 'in', [R('task_abc_h01').id, R('task_abc_h02').id]),
                                        ('parent_id', 'in', [R('task_abc_h01').id, R('task_abc_h02').id])])
    MM.search([('message_type', '!=', 'comment'), ('model', '=', 'project.task'), ('res_id', 'in', found.ids)]).write({'date': DT(12, 18, 16, 0)})
    for (xid, rec, old_text, who, m, d, hh, mm, body) in [
            ('legacy_01', TK[5], 'Gap Analysis entregado', 'S', 11, 9, 21, 30, '<p>Inicio del Gap Analysis: cláusulas 4 a 7 revisadas con Gerencia y RR.HH. Mañana continuamos con operación, desempeño y mejora.</p>'),
            ('legacy_02', TK[37], 'Hallazgo 01', 'D', 12, 18, 16, 30, '<p>Hallazgos 01 y 02 de la revisión documental previa registrados como tareas de esta etapa, con sus acciones correctivas como subtareas.</p>'),
            ('legacy_03', TK[39], 'Hallazgo 02', 'S', 12, 18, 16, 40, '<p>Acciones correctivas preliminares definidas para los hallazgos 01 y 02; se completarán tras la auditoría en terreno.</p>'),
            ('legacy_04', proj, 'Proyecto ISO 9001 iniciado', 'S', 11, 2, 22, 0, '<p>Proyecto ISO 9001 iniciado con la reunión de kick-off. Equipo: Valentina Rojas (Consultor Senior) y Diego Muñoz (Consultor ISO).</p>')]:
        msg = R(xid) or MM.search([('model', '=', rec._name), ('res_id', '=', rec.id), ('body', 'ilike', old_text)], limit=1)
        if msg:
            msg.write({'body': body, 'author_id': WHO[who].id, 'email_from': WHO[who].email_formatted, 'date': DT(m, d, hh, mm)})
            if not R(xid):
                bind(xid, msg)
    order = R('sale_abc')
    inv = R('invoice_abc_h1')
    if order:
        MM.search([('model', '=', 'sale.order'), ('res_id', '=', order.id)]).write({'date': order.date_order})
    if inv:
        MM.search([('model', '=', 'account.move'), ('res_id', '=', inv.id)]).write({'date': '%s 15:00:00' % inv.invoice_date})
        for pay in env['account.payment'].search([('partner_id', '=', inv.partner_id.id)]):
            MM.search(['|', '&', ('model', '=', 'account.payment'), ('res_id', '=', pay.id),
                       '&', ('model', '=', 'account.move'), ('res_id', '=', pay.move_id.id)]).write({'date': '%s 15:00:00' % pay.date})

    for model, en, es in [('project.project', 'Project created', 'Proyecto creado'),
                          ('sale.order', 'Sales Order created', 'Orden de venta creada'),
                          ('account.move', 'Invoice Created', 'Factura creada'),
                          ('account.move', 'Journal Entry created', 'Asiento contable creado'),
                          ('account.move', 'This journal entry has been created from:', 'Este asiento contable se creó desde:'),
                          ('account.payment', 'Payments created', 'Pago creado'),
                          ('res.partner', 'Contact created', 'Contacto creado'),
                          ('product.template', 'Product created', 'Producto creado'),
                          ('hr.employee', 'Employee created', 'Empleado creado')]:
        for msg in MM.search([('model', '=', model), ('message_type', '=', 'notification'), ('body', 'like', en)]):
            msg.write({'body': str(msg.body).replace(en, es)})
    if order:
        for msg in MM.search([('model', '=', 'sale.order'), ('res_id', '=', order.id), ('body', 'like', ' paid')]):
            msg.write({'body': str(msg.body).replace('Invoice ', 'Factura ').replace(' paid', ' pagada')})
    for model, ids in [('project.task', env['project.task'].search([('project_id', 'in', [R('proj_' + k).id for k in ['abc', 'b', 'c', 'd']])]).ids),
                       ('project.project', [R('proj_' + k).id for k in ['abc', 'b', 'c', 'd']])]:
        last = {}
        for msg in MM.search([('model', '=', model), ('res_id', 'in', ids)], order='id'):
            prev = last.get(msg.res_id)
            when = msg.date
            if prev and when < prev:
                when = prev + datetime.timedelta(minutes=1)
                msg.write({'date': when})
            last[msg.res_id] = when

    OPEN = "('state', 'not in', ['1_done', '1_canceled'])"
    TODAY = "context_today().strftime('%Y-%m-%d')"
    if 'favorite_user_ids' in env['project.project']._fields:
        followers = [(4, env.ref('base.user_admin').id)]
        if R('user_gerencia'):
            followers.append((4, R('user_gerencia').id))
        for pkey in ['abc', 'b', 'c', 'd']:
            R('proj_' + pkey).write({'favorite_user_ids': followers})
    favorite('flt_p_mis', 'Mis proyectos ISO', 'project.project',
             "['&', ('tag_ids.name', 'ilike', 'ISO'), '|', ('user_id', '=', uid), ('favorite_user_ids', 'in', [uid])]", '{}')
    favorite('flt_p_activos', 'Proyectos activos', 'project.project', "[('last_update_status', 'not in', ['done', 'on_hold'])]", '{}')
    favorite('flt_p_9001', 'Proyectos ISO 9001', 'project.project', "[('tag_ids.name', 'ilike', 'ISO 9001')]", '{}')
    favorite('flt_p_cliente', 'Cartera por cliente', 'project.project', '[]', "{'group_by': ['partner_id']}")
    favorite('flt_p_resp', 'Cartera por responsable', 'project.project', '[]', "{'group_by': ['user_id']}")
    favorite('flt_t_aud', 'Auditorías pendientes', 'project.task', "[('stage_id.name', '=', 'Auditoría interna'), " + OPEN + "]", '{}')
    favorite('flt_t_atraso', 'Tareas atrasadas', 'project.task', "[('date_deadline', '<', " + TODAY + "), " + OPEN + "]", '{}')
    favorite('flt_t_prio', 'Tareas de alta prioridad', 'project.task', "[('priority', 'in', ['2', '3']), " + OPEN + "]", '{}')
    favorite('flt_t_semana', 'Actividades de esta semana', 'project.task',
             "[('activity_date_deadline', '>=', (context_today() + relativedelta(weeks=-1, days=1, weekday=0)).strftime('%Y-%m-%d')), "
             "('activity_date_deadline', '<=', (context_today() + relativedelta(weekday=6)).strftime('%Y-%m-%d'))]", '{}')
    favorite('flt_t_consultor', 'Consultor ISO', 'project.task', "[('user_ids', 'in', [" + str(consultor.id) + "])]", '{}')
    favorite('flt_t_senior', 'Consultor Senior', 'project.task', "[('user_ids', 'in', [" + str(senior.id) + "])]", '{}')
    favorite('flt_t_proyecto', 'Por proyecto y etapa', 'project.task', '[]', "{'group_by': ['project_id', 'stage_id']}")
    favorite('flt_t_carga', 'Carga por consultor', 'project.task', "[" + OPEN + "]", "{'group_by': ['user_ids', 'project_id']}")
    favorite('flt_t_cliente', 'Por cliente', 'project.task', '[]', "{'group_by': ['partner_id']}")
    favorite('flt_t_fecha', 'Por fecha límite', 'project.task', "[" + OPEN + "]", "{'group_by': ['date_deadline:week']}")
    favorite('flt_t_todas', 'Metodología ISO (todas las tareas)', 'project.task', '[]', '{}',
             env.ref('project.act_project_project_2_project_task_all').id)
    OUT.append('extras: reporte de avance, 7 actividades, 14 mensajes de chatter y 16 filtros favoritos')

# ------------------------------------------- limpieza de la cola de correos
if want('cleanup'):
    if not env['ir.mail_server'].search_count([]):
        queued = env['mail.mail'].search([('state', 'in', ['outgoing', 'exception'])])
        if queued:
            queued.write({'state': 'cancel'})
            OUT.append('correo: %d notificaciones a direcciones demo canceladas (no hay servidor de correo)' % len(queued))

action = {'type': 'ir.actions.act_window_close', 'infos': OUT}
