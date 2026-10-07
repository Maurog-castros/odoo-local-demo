import os

from odoo.tools import file_open

BUILDER = "iso_demo/scripts/build_demo.py"


def post_init_hook(env):
    """Construye la demo ISO al instalar el módulo en una base nueva.

    Toda la lógica vive en scripts/build_demo.py, un script ORM idempotente
    que también se puede volver a ejecutar con scripts/rebuild_demo.ps1.
    La contraseña de los usuarios demo se lee de la variable de entorno
    ISO_DEMO_PASSWORD; si no existe, los usuarios se crean sin contraseña.
    """
    with file_open(BUILDER, "r") as handle:
        source = handle.read()
    env = env(context=dict(env.context, iso_demo_password=os.environ.get("ISO_DEMO_PASSWORD")))
    exec(compile(source, BUILDER, "exec"), {"env": env})
    _set_app_launcher_as_home(env)


def _set_app_launcher_as_home(env):
    """Abre el launcher visual al iniciar sesión en una base creada desde cero."""
    action = env.ref("iso_demo.action_app_launcher", raise_if_not_found=False)
    if action:
        env["res.users"].search([("share", "=", False), ("active", "=", True)]).action_id = action
