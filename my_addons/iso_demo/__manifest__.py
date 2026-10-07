{
    "name": "ISO Consulting Demo",
    "version": "19.0.2.0.0",
    "summary": "Demo comercial reproducible para una consultora ISO",
    "category": "Services/Project",
    "author": "Asesorias ISO Demo",
    "license": "LGPL-3",
    "depends": [
        "web",
        "project",
        "hr_timesheet",
        "hr_hourly_cost",
        "analytic",
        "account",
        "l10n_cl",
        "contacts",
        "sale_management",
        "sale_timesheet",
    ],
    "data": [
        "views/app_launcher.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "iso_demo/static/src/app_launcher/app_launcher.js",
            "iso_demo/static/src/app_launcher/app_launcher.xml",
            "iso_demo/static/src/app_launcher/app_launcher.scss",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
