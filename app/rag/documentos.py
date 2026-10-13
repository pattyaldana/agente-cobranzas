"""Lectura de la base de conocimiento: archivos .md con metadata (frontmatter YAML).

Cada archivo empieza con un encabezado como:

    ---
    tema: prorrateo
    categoria: facturacion
    titulo: Cómo se calcula el prorrateo
    palabras_clave: [prorrateo, alta, baja]
    ---
    # Contenido en Markdown...

La metadata se separa del texto para poder filtrar por ella (p. ej. `categoria`)
al recuperar. Esta función la comparten los dos backends de RAG.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def leer_markdown(carpeta: str) -> list[tuple[dict, str]]:
    """Devuelve una lista de (metadata, contenido), una por archivo .md.

    A la metadata se le agrega `archivo` (nombre del .md de origen).
    """
    archivos = sorted(Path(carpeta).glob("*.md"))
    if not archivos:
        raise FileNotFoundError(
            f"No hay archivos .md en '{carpeta}'. Copia ahí los documentos de tu base de conocimiento."
        )

    documentos = []
    for path in archivos:
        texto = path.read_text(encoding="utf-8-sig")
        match = FRONTMATTER_RE.match(texto)
        if match:
            metadata_raw, contenido = match.groups()
            metadata = yaml.safe_load(metadata_raw) or {}
        else:
            logger.warning("%s no tiene frontmatter: se indexa sin metadata.", path.name)
            metadata, contenido = {}, texto
        metadata["archivo"] = path.name
        documentos.append((metadata, contenido.strip()))
    return documentos
