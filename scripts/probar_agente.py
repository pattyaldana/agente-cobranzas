"""Prueba de humo del agente por consola (sin interfaz web).

Repite las conversaciones de prueba del notebook con IDs de cliente distintos
(prueba-001 ... prueba-004) y al final muestra cuántos mensajes guardó la memoria
de cada uno, para comprobar que no se mezclan.

    python -m scripts.probar_agente
    python -m scripts.probar_agente --reiniciar    # borra antes la memoria de esos IDs

OJO: usa las herramientas reales, así que escribe en tu base (compromisos y gestiones
de cobranza), igual que el notebook.
"""
from __future__ import annotations

import argparse
import logging

from app import agent

ESCENARIOS = {
    "prueba-001": [  # deuda -> detalle -> historial
        "Hola, quiero saber cuánto debo. Mi DNI es 10234567",
        "Sí, explícame el detalle",
        "Dame mi historial de pagos",
    ],
    "prueba-002": [  # el cliente no quiere comprometerse: motivo de no pago
        "Hola, quiero saber mi deuda",
        "20345678",
        "No",
        "No estoy seguro de cuándo me pagan",
    ],
    "prueba-003": [  # preguntas conceptuales: RAG
        "Hola, quiero saber cuánto debo. Mi DNI es 44556677",
        "Y si compro un celular, ¿en cuántas cuotas máximo lo puedo financiar?",
        "¿Cuáles son los medios para pagar mi recibo?",
        "¿Cuál es el proceso para afiliarme al débito automático?",
    ],
    "prueba-004": [  # documento inexistente: manejo de errores
        "Hola, quiero saber cuánto debo. Mi DNI es 12345678",
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba de humo del agente.")
    parser.add_argument("--reiniciar", action="store_true", help="borra antes la memoria de los IDs de prueba")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    if args.reiniciar:
        for cliente_id in ESCENARIOS:
            agent.reiniciar(cliente_id)

    for cliente_id, mensajes in ESCENARIOS.items():
        print(f"\n{'=' * 70}\nCliente {cliente_id}\n{'=' * 70}")
        for mensaje in mensajes:
            print(f"\nCliente: {mensaje}")
            print(f"Agente:  {agent.chat(cliente_id, mensaje)}")

    print(f"\n{'=' * 70}\nMensajes guardados en la memoria de cada cliente\n{'=' * 70}")
    for cliente_id, mensajes in ESCENARIOS.items():
        guardados = agent.historial(cliente_id)
        esperados = 2 * len(mensajes)  # una pregunta y una respuesta por turno
        print(f"{cliente_id}: {len(guardados)} mensajes guardados (esperados: {esperados})")


if __name__ == "__main__":
    main()
