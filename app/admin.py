"""Vista de administrador: consultas de solo lectura sobre los compromisos de pago y los
motivos de no pago registrados por el agente.

Las dos consultas son las del proyecto. Solo se agregó (a) el filtro opcional por DNI,
con parámetro (nunca se concatena texto del usuario al SQL), (b) ORDER BY y (c) LIMIT.
Si quieres ver solo lo que registró el chatbot en "motivos", agrega
`AND tipo_gestion = 'Chatbot'` a MOTIVOS_SQL.
"""
from __future__ import annotations

import hmac
import os
from datetime import date, datetime
from decimal import Decimal

from app.db import get_connection

LIMITE_FILAS = 500
# Con DNI vacío el filtro no hace nada; con DNI busca coincidencias parciales.
_FILTRO = "AND (%(dni)s = '' OR strpos(clientes.nro_documento::text, %(dni)s) > 0)"

COMPROMISOS_SQL = f"""
    SELECT tipo_documento, nro_documento, nombre, apellidos, nro_recibo, emision, vencimiento, saldo,
           compromiso_pago.fecha AS fecha_compromiso, compromiso_pago.monto AS monto_compromiso
    FROM clientes
    JOIN cuentas ON clientes.id_cliente = cuentas.id_cliente
    JOIN recibos ON cuentas.id_cuenta = recibos.id_cuenta
    JOIN asignacion_cobranza ON recibos.id_recibo = asignacion_cobranza.id_recibo
    JOIN gestion_cobranza ON asignacion_cobranza.id_asignacion = gestion_cobranza.id_asignacion
    JOIN compromiso_pago ON gestion_cobranza.id_gestion = compromiso_pago.id_gestion
    WHERE tipo_documento = 'DNI' {_FILTRO}
    ORDER BY compromiso_pago.fecha DESC
    LIMIT %(limite)s
"""

MOTIVOS_SQL = f"""
    SELECT tipo_documento, nro_documento, nombre, apellidos, nro_recibo, emision, vencimiento, saldo,
           tipo_gestion, fecha_gestion, resultado, comentario
    FROM clientes
    JOIN cuentas ON clientes.id_cliente = cuentas.id_cliente
    JOIN recibos ON cuentas.id_cuenta = recibos.id_cuenta
    JOIN asignacion_cobranza ON recibos.id_recibo = asignacion_cobranza.id_recibo
    JOIN gestion_cobranza ON asignacion_cobranza.id_asignacion = gestion_cobranza.id_asignacion
    WHERE tipo_documento = 'DNI' {_FILTRO}
    ORDER BY gestion_cobranza.fecha_gestion DESC
    LIMIT %(limite)s
"""

ENCABEZADOS = {
    "tipo_documento": "Tipo doc.",
    "nro_documento": "DNI",
    "nombre": "Nombre",
    "apellidos": "Apellidos",
    "nro_recibo": "N° recibo",
    "emision": "Emisión",
    "vencimiento": "Vencimiento",
    "saldo": "Saldo (S/)",
    "fecha_compromiso": "Fecha compromiso",
    "monto_compromiso": "Monto compromiso (S/)",
    "tipo_gestion": "Tipo de gestión",
    "fecha_gestion": "Fecha de gestión",
    "resultado": "Resultado",
    "comentario": "Comentario / motivo",
}


def _formatear(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (Decimal, float)):
        return f"{valor:.2f}"
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d %H:%M")
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _consultar(sql: str, dni: str) -> tuple[list[str], list[list[str]]]:
    dni = (dni or "").strip()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, {"dni": dni, "limite": LIMITE_FILAS})
        columnas = [c.name for c in cur.description]
        filas = cur.fetchall()
    return (
        [ENCABEZADOS.get(c, c) for c in columnas],
        [[_formatear(v) for v in fila] for fila in filas],
    )


def compromisos_pago(dni: str = "") -> tuple[list[str], list[list[str]]]:
    return _consultar(COMPROMISOS_SQL, dni)


def motivos_no_pago(dni: str = "") -> tuple[list[str], list[list[str]]]:
    return _consultar(MOTIVOS_SQL, dni)


# --- acceso -------------------------------------------------------------------
def admin_habilitado() -> bool:
    return bool(os.environ.get("ADMIN_PASSWORD", "").strip())


def clave_admin_valida(clave: str) -> bool:
    esperada = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not esperada:
        return False
    return hmac.compare_digest((clave or "").encode("utf-8"), esperada.encode("utf-8"))
