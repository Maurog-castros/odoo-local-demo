# Odoo Local Demo — Docker Compose

Ambiente Odoo 19 Community con containers separados para desarrollo local.

## Arquitectura

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Nginx     │     │   Odoo       │     │  PostgreSQL  │
│  (puerto 80)│───▶│  (puerto     │───▶│  (puerto     │
│  Frontend   │     │   8069)      │     │   5432)      │
│  Proxy      │     │  Backend     │     │  Database    │
└─────────────┘     └──────────────┘     └──────────────┘
```

## Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo
- PowerShell (Windows) o bash (Linux/Mac)

## Uso rápido

```powershell
# Levantar todo
.\start.ps1

# Detener todo
docker compose down

# Ver logs en tiempo real
docker compose logs -f odoo

# Reiniciar
docker compose restart
```

## URLs

| Servicio    | URL                  |
|-------------|----------------------|
| Frontend    | http://localhost     |
| Backend     | http://localhost:8069|
| PostgreSQL  | localhost:5432       |

## Credenciales

| Campo      | Valor       |
|------------|-------------|
| Usuario inicial | `admin` |
| Contraseña inicial | `admin` |
| Contraseña maestra de BD | Configurada en `odoo.conf` |
| DB name    | `odoo_demo_19`   |
| DB user    | `odoo_user` |
| DB pass    | `odoo_pass` |

## Estructura

```
.
├── docker-compose.yml    # Definición de servicios
├── odoo.conf             # Configuración de Odoo
├── start.ps1             # Script de inicio
├── nginx/
│   └── conf.d/
│       └── default.conf  # Reverse proxy config
└── my_addons/
    ├── mi_modulo/        # Addon mínimo de ejemplo
    └── iso_demo/         # Demo ISO: hooks.py + scripts/build_demo.py
```

## Demo ISO

El módulo `iso_demo` construye una demo comercial para la consultora **Asesorías ISO**: compañía chilena (CLP, IVA 19 %), cuatro proyectos ISO, tareas, horas, documentos, venta, factura y pago.

- Toda la lógica está en `my_addons/iso_demo/scripts/build_demo.py`, un script ORM idempotente: cada registro lleva un XML-ID de `iso_demo`, así que volver a ejecutarlo actualiza en vez de duplicar.
- En una base nueva lo ejecuta `hooks.post_init_hook` al instalar el módulo.
- Sobre una base existente se vuelve a ejecutar con `./scripts/rebuild_demo.ps1`.

### Mover el calendario de la demo

Las fechas están escritas en el calendario original (proyecto ISO 9001 del 01/11/2026 al 28/02/2027) y se adelantan `SHIFT_WEEKS` semanas (11 por defecto) para que el proyecto se vea en ejecución. Para cambiarlo:

```powershell
./scripts/rebuild_demo.ps1 -ShiftWeeks 12
```

La factura y el pago ya emitidos conservan su fecha.

### Usuarios demo

| Usuario | Rol |
|---------|-----|
| `diego.munoz@asesoriasiso.demo` | Consultor ISO |
| `valentina.rojas@asesoriasiso.demo` | Consultor Senior |
| `carolina.fuentes@asesoriasiso.demo` | Gerencia |

La contraseña es la de la variable `ISO_DEMO_PASSWORD` de `docker-compose.yml`.

## Crear un módulo personalizado

1. Crea un directorio bajo `my_addons/`
2. Agrega `__manifest__.py` con la metadata
3. Reinicia Odoo: `docker compose restart odoo`
4. Actívalo en **Apps > Update Apps List > Install**

## Notas

- Los módulos en `my_addons/` se montan como volumen → cambios en código se reflejan al reiniciar Odoo
- Los datos de PostgreSQL persisten en un Docker volume (`postgres_data_19`)
- La demo ISO se instala automáticamente junto con el stack (ver sección "Demo ISO").
- Nginx maneja estáticos, gzip, y WebSocket para longpolling
