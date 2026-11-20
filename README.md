# HelpDesk Lite - ITSM

[![Tests](https://github.com/Virus34558/helpdesk-lite/actions/workflows/tests.yml/badge.svg)](https://github.com/Virus34558/helpdesk-lite/actions/workflows/tests.yml)

Sistema de gestión de incidencias IT inspirado en la herramienta interna de un departamento de soporte. Desarrollado con **FastAPI** y **SQLAlchemy**: roles de usuario, autenticación **JWT**, prioridad calculada con la matriz **ITIL**, un flujo de estados con reglas y **SLAs con calendario laboral y pausas**.

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
- **Filtros completos:** por estado, prioridad, tipo de ticket, técnico asignado (`?agente_asignado_id=`), tickets sin asignar (`?sin_asignar=true`), SLA vencido (`?sla_vencido=true`) y SLA en riesgo (`?sla_en_riesgo=true`).
- **Búsqueda flexible:** consulta por ID numérico (`/incidencias/1`) o por código legible (`/incidencias/INC-2026-000001`).
- **Comunicación dual en hilo cronológico:** respuestas públicas para interactuar con el solicitante y notas internas privadas confidenciales exclusivas para el equipo técnico.
- **Observadores en copia (CC):** cualquier persona con acceso al ticket puede añadir correos que reciben las respuestas públicas y la resolución.
- **Categorías jerárquicas y grupos de soporte:** clasificación por categoría/subcategoría y asignación a equipos de trabajo con sus miembros.
- **Automatización (M3):** motor de reglas con condiciones `AND`/`OR` y acciones de grupo y auto-asignación `round-robin` o por carga (menos tickets abiertos).
- **Plantillas de respuesta:** los agentes insertan un texto predefinido en el hilo con un clic; las plantillas internas activan solas la casilla de nota privada.
- **Fusión de duplicados:** un agente cierra un ticket repetido dentro de otro; su conversación y adjuntos pasan al principal, los observadores se heredan sin duplicar y ambos quedan registrados en la auditoría.
- **Reactivación automática (ITIL):** cuando un solicitante responde a una incidencia en estado `Pendiente de usuario`, esta pasa automáticamente a `En progreso`.
- **Historial de auditoría inmutable:** línea de tiempo inalterable que registra automáticamente quién hizo qué y cuándo (creación, transiciones de estado, cambios de prioridad, asignación de técnicos, resolución y comentarios).
- **Vista de detalle en la web:** al pulsar `Ver` se abre el ticket completo con sus datos, SLA, conversación (respuestas públicas y notas internas), asignación de técnico e historial de auditoría.
- **Adjuntos:** subida y descarga de archivos desde el detalle del ticket (límite configurable de 25 MB), bloqueo de extensiones peligrosas y adjuntos internos ocultos para el solicitante.

### Acuerdos de Nivel de Servicio (SLA)
- **Dos métricas por ticket:** tiempo de primera respuesta (FRT) y tiempo de resolución (RT), con objetivos por prioridad (P1 15 min / 4 h, P2 1 h / 8 h, P3 4 h / 24 h, P4 8 h / 72 h).
- **Calendario laboral (L-V 09:00-18:00):** los tickets P2-P4 solo consumen tiempo dentro del horario laboral; P1 usa calendario continuo 24×7.
- **Stop the Clock:** al pasar a `Pendiente de usuario` o `Pendiente de tercero` el reloj se pausa y, al reanudarse, el límite de resolución se amplía por el tiempo pausado.
- **Estado SLA en tiempo real:** `en tiempo`, `en riesgo` (≥75 % del tiempo consumido), `vencido`, `pausado` o `cumplido`, visible en la interfaz web.
- **Filtros SLA:** `?sla_vencido=true` incluye tickets abiertos fuera de plazo y resoluciones tardías; `?sla_en_riesgo=true` muestra los que están cerca de vencer.
- **Alertas y escalado:** al 80 % se notifica al agente asignado y al 100 % se marca el breach y se avisa a supervisores y administradores. Las alertas son idempotentes y quedan registradas en la auditoría interna.
- **Vigilancia programada:** un job opcional revisa los SLA cada 5 minutos (configurable) y una revisión manual está disponible para supervisores/administradores.
- **Notificaciones por email:** confirmación de alta, respuestas públicas, resolución y alertas de SLA. Se envían por SMTP si está configurado; en local se registran como envíos simulados sin bloquear la petición.

### Base de Conocimiento
- Artículos con título, resumen, contenido y categoría opcional.
- **Visibilidad:** `Públicos` (visibles para cualquier usuario, incluidos solicitantes) o `Internos` (solo agentes, supervisores y administradores).
- Agentes y supervisores pueden crear y editar artículos; solo el administrador puede eliminarlos.
- **Búsqueda** por texto en título, resumen y contenido, con filtro por categoría.
- **Deflexión de incidencias:** mientras se escribe el título de un ticket se sugieren hasta 5 artículos públicos (con *debounce*) y se pueden abrir en el momento.
- Si no se indica resumen, se genera automáticamente a partir del contenido.

### Reportes y KPIs
- **Resumen en tiempo real** (solo supervisor/administrador): tickets creados y resueltos hoy, abiertos, sin asignar, SLA en riesgo/vencido/pausado y distribución por estado, prioridad, canal y categoría.
- **KPIs históricos** filtrables por rango de fechas, grupo, técnico, solicitante y departamento: % de cumplimiento de SLA, **MTTA** (primera asignación), **MTTR** (resolución), **FCR** (resuelto con una sola interacción pública del técnico) y **CSAT** (media de las valoraciones de 1 a 5 que deja el solicitante al resolverse el ticket).
- **Exportación a CSV** del listado filtrado (con BOM UTF-8 para Excel), incluyendo datos de ticket, clasificación, responsables, fechas y estado del SLA.

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
- **pytest**: 267 tests automáticos (incidencias, autenticación, permisos, asignación, reglas ITIL, notas internas, seguridad, auditoría inmutable, SLA, notificaciones, adjuntos, correo, categorías, grupos, automatización, base de conocimiento, reportes y migraciones)
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
| Listar técnicos asignables | `GET /auth/tecnicos` | `agente`, `supervisor`, `administrador` |
| Listar usuarios | `GET /auth/usuarios` | `supervisor`, `administrador` |
| Cambiar rol de un usuario | `PATCH /auth/usuarios/{id}/rol` | `administrador` |

### Incidencias (`/incidencias`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Crear incidencia / ticket | `POST /incidencias` | Autenticado |
| Listar (con filtros: estado, prioridad, tipo, categoría, grupo, agente, sin asignar, sin grupo, SLA) | `GET /incidencias?estado=Nuevo&prioridad=P1 - Crítica&tipo=Incidencia&categoria_id=1&grupo_asignado_id=2&sin_asignar=true&sin_grupo=true&sla_vencido=true` | Autenticado (el solicitante solo ve las suyas) |
| Buscar y paginar | `GET /incidencias?q=impresora&limite=25&desplazamiento=0` — `q` busca en título, descripción y código legible; el total llega en `X-Total-Count` | Autenticado |
| Consultar una (por ID numérico o código legible) | `GET /incidencias/{id_o_codigo}` | Autenticado (idem) |
| Asignar o desasignar técnico | `POST /incidencias/{id_o_codigo}/asignar` | `agente`, `supervisor`, `administrador` |
| Actualizar estado, tipo, impacto, urgencia, categoría o grupo | `PATCH /incidencias/{id_o_codigo}` | `agente`, `supervisor`, `administrador` |
| Reevaluar reglas de automatización | `POST /incidencias/{id_o_codigo}/aplicar-reglas` | `administrador` |
| Resolver (con nota obligatoria) | `POST /incidencias/{id_o_codigo}/resolver` | `agente`, `supervisor`, `administrador` |
| Valorar la resolución (CSAT 1-5) | `POST /incidencias/{id_o_codigo}/csat` | Solicitante dueño, con el ticket resuelto |
| Añadir comentario (público o nota interna) | `POST /incidencias/{id_o_codigo}/comentarios` | Autenticado (nota interna solo técnicos) |
| Listar / añadir / quitar observadores en copia | `GET`, `POST /incidencias/{id_o_codigo}/observadores`, `DELETE .../observadores/{id}` | Autenticado (el solicitante, solo en las suyas) |
| Fusionar un duplicado en otro ticket | `POST /incidencias/{id_o_codigo}/fusionar/{id_o_codigo_duplicado}` | `agente`, `supervisor`, `administrador` |
| Listar hilo de comentarios | `GET /incidencias/{id_o_codigo}/comentarios` | Autenticado (solicitante no ve notas internas) |
| Consultar historial de auditoría | `GET /incidencias/{id_o_codigo}/historial` | Autenticado (solicitante no ve eventos internos) |
| Listar adjuntos | `GET /incidencias/{id_o_codigo}/adjuntos` | Autenticado (solicitante no ve adjuntos internos) |
| Subir adjunto | `POST /incidencias/{id_o_codigo}/adjuntos` | Autenticado (adjunto interno solo técnicos) |
| Descargar adjunto | `GET /adjuntos/{adjunto_id}` | Autenticado (valida visibilidad del ticket) |
| Revisar SLA y generar alertas | `POST /sla/revisar` | `supervisor`, `administrador` |

### Categorías, grupos y automatización

| Acción | Método y ruta | Acceso |
|---|---|---|
| Listar categorías (opcional `?incluir_inactivas=true` solo admin) | `GET /categorias` | Autenticado |
| Crear / actualizar / eliminar categoría | `POST /categorias`, `PATCH /categorias/{id}`, `DELETE /categorias/{id}` | `administrador` |
| Listar grupos (opcional `?incluir_inactivos=true` solo admin) | `GET /grupos` | `agente`, `supervisor`, `administrador` |
| Crear / actualizar / eliminar grupo | `POST /grupos`, `PATCH /grupos/{id}`, `DELETE /grupos/{id}` | `administrador` |
| Añadir / quitar miembro de un grupo | `POST /grupos/{id}/miembros/{usuario_id}`, `DELETE /grupos/{id}/miembros/{usuario_id}` | `administrador` |
| Listar técnicos (opcional `?grupo_id=`) | `GET /auth/tecnicos?grupo_id=2` | `agente`, `supervisor`, `administrador` |
| Listar / crear / actualizar / eliminar reglas | `GET /reglas`, `POST /reglas`, `PATCH /reglas/{id}`, `DELETE /reglas/{id}` | `administrador` |

Las categorías y los grupos con tickets, subcategorías o reglas asociadas no se pueden borrar: devuelven `409 Conflict` y se recomienda desactivarlos.

### Base de Conocimiento (`/conocimiento`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Listar artículos (filtros `?q=` y `?categoria_id=`) | `GET /conocimiento` | Autenticado (el solicitante solo ve los públicos) |
| Sugerir artículos públicos (`?q=`) | `GET /conocimiento/sugerencias` | Autenticado |
| Consultar un artículo | `GET /conocimiento/{id}` | Autenticado (el solicitante no ve los internos) |
| Crear artículo | `POST /conocimiento` | `agente`, `supervisor`, `administrador` |
| Actualizar artículo | `PATCH /conocimiento/{id}` | `agente`, `supervisor`, `administrador` |
| Eliminar artículo | `DELETE /conocimiento/{id}` | `administrador` |

### Reportes (`/reportes`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Resumen en tiempo real | `GET /reportes/resumen` | `supervisor`, `administrador` |
| KPIs por periodo y filtros (`desde`, `hasta`, `grupo_asignado_id`, `agente_asignado_id`, `solicitante_id`, `departamento`) | `GET /reportes/kpis?desde=2026-01-01&hasta=2026-12-31` | `supervisor`, `administrador` |
| Exportar CSV del listado filtrado (`estado`, `prioridad`, `categoria_id`, ...) | `GET /reportes/incidencias.csv?estado=Resuelto` | `supervisor`, `administrador` |

### Plantillas de respuesta (`/macros`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Listar plantillas activas | `GET /macros` | `agente`, `supervisor`, `administrador` |
| Crear / actualizar / eliminar plantilla | `POST /macros`, `PATCH /macros/{id}`, `DELETE /macros/{id}` | `administrador` |

### Ingesta de correo (`/ingesta`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Recibir un correo normalizado (crea ticket o responde al hilo) | `POST /ingesta/correo` | Cabecera `X-Ingesta-Token` |

El conector de correo (IMAP, Microsoft Graph, SES) normaliza el mensaje y lo envía aquí. Si el asunto o la cabecera `In-Reply-To` contiene un código (`INC-2026-000001`), el cuerpo se añade como comentario público; si el ticket estaba `Pendiente de usuario`, se reactiva. Sin código se crea un ticket con canal `Email` y el remitente como solicitante (se da de alta como usuario provisional si no existe). Las respuestas automáticas (`Auto-Submitted`), los remitentes `no-reply@`/`mailer-daemon@` y los `mensaje_id` ya procesados se descartan para evitar bucles y duplicados.

### Notificaciones (`/notificaciones`)

| Acción | Método y ruta | Acceso |
|---|---|---|
| Listar mis notificaciones (opcional `?solo_no_leidas=true`) | `GET /notificaciones` | Autenticado |
| Marcar una notificación como leída | `POST /notificaciones/{id}/leer` | Autenticado (solo las propias) |

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

## Migraciones de base de datos

El esquema se gestiona con **Alembic**. Al arrancar, la aplicación aplica automáticamente las migraciones pendientes (`alembic upgrade head`). También puedes ejecutarlas a mano:

```bash
alembic upgrade head                      # aplicar migraciones
alembic downgrade -1                      # revertir la última
alembic revision --autogenerate -m "..."  # crear una migración tras cambiar models.py
```

Las bases creadas antes de adoptar Alembic se detectan y se sellan automáticamente en la revisión inicial, sin recrear tablas ni perder datos. Para gestionar las migraciones como paso separado en el despliegue, define `AUTO_MIGRATE=0` y ejecuta `alembic upgrade head` antes de arrancar la app.

## Configuración (variables de entorno)

| Variable | Para qué sirve | Si no existe |
|---|---|---|
| `DATABASE_URL` | Dirección de la base de datos (PostgreSQL en producción) | Usa SQLite local (`helpdesk.db`) |
| `AUTO_MIGRATE` | Aplica `alembic upgrade head` al arrancar | Activado (`1`) |
| `SECRET_KEY` | Clave con la que se firman los tokens JWT | Se genera una aleatoria en cada arranque (las sesiones se pierden al reiniciar) |
| `ADMIN_EMAIL` | Único correo que puede convertirse en el primer administrador | El primer usuario registrado es administrador |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración de la sesión | 1440 (24 horas) |
| `SLA_SCHEDULER_ENABLED` | Activa la revisión automática de SLA en segundo plano | Desactivada |
| `SLA_CHECK_INTERVAL_SECONDS` | Intervalo entre revisiones de SLA (mínimo 30 s) | 300 (5 minutos) |
| `DIAS_FESTIVOS` | Festivos que no cuentan como días laborables (`2026-01-01,2026-01-06`) | Vacío |
| `SLA_POLITICAS` | Sobrescribe objetivos por prioridad en JSON: `{"P4 - Baja": {"frt_minutos": 60, "rt_horas": 8}}` | Matriz ITIL por defecto |
| `INGESTA_CORREO_TOKEN` | Token compartido que debe enviar el conector de correo en `X-Ingesta-Token` | Ingesta desactivada (503) |
| `UPLOAD_DIR` | Carpeta donde se guardan los adjuntos (backend local) | `uploads` |
| `STORAGE_BACKEND` | `local` (disco) o `s3` (bucket S3 compatible) | `local` |
| `S3_BUCKET` | Bucket de adjuntos cuando `STORAGE_BACKEND=s3` | Obligatorio con S3 |
| `S3_ENDPOINT_URL` | Endpoint S3 alternativo (MinIO, Backblaze) | AWS por defecto |
| `S3_REGION` | Región del bucket | La del cliente boto3 |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Credenciales del bucket | Cadena de credenciales de AWS |
| `S3_PRESIGN_SECONDS` | Validez de la URL firmada de descarga (mínimo 60) | 300 |
| `MAX_UPLOAD_MB` | Tamaño máximo por adjunto en MB | 25 |
| `AUTH_MAX_INTENTOS` | Peticiones permitidas por IP y ruta en login/registro | 10 |
| `AUTH_VENTANA_SEGUNDOS` | Ventana del límite de intentos, en segundos | 60 |
| `ENTORNO` | `produccion` exige `DATABASE_URL` al arrancar (Render lo activa solo) | Vacío |
| `SMTP_HOST` | Servidor SMTP para enviar correos | Sin correo real (envío simulado) |
| `SMTP_PORT` | Puerto SMTP | 587 |
| `SMTP_USER` / `SMTP_PASSWORD` | Credenciales SMTP | Sin autenticación |
| `SMTP_FROM` | Remitente de los correos | `SMTP_USER` o `no-reply@helpdesk.local` |
| `SMTP_TLS` | Usar STARTTLS | `true` |

En producción, `SECRET_KEY` debe ser una cadena larga y aleatoria, y nunca debe subirse al repositorio.

El servidor de producción detecta si corre en Render (`RENDER`) o con `ENTORNO=produccion`: en ese caso **exige `DATABASE_URL`** y se niega a arrancar si fuese a usar SQLite efímero. Expone `GET /health`, que comprueba la base de datos y devuelve `503` si no responde.

### Zona horaria y adjuntos en producción

- El calendario laboral y las fechas se calculan con la hora local del servidor. La imagen Docker fija `TZ=Europe/Madrid`; si despliegas sin Docker, define `TZ` en el panel del proveedor. Las fechas se muestran con la zona del navegador.
- El disco de Render es efímero: los adjuntos guardados en local se pierden en cada despliegue. En producción configura `STORAGE_BACKEND=s3` con un bucket y las descargas pasan a usar URLs firmadas temporales.
- El límite de intentos de login y registro se lleva en memoria del proceso: con varios workers cada uno cuenta por separado.

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
|   |   |-- auth.py          # Endpoints de autenticación y usuarios
|   |   |-- categorias.py    # CRUD de categorías jerárquicas
|   |   |-- conocimiento.py  # Base de conocimiento y sugerencias
|   |   |-- grupos.py        # Grupos de soporte y sus miembros
|   |   |-- notificaciones.py # Endpoints de notificaciones
|   |   |-- reglas.py        # CRUD de reglas de automatización
|   |   `-- reportes.py      # Resumen, KPIs y exportación CSV
|   |-- auditoria.py     # Helper de registro inmutable de auditoría
|   |-- automatizacion.py # Motor de reglas y auto-asignación
|   |-- correo.py        # Envío de correos por SMTP (con modo simulado)
|   |-- auth.py          # bcrypt, JWT y dependencias de permisos
|   |-- database.py      # Conexión a la base de datos
|   |-- main.py          # Aplicación FastAPI y endpoints de incidencias
|   |-- migraciones.py   # Ejecución de Alembic y sellado de bases previas
|   |-- models.py        # Modelos (Usuario, Incidencia, Categoría, Grupo, Regla, ...)
|   |-- reglas.py        # Matriz ITIL y máquina de estados
|   |-- scheduler.py     # Revisión periódica de SLA en segundo plano
|   |-- schemas.py       # Validación de datos (Pydantic)
|   |-- sla.py           # Cálculo de SLA, calendario laboral y pausas
|   |-- sla_vigilancia.py # Alertas al 80 %/100 % y notificaciones de escalado
|   `-- static/
|       `-- index.html   # Interfaz web (listado, detalle, configuración y avisos)
|-- tests/
|   |-- test_adjuntos.py           # Tests de subida, descarga y privacidad de adjuntos
|   |-- test_auditoria.py          # Tests de historial y trazabilidad inmutable
|   |-- test_auth.py               # Tests de autenticación y RBAC
|   |-- test_automatizacion.py     # Tests del motor de reglas y auto-asignación
|   |-- test_comentarios.py        # Tests de respuestas públicas y notas internas
|   |-- test_comentarios_extra.py  # Tests adicionales del hilo de comentarios
|   |-- test_conocimiento.py       # Tests de base de conocimiento y sugerencias
|   |-- test_correo.py             # Tests de notificaciones por email
|   |-- test_grupos_categorias.py  # Tests de categorías, grupos y borrado seguro
|   |-- test_incidencias.py        # Tests de tickets, estados y asignación
|   |-- test_privacidad.py         # Tests de privacidad de datos y autoría
|   |-- test_reglas.py             # Tests de matriz ITIL y máquina de estados
|   |-- test_reportes.py           # Tests de dashboard, KPIs y exportación CSV
|   |-- test_seguridad_tickets.py  # Tests de permisos y restricciones de seguridad
|   `-- test_sla.py                # Tests de SLA, calendario laboral y pausas
|-- docs/                # Capturas del README
|-- migrations/          # Migraciones de Alembic (env.py y versions/)
|-- .github/workflows/   # GitHub Actions
|-- alembic.ini          # Configuración de Alembic
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
- [x] SLA con calendario laboral y pausas (FRT/RT, Stop the Clock, filtros, alertas al 80 %/100 %, breach persistido y escalado a supervisión)
- [x] Adjuntos en los tickets (límite de tamaño, extensiones bloqueadas, adjuntos internos) y notificaciones por email
- [x] Categorías jerárquicas, grupos de soporte y motor de reglas con auto-asignación (round-robin y carga)
- [x] Base de Conocimiento (artículos públicos/internos, búsqueda y sugerencias)
- [x] Dashboard con KPIs (SLA, MTTA, MTTR, FCR) y exportación a CSV
- [x] Migraciones con Alembic
- [x] Paginación (`limite`/`desplazamiento` con `X-Total-Count`) y búsqueda por texto en título, descripción y código legible
- [x] Plantillas de respuesta reutilizables (texto público o nota interna)
- [x] Fusión de tickets duplicados con herencia de hilo, adjuntos y observadores
- [x] Observadores en copia (CC) por ticket, notificados en cada respuesta pública
- [x] Ingesta de tickets por correo vía webhook (conector IMAP/Graph/SES), con antiduplicados y autorrespuestas ignoradas
- [x] Encuesta de satisfacción (CSAT) y su KPI en los reportes
- [ ] Exportación a XLSX además de CSV
- [ ] Búsqueda full-text indexada (PostgreSQL `tsvector` / Meilisearch)

## Autor

Hecho por [Virus34558](https://github.com/Virus34558) como proyecto de portfolio.