"""Pruebas rápidas que NO necesitan Postgres, Elasticsearch ni OpenAI (todo se simula).

    pip install -r requirements-dev.txt
    pytest
"""
from __future__ import annotations

import re
from collections import namedtuple
from contextlib import contextmanager
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app import agent, rag
from app.config import hora_local, validar_id_cliente
from app.main import app
from app.rag.documentos import leer_markdown
from app.tools.conocimiento import buscar_base_conocimiento
from app.tools.cuenta import _situacion_vencimiento, consultar_estado_cuenta
from app.tools.utilidades import obtener_fecha_actual

cliente_http = TestClient(app)


# --- configuración -----------------------------------------------------------
@pytest.mark.parametrize("valido", ["cliente-001", "demo_rag", "A1", "x.y-z"])
def test_id_valido(valido):
    assert validar_id_cliente(valido) == valido


@pytest.mark.parametrize("invalido", ["", "  ", "../etc", "con espacio", "-empieza", "a" * 65])
def test_id_invalido(invalido):
    with pytest.raises(ValueError):
        validar_id_cliente(invalido)


def test_hora_local_es_hora_de_lima():
    # Lima es UTC-5 todo el año (sin horario de verano).
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    assert hora_local().tzinfo is None
    assert abs((utc - hora_local()).total_seconds() - 5 * 3600) < 60


def test_fecha_actual_en_espanol():
    texto = obtener_fecha_actual.invoke({})
    assert re.match(
        r"Hoy es \d{4}-\d{2}-\d{2} \((lunes|martes|miércoles|jueves|viernes|sábado|domingo)\)", texto
    )


# --- base de conocimiento --------------------------------------------------------
def test_leer_markdown(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\ntema: prorrateo\ncategoria: facturacion\npalabras_clave: [uno, dos]\n---\n# Título\nTexto\n",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text("# Sin frontmatter\nTexto", encoding="utf-8")
    (a_meta, a_texto), (b_meta, b_texto) = leer_markdown(str(tmp_path))
    assert a_meta["categoria"] == "facturacion" and a_meta["archivo"] == "a.md"
    assert a_meta["palabras_clave"] == ["uno", "dos"]
    assert a_texto.startswith("# Título")
    assert b_meta == {"archivo": "b.md"} and b_texto.startswith("# Sin frontmatter")


def test_leer_markdown_carpeta_vacia(tmp_path):
    with pytest.raises(FileNotFoundError):
        leer_markdown(str(tmp_path))


def test_herramienta_rag_formatea_resultados(monkeypatch):
    monkeypatch.setattr(rag, "buscar", lambda p, c, k=3: [("Título A", "Texto A"), ("Título B", "Texto B")])
    salida = buscar_base_conocimiento.invoke({"pregunta": "prorrateo", "categoria": "facturacion"})
    assert salida == "### Título A\nTexto A\n\n### Título B\nTexto B"


def test_herramienta_rag_sin_resultados_y_con_error(monkeypatch):
    monkeypatch.setattr(rag, "buscar", lambda p, c, k=3: [])
    assert "No se encontro" in buscar_base_conocimiento.invoke({"pregunta": "x"})

    def falla(*args, **kwargs):
        raise RuntimeError("ES caído")

    monkeypatch.setattr(rag, "buscar", falla)
    assert buscar_base_conocimiento.invoke({"pregunta": "x"}).startswith("ERROR:")


# --- herramientas SQL (con una conexión falsa) --------------------------------------
Fila = namedtuple("Fila", "monto_total fecha_vencimiento estado")


def _conexion_falsa(fila=None, error=None):
    class Cursor:
        def execute(self, *args):
            if error:
                raise error

        def fetchone(self):
            return fila

    class Conexion:
        def cursor(self):
            return Cursor()

    @contextmanager
    def get_connection():
        yield Conexion()

    return get_connection


def test_estado_cuenta_con_deuda_vencida(monkeypatch):
    monkeypatch.setattr("app.tools.cuenta.hora_local", lambda: datetime(2026, 10, 13, 12, 0))
    monkeypatch.setattr(
        "app.tools.cuenta.get_connection", _conexion_falsa(Fila(99.8, date(2024, 1, 20), "EMITIDO"))
    )
    salida = consultar_estado_cuenta.invoke({"nro_documento": "10234567"})
    assert salida == (
        "Estado: EMITIDO. Monto total adeudado: S/ 99.80. Fecha de vencimiento: 2024-01-20. "
        "Situacion: VENCIDA, con 997 dias de mora (hoy es 2026-10-13)."
    )


@pytest.mark.parametrize(
    "vencimiento, esperado",
    [
        (date(2026, 10, 20), "AUN NO VENCE, faltan 7 dias"),
        (date(2026, 10, 13), "vence HOY"),
        (datetime(2026, 10, 12, 8, 0), "VENCIDA, con 1 dias de mora"),
        ("2026-10-01", "VENCIDA, con 12 dias de mora"),
    ],
)
def test_situacion_vencimiento(monkeypatch, vencimiento, esperado):
    monkeypatch.setattr("app.tools.cuenta.hora_local", lambda: datetime(2026, 10, 13, 12, 0))
    assert esperado in _situacion_vencimiento(vencimiento)


def test_estado_cuenta_sin_deuda_y_con_error_de_bd(monkeypatch):
    monkeypatch.setattr("app.tools.cuenta.get_connection", _conexion_falsa(Fila(None, None, None)))
    assert consultar_estado_cuenta.invoke({"nro_documento": "1"}).startswith("ERROR: No se encontro deuda")

    monkeypatch.setattr("app.tools.cuenta.get_connection", _conexion_falsa(error=OSError("sin red")))
    assert consultar_estado_cuenta.invoke({"nro_documento": "1"}).startswith("ERROR: No se pudo consultar")


# --- historial ---------------------------------------------------------------------
def test_historial_omite_herramientas(monkeypatch):
    mensajes = [
        HumanMessage(content="Hola, mi DNI es 10234567"),
        AIMessage(content="", tool_calls=[{"name": "consultar_estado_cuenta", "args": {}, "id": "1"}]),
        ToolMessage(content="Estado: EMITIDO", tool_call_id="1"),
        AIMessage(content="Tu deuda es S/ 99.80"),
    ]

    class Checkpointer:
        def get_tuple(self, config):
            return type("T", (), {"checkpoint": {"channel_values": {"messages": mensajes}}})()

    monkeypatch.setattr(agent, "get_checkpointer", lambda: Checkpointer())
    assert agent.historial("cliente-001") == [
        {"role": "user", "content": "Hola, mi DNI es 10234567"},
        {"role": "assistant", "content": "Tu deuda es S/ 99.80"},
    ]


def test_historial_cliente_nuevo(monkeypatch):
    class Checkpointer:
        def get_tuple(self, config):
            return None

    monkeypatch.setattr(agent, "get_checkpointer", lambda: Checkpointer())
    assert agent.historial("cliente-nuevo") == []


# --- API ----------------------------------------------------------------------------
def test_health():
    r = cliente_http.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_chat_ok(monkeypatch):
    monkeypatch.setattr(agent, "chat", lambda cliente_id, mensaje: f"eco({cliente_id}): {mensaje}")
    r = cliente_http.post("/chat", json={"cliente_id": "cliente-001", "mensaje": "hola"})
    assert r.status_code == 200
    assert r.json() == {"cliente_id": "cliente-001", "respuesta": "eco(cliente-001): hola"}


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"cliente_id": "../etc", "mensaje": "hola"},
        {"cliente_id": "cliente-001", "mensaje": ""},
        {"cliente_id": "cliente-001"},
    ],
)
def test_chat_rechaza_entradas_invalidas(cuerpo):
    assert cliente_http.post("/chat", json=cuerpo).status_code == 422


def test_chat_error_interno_devuelve_503_sin_detalles(monkeypatch):
    def falla(cliente_id, mensaje):
        raise RuntimeError("password=secreta host=10.0.0.5")

    monkeypatch.setattr(agent, "chat", falla)
    r = cliente_http.post("/chat", json={"cliente_id": "cliente-001", "mensaje": "hola"})
    assert r.status_code == 503
    assert "secreta" not in r.text and "10.0.0.5" not in r.text


def test_historial_y_reinicio(monkeypatch):
    borrados = []
    monkeypatch.setattr(agent, "historial", lambda cliente_id: [{"role": "user", "content": "hola"}])
    monkeypatch.setattr(agent, "reiniciar", borrados.append)
    assert cliente_http.get("/historial/cliente-001").json()["mensajes"] == [{"role": "user", "content": "hola"}]
    assert cliente_http.delete("/historial/cliente-001").json()["reiniciado"] is True
    assert borrados == ["cliente-001"]
    assert cliente_http.get("/historial/a b").status_code == 422


def test_ready_ok_y_con_fallo(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-prueba")
    monkeypatch.setattr("app.main.verificar_postgres", lambda: None)
    monkeypatch.setattr(rag, "verificar", lambda: "Elasticsearch 8.19, índice con 29 chunks")
    r = cliente_http.get("/ready")
    assert r.status_code == 200 and r.json()["elasticsearch"]["ok"] is True
    assert r.json()["openai"]["ok"] is True

    def sin_conexion():
        raise OSError("connection to server at 10.0.0.5 failed")

    monkeypatch.setattr("app.main.verificar_postgres", sin_conexion)
    r = cliente_http.get("/ready")
    assert r.status_code == 503
    assert r.json()["postgres"]["ok"] is False
    assert "10.0.0.5" not in r.text  # los hosts no se filtran en la respuesta pública

    monkeypatch.delenv("OPENAI_API_KEY")
    r = cliente_http.get("/ready")
    assert r.json()["openai"]["ok"] is False and "OPENAI_API_KEY" in r.json()["openai"]["error"]


def test_la_interfaz_se_sirve_en_la_raiz():
    r = cliente_http.get("/")
    assert r.status_code == 200 and "gradio" in r.text.lower()
