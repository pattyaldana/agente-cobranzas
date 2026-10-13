"""Indexa la base de conocimiento (carpeta base_conocimiento/) en Elasticsearch.

Se ejecuta una vez desde tu PC, antes de usar o desplegar la app:

    python -m scripts.ingest            # indexa solo si el índice está vacío
    python -m scripts.ingest --reset    # borra el índice y vuelve a indexar (al cambiar documentos)

Usa el backend de RAG definido en RAG_BACKEND (langchain por defecto).
"""
from __future__ import annotations

import argparse
import logging

from app import rag
from app.config import CARPETA_DOCUMENTOS, ES_INDEX, RAG_BACKEND


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa la base de conocimiento en Elasticsearch.")
    parser.add_argument("--reset", action="store_true", help="borra el índice antes de indexar")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    print(f"Backend: {RAG_BACKEND} | índice: {ES_INDEX} | carpeta: {CARPETA_DOCUMENTOS}")
    total = rag.indexar(reset=args.reset)
    if total:
        print(f"Listo: {total} chunks indexados.")
    else:
        print("El índice ya tenía documentos y no se tocó. Usa --reset para volver a indexar.")
    print(rag.verificar())


if __name__ == "__main__":
    main()
