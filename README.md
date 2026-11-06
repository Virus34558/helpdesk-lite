# HelpDesk Lite - ITSM

[![Tests](https://github.com/Virus34558/helpdesk-lite/actions/workflows/tests.yml/badge.svg)](https://github.com/Virus34558/helpdesk-lite/actions/workflows/tests.yml)

Sistema de gestión de incidencias IT inspirado en la herramienta interna de un departamento de soporte. Desarrollado con **FastAPI** y **SQLAlchemy**: roles de usuario, autenticación **JWT**, prioridad calculada con la matriz **ITIL** y un flujo de estados con reglas.

**Demo en vivo:** https://helpdesk-lite-6x8a.onrender.com

> La demo está en un plan gratuito: si lleva un rato sin visitas, la primera carga puede tardar alrededor de un minuto en despertar. Es una demo pública: regístrate con una contraseña que no uses en ningún otro sitio y no introduzcas datos reales. Los usuarios nuevos se crean con el rol `solicitante`.

![Captura de la aplicación](docs/captura.png)

## Qué permite hacer

### Gestión de incidencias
- Crear incidencias con título y descripción.
- **Prioridad calculada automáticamente** a partir de impacto y urgencia (matriz ITIL, P1 a P4).
- **Flujo de estados con reglas:** Nuevo, En progreso, Pendiente de usuario, Pendiente de tercero, Resuelto, Cerrado y Cancelado. Las transiciones no permitidas se rechazan.
- Para resolver una incidencia es **obligatorio** escribir una nota de resolución (causa y solución).
- Cerrado y Cancelado son estados finales: no se puede volver a abrir.
- Filtrar por estado y por prioridad.

### Usuarios y control de acceso (RBAC)
- **4 roles:** `solicitante` (usuario final), `agente`, `supervisor` y `administrador`.
- Contraseñas con **bcrypt** y sesiones con **JWT** (Bearer, HS256) con caducidad.
- Un **solicitante** solo ve sus propias incidencias y no puede fijar impacto ni urgencia.
- Solo agentes, supervisores y administradores pueden cambiar el estado o resolver.
- El registro público siempre crea un `solicitante`. Solo un administrador puede cambiar roles.
- El primer administrador se crea con la variable `ADMIN_EMAIL`. Si no está definida (por ejemplo en local), el primer usuario registrado es administrador.

### Matriz de prioridad (ITIL)

| Impacto \ Urgencia | Crítica | Alta | Media | Baja |
|---|---|---|---|---|
| **Alto** | P1 | P1 | P2 | P3 |
| **Medio** | P1 | P2 | P3 | P4 |
| **Bajo** | P2 | P3 | P4 | P4 |

## Tecnologías

- **Python** y **FastAPI**: API REST con documentación OpenAPI en `/docs`
- **SQLAlchemy 2.0**: acceso a la base de datos
- **SQLite** en local y **PostgreSQL** (`psycopg`) en producción
- **bcrypt** y **PyJWT**: contraseñas y autenticación
- **HTML, CSS y JavaScript** sin frameworks para la interfaz
- **pytest**: 53 tests automáticos (incidencias, autenticación, permisos y reglas ITIL)
- **GitHub Actions**: ejecuta los tests en cada subida
- **Docker**: contenedor basado en `python:3.13-slim`
- **Render**: despliegue en la nube

## API

Todas las rutas de `/incidencias` requieren un token (`Authorization: Bearer <token>`).

### Autenticación y usuarios (`/auth`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Registrar usuario | `POST /auth/registro` | Público |
| Iniciar sesión (obtener JWT) | `POST /auth/login` | Público |
| Ver mi perfil | `GET /auth/me` | Autenticado |
| Listar usuarios | `GET /auth/usuarios` | `supervisor`, `administrador` |
| Cambiar rol de un usuario | `PATCH /auth/usuarios/{id}/rol` | `administrador` |

### Incidencias (`/incidencias`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Crear incidencia | `POST /incidencias` | Autenticado |
| Listar (con filtros) | `GET /incidencias?estado=Nuevo&prioridad=P1 - Crítica` | Autenticado (el solicitante solo ve las suyas) |
| Consultar una | `GET /incidencias/{id}` | Autenticado (idem) |
| Actualizar estado, impacto o urgencia | `PATCH /incidencias/{id}` | `agente`, `supervisor`, `administrador` |
| Resolver (con nota obligatoria) | `POST /incidencias/{id}/resolver` | `agente`, `supervisor`, `administrador` |

Documentación interactiva en `/docs`:

![Documentación de la API](docs/api-docs.png)

## Ejecutar en local

```bash
git clone https://github.com/Virus34558/helpdesk-lite.git
cd helpdesk-lite
python -m venv venv
venv\Scripts\activate        # En Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abre http://127.0.0.1:8000. El primer usuario que registres será administrador.

## Configuración (variables de entorno)

| Variable | Para qué sirve | Si no existe |
|---|---|---|
| `DATABASE_URL` | Dirección de la base de datos (PostgreSQL en producción) | Usa SQLite local (`helpdesk.db`) |
| `SECRET_KEY` | Clave con la que se firman los tokens JWT | Se genera una aleatoria en cada arranque (las sesiones se pierden al reiniciar) |
| `ADMIN_EMAIL` | Único correo que puede convertirse en el primer administrador | El primer usuario registrado es administrador |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración de la sesión | 1440 (24 horas) |

En producción, `SECRET_KEY` debe ser una cadena larga y aleatoria, y nunca debe subirse al repositorio.

## Ejecutar con Docker

```bash
docker build -t helpdesk-lite .
docker run -p 8000:8000 helpdesk-lite
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

Los tests usan una base de datos temporal en memoria, sin tocar los datos locales.

## Estructura

```
helpdesk-lite/
|-- app/
|   |-- routers/
|   |   `-- auth.py      # Endpoints de autenticación y usuarios
|   |-- auth.py          # bcrypt, JWT y dependencias de permisos
|   |-- database.py      # Conexión a la base de datos
|   |-- main.py          # Aplicación FastAPI y endpoints de incidencias
|   |-- models.py        # Modelos (Usuario, Incidencia)
|   |-- reglas.py        # Matriz ITIL y máquina de estados
|   |-- schemas.py       # Validación de datos (Pydantic)
|   `-- static/
|       `-- index.html   # Interfaz web
|-- tests/               # Tests con pytest
|-- docs/                # Capturas del README
|-- .github/workflows/   # GitHub Actions
|-- Dockerfile
|-- requirements.txt
|-- requirements-dev.txt
`-- README.md
```

## Roadmap

Es un proyecto de aprendizaje basado en una especificación de requisitos de un helpdesk ITSM. Estado actual:

- [x] Autenticación y roles (`solicitante`, `agente`, `supervisor`, `administrador`)
- [x] Matriz ITIL (impacto x urgencia = prioridad P1 a P4)
- [x] Máquina de estados con 7 estados y nota de resolución obligatoria
- [ ] Bloquear por completo la edición de tickets en estado Cerrado
- [ ] Identificador legible (`INC-2026-000142`), tipo de ticket y categorías
- [ ] Asignación de incidencias a agentes
- [ ] Comentarios públicos y notas internas
- [ ] Historial de auditoría inmutable
- [ ] SLA con calendario laboral y pausas
- [ ] Dashboard con KPIs y exportación a CSV
- [ ] Migraciones con Alembic
- [ ] Paginación y búsqueda

## Autor

Hecho por [Virus34558](https://github.com/Virus34558) como proyecto de portfolio.