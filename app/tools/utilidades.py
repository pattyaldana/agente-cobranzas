"""Herramienta de fecha actual."""
from __future__ import annotations

from langchain.tools import tool

from app.config import ZONA_HORARIA, hora_local

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@tool
def obtener_fecha_actual() -> str:
    """Devuelve la fecha y hora actuales. Usar esta herramienta siempre que
    se necesite saber "hoy", por ejemplo para calcular dias de mora, decir si
    un recibo esta vencido, o validar una fecha de compromiso de pago futura.
    No asumas la fecha de memoria: siempre consulta esta herramienta primero.
    """
    ahora = hora_local()
    dia = _DIAS[ahora.weekday()]
    # El día de la semana se arma a mano: strftime("%A") depende del idioma del servidor.
    return ahora.strftime(f"Hoy es %Y-%m-%d ({dia}), hora local %H:%M ({ZONA_HORARIA.key}).")
