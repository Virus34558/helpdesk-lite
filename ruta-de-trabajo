# Especificación de Requisitos Funcionales (ERS)
**Proyecto:** Sistema de Gestión de Helpdesk y Soporte Técnico (ITSM)  
**Versión:** 1.0  
**Estado:** Borrador para Revisión Técnica  
**Destinatarios:** Equipo de Desarrollo, Arquitectura de Software y QA  

---

## 1. Introducción y Propósito

### 1.1 Objetivo del Documento
El presente documento detalla los requisitos funcionales, reglas de negocio y criterios técnicos para el desarrollo de una plataforma de Helpdesk. Su propósito es servir como referencia base para el diseño de la arquitectura, el modelado de datos, la estimación de esfuerzo y la creación del *Product Backlog*.

### 1.2 Alcance del Producto
El sistema permitirá centralizar la recepción, clasificación, asignación, seguimiento y resolución de incidencias y solicitudes de servicio (tickets) provenientes de múltiples canales, garantizando el cumplimiento de Acuerdos de Nivel de Servicio (SLAs) y ofreciendo métricas operativas en tiempo real.

---

## 2. Actores, Roles y Control de Acceso (RBAC)

El sistema debe implementar control de acceso basado en roles (RBAC) y soportar autenticación mediante credenciales locales y proveedores de identidad corporativos (**SSO / OAuth 2.0 / SAML 2.0 / Microsoft Entra ID**).

| Rol | Descripción | Alcance de Visibilidad | Permisos Clave |
| :--- | :--- | :--- | :--- |
| **Solicitante (Usuario Final / Cliente)** | Empleado interno o cliente externo que reporta una incidencia o solicita un servicio. | Exclusivamente sus propios tickets (o los de su organización si se habilita vista de empresa). | Crear tickets, adjuntar archivos, añadir comentarios públicos, reabrir tickets resueltos, responder encuestas CSAT y consultar la Base de Conocimiento pública. |
| **Agente de Soporte (N1 / N2 / N3)** | Técnico encargado de diagnosticar y resolver tickets. | Tickets asignados directamente a él, a sus grupos de soporte o sin asignar dentro de su cola. | Tomar tickets, cambiar estados/prioridades, escribir respuestas públicas y notas internas, escalar a otros niveles, fusionar tickets, aplicar macros y crear artículos de KB. |
| **Supervisor / Team Lead** | Responsable operativo de uno o varios grupos de soporte. | Todos los tickets de los grupos bajo su supervisión y métricas de su equipo. | Todos los permisos de Agente + reasignación masiva, gestión de SLAs en riesgo, configuración de turnos/ausencias de agentes y visualización de dashboards de rendimiento. |
| **Administrador del Sistema** | Responsable técnico de la configuración global de la herramienta. | Acceso total al sistema y registros de auditoría. | CRUD de usuarios/grupos, diseño de formularios dinámicos, definición de pólizas SLA, calendarios laborales, reglas de automatización, webhooks y claves API. |

---

## 3. Modelo de Datos Lógico del Ticket (Atributos Base)

Para estandarizar el desarrollo del *backend* y la base de datos, la entidad principal `Ticket` deberá contemplar como mínimo los siguientes atributos:

* **`id_legible`**: Identificador único amigable indexado (ej. `INC-2026-000142` o `REQ-10450`).
* **`tipo`**: `Incidencia` (interrupción no planificada) | `Solicitud de Servicio` (petición estándar) | `Problema` (causa raíz) | `Cambio`.
* **`asunto`**: Cadena de texto (máx. 255 caracteres).
* **`descripcion`**: Contenido en formato HTML sanitizado o Markdown.
* **`estado`**: `Nuevo`, `Abierto / Asignado`, `En Progreso`, `Pendiente de Usuario`, `Pendiente de Tercero`, `Resuelto`, `Cerrado`, `Cancelado`.
* **`impacto`**: `Bajo` (1 usuario), `Medio` (departamento/grupo), `Alto` (toda la organización / servicio crítico).
* **`urgencia`**: `Baja`, `Media`, `Alta`, `Crítica`.
* **`prioridad`**: Calculada automáticamente (`P4 - Baja`, `P3 - Media`, `P2 - Alta`, `P1 - Crítica`).
* **`canal_origen`**: `Portal Web`, `Email`, `API / Monitoreo`, `Teléfono (Carga manual)`, `Chat`.
* **`solicitante_id`**: Referencia al usuario creador.
* **`observadores (CC)`**: Lista de correos o usuarios suscritos a las notificaciones del ticket.
* **`grupo_asignado_id`**: Equipo responsable actual (ej. *Soporte N1*, *Redes*, *Desarrollo*).
* **`agente_asignado_id`**: Técnico responsable actual (nullable).
* **`categoria_id` / `subcategoria_id`**: Clasificación taxonómica del ticket.
* **`sla_policy_id`**: Póliza de SLA aplicada al ticket.
* **`fechas_control`**: `created_at`, `updated_at`, `first_response_at`, `resolved_at`, `closed_at`, `sla_due_date`.

---

## 4. Especificación de Módulos y Requisitos Funcionales

### Módulo 1: Captura y Creación Omnicanal de Tickets

#### RF-1.1 Portal de Autoservicio y Formularios Dinámicos
* **Descripción:** Interfaz web para que los usuarios registren tickets seleccionando primero la categoría del problema.
* **Reglas de Negocio:**
  * El formulario debe renderizar campos personalizados condicionales según la categoría elegida (ej. si selecciona *"Solicitud de Nuevo Equipo"*, mostrar campos obligatorios *"Centro de Costos"* y *"Aprobador"*).
  * Soporte para validación en cliente y servidor de campos obligatorios, formatos de fecha y expresiones regulares.

#### RF-1.2 Ingesta por Correo Electrónico (Email Piping)
* **Descripción:** El sistema debe monitorear una o varias casillas de correo (ej. `soporte@empresa.com`) vía IMAP/OAuth2 o webhooks de correo (Microsoft Graph API / Google Workspace / AWS SES).
* **Reglas de Negocio:**
  * **Correo nuevo:** Si el asunto no contiene un patrón de ID de ticket existente ni coincide con la cabecera `In-Reply-To` / `References`, se crea un nuevo ticket en estado `Nuevo`, asignando al remitente como `Solicitante` (si no existe en BD, se crea un usuario provisional).
  * **Respuesta a hilo existente:** Si se detecta un ID de ticket válido o cabecera de hilo, el cuerpo del correo (limpiando el historial citado anterior) se añade como comentario público al ticket correspondiente.
  * **Reapertura por correo:** Si el ticket estaba en estado `Pendiente de Usuario` o `Resuelto` y el cliente responde por correo, el estado debe cambiar automáticamente a `Abierto / En Progreso`.
  * **Prevención de bucles:** Ignorar correos con cabeceras `Auto-Submitted: auto-generated`, respuestas automáticas (*Out of Office*) o remitentes en lista negra (`no-reply@`).

#### RF-1.3 API REST y Webhooks de Entrada
* **Descripción:** Endpoint autenticado mediante API Token / OAuth para la creación programática de tickets desde sistemas de monitoreo (Zabbix, Datadog, Prometheus) o ERPs.
* **Reglas de Negocio:** Permitir un campo `deduplication_key` para evitar que una misma caída de servidor genere cientos de tickets idénticos en pocos minutos; si la clave ya existe en un ticket abierto, se añade una nota al ticket existente en lugar de crear uno nuevo.

#### RF-1.4 Gestión de Archivos Adjuntos
* **Descripción:** Capacidad de adjuntar archivos tanto en la creación como en las respuestas.
* **Reglas de Negocio:**
  * Soporte para pegar capturas de pantalla directamente desde el portapapeles (`Ctrl+V` / `Cmd+V`) dentro del editor de texto enriquecido.
  * Restricción configurable por tamaño máximo por archivo (ej. 25 MB) y bloqueo de extensiones ejecutables peligrosas (`.exe`, `.bat`, `.sh`, `.vbs`).

---

### Módulo 2: Ciclo de Vida y Gestión Operativa del Ticket

#### RF-2.1 Máquina de Estados (Workflow)
El sistema debe validar las transiciones permitidas entre estados según la siguiente lógica operativa:

1. **`Nuevo`**: Ticket recién creado, aún sin agente asignado ni primera respuesta.
2. **`Asignado / En Progreso`**: Un agente ha tomado el ticket y está trabajando en él.
3. **`Pendiente de Usuario`**: El agente requiere información adicional o validación por parte del solicitante. *(Pausa el reloj de SLA)*.
4. **`Pendiente de Tercero`**: El ticket depende de un proveedor externo o fabricante. *(Pausa el reloj de SLA)*.
5. **`Resuelto`**: El agente ha proporcionado una solución. Se requiere completar el campo obligatorio *"Causa Raíz / Nota de Resolución"*.
6. **`Cerrado`**: Estado final inmutable tras confirmación del usuario o por vencimiento del tiempo de inactividad en estado `Resuelto`. Si un usuario intenta responder a un ticket `Cerrado`, el sistema creará un nuevo ticket vinculado al anterior (`Ticket de Seguimiento`).

#### RF-2.2 Matriz de Priorización Automática (ITIL)
* **Descripción:** Los agentes o reglas del sistema definen el **Impacto** y la **Urgencia**, y el sistema calcula la **Prioridad** automáticamente según la siguiente matriz configurable:

| Impacto \ Urgencia | Crítica | Alta | Media | Baja |
| :--- | :---: | :---: | :---: | :---: |
| **Alto (Organización)** | **P1 - Crítica** | **P1 - Crítica** | **P2 - Alta** | **P3 - Media** |
| **Medio (Departamento)** | **P1 - Crítica** | **P2 - Alta** | **P3 - Media** | **P4 - Baja** |
| **Bajo (Individual)** | **P2 - Alta** | **P3 - Media** | **P4 - Baja** | **P4 - Baja** |

#### RF-2.3 Comunicación Dual (Pública vs. Privada)
* **Descripción:** La vista de detalle del ticket debe contar con dos pestañas claramente diferenciadas visualmente (ej. distinto color de fondo en el editor):
  * **Responder al Cliente (Público):** Envía notificación por email al solicitante y a los usuarios en CC, y queda visible en el portal web.
  * **Nota Interna (Privada):** Visible únicamente para Agentes, Supervisores y Administradores. Soporta menciones (`@nombre_agente`) que disparan una notificación interna o por correo al compañero mencionado.

#### RF-2.4 Fusión y Vinculación de Tickets
* **Fusión (Merge):** Si un usuario abre dos tickets por el mismo problema, el agente puede fusionar el Ticket B dentro del Ticket A. El Ticket B pasa a estado `Cerrado`, sus mensajes y adjuntos se copian cronológicamente al Ticket A y se deja una nota de auditoría en ambos.
* **Relación Padre-Hijo (Incidente Mayor):** Ante una caída masiva (ej. caída del servidor de correo), los agentes pueden vincular múltiples tickets individuales (`Hijos`) a un `Ticket Maestro`. Al resolver el `Ticket Maestro`, el sistema ofrece la opción de resolver y notificar en bloque a todos los tickets hijos asociados.

#### RF-2.5 Control de Colisión de Agentes (Tiempo Real)
* **Descripción:** Mediante WebSockets o Server-Sent Events (SSE), cuando un agente entra a la vista de un ticket, el resto de los agentes deben ver un indicador con su avatar mostrando: *"Agente X está viendo este ticket"* o *"Agente X está escribiendo una respuesta..."*.
* **Bloqueo optimista:** Si el estado del ticket cambia mientras otro agente tiene la pantalla abierta, el sistema debe avisar antes de permitir sobrescribir cambios.

---

### Módulo 3: Enrutamiento, Colas y Automatización

#### RF-3.1 Vistas y Colas de Trabajo
* Los agentes deben disponer de vistas predefinidas y filtros guardados: *Mis tickets abiertos*, *Tickets sin asignar de mi grupo*, *Tickets pendientes de mi respuesta*, *Tickets con SLA próximo a vencer (< 2 horas)* y *Todos los tickets*.

#### RF-3.2 Motor de Reglas de Negocio (Triggers y Automatizaciones)
* **Triggers Basados en Eventos (Al crear o actualizar un ticket):**
  * Condiciones lógicas (`AND` / `OR`). Ejemplo: *SI `Categoría = SAP` Y `Impacto = Alto` ENTONCES `Asignar a Grupo = Consultores ERP` Y `Enviar alerta a canal de Teams/Slack`*.
* **Asignación Automática (Auto-Assignment):**
  * Soporte para asignación **Round-Robin** (reparto secuencial equitativo entre agentes con estado *"Disponible"*) o **Load Balanced** (asignar al agente del grupo que tenga menos tickets abiertos en ese momento).
* **Automatizaciones Basadas en Tiempo (Cron Jobs):**
  * Si un ticket lleva $48\text{ horas}$ en estado `Pendiente de Usuario`, enviar correo recordatorio automático al solicitante.
  * Si un ticket lleva $5\text{ días}$ hábiles en estado `Resuelto` sin respuesta del usuario, transicionar automáticamente a `Cerrado` y enviar encuesta de satisfacción.

#### RF-3.3 Macros y Plantillas de Respuesta
* Los agentes pueden ejecutar **Macros** que aplican múltiples acciones con un solo clic: insertar un bloque de texto con variables dinámicas (ej. `Hola {{ticket.requester.first_name}}, tu caso {{ticket.id}} ha sido escalado...`), cambiar el estado a `Resuelto` y rellenar la categoría simultáneamente.

---

### Módulo 4: Acuerdos de Nivel de Servicio (SLA) y Escalado

#### RF-4.1 Definición de Pólizas SLA
El sistema debe calcular y monitorear dos métricas independientes por cada ticket:
1. **Tiempo de Primera Respuesta (FRT):** Tiempo transcurrido desde la creación del ticket hasta el primer comentario público enviado por un agente humano (las respuestas automáticas de confirmación de recepción no cuentan).
2. **Tiempo de Resolución (RT):** Tiempo neto activo transcurrido desde la creación hasta que el ticket pasa a estado `Resuelto`.

*Ejemplo de matriz de tiempos objetivo por defecto:*

| Prioridad | Objetivo Primera Respuesta (FRT) | Objetivo Resolución (RT) | Tipo de Calendario |
| :--- | :---: | :---: | :--- |
| **P1 - Crítica** | $15\text{ min}$ | $4\text{ horas}$ | $24\times7$ (Continuo) |
| **P2 - Alta** | $1\text{ hora}$ | $8\text{ horas}$ | Horario Laboral ($8\times5$) |
| **P3 - Media** | $4\text{ horas}$ | $24\text{ horas}$ | Horario Laboral ($8\times5$) |
| **P4 - Baja** | $8\text{ horas}$ | $72\text{ horas}$ | Horario Laboral ($8\times5$) |

#### RF-4.2 Cálculo con Calendarios Laborales y Pausas
* **Exclusión fuera de horario:** Si el horario laboral configurado es de Lunes a Viernes de 09:00 a 18:00, y un ticket `P3` (4 horas de FRT) entra el viernes a las 17:00, habrá consumido $1\text{ hora}$ el viernes y su vencimiento real será el lunes siguiente a las 12:00 (descontando también días festivos cargados en el calendario).
* **Stop the Clock (Pausa de SLA):** Cuando el ticket cambia a `Pendiente de Usuario` o `Pendiente de Tercero`, el temporizador de resolución se congela. Al volver a `En Progreso`, el sistema recalcula el `sla_due_date` sumando el tiempo que estuvo pausado.

#### RF-4.3 Alertas de Incumplimiento y Escalado Jerárquico
* El sistema mostrará etiquetas visuales en la lista de tickets: Verde (En tiempo), Ámbar ($\ge 75\%$ del tiempo consumido), Rojo (`SLA Vencido`).
* Al alcanzar el $80\%$ del tiempo sin resolución, disparar notificación de advertencia al agente asignado.
* Al superar el $100\%$ (`Breach`), registrar la marca `sla_resolution_breached = true` en base de datos y notificar inmediatamente al Supervisor del grupo.

---

### Módulo 5: Base de Conocimiento (Knowledge Base)

#### RF-5.1 Gestión de Artículos
* Editor WYSIWYG / Markdown para crear artículos categorizados con soporte para imágenes, bloques de código y videos embebidos.
* **Control de Visibilidad:** Artículos marcados como `Públicos` (visibles para cualquier usuario en el portal) o `Internos` (procedimientos técnicos confidenciales visibles solo para agentes).

#### RF-5.2 Deflexión Inteligente de Tickets
* En el portal de usuario, mientras el solicitante escribe el *Asunto* del ticket (evento `onInput` con *debounce*), el sistema realizará una búsqueda de texto completo y mostrará una lista desplegable con hasta 5 artículos sugeridos de la Base de Conocimiento con un botón *"Esto resolvió mi problema"*.

---

### Módulo 6: Reportes, Analítica y Auditoría

#### RF-6.1 Dashboard en Tiempo Real
* Panel principal para supervisores con widgets actualizados dinámicamente:
  * Total de tickets abiertos hoy vs. resueltos hoy.
  * Tickets sin asignar en cola.
  * Tickets con SLA en riesgo o vencido.
  * Distribución de tickets por categoría, canal y prioridad.

#### RF-6.2 KPIs e Informes Históricos
* Generación de reportes filtrables por rango de fechas, grupo de soporte, agente o cliente/departamento:
  * **% Cumplimiento de SLA:** Porcentaje de tickets resueltos dentro del tiempo objetivo.
  * **MTTA (Mean Time to Acknowledge):** Tiempo promedio desde creación hasta asignación.
  * **MTTR (Mean Time to Resolve):** Tiempo promedio neto de resolución.
  * **FCR (First Contact Resolution):** Porcentaje de tickets resueltos con una única interacción del agente.
  * **CSAT (Customer Satisfaction Score):** Promedio de calificaciones (escala de 1 a 5 o Caras: Malo/Regular/Bueno) + comentario opcional enviado por el usuario al cerrarse el ticket.
* **Exportación:** Todos los listados de datos deben poder exportarse en formato `.CSV` y `.XLSX`.

#### RF-6.3 Historial de Auditoría Inmutable (Audit Log)
* Cada ticket debe poseer una línea de tiempo inalterable que registre quién hizo qué y cuándo (con *timestamp* en UTC).
* Formato de registro: `[Fecha/Hora] - [Usuario/Sistema] - [Acción] - [Valor Anterior -> Valor Nuevo]`. Ningún usuario, ni siquiera el Administrador, puede borrar registros del historial de auditoría.

---

## 5. Requisitos No Funcionales (RNF) para Arquitectura

1. **RNF-01 Rendimiento y Búsqueda:** El motor de búsqueda global (búsqueda por número de ticket, texto en asunto/comentarios o email del solicitante) debe devolver resultados paginados en menos de $500\text{ ms}$ para un volumen de hasta $1,000,000$ de tickets (se recomienda indexación Full-Text en PostgreSQL o Elasticsearch/Meilisearch).
2. **RNF-02 Procesamiento Asíncrono:** La lectura/envío de correos electrónicos, ejecución de webhooks, generación de reportes pesados y recálculo masivo de SLAs deben ejecutarse mediante colas de trabajos en segundo plano (ej. Redis + BullMQ / RabbitMQ / Celery) con política de reintentos (*exponential backoff*) para no afectar la latencia de la interfaz web.
3. **RNF-03 Seguridad y Privacidad:**
   * Sanitización estricta del HTML entrante por correo electrónico para prevenir ataques **XSS (Cross-Site Scripting)** cuando el agente abre el ticket.
   * Almacenamiento de adjuntos en servicio de objetos compatible con S3 (AWS S3, MinIO, Azure Blob Storage) utilizando URLs firmadas temporales (*Pre-signed URLs*) para su descarga segura.
   * Cumplimiento de normativas de protección de datos (opción de anonimizar datos personales de usuarios dados de baja sin perder la estadística operativa de los tickets).
4. **RNF-04 Escalabilidad e Integraciones:** Arquitectura *API-First* documentada bajo estándar **OpenAPI 3.0 (Swagger)**, permitiendo conectar fácilmente clientes móviles futuros o integraciones bidireccionales con herramientas de desarrollo como **Jira**, **GitLab** o **GitHub Issues**.

---

## 6. Propuesta de Fases de Entrega (Roadmap MVP)

Para facilitar la planificación de sprints del equipo de desarrollo, se sugiere dividir la construcción en tres fases incrementales:

* **Fase 1 - MVP Core (Sprints 1 a 4):** Autenticación y Roles, CRUD de Tickets vía Portal Web, Hilo de respuestas públicas y notas internas, adjuntos, vistas por estados y notificaciones básicas por email saliente.
* **Fase 2 - Automatización y SLAs (Sprints 5 a 7):** Ingesta de tickets por correo entrante (*Email Piping*), motor de cálculo de SLAs con calendarios laborales y pausas, reglas de asignación automática y detección de colisión de agentes en tiempo real.
* **Fase 3 - Autoservicio y Analítica Avanzada (Sprints 8 a 10):** Base de Conocimiento con sugerencia de artículos, encuestas CSAT, fusión/vinculación de tickets maestros, dashboards de métricas (MTTR, FRT) y webhooks/integración con Jira/Teams.