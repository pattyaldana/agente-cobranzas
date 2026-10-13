"""Herramientas de consulta de cuenta (solo lectura) sobre Postgres.

Son las del notebook V4. Los docstrings se conservan tal cual porque el LLM los
lee para decidir cuándo usar cada herramienta. Cambio respecto al notebook: los
errores se registran en el log (`logger.exception`) además de devolver el mensaje
"ERROR: ..." al agente; en Cloud Run es la única forma de saber por qué falló.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from langchain.tools import tool

from app.config import hora_local
from app.db import get_connection

logger = logging.getLogger(__name__)


def _situacion_vencimiento(vencimiento) -> str:
    """Compara el vencimiento con la fecha de hoy (hora de Lima) y lo dice con todas las letras.

    El resultado viaja dentro de la respuesta de la herramienta: así el agente no depende de
    acordarse de llamar a obtener_fecha_actual para saber si la deuda ya venció.
    """
    try:
        if isinstance(vencimiento, datetime):
            vencimiento = vencimiento.date()
        elif not isinstance(vencimiento, date):
            vencimiento = date.fromisoformat(str(vencimiento)[:10])
    except ValueError:
        return ""
    hoy = hora_local().date()
    dias = (hoy - vencimiento).days
    if dias > 0:
        return f" Situacion: VENCIDA, con {dias} dias de mora (hoy es {hoy})."
    if dias == 0:
        return f" Situacion: vence HOY (hoy es {hoy})."
    return f" Situacion: AUN NO VENCE, faltan {-dias} dias (hoy es {hoy})."


@tool
def consultar_estado_cuenta(nro_documento: str) -> str:
    """Consulta el estado de cuenta de un cliente a partir de su documento de
    identidad (DNI): monto total adeudado, fecha de vencimiento y estado,
    sumando los recibos no pagados.

    Args:
        nro_documento: Numero de documento de identidad del cliente (DNI),
            tal como esta en Clientes.nro_documento.
    """
    query = """
        SELECT SUM(r.saldo) AS monto_total,
               MIN(r.vencimiento) AS fecha_vencimiento,
               MAX(r.estado) AS estado
        FROM Recibos r
        JOIN Cuentas cu ON cu.id_cuenta = r.id_cuenta
        JOIN Clientes c ON c.id_cliente = cu.id_cliente
        WHERE c.nro_documento = %s AND r.saldo > 0
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (nro_documento,))
            row = cur.fetchone()
    except Exception:
        logger.exception("consultar_estado_cuenta falló")
        return "ERROR: No se pudo consultar el estado de cuenta en este momento."

    if not row or row.monto_total is None:
        return f"ERROR: No se encontro deuda pendiente para el documento '{nro_documento}'. Verifica el numero con el cliente."

    return (
        f"Estado: {row.estado}. "
        f"Monto total adeudado: S/ {row.monto_total:.2f}. "
        f"Fecha de vencimiento: {row.fecha_vencimiento}."
        f"{_situacion_vencimiento(row.fecha_vencimiento)}"
    )


@tool
def consultar_detalle_recibo(nro_documento: str) -> str:
    """Consulta el desglose del recibo mas reciente de un cliente, a partir
    de su documento de identidad: cada concepto (plan, consumo, impuestos,
    mora) con su monto.

    Args:
        nro_documento: Numero de documento de identidad del cliente (DNI),
            tal como esta en Clientes.nro_documento.
    """
    query_recibo = """
        SELECT r.id_recibo
        FROM Recibos r
        JOIN Cuentas cu ON cu.id_cuenta = r.id_cuenta
        JOIN Clientes c ON c.id_cliente = cu.id_cliente
        WHERE c.nro_documento = %s
        ORDER BY r.fecha_creacion DESC, r.id_recibo DESC
        LIMIT 1
    """
    query_detalle = """
        SELECT concepto_cobro, monto
        FROM Detalle_recibo
        WHERE id_recibo = %s
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query_recibo, (nro_documento,))
            recibo = cur.fetchone()
            if not recibo:
                return f"ERROR: No se encontro ningun recibo para el documento '{nro_documento}'."
            cur.execute(query_detalle, (recibo.id_recibo,))
            conceptos = cur.fetchall()
    except Exception:
        logger.exception("consultar_detalle_recibo falló")
        return "ERROR: No se pudo consultar el detalle del recibo en este momento."

    if not conceptos:
        return "El recibo no tiene conceptos registrados."

    lineas = [f"- {c.concepto_cobro}: S/ {c.monto:.2f}" for c in conceptos]
    return "Detalle del recibo:\n" + "\n".join(lineas)


@tool
def consultar_historial_pagos(nro_documento: str) -> str:
    """Consulta los ultimos pagos registrados de un cliente, a partir de su
    documento de identidad, con fecha y monto.

    Args:
        nro_documento: Numero de documento de identidad del cliente (DNI),
            tal como esta en Clientes.nro_documento.
    """
    query = """
        SELECT p.fecha_pago, p.monto_pago
        FROM Pagos p
        JOIN detalle_recibos_pagos drp ON drp.id_pago = p.id_pago
        JOIN Recibos r ON r.id_recibo = drp.id_recibo
        JOIN Cuentas cu ON cu.id_cuenta = r.id_cuenta
        JOIN Clientes c ON c.id_cliente = cu.id_cliente
        WHERE c.nro_documento = %s
        ORDER BY p.fecha_pago DESC
        LIMIT 5
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (nro_documento,))
            pagos = cur.fetchall()
    except Exception:
        logger.exception("consultar_historial_pagos falló")
        return "ERROR: No se pudo consultar el historial de pagos en este momento."

    if not pagos:
        return "No se registran pagos previos para esta cuenta."

    lineas = [f"- {p.fecha_pago}: S/ {p.monto_pago:.2f}" for p in pagos]
    return "Historial de pagos:\n" + "\n".join(lineas)
