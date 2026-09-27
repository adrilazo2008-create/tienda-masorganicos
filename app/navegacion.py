"""Seguimiento de navegación anónima, para poder mostrar "Vistos
recientemente" sin necesidad de que el cliente se loguee.

Vive en la base de la tienda (`iebbbhrt_prueba_paginaweb`), no en el ERP: es
dato de comportamiento web efímero, no información de negocio. `visitante_id`
es un UUID que se genera una sola vez por navegador y se guarda en la misma
cookie de sesión que ya usa la tienda (dura 2 años, ver main.py) — no hace
falta login para tenerlo.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text

from .db import engine_tienda


def _asegurar_tabla() -> None:
    with engine_tienda.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS vistas_producto (
                visitante_id CHAR(36) NOT NULL,
                producto_id INT NOT NULL,
                cliente_id INT NULL,
                visto_en DATETIME NOT NULL,
                PRIMARY KEY (visitante_id, producto_id)
            )
        """))


def visitante_id(session: dict) -> str:
    """UUID estable por navegador, generado una sola vez y guardado en la
    sesión (cookie de 2 años). No identifica a la persona, solo al dispositivo."""
    vid = session.get("visitante_id")
    if not vid:
        vid = str(uuid.uuid4())
        session["visitante_id"] = vid
    return vid


def registrar_vista(visitante_id: str, producto_id: int, cliente_id: int | None = None) -> None:
    """Anota que este visitante vio este producto ahora. Un solo renglón por
    (visitante, producto): si ya lo había visto, se actualiza la fecha (para
    que "recientes" refleje la última vez que lo miró, no la primera)."""
    _asegurar_tabla()
    with engine_tienda.begin() as cx:
        cx.execute(text("""
            INSERT INTO vistas_producto (visitante_id, producto_id, cliente_id, visto_en)
            VALUES (:vid, :pid, :cid, :ahora)
            ON DUPLICATE KEY UPDATE visto_en = :ahora, cliente_id = COALESCE(:cid, cliente_id)
        """), dict(vid=visitante_id, pid=producto_id, cid=cliente_id, ahora=datetime.now()))


def recientes_ids(visitante_id: str, excluir: int | None = None, limite: int = 8) -> list[int]:
    """Ids de producto vistos por este visitante, del más reciente al más
    viejo. `excluir` es útil en la ficha de producto (no listarse a sí mismo)."""
    _asegurar_tabla()
    sql = "SELECT producto_id FROM vistas_producto WHERE visitante_id = :vid"
    params = {"vid": visitante_id, "limite": limite}
    if excluir is not None:
        sql += " AND producto_id != :excluir"
        params["excluir"] = excluir
    sql += " ORDER BY visto_en DESC LIMIT :limite"
    with engine_tienda.connect() as cx:
        return [r.producto_id for r in cx.execute(text(sql), params)]
