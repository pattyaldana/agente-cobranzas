"""RAG con LlamaIndex + Elasticsearch (backend opcional: RAG_BACKEND=llamaindex).

Es el pipeline del notebook (celdas 38-47): MarkdownNodeParser + SentenceSplitter,
VectorStoreIndex sobre ElasticsearchStore y recuperación con MetadataFilters.

El cliente de Elasticsearch que usa LlamaIndex es asíncrono. Para que no dependa
del bucle de eventos de quien lo llame (FastAPI, hilos de Gradio, Jupyter), las
consultas se ejecutan en un hilo propio con su bucle aislado, igual que en el notebook.

Requiere instalar requirements-llamaindex.txt.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
from functools import lru_cache

from elasticsearch import Elasticsearch
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.elasticsearch import ElasticsearchStore

from app.config import CARPETA_DOCUMENTOS, EMBEDDING_MODEL, ES_INDEX, ES_USER, requerida
from app.rag.documentos import leer_markdown

if sys.platform == "win32":  # necesario para el cliente async de Elasticsearch en Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = logging.getLogger(__name__)


class _BucleAislado:
    """Un bucle de eventos propio, corriendo en un hilo daemon."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._hilo = threading.Thread(target=self._correr, daemon=True)
        self._hilo.start()

    def _correr(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def ejecutar(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()


@lru_cache(maxsize=1)
def _bucle() -> _BucleAislado:
    return _BucleAislado()


def _configurar_embeddings() -> None:
    Settings.embed_model = OpenAIEmbedding(model=EMBEDDING_MODEL)


def _crear_store() -> ElasticsearchStore:
    return ElasticsearchStore(
        index_name=ES_INDEX,
        es_url=requerida("ES_URL"),
        es_user=ES_USER,
        es_password=requerida("ES_PASSWORD"),
    )


def _cliente_admin() -> Elasticsearch:
    return Elasticsearch(requerida("ES_URL"), basic_auth=(ES_USER, requerida("ES_PASSWORD")))


@lru_cache(maxsize=1)
def _indice() -> VectorStoreIndex:
    # Objeto de conexión dedicado a consultas: su cliente async se enlaza por primera
    # vez dentro del bucle aislado (en la primera llamada a buscar()).
    _configurar_embeddings()
    return VectorStoreIndex.from_vector_store(_crear_store())


def _filtros_categoria(categoria: str) -> MetadataFilters | None:
    if not categoria:
        return None
    return MetadataFilters(
        filters=[MetadataFilter(key="categoria", value=categoria, operator=FilterOperator.EQ)]
    )


def buscar(pregunta: str, categoria: str = "", k: int = 3) -> list[tuple[str, str]]:
    """Devuelve [(título, texto)] de los k chunks más parecidos."""
    retriever = _indice().as_retriever(similarity_top_k=k, filters=_filtros_categoria(categoria))
    resultados = _bucle().ejecutar(retriever.aretrieve(pregunta))
    salida = []
    for r in resultados:
        meta = r.node.metadata
        salida.append((meta.get("titulo", meta.get("tema", "Documento")), r.node.get_content()))
    return salida


def verificar() -> str:
    cliente = _cliente_admin()
    try:
        version = cliente.info()["version"]["number"]
        total = cliente.count(index=ES_INDEX)["count"]
    finally:
        cliente.close()
    if total == 0:
        raise RuntimeError(f"El índice '{ES_INDEX}' está vacío: ejecuta `python -m scripts.ingest`.")
    return f"Elasticsearch {version}, índice '{ES_INDEX}' con {total} chunks"


def _a_documentos() -> list[Document]:
    documentos = []
    for metadata, contenido in leer_markdown(CARPETA_DOCUMENTOS):
        # La metadata de LlamaIndex debe ser plana: las listas se pasan a texto separado por comas.
        plana = {
            k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in metadata.items()
        }
        doc = Document(text=contenido, metadata=plana)
        # 'archivo' queda como metadata pero no se mezcla con el texto embebido ni con el del LLM.
        doc.excluded_embed_metadata_keys = ["archivo"]
        doc.excluded_llm_metadata_keys = ["archivo"]
        documentos.append(doc)
    return documentos


def indexar(reset: bool = False) -> int:
    """Indexa los .md. Idempotente (ver langchain_rag.indexar). Devuelve chunks indexados."""
    admin = _cliente_admin()
    try:
        existe = admin.indices.exists(index=ES_INDEX)
        if reset and existe:
            admin.indices.delete(index=ES_INDEX)
            existe = False
        if existe and admin.count(index=ES_INDEX)["count"] > 0:
            logger.info("El índice '%s' ya tiene documentos: no se re-indexa.", ES_INDEX)
            return 0
    finally:
        admin.close()

    _configurar_embeddings()
    documentos = _a_documentos()
    nodos = SentenceSplitter(chunk_size=512, chunk_overlap=50).get_nodes_from_documents(
        MarkdownNodeParser().get_nodes_from_documents(documentos)
    )
    # Descarta chunks que son solo un encabezado: no aportan contenido y meten ruido.
    nodos = [n for n in nodos if len(n.text.strip()) > 40]

    storage_context = StorageContext.from_defaults(vector_store=_crear_store())
    VectorStoreIndex(nodos, storage_context=storage_context, show_progress=True)
    logger.info("%d documentos -> %d chunks indexados en '%s'.", len(documentos), len(nodos), ES_INDEX)
    return len(nodos)
