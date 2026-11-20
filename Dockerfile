FROM python:3.13-slim

# El calendario laboral (L-V 09:00-18:00) y las horas mostradas usan la hora
# local del contenedor. Sin TZ, el contenedor arranca en UTC y los SLA de los
# tickets entrarían desplazados respecto al horario de oficina.
ENV TZ=Europe/Madrid
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
