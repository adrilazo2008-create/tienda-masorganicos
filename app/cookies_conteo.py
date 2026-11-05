"""Cuenta cuántas veces se mostró el cartel de cookies y qué se eligió (Aceptar / Rechazar).

Tabla `cookies_conteo` (base de la tienda, se crea sola): un renglón por día y evento con un contador.
No guarda IP, cookies ni ningún dato de la persona: solo cantidades. Sirve para medir la tasa de aceptación
(aceptaron / vieron el cartel) y comparar variantes del cartel con datos propios.

Eventos: `visto` (una vez por sesión del navegador), `si` (Aceptar), `no` (Rechazar).
Nunca puede romper la navegación: cualquier error queda solo logueado.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from .db import engine_tienda

log = logging.getLogger(__name__)

EVENTOS = ("visto", "si", "no")
_tabla_lista = False


def _asegurar_tabla() -> None:
    global _tabla_lista
    if _tabla_lista:
        return
    with engine_tienda.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS cookies_conteo (
                dia DATE NOT NULL,
                evento VARCHAR(10) NOT NULL,
                n INT NOT NULL DEFAULT 0,
                PRIMARY KEY (dia, evento)
            )
        """))
    _tabla_lista = True


def contar(evento: str) -> bool:
    """Suma 1 al contador de hoy para `evento`. Devuelve False si el evento no es válido o falló."""
    if evento not in EVENTOS:
        return False
    try:
        _asegurar_tabla()
        with engine_tienda.begin() as cx:
            cx.execute(text("""
                INSERT INTO cookies_conteo (dia, evento, n) VALUES (CURDATE(), :e, 1)
                ON DUPLICATE KEY UPDATE n = n + 1
            """), {"e": evento})
        return True
    except Exception:
        log.exception("cookies_conteo.contar")
        return False
