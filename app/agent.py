"""Agente ReAct de LangChain (`create_agent`) con memoria persistente por cliente.

La memoria vive en Postgres (PostgresSaver de LangGraph) y su clave es el `thread_id`,
que aquí es el ID del cliente: cada ID tiene su propio historial y el agente solo ve
el de ese cliente. Como está en Postgres y no en RAM, sobrevive a reinicios y a que
Cloud Run apague o escale instancias.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.postgres import PostgresSaver

from app.config import OPENAI_MODEL, validar_id_cliente
from app.db import pool_memoria
from app.prompts import SYSTEM_PROMPT
from app.tools import TOOLS

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_checkpointer() -> PostgresSaver:
    checkpointer = PostgresSaver(pool_memoria())
    checkpointer.setup()  # crea las tablas la primera vez (es idempotente)
    return checkpointer


def _crear_modelo():
    return init_chat_model(
        f"openai:{OPENAI_MODEL}",
        temperature=0,
        default_headers={"Accept-Encoding": "gzip, deflate"},  # igual que en el notebook
    )


@lru_cache(maxsize=1)
def get_agent():
    return create_agent(
        model=_crear_modelo(),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=get_checkpointer(),
    )


def _config(cliente_id: str) -> dict:
    return {"configurable": {"thread_id": validar_id_cliente(cliente_id)}}


def _texto(contenido) -> str:
    """El contenido de un mensaje suele ser str, pero algunos modelos devuelven bloques."""
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        partes = []
        for bloque in contenido:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict) and bloque.get("type") == "text":
                partes.append(bloque.get("text", ""))
        return "".join(partes)
    return str(contenido)


def chat(cliente_id: str, mensaje: str) -> str:
    """Envía un mensaje del cliente al agente y devuelve su respuesta."""
    resultado = get_agent().invoke(
        {"messages": [{"role": "user", "content": mensaje}]},
        config=_config(cliente_id),
    )
    return _texto(resultado["messages"][-1].content)


def historial(cliente_id: str) -> list[dict]:
    """Conversación guardada del cliente, lista para mostrar: [{"role", "content"}].

    Solo incluye lo que el cliente escribió y las respuestas finales del agente
    (se omiten las llamadas a herramientas y sus resultados).
    """
    tupla = get_checkpointer().get_tuple(_config(cliente_id))
    if tupla is None:
        return []
    mensajes = tupla.checkpoint.get("channel_values", {}).get("messages", [])

    salida = []
    for m in mensajes:
        texto = _texto(m.content).strip()
        if m.type == "human" and texto:
            salida.append({"role": "user", "content": texto})
        elif m.type == "ai" and texto and not getattr(m, "tool_calls", None):
            salida.append({"role": "assistant", "content": texto})
    return salida


def reiniciar(cliente_id: str) -> None:
    """Borra la memoria de un cliente (útil para repetir la demo desde cero)."""
    get_checkpointer().delete_thread(validar_id_cliente(cliente_id))
