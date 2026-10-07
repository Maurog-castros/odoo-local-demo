import base64
from datetime import date, timedelta


def _user(env, name, login):
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if not user:
        user = env["res.users"].with_context(no_reset_password=True).create({
            "name": name,
            "login": login,
            "password": "demo2026",
            "group_ids": [(4, env.ref("base.group_user").id)],
        })
    employee = env["hr.employee"].search([("user_id", "=", user.id)], limit=1)
    if not employee:
        employee = env["hr.employee"].create({"name": name, "user_id": user.id, "work_email": login})
    return user, employee


def _partner(env, name, **values):
    partner = env["res.partner"].search([("name", "=", name)], limit=1)
    return partner or env["res.partner"].create({"name": name, "company_type": "company", **values})


def _stage(env, name, sequence):
    stage = env["project.task.type"].search([("name", "=", name)], limit=1)
    return stage or env["project.task.type"].create({"name": name, "sequence": sequence})


def _task(env, project, stage, title, user, hours, offset, priority="1"):
    return env["project.task"].create({
        "name": title,
        "project_id": project.id,
        "stage_id": stage.id,
        "user_ids": [(6, 0, [user.id])],
        "allocated_hours": hours,
        "priority": priority,
        "date_deadline": f"2026-11-{min(28, 3 + offset):02d} 18:00:00",
        "description": (
            f"<p>Entregable ISO 9001:2015 para Empresa ABC. {title}. "
            "Registrar evidencia, responsable, fecha de revisión y acuerdo con el cliente.</p>"
        ),
    })


def post_init_hook(env):
    if env["project.project"].search_count([("name", "=", "Implementación ISO 9001:2015 – Empresa ABC")]):
        return

    senior, senior_employee = _user(env, "Valentina Rojas - Consultor Senior", "valentina.rojas@asesoriasiso.demo")
    consultant, consultant_employee = _user(env, "Diego Muñoz - Consultor ISO", "diego.munoz@asesoriasiso.demo")
    abc = _partner(env, "Empresa ABC SpA", street="Av. Providencia 1234, Oficina 601", city="Santiago", email="contacto@empresaabc.demo", phone="+56 2 2400 1000")
    _partner(env, "Cliente B SpA", city="Santiago", email="contacto@clienteb.demo")
    _partner(env, "Cliente C Ltda.", city="Santiago", email="contacto@clientec.demo")
    _partner(env, "Cliente D S.A.", city="Santiago", email="contacto@cliented.demo")

    stages = {name: _stage(env, name, sequence) for sequence, name in enumerate([
        "Diagnóstico", "Planificación", "Implementación", "Capacitación", "Auditoría interna", "Certificación"
    ], 1)}
    project = env["project.project"].create({
        "name": "Implementación ISO 9001:2015 – Empresa ABC",
        "partner_id": abc.id,
        "user_id": senior.id,
        "date_start": date(2026, 11, 1),
        "date": date(2027, 2, 28),
        "allocated_hours": 120,
        "allow_timesheets": True,
        "type_ids": [(6, 0, [stage.id for stage in stages.values()])],
    })
    project.message_post(body="Proyecto ISO 9001 iniciado. Diagnóstico y planificación cerrados; implementación en ejecución.")

    specs = {
        "Diagnóstico": ["Reunión Kick-Off", "Solicitar antecedentes al cliente", "Levantar procesos actuales", "Definir alcance del sistema de gestión", "Ejecutar Gap Analysis", "Identificar brechas", "Clasificar brechas por criticidad", "Elaborar informe de diagnóstico", "Reunión de revisión con cliente"],
        "Planificación": ["Crear plan de implementación", "Definir responsables", "Construir matriz de requisitos ISO 9001", "Definir cronograma", "Planificar documentación", "Identificar riesgos del proyecto", "Validar plan con cliente"],
        "Implementación": ["Diseñar mapa de procesos", "Definir procedimientos", "Crear documentación", "Implementar control documental", "Implementar gestión de riesgos", "Implementar tratamiento de no conformidades", "Validar procesos", "Revisar registros", "Revisar evidencias", "Ejecutar acciones pendientes"],
        "Capacitación": ["Preparar material de capacitación", "Capacitación introducción ISO 9001", "Capacitación gestión documental", "Capacitación auditoría interna", "Registrar asistencia", "Evaluar capacitación"],
        "Auditoría interna": ["Crear plan de auditoría", "Preparar checklist", "Ejecutar auditoría interna", "Registrar observaciones", "Registrar hallazgos", "Registrar no conformidades", "Definir acciones correctivas", "Asignar responsables", "Verificar evidencias", "Verificar cierre de hallazgos"],
        "Certificación": ["Revisión final del sistema", "Preparar documentación para auditor externo", "Revisar evidencias finales", "Preparar equipo del cliente", "Simulación de auditoría", "Acompañamiento auditoría de certificación", "Resolver observaciones finales", "Cerrar proyecto"],
    }
    tasks = {}
    offset = 0
    for phase, titles in specs.items():
        for title in titles:
            offset += 1
            owner = senior if phase in ("Diagnóstico", "Planificación") or (phase == "Auditoría interna" and title != "Verificar cierre de hallazgos") else consultant
            hours = 4 if phase == "Implementación" else 2
            tasks[title] = _task(env, project, stages[phase], title, owner, hours, offset, "3" if "Gap" in title or "hallazgos" in title.lower() else "1")
    tasks["Ejecutar Gap Analysis"].message_post(body="Gap Analysis entregado; 12 brechas priorizadas para el plan de implementación.")
    tasks["Registrar hallazgos"].message_post(body="Hallazgo 01: registros de capacitación incompletos. Acción: control mensual de evidencias.")
    tasks["Definir acciones correctivas"].message_post(body="Hallazgo 02: revisión anual de proveedores críticos sin evidencia uniforme. Acción: checklist y calendario anual.")

    entries = [
        ("Reunión Kick-Off", senior_employee, 6), ("Levantar procesos actuales", senior_employee, 8),
        ("Ejecutar Gap Analysis", senior_employee, 12), ("Elaborar informe de diagnóstico", senior_employee, 8),
        ("Crear plan de implementación", senior_employee, 6), ("Validar plan con cliente", senior_employee, 4),
        ("Definir procedimientos", consultant_employee, 8), ("Crear documentación", consultant_employee, 8),
        ("Implementar control documental", consultant_employee, 6), ("Implementar gestión de riesgos", consultant_employee, 4),
        ("Capacitación introducción ISO 9001", consultant_employee, 4),
    ]
    today = date(2026, 11, 3)
    for index, (title, employee, hours) in enumerate(entries):
        env["account.analytic.line"].create({
            "name": f"ISO 9001 | {title}", "date": today + timedelta(days=index), "unit_amount": hours,
            "employee_id": employee.id, "project_id": project.id, "task_id": tasks[title].id,
        })

    for name, partner_name, phase in [
        ("Implementación ISO 45001:2018 – Cliente B", "Cliente B SpA", "Diagnóstico"),
        ("Implementación ISO 27001:2022 – Cliente C", "Cliente C Ltda.", "Implementación"),
        ("Implementación ISO 14001:2015 – Cliente D", "Cliente D S.A.", "Auditoría interna"),
    ]:
        partner = env["res.partner"].search([("name", "=", partner_name)], limit=1)
        portfolio = env["project.project"].create({"name": name, "partner_id": partner.id, "user_id": consultant.id, "allow_timesheets": True, "type_ids": [(6, 0, [stage.id for stage in stages.values()])]})
        _task(env, portfolio, stages[phase], f"{phase} inicial", consultant, 8, 10)
        _task(env, portfolio, stages[phase], "Revisión de avance con cliente", senior, 4, 12)

    attachment_names = ["01_Informe_Diagnostico_ISO9001.pdf", "02_Gap_Analysis_ISO9001.xlsx", "03_Plan_Implementacion_ISO9001.pdf", "04_Mapa_Procesos.pdf", "05_Procedimiento_Control_Documentos.pdf", "06_Matriz_Riesgos.xlsx", "07_Plan_Auditoria_Interna.pdf", "08_Informe_Auditoria_Interna.pdf", "09_Registro_Hallazgos.xlsx", "10_Plan_Acciones_Correctivas.xlsx"]
    for filename in attachment_names:
        env["ir.attachment"].create({"name": filename, "type": "binary", "datas": base64.b64encode(f"Documento demo ISO 9001 - {filename}".encode()), "res_model": "project.project", "res_id": project.id, "mimetype": "text/plain"})

    order = env["sale.order"].create({"partner_id": abc.id, "client_order_ref": "ISO-ABC-2026", "order_line": [(0, 0, {"name": "Implementación Sistema de Gestión ISO 9001:2015", "product_uom_qty": 1, "price_unit": 6000000})]})
    env["account.move"].create({"move_type": "out_invoice", "partner_id": abc.id, "invoice_date": date(2026, 11, 1), "invoice_origin": order.name, "invoice_line_ids": [(0, 0, {"name": "40% Implementación ISO 9001 – Inicio y Diagnóstico", "quantity": 1, "price_unit": 2400000})]})
