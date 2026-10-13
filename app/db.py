"""Conexiones a Postgres (Cloud SQL).

Se usan dos pools distintos porque los requisitos son diferentes:
  - herramientas: transacciones normales (commit al salir del `with`) y filas
    como namedtuple, para poder escribir `row.monto_total`;
  - memoria (PostgresSaver de LangGraph): autocommit y filas como dict, que es
    lo que exige el checkpointer.

Los pools se crean la primera vez que se usan, no al importar el módulo: así la
app arranca (y /health responde) aunque la base de datos no esté disponible.
"""
from __future__ import annotations

import os
from functools import lru_cache

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row, namedtuple_row
from psycopg_pool import ConnectionPool

from app.config import requerida


def _conninfo() -> str:
    # make_conninfo escapa bien contraseñas con caracteres especiales (@, /, :)
    # y admite tanto una IP/host como un socket de Cloud Run (/cloudsql/...).
    # Con socket Unix, libpq ignora sslmode.
    return make_conninfo(
        host=requerida("PG_HOST"),
        port=os.environ.get("PG_PORT", "5432"),
        dbname=requerida("PG_DB"),
        user=requerida("PG_USER"),
        password=requerida("PG_PASSWORD"),
        sslmode=os.environ.get("PG_SSLMODE", "require"),
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )


def _abrir_pool(kwargs: dict, max_size: int) -> ConnectionPool:
    return ConnectionPool(
        conninfo=_conninfo(),
        min_size=1,
        max_size=max_size,
        kwargs=kwargs,
        # Cloud SQL cierra conexiones inactivas: se comprueba cada conexión antes de prestarla.
        check=ConnectionPool.check_connection,
        timeout=15,
        open=True,
    )


@lru_cache(maxsize=1)
def pool_herramientas() -> ConnectionPool:
    return _abrir_pool({"row_factory": namedtuple_row}, max_size=5)


@lru_cache(maxsize=1)
def pool_memoria() -> ConnectionPool:
    return _abrir_pool({"autocommit": True, "row_factory": dict_row}, max_size=5)


def get_connection():
    """Uso: `with get_connection() as conn:` (hace commit al salir sin error)."""
    return pool_herramientas().connection()


def verificar_postgres() -> None:
    """Lanza una excepción si no se puede consultar Postgres (lo usa /ready)."""
    with get_connection() as conn:
        conn.execute("SELECT 1").fetchone()


def cerrar_pools() -> None:
    """Cierra los pools al apagar la app (si se crearon)."""
    for fabrica in (pool_herramientas, pool_memoria):
        if fabrica.cache_info().currsize:
            fabrica().close()
