"""RAG con LangChain + Elasticsearch (backend por defecto).

Es el pipeline del notebook (celdas 26-36): carga de .md con frontmatter ->
RecursiveCharacterTextSplitter -> embeddings de OpenAI -> ElasticsearchStore, y
búsqueda por similitud con filtro por metadata.categoria.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langchain_core.documents import Document
from langchain_elasticsearch import ElasticsearchStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import CARPETA_DOCUMENTOS, EMBEDDING_MODEL, ES_INDEX, ES_USER, requerida
from app.rag.documentos import leer_markdown

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _store() -> ElasticsearchStore:
    # El constructor se conecta a Elasticsearch (hace un info()). Si falla, la
    # excepción sube y lru_cache no la guarda: el siguiente intento reintenta.
    return ElasticsearchStore(
        index_name=ES_INDEX,
        embedding=OpenAIEmbeddings(model=EMBEDDING_MODEL),
        es_url=requerida("ES_URL"),
        es_user=ES_USER,
        es_password=requerida("ES_PASSWORD"),
    )


def buscar(pregunta: str, categoria: str = "", k: int = 3) -> list[tuple[str, str]]:
    """Devuelve [(título, texto)] de los k chunks más parecidos."""
    filtro = [{"term": {"metadata.categoria.keyword": categoria}}] if categoria else None
    resultados = _store().similarity_search(pregunta, k=k, filter=filtro)
    return [
        (r.metadata.get("titulo", r.metadata.get("tema", "Documento")), r.page_content)
        for r in resultados
    ]


def verificar() -> str:
    """Comprueba la conexión y que el índice tenga contenido (lo usa /ready)."""
    cliente = _store().client
    version = cliente.info()["version"]["number"]
    total = cliente.count(index=ES_INDEX)["count"]
    if total == 0:
        raise RuntimeError(f"El índice '{ES_INDEX}' está vacío: ejecuta `python -m scripts.ingest`.")
    return f"Elasticsearch {version}, índice '{ES_INDEX}' con {total} chunks"


def indexar(reset: bool = False) -> int:
    """Carga los .md, los parte en chunks y los indexa. Devuelve cuántos chunks indexó.

    Es idempotente: si el índice ya tiene documentos y no se pide `reset`, no hace nada
    (así no se duplican chunks ni se pagan embeddings otra vez). Devuelve 0 en ese caso.
    """
    store = _store()
    cliente = store.client

    if reset and cliente.indices.exists(index=ES_INDEX):
        cliente.indices.delete(index=ES_INDEX)
        _store.cache_clear()  # el índice se recrea al agregar documentos
        store = _store()
        cliente = store.client
    elif cliente.indices.exists(index=ES_INDEX) and cliente.count(index=ES_INDEX)["count"] > 0:
        logger.info("El índice '%s' ya tiene documentos: no se re-indexa.", ES_INDEX)
        return 0

    documentos = [
        Document(page_content=contenido, metadata=metadata)
        for metadata, contenido in leer_markdown(CARPETA_DOCUMENTOS)
    ]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )
    chunks = splitter.split_documents(documentos)
    ids = store.add_documents(chunks)
    logger.info("%d documentos -> %d chunks indexados en '%s'.", len(documentos), len(ids), ES_INDEX)
    return len(ids)
