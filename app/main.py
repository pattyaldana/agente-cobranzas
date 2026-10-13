"""Punto de entrada: una API REST (FastAPI) con la interfaz de Gradio montada en "/".

    uvicorn app.main:app --host 0.0.0.0 --port 8080

Endpoints:
    GET    /health               la app está viva (no toca bases de datos)
    GET    /ready                Postgres y Elasticsearch responden
    POST   /chat                 {cliente_id, mensaje} -> {cliente_id, respuesta}
    GET    /historial/{id}       conversación guardada de un cliente
    DELETE /historial/{id}       reinicia la memoria de un cliente
    GET    /docs                 documentación interactiva (Swagger)
    GET    /                     interfaz de chat (Gradio)
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import gradio as gr
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import agent, rag, ui
from app.config import PATRON_ID_CLIENTE, RAG_BACKEND, requerida, validar_id_cliente
from app.db import cerrar_pools, verificar_postgres

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for _ruidoso in ("elastic_transport", "httpx", "httpcore"):  # un INFO por cada petición HTTP: solo ruido
    logging.getLogger(_ruidoso).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    cerrar_pools()  # al apagar el servicio (p. ej. cuando Cloud Run baja una instancia)


api = FastAPI(
    lifespan=lifespan,
    title="Agente de cobranzas",
    version="1.0.0",
    description="Agente LangChain con herramientas (Postgres) y RAG (Elasticsearch), con memoria por cliente.",
)

# Solo hace falta si más adelante se consume la API desde otro dominio (p. ej. un frontend en Vercel).
_origenes = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if _origenes:
    api.add_middleware(
        CORSMiddleware, allow_origins=_origenes, allow_methods=["*"], allow_headers=["*"]
    )


class ChatEntrada(BaseModel):
    cliente_id: str = Field(pattern=PATRON_ID_CLIENTE, examples=["cliente-001"])
    mensaje: str = Field(min_length=1, max_length=2000, examples=["Hola, quiero saber cuánto debo. Mi DNI es 10234567"])


class ChatSalida(BaseModel):
    cliente_id: str
    respuesta: str


@api.get("/health", tags=["estado"])
def health() -> dict:
    return {"status": "ok", "rag_backend": RAG_BACKEND}


def _verificar_openai() -> str:
    requerida("OPENAI_API_KEY")  # solo comprueba que exista; no llama a OpenAI
    return "API key configurada"


@api.get("/ready", tags=["estado"])
def ready() -> JSONResponse:
    """Comprueba las dependencias externas. Útil para depurar un despliegue nuevo."""
    comprobaciones = {
        "openai": _verificar_openai,
        "postgres": verificar_postgres,
        "elasticsearch": rag.verificar,
    }
    resultado: dict[str, dict] = {}
    todo_ok = True
    for nombre, comprobar in comprobaciones.items():
        try:
            resultado[nombre] = {"ok": True, "detalle": comprobar() or "ok"}
        except Exception as error:
            todo_ok = False
            logger.exception("Falló la comprobación de %s", nombre)
            # Los mensajes de conexión incluyen hosts/IP: solo se muestran los nuestros (RuntimeError).
            detalle = str(error) if isinstance(error, RuntimeError) else "ver logs del servicio"
            resultado[nombre] = {"ok": False, "error": f"{type(error).__name__}: {detalle}"}
    return JSONResponse(resultado, status_code=200 if todo_ok else 503)


@api.post("/chat", response_model=ChatSalida, tags=["agente"])
def chat(entrada: ChatEntrada) -> ChatSalida:
    try:
        respuesta = agent.chat(entrada.cliente_id, entrada.mensaje)
    except Exception:
        logger.exception("Error en /chat (cliente %s)", entrada.cliente_id)
        raise HTTPException(status_code=503, detail="No se pudo procesar el mensaje. Revisa /ready y los logs.")
    return ChatSalida(cliente_id=entrada.cliente_id, respuesta=respuesta)


def _id_valido(cliente_id: str) -> str:
    try:
        return validar_id_cliente(cliente_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@api.get("/historial/{cliente_id}", tags=["agente"])
def obtener_historial(cliente_id: str) -> dict:
    cliente_id = _id_valido(cliente_id)
    try:
        mensajes = agent.historial(cliente_id)
    except Exception:
        logger.exception("Error leyendo el historial de %s", cliente_id)
        raise HTTPException(status_code=503, detail="No se pudo leer el historial. Revisa /ready y los logs.")
    return {"cliente_id": cliente_id, "mensajes": mensajes}


@api.delete("/historial/{cliente_id}", tags=["agente"])
def borrar_historial(cliente_id: str) -> dict:
    cliente_id = _id_valido(cliente_id)
    try:
        agent.reiniciar(cliente_id)
    except Exception:
        logger.exception("Error reiniciando la memoria de %s", cliente_id)
        raise HTTPException(status_code=503, detail="No se pudo reiniciar la memoria. Revisa /ready y los logs.")
    return {"cliente_id": cliente_id, "reiniciado": True}


# Las rutas de la API se definen antes del montaje: así tienen prioridad sobre "/" (Gradio).
app = gr.mount_gradio_app(api, ui.demo, path="/", theme=ui.TEMA, css=ui.CSS)
