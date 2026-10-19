"""Interfaz web (Gradio): chat con selector de cliente.

Cada cliente es un ID que se usa como `thread_id` de la memoria del agente: al
cambiar de cliente se carga su conversación guardada en Postgres y el agente solo
"recuerda" lo que habló con ese cliente.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr  # noqa: E402  (después de fijar la variable de arriba)

from app import admin, agent  # noqa: E402
from app.config import ARCHIVO_CLIENTES_DEMO, validar_id_cliente  # noqa: E402

logger = logging.getLogger(__name__)

TEMA = gr.themes.Soft(primary_hue="indigo", neutral_hue="slate")
CSS = """
#titulo h1 { margin-bottom: 0.2rem; }
#panel-cliente { padding-right: 8px; }
.fila-vista { justify-content: flex-end; }
"""


def _cargar_clientes() -> list[dict]:
    try:
        return json.loads(Path(ARCHIVO_CLIENTES_DEMO).read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("No se encontró %s: se usa un cliente por defecto.", ARCHIVO_CLIENTES_DEMO)
        return [{"id": "cliente-001", "nombre": "Cliente 1", "dni": "", "escenario": ""}]


CLIENTES = _cargar_clientes()
_POR_ID = {c["id"]: c for c in CLIENTES}


def _descripcion(cliente_id: str) -> str:
    cliente = _POR_ID.get(cliente_id)
    if not cliente:
        return f"ID personalizado `{cliente_id}`: memoria nueva, independiente de los demás clientes."
    dni = f" · DNI de prueba: `{cliente['dni']}`" if cliente.get("dni") else ""
    return f"**{cliente['nombre']}**{dni}\n\n{cliente.get('escenario', '')}"


def cambiar_cliente(cliente_id: str):
    """Carga la conversación guardada del cliente elegido."""
    try:
        cliente_id = validar_id_cliente(cliente_id)
    except ValueError as error:
        gr.Warning(str(error))
        return [], f"⚠️ {error}"
    try:
        mensajes = agent.historial(cliente_id)
    except Exception:
        logger.exception("No se pudo cargar el historial de %s", cliente_id)
        gr.Warning("No pude cargar el historial de este cliente (¿base de datos disponible?).")
        mensajes = []
    return mensajes, _descripcion(cliente_id)


def enviar(mensaje: str, historial: list, cliente_id: str):
    """Muestra el mensaje enseguida y, cuando el agente responde, agrega la respuesta."""
    mensaje = (mensaje or "").strip()
    if not mensaje:
        yield gr.skip(), gr.skip()
        return
    try:
        cliente_id = validar_id_cliente(cliente_id)
    except ValueError as error:
        gr.Warning(str(error))
        yield gr.skip(), gr.skip()
        return

    historial = list(historial or []) + [{"role": "user", "content": mensaje}]
    yield "", historial
    try:
        respuesta = agent.chat(cliente_id, mensaje)
    except Exception:
        logger.exception("Error al responder al cliente %s", cliente_id)
        respuesta = "⚠️ Ocurrió un error técnico al procesar tu mensaje. Intenta de nuevo en unos segundos."
    yield "", historial + [{"role": "assistant", "content": respuesta}]


def saludo_con_dni(cliente_id: str) -> str:
    dni = _POR_ID.get(cliente_id, {}).get("dni")
    return f"Hola, quiero saber cuánto debo. Mi DNI es {dni}" if dni else "Hola, quiero saber cuánto debo."


def reiniciar_memoria(cliente_id: str):
    try:
        cliente_id = validar_id_cliente(cliente_id)
        agent.reiniciar(cliente_id)
        gr.Info(f"Memoria de '{cliente_id}' reiniciada.")
        return []
    except Exception as error:
        logger.exception("No se pudo reiniciar la memoria")
        gr.Warning(f"No se pudo reiniciar la memoria: {error}")
        return gr.skip()


# --- vista de administrador ---------------------------------------------------------
def _tabla(consulta, dni: str):
    """Devuelve (texto del contador, tabla) para un Dataframe."""
    encabezados, filas = consulta(dni)
    filtro = f" para el DNI «{dni.strip()}»" if (dni or "").strip() else ""
    if len(filas) >= admin.LIMITE_FILAS:
        conteo = f"Se muestran los primeros {admin.LIMITE_FILAS} registros{filtro}. Usa el buscador para acotar."
    else:
        conteo = f"**{len(filas)}** registro(s){filtro}."
    return conteo, {"headers": encabezados, "data": filas}


def ir_a_admin():
    return gr.update(visible=False), gr.update(visible=True)


def volver_a_cliente():
    """Vuelve a la vista de cliente y cierra la sesión de administrador."""
    return (
        gr.update(visible=True),  # vista_cliente
        gr.update(visible=False),  # vista_admin
        False,  # autenticado
        gr.update(visible=True),  # login
        gr.update(visible=False),  # panel_admin
        "",  # clave
        "",  # mensaje_login
    )


def entrar_admin(clave: str):
    if not admin.admin_habilitado():
        return False, gr.skip(), gr.skip(), "⚠️ La vista de administrador está desactivada: falta la variable ADMIN_PASSWORD."
    if not admin.clave_admin_valida(clave):
        time.sleep(1)  # frena los intentos de adivinar la clave
        return False, gr.skip(), gr.skip(), "❌ Clave incorrecta."
    return True, gr.update(visible=False), gr.update(visible=True), ""


def consultar_admin(dni: str, autenticado: bool):
    """Llena las dos tablas. El estado `autenticado` vive en el servidor, no en el navegador."""
    if not autenticado:
        return gr.skip(), gr.skip(), gr.skip(), gr.skip()
    try:
        texto_c, tabla_c = _tabla(admin.compromisos_pago, dni)
        texto_m, tabla_m = _tabla(admin.motivos_no_pago, dni)
    except Exception:
        logger.exception("No se pudieron consultar los datos de administrador")
        gr.Warning("No se pudieron consultar los datos (¿base de datos disponible?).")
        return gr.skip(), gr.skip(), gr.skip(), gr.skip()
    return texto_c, tabla_c, texto_m, tabla_m


def limpiar_busqueda():
    return ""


with gr.Blocks(title="Asistente de cobranzas") as demo:
    gr.Markdown(
        "# Asistente de cobranzas\n"
        "Agente con herramientas y RAG que explica la deuda y el recibo de un cliente. "
        "Cada cliente tiene su propia memoria.",
        elem_id="titulo",
    )
    autenticado = gr.State(False)

    # ---------------- vista de cliente ----------------
    with gr.Column(visible=True) as vista_cliente:
        with gr.Row(elem_classes="fila-vista"):
            boton_a_admin = gr.Button(
                "Vista de administrador", size="sm", variant="secondary", scale=0, min_width=200
            )
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=300, elem_id="panel-cliente"):
                cliente = gr.Dropdown(
                    choices=[(c["nombre"], c["id"]) for c in CLIENTES],
                    value=CLIENTES[0]["id"],
                    allow_custom_value=True,
                    label="Cliente (ID de memoria)",
                    info="También puedes escribir un ID nuevo para empezar con memoria en blanco.",
                )
                descripcion = gr.Markdown()
                boton_dni = gr.Button("Escribir saludo con el DNI de prueba")
                boton_reiniciar = gr.Button("Reiniciar memoria de este cliente", variant="secondary")
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    label="Conversación",
                    height=520,
                    # Respaldo: si el modelo igual escribe LaTeX, se dibuja en vez de verse como código.
                    latex_delimiters=[
                        {"left": "$$", "right": "$$", "display": True},
                        {"left": "\\[", "right": "\\]", "display": True},
                        {"left": "\\(", "right": "\\)", "display": False},
                    ],
                    placeholder="Elige un cliente y escribe un mensaje para empezar.",
                )
                with gr.Row():
                    caja = gr.Textbox(
                        show_label=False,
                        container=False,
                        placeholder="Escribe tu mensaje y presiona Enter",
                        scale=6,
                        autofocus=True,
                    )
                    boton_enviar = gr.Button("Enviar", variant="primary", scale=1)


    # ---------------- vista de administrador ----------------
    with gr.Column(visible=False) as vista_admin:
        with gr.Row(elem_classes="fila-vista"):
            boton_a_cliente = gr.Button(
                "Vista de cliente", size="sm", variant="secondary", scale=0, min_width=200
            )
        with gr.Group(visible=True) as login:
            clave = gr.Textbox(label="Clave de administrador", type="password")
            boton_entrar = gr.Button("Entrar", variant="primary")
            mensaje_login = gr.Markdown()
        with gr.Column(visible=False) as panel_admin:
            with gr.Row():
                dni_busqueda = gr.Textbox(
                    label="Buscar por DNI",
                    placeholder="Ej.: 10234567 (vacío = todos)",
                    scale=4,
                )
                boton_buscar = gr.Button("Buscar", variant="primary", scale=1)
                boton_limpiar = gr.Button("Limpiar", scale=1)
            with gr.Tabs():
                with gr.Tab("Compromisos de pago"):
                    conteo_compromisos = gr.Markdown()
                    tabla_compromisos = gr.Dataframe(interactive=False, wrap=True, max_height=480)
                with gr.Tab("Motivos de no pago"):
                    conteo_motivos = gr.Markdown()
                    tabla_motivos = gr.Dataframe(interactive=False, wrap=True, max_height=480)

    cliente.change(cambiar_cliente, cliente, [chatbot, descripcion])
    demo.load(cambiar_cliente, cliente, [chatbot, descripcion])

    entradas = [caja, chatbot, cliente]
    caja.submit(enviar, entradas, [caja, chatbot])
    boton_enviar.click(enviar, entradas, [caja, chatbot])

    boton_dni.click(saludo_con_dni, cliente, caja)
    boton_reiniciar.click(reiniciar_memoria, cliente, chatbot)

    # --- eventos de la vista de administrador ---
    salidas_tablas = [conteo_compromisos, tabla_compromisos, conteo_motivos, tabla_motivos]
    boton_a_admin.click(ir_a_admin, None, [vista_cliente, vista_admin])
    boton_a_cliente.click(
        volver_a_cliente,
        None,
        [vista_cliente, vista_admin, autenticado, login, panel_admin, clave, mensaje_login],
    )
    for disparador in (clave.submit, boton_entrar.click):
        disparador(
            entrar_admin, clave, [autenticado, login, panel_admin, mensaje_login]
        ).then(consultar_admin, [dni_busqueda, autenticado], salidas_tablas)
    for disparador in (dni_busqueda.submit, boton_buscar.click):
        disparador(consultar_admin, [dni_busqueda, autenticado], salidas_tablas)
    boton_limpiar.click(limpiar_busqueda, None, dni_busqueda).then(
        consultar_admin, [dni_busqueda, autenticado], salidas_tablas
    )

demo.queue(default_concurrency_limit=8)
