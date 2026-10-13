"""Las 7 herramientas del agente (mismo orden que en el notebook)."""
from app.tools.cobranza import registrar_compromiso_pago, registrar_gestion_cobranza
from app.tools.conocimiento import buscar_base_conocimiento
from app.tools.cuenta import (
    consultar_detalle_recibo,
    consultar_estado_cuenta,
    consultar_historial_pagos,
)
from app.tools.utilidades import obtener_fecha_actual

TOOLS = [
    consultar_estado_cuenta,
    consultar_detalle_recibo,
    consultar_historial_pagos,
    obtener_fecha_actual,
    registrar_compromiso_pago,
    registrar_gestion_cobranza,
    buscar_base_conocimiento,
]
