"""Herramientas de escritura: compromiso de pago y gestión de cobranza (Postgres).

Son las del notebook V4 (celda de Postgres). Los INSERT se confirman al salir del
bloque `with` (commit automático del pool).
"""
from __future__ import annotations

import logging

from langchain.tools import tool

from app.config import hora_local
from app.db import get_connection

logger = logging.getLogger(__name__)

ID_TIPIFICACION_MOTIVO_CLIENTE = 11  # categoria fija: motivo registrado por el cliente


@tool
def registrar_compromiso_pago(nro_documento: str, monto: float, fecha_compromiso: str) -> str:
    """Registra un compromiso de pago para el cliente (identificado por su
    documento de identidad), siempre y cuando ya exista una gestion de
    cobranza asociada a su recibo. Usar SOLO despues de que el cliente haya
    confirmado explicitamente el monto y la fecha.

    Args:
        nro_documento: Numero de documento de identidad del cliente (DNI),
            tal como esta en Clientes.nro_documento.
        monto: Monto que el cliente se compromete a pagar.
        fecha_compromiso: Fecha del compromiso en formato YYYY-MM-DD.
    """
    query_gestion = """
        SELECT gc.id_gestion
        FROM Gestion_cobranza gc
        JOIN Asignacion_cobranza ac ON ac.id_asignacion = gc.id_asignacion
        JOIN Recibos r ON r.id_recibo = ac.id_recibo
        JOIN Cuentas cu ON cu.id_cuenta = r.id_cuenta
        JOIN Clientes c ON c.id_cliente = cu.id_cliente
        WHERE c.nro_documento = %s
        ORDER BY gc.fecha_gestion DESC, gc.id_gestion DESC
        LIMIT 1
    """
    insert_compromiso = """
        INSERT INTO Compromiso_pago (fecha, monto, estado, id_gestion)
        VALUES (%s, %s, 'PENDIENTE', %s)
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query_gestion, (nro_documento,))
            gestion = cur.fetchone()
            if not gestion:
                return (
                    "ERROR: Este cliente aun no tiene una gestion de cobranza activa, "
                    "asi que no se puede registrar un compromiso de pago automatico. "
                    "Deriva a un asesor humano."
                )
            cur.execute(insert_compromiso, (fecha_compromiso, monto, gestion.id_gestion))
            # el commit se hace al salir del bloque "with"
    except Exception:
        logger.exception("registrar_compromiso_pago falló")
        return "ERROR: No se pudo registrar el compromiso de pago en este momento."

    return f"Compromiso de pago registrado: S/ {monto:.2f} para el {fecha_compromiso}."


@tool
def registrar_gestion_cobranza(nro_documento: str, comentario: str) -> str:
    """Registra una gestion de cobranza cuando el cliente muestra que no va a
    pagar, guardando el motivo que dio el cliente. Si el recibo no tenia una
    Asignacion_cobranza previa, la crea con gestor 'Agente_cobranza'.

    Args:
        nro_documento: Numero de documento de identidad del cliente (DNI).
        comentario: Motivo en las propias palabras del cliente (por ejemplo,
            "esta esperando que le paguen", "perdio el trabajo", etc.).
    """
    query_recibo = """
        SELECT r.id_recibo, r.saldo, r.vencimiento
        FROM Recibos r
        JOIN Cuentas cu ON cu.id_cuenta = r.id_cuenta
        JOIN Clientes c ON c.id_cliente = cu.id_cliente
        WHERE c.nro_documento = %s AND r.saldo > 0
        ORDER BY r.fecha_creacion DESC, r.id_recibo DESC
        LIMIT 1
    """
    query_asignacion = """
        SELECT id_asignacion
        FROM Asignacion_cobranza
        WHERE id_recibo = %s
        ORDER BY fecha_asignacion DESC
        LIMIT 1
    """
    insert_asignacion = """
        INSERT INTO Asignacion_cobranza
            (fecha_asignacion, fecha_fin, deuda_asignada, etapa_cobranza, gestor, dias_mora, id_recibo)
        VALUES (%s, NULL, %s, 'Inicial', 'Agente_cobranza', %s, %s)
        RETURNING id_asignacion
    """
    insert_gestion = """
        INSERT INTO Gestion_cobranza
            (tipo_gestion, fecha_gestion, contacto, resultado, comentario, id_asignacion, id_tipificacion)
        VALUES ('Chatbot', %s, TRUE, 'Motivo de no pago registrado', %s, %s, %s)
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()

            cur.execute(query_recibo, (nro_documento,))
            recibo = cur.fetchone()
            if not recibo:
                return f"ERROR: No se encontro deuda pendiente para el documento '{nro_documento}'."

            cur.execute(query_asignacion, (recibo.id_recibo,))
            asignacion = cur.fetchone()

            ahora = hora_local()

            if asignacion:
                id_asignacion = asignacion.id_asignacion
            else:
                venc = recibo.vencimiento
                venc_date = venc.date() if hasattr(venc, "date") else venc
                dias_mora = (ahora.date() - venc_date).days if venc_date else 0

                cur.execute(
                    insert_asignacion,
                    (ahora, recibo.saldo, dias_mora, recibo.id_recibo),
                )
                id_asignacion = cur.fetchone()[0]

            cur.execute(
                insert_gestion,
                (ahora, comentario, id_asignacion, ID_TIPIFICACION_MOTIVO_CLIENTE),
            )
            # el commit se hace al salir del bloque "with"
    except Exception:
        logger.exception("registrar_gestion_cobranza falló")
        return "ERROR: No se pudo registrar la gestion de cobranza en este momento."

    return "Gestion de cobranza registrada correctamente con el motivo indicado por el cliente."
