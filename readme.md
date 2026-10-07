# Odoo Local Demo — Docker Compose

Ambiente Odoo con containers separados para desarrollo local.

## Arquitectura

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Nginx     │     │   Odoo       │     │  PostgreSQL  │
│  (puerto 80)│────▶│  (puerto     │────▶│  (puerto     │
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
| Admin pass | `Admin123`  |
| DB name    | `odoo_db`   |
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
    └── mi_modulo/        # Módulos personalizados (live reload)
```

## Crear un módulo personalizado

1. Crea un directorio bajo `my_addons/`
2. Agrega `__manifest__.py` con la metadata
3. Reinicia Odoo: `docker compose restart odoo`
4. Actívalo en **Apps > Update Apps List > Install**

## Notas

- Los módulos en `my_addons/` se montan como volumen → cambios en código se reflejan al reiniciar Odoo
- Los datos de PostgreSQL persisten en un Docker volume (`postgres_data`)
- Nginx maneja estáticos, gzip, y WebSocket para longpolling
