#!/usr/bin/env pwsh
# Reconstruye o actualiza la demo ISO en la base en ejecucion (idempotente:
# actualiza los registros existentes, no los duplica).
#
#   .\scripts\rebuild_demo.ps1                 # usa SHIFT_WEEKS definido en build_demo.py
#   .\scripts\rebuild_demo.ps1 -ShiftWeeks 12  # mueve el calendario de la demo
#
# ShiftWeeks = semanas que se adelanta el calendario original (inicio 01/11/2026).
# La factura y el pago ya emitidos conservan su fecha.
param(
    [int]$ShiftWeeks = -1,
    [string]$Database = "odoo_demo_19"
)

$shift = ""
if ($ShiftWeeks -ge 0) { $shift = ", iso_shift_weeks=$ShiftWeeks" }

$code = @"
import os
env = env(context=dict(env.context, iso_demo_password=os.environ.get('ISO_DEMO_PASSWORD')$shift))
exec(open('/mnt/addons/iso_demo/scripts/build_demo.py', encoding='utf-8').read())
env.cr.commit()
print('\n'.join(OUT))
"@

$code | docker compose exec -T odoo odoo shell -d $Database --no-http
