# HelpDesk Lite

![Tests](https://github.com/Virus34558/helpdesk-lite/actions/workflows/tests.yml/badge.svg)

Gestor de incidencias IT inspirado en la herramienta interna de un departamento de soporte. Permite **registrar, consultar, actualizar y resolver incidencias**, con filtros por estado y prioridad.

**Demo en vivo:** helpdesk-lite-6x8a.onrender.com/

> La demo está en un plan gratuito: si lleva un rato sin visitas, la primera carga puede tardar alrededor de un minuto en despertar. Es una demo pública, no introduzcas datos reales.

![Captura de la aplicación](docs/captura.png)

## Qué permite hacer

| Incidencia | Prioridad | Estado |
|---|---|---|
| No funciona Internet | Alta | Abierta |
| Error al instalar software | Media | En proceso |
| Problema con impresora | Baja | Resuelta |

- Crear incidencias con título, descripción y prioridad (Alta, Media, Baja)
- Cambiar el estado: Abierta, En proceso, Resuelta
- Resolver una incidencia con un clic (se guarda la fecha de resolución)
- Filtrar por estado y por prioridad
- Validación de datos: la API rechaza prioridades inventadas o títulos demasiado cortos

## Tecnologías

- **Python** y **FastAPI**: API REST con documentación automática en `/docs`
- **SQLAlchemy**: acceso a la base de datos
- **SQLite** en local y **PostgreSQL** en producción
- **HTML, CSS y JavaScript** sin frameworks para la interfaz
- **pytest**: 10 tests automáticos
- **GitHub Actions**: ejecuta los tests en cada subida
- **Docker**: la app empaquetada en un contenedor
- **Render**: despliegue en la nube

## API

| Acción | Método y ruta |
|---|---|
| Crear incidencia | `POST /incidencias` |
| Listar (con filtros) | `GET /incidencias?estado=Abierta&prioridad=Alta` |
| Consultar una | `GET /incidencias/{id}` |
| Actualizar | `PATCH /incidencias/{id}` |
| Resolver | `POST /incidencias/{id}/resolver` |

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

Abre http://127.0.0.1:8000

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

Los tests usan una base de datos temporal en memoria y no tocan los datos reales.

## Estructura

```
helpdesk-lite/
|-- app/
|   |-- main.py          # Endpoints de la API
|   |-- models.py        # Tabla de incidencias (SQLAlchemy)
|   |-- schemas.py       # Validacion de datos (Pydantic)
|   |-- database.py      # Conexion a la base de datos
|   `-- static/
|       `-- index.html   # Interfaz web
|-- tests/               # Tests con pytest
|-- .github/workflows/   # GitHub Actions
|-- Dockerfile
|-- requirements.txt
`-- README.md
```


## Limitaciones y próximas mejoras

Es un proyecto de aprendizaje, así que he dejado fuera algunas cosas a propósito:

- [ ] Autenticación de usuarios y roles (técnico / usuario)
- [ ] Asignar incidencias a un técnico
- [ ] Comentarios e historial de cambios
- [ ] Migraciones de base de datos con Alembic
- [ ] Paginación del listado

## Autor

Hecho por [Virus34558](https://github.com/Virus34558) como proyecto de portfolio.
