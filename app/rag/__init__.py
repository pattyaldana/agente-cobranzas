"""Capa de RAG: elige el backend (LangChain o LlamaIndex) según RAG_BACKEND.

El resto de la app solo conoce estas tres funciones, así que cambiar de librería es
cambiar una variable de entorno. El backend se importa solo cuando se usa, por lo que
LlamaIndex no hace falta instalarlo si trabajas con LangChain.
"""
from __future__ import annotations

from app.config import RAG_BACKEND


def _backend():
    if RAG_BACKEND == "llamaindex":
        from app.rag import llamaindex_rag as backend
    else:
        from app.rag import langchain_rag as backend
    return backend


def buscar(pregunta: str, categoria: str = "", k: int = 3) -> list[tuple[str, str]]:
    """Busca en la base de conocimiento. Devuelve [(título, texto)]."""
    return _backend().buscar(pregunta, categoria, k)


def indexar(reset: bool = False) -> int:
    """Indexa los documentos de CARPETA_DOCUMENTOS. Devuelve cuántos chunks indexó."""
    return _backend().indexar(reset)


def verificar() -> str:
    """Comprueba la conexión al vector store (lanza excepción si falla)."""
    return _backend().verificar()
