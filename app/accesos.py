"""Registro de qué clientes con sesión iniciada entraron a la tienda y cuándo.

Una fila por cliente y por día (`accesos_clientes`): primera y última hora en
que se lo vio, y cuántas páginas vio. Lo lee `conectar` (pantalla "Accesos a
la tienda"). Solo cuenta clientes logueados; los visitantes anónimos no se
registran. Las visitas internas (cookie `mo_interno=1`, que se pone entrando
una vez con `?interno=1`) se ignoran. Nunca debe romper ni demorar una página:
se escribe en segundo plano y cualquier error se traga.
"""
from __future__ import annotations

import threading

from sqlalchemy import text

from .db import engine_tienda

_tabla_lista = False


def _asegurar_tabla() -> None:
    global _tabla_lista
    if _tabla_lista:
        return
    with engine_tienda.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS accesos_clientes (
                fecha DATE NOT NULL,
                user_id INT NOT NULL,
                primera DATETIME NOT NULL,
                ultima DATETIME NOT NULL,
                paginas INT NOT NULL DEFAULT 1,
                PRIMARY KEY (fecha, user_id)
            )
        """))
    _tabla_lista = True


def _escribir(user_id: int) -> None:
    try:
        _asegurar_tabla()
        with engine_tienda.begin() as cx:
            cx.execute(text("""
                INSERT INTO accesos_clientes (fecha, user_id, primera, ultima, paginas)
                VALUES (CURDATE(), :u, NOW(), NOW(), 1)
                ON DUPLICATE KEY UPDATE ultima = NOW(), paginas = paginas + 1
            """), {"u": user_id})
    except Exception:
        pass


def registrar(request, cliente) -> None:
    """Llamar al renderizar una página completa (GET, no HTMX) con el cliente
    de la sesión (o None)."""
    if cliente is None or request.method != "GET":
        return
    if request.headers.get("HX-Request") or request.cookies.get("mo_interno") == "1":
        return
    threading.Thread(target=_escribir, args=(cliente.id,), daemon=True).start()
