"""Configuración central de la aplicación.

Todo se lee de variables de entorno. En local se cargan desde el archivo `.env`;
en Cloud Run las define el propio servicio (secretos incluidos), por lo que el
`.env` no existe allí y `load_dotenv()` simplemente no hace nada.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def requerida(nombre: str) -> str:
    """Devuelve una variable de entorno obligatoria o falla con un mensaje claro."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. "
            "Revisa tu archivo .env (local) o la configuración del servicio (Cloud Run)."
        )
    return valor


# --- LLM -------------------------------------------------------------------
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
# Debe ser el MISMO modelo con el que se indexó la base de conocimiento.
EMBEDDING_MODEL = "text-embedding-3-small"

# --- RAG -------------------------------------------------------------------
RAG_BACKEND = os.environ.get("RAG_BACKEND", "langchain").strip().lower()
if RAG_BACKEND not in ("langchain", "llamaindex"):
    raise RuntimeError("RAG_BACKEND debe ser 'langchain' o 'llamaindex'.")

# Cada backend tiene su propio índice en Elasticsearch (los nombres de tu notebook).
_INDICE_POR_BACKEND = {
    "langchain": "base_conocimiento_telecom",
    "llamaindex": "base_conocimiento_telecom_llamaindex",
}
ES_INDEX = os.environ.get("ES_INDEX") or _INDICE_POR_BACKEND[RAG_BACKEND]
ES_USER = os.environ.get("ES_USER", "elastic")
CARPETA_DOCUMENTOS = os.environ.get("CARPETA_DOCUMENTOS", "base_conocimiento")

# --- Clientes de la demo -----------------------------------------------------
ARCHIVO_CLIENTES_DEMO = os.environ.get("ARCHIVO_CLIENTES_DEMO", "clientes_demo.json")
# El ID del cliente es el thread_id de la memoria del agente.
PATRON_ID_CLIENTE = r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"
_RE_ID = re.compile(PATRON_ID_CLIENTE)


def validar_id_cliente(cliente_id: str) -> str:
    """Normaliza y valida el ID de cliente (letras, números, guion, guion bajo, punto)."""
    cliente_id = (cliente_id or "").strip()
    if not _RE_ID.match(cliente_id):
        raise ValueError(
            "ID de cliente inválido: usa de 1 a 64 caracteres (letras, números, '-', '_' o '.')."
        )
    return cliente_id


# --- Hora local ---------------------------------------------------------------
# Cloud Run corre en UTC; sin esto, después de las 19:00 en Lima el agente
# creería que "hoy" ya es mañana.
ZONA_HORARIA = ZoneInfo(os.environ.get("APP_TZ", "America/Lima"))


def hora_local() -> datetime:
    """Hora actual en la zona configurada, sin tzinfo (igual que datetime.now() en tu PC)."""
    return datetime.now(ZONA_HORARIA).replace(tzinfo=None)
