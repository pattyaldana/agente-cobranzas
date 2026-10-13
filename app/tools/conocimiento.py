"""Herramienta de RAG: busca en la base de conocimiento con filtro por metadata."""
from __future__ import annotations

import logging

from langchain.tools import tool

from app import rag

logger = logging.getLogger(__name__)


@tool
def buscar_base_conocimiento(pregunta: str, categoria: str = "") -> str:
    """Busca informacion conceptual en la base de conocimiento: como
    funciona el financiamiento (de servicio o de equipos), el ciclo de
    facturacion, el prorrateo, el billshock, el debito automatico o los
    medios de pago. Usar SOLO para preguntas conceptuales/generales, NUNCA
    para consultar la deuda o el recibo personal de un cliente especifico
    (para eso existen las otras herramientas de consulta).

    Args:
        pregunta: la pregunta o tema que quiere entender el cliente.
        categoria: opcional. Una de 'financiamiento', 'facturacion' o
            'pagos', si la pregunta claramente pertenece a una sola
            categoria. Dejar vacio para buscar en todas.
    """
    try:
        resultados = rag.buscar(pregunta, categoria, k=3)
    except Exception:
        logger.exception("buscar_base_conocimiento falló")
        return "ERROR: No se pudo consultar la base de conocimiento en este momento."

    if not resultados:
        return "No se encontro informacion relevante en la base de conocimiento."

    return "\n\n".join(f"### {titulo}\n{texto}" for titulo, texto in resultados)
