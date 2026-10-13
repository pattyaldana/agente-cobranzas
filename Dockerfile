FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    APP_TZ=America/Lima \
    PORT=8080

WORKDIR /srv

# Primero las dependencias: así Docker reutiliza esta capa mientras no cambie requirements.txt
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY base_conocimiento ./base_conocimiento
COPY clientes_demo.json .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8080

# Cloud Run inyecta la variable PORT. --proxy-headers: la app corre detrás del proxy HTTPS de Cloud Run.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
