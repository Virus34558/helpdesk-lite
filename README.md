# HelpDesk Lite - ITSM

[![Tests](https://github.com/Virus34558/helpdesk-lite/actions/workflows/tests.yml/badge.svg)](https://github.com/Virus34558/helpdesk-lite/actions/workflows/tests.yml)

Sistema de gestión de incidencias IT inspirado en la herramienta interna de un departamento de soporte. Desarrollado con **FastAPI** y **SQLAlchemy**: roles de usuario, autenticación **JWT**, prioridad calculada con la matriz **ITIL** y un flujo de estados con reglas.

**Demo en vivo:** https://helpdesk-lite-6x8a.onrender.com

> La demo está en un plan gratuito: si lleva un rato sin visitas, la primera carga puede tardar alrededor de un minuto en despertar. Es una demo pública: regístrate con una contraseña que no uses en ningún otro sitio y no introduzcas datos reales. Los usuarios nuevos se crean con el rol `solicitante`.

![Captura de la aplicación](docs/captura.png)

## Qué permite hacer

### Gestión de incidencias
- Crear tickets con título, descripción, tipo y canal de origen.
- **Identificador único legible e indexado:** generación automática de códigos amigables según el tipo (ej: `INC-2026-000001` para Incidencias, `REQ-2026-000001` para Solicitudes de Servicio).
- **Tipología ITSM:** `Incidencia`, `Solicitud de Servicio`, `Problema` y `Cambio`.
- **Canales de origen:** `Portal Web`, `Email`, `API / Monitoreo`, `Teléfono`, `Chat`.
- **Asignación de técnicos:** asignación de incidencias a agentes con validación de rol (un solicitante no puede ser asignado). Al asignarse desde `Nuevo`, transiciona automáticamente a `En progreso`.
- **Prioridad calculada automáticamente** a partir de impacto y urgencia (matriz ITIL, P1 a P4).
- **Flujo de estados con reglas:** Nuevo, En progreso, Pendiente de usuario, Pendiente de tercero, Resuelto, Cerrado y Cancelado. Las transiciones no permitidas se rechazan con `409 Conflict`.
- Para resolver una incidencia es **obligatorio** escribir una nota de resolución (causa raíz y solución).
- **Inmutabilidad total:** Cerrado y Cancelado son estados finales e inmutables (se bloquea cualquier modificación o asignación).
- **Filtros completos:** por estado, prioridad, tipo de ticket, técnico asignado (`?agente_asignado_id=`) o tickets sin asignar (`?sin_asignar=true`).
- **Búsqueda flexible:** consulta por ID numérico (`/incidencias/1`) o por código legible (`/incidencias/INC-2026-000001`).
- **Comunicación dual en hilo cronológico:** respuestas públicas para interactuar con el solicitante y notas internas privadas confidenciales exclusivas para el equipo técnico.
- **Reactivación automática (ITIL):** cuando un solicitante responde a una incidencia en estado `Pendiente de usuario`, esta pasa automáticamente a `En progreso`.
- **Historial de auditoría inmutable:** línea de tiempo inalterable que registra automáticamente quién hizo qué y cuándo (creación, transiciones de estado, cambios de prioridad, asignación de técnicos, resolución y comentarios).

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
- **pytest**: 91 tests automáticos (incidencias, autenticación, permisos, asignación, reglas ITIL, notas internas, seguridad y auditoría inmutable)
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
| Crear incidencia / ticket | `POST /incidencias` | Autenticado |
| Listar (con filtros: estado, prioridad, tipo, agente, sin asignar) | `GET /incidencias?estado=Nuevo&prioridad=P1 - Crítica&tipo=Incidencia&sin_asignar=true` | Autenticado (el solicitante solo ve las suyas) |
| Consultar una (por ID numérico o código legible) | `GET /incidencias/{id_o_codigo}` | Autenticado (idem) |
| Asignar o desasignar técnico | `POST /incidencias/{id_o_codigo}/asignar` | `agente`, `supervisor`, `administrador` |
| Actualizar estado, impacto o urgencia | `PATCH /incidencias/{id_o_codigo}` | `agente`, `supervisor`, `administrador` |
| Resolver (con nota obligatoria) | `POST /incidencias/{id_o_codigo}/resolver` | `agente`, `supervisor`, `administrador` |
| Añadir comentario (público o nota interna) | `POST /incidencias/{id_o_codigo}/comentarios` | Autenticado (nota interna solo técnicos) |
| Listar hilo de comentarios | `GET /incidencias/{id_o_codigo}/comentarios` | Autenticado (solicitante no ve notas internas) |
| Consultar historial de auditoría | `GET /incidencias/{id_o_codigo}/historial` | Autenticado (solicitante no ve eventos internos) |

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
|   |-- auditoria.py     # Helper de registro inmutable de auditoría
|   |-- auth.py          # bcrypt, JWT y dependencias de permisos
|   |-- database.py      # Conexión a la base de datos
|   |-- main.py          # Aplicación FastAPI y endpoints de incidencias
|   |-- models.py        # Modelos (Usuario, Incidencia, Comentario, RegistroAuditoria)
|   |-- reglas.py        # Matriz ITIL y máquina de estados
|   |-- schemas.py       # Validación de datos (Pydantic)
|   `-- static/
|       `-- index.html   # Interfaz web
|-- tests/
|   |-- test_auditoria.py          # Tests de historial y trazabilidad inmutable
|   |-- test_auth.py               # Tests de autenticación y RBAC
|   |-- test_comentarios.py        # Tests de respuestas públicas y notas internas
|   |-- test_incidencias.py        # Tests de tickets, estados y asignación
|   |-- test_reglas.py             # Tests de matriz ITIL y máquina de estados
|   `-- test_seguridad_tickets.py  # Tests de permisos y restricciones de seguridad
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
- [x] Bloquear por completo la edición de tickets en estado Cerrado o Cancelado
- [x] Identificador legible (`INC-2026-000142`, `REQ-2026-000001`), tipología de tickets y canales de origen
- [x] Asignación de incidencias a agentes (con validación de rol, auto-transición y filtros)
- [x] Comentarios públicos y notas internas (comunicación dual)
- [x] Historial de auditoría inmutable
- [ ] SLA con calendario laboral y pausas
- [ ] Base de Conocimiento (Knowledge Base)
- [ ] Dashboard con KPIs y exportación a CSV
- [ ] Migraciones con Alembic
- [ ] Paginación y búsqueda全文

## Autor

Hecho por [Virus34558](https://github.com/Virus34558) como proyecto de portfolio.