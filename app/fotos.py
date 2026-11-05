"""Versión de las fotos de producto (para saltarse la caché del hosting y del navegador).

`stock` anota en el ERP (tabla `fotos_version`: codigo en minúscula, version = momento del cambio; '*' = todas)
cuando se cambia una foto o se aprieta «Refrescar en la tienda». Acá se lee (cacheado un minuto) y se agrega
`?v=<version>` a la URL de la foto: URL nueva = el NGINX del hosting y el navegador la piden de nuevo.
Sin fila, la URL queda igual que siempre. Nunca rompe una página: cualquier error = sin versión.
"""
from __future__ import annotations

import time

from sqlalchemy import text

from .db import engine_erp

_TTL = 60
_cache = {"ts": 0.0, "datos": {}}


def _versiones() -> dict:
    ahora = time.time()
    if ahora - _cache["ts"] < _TTL:
        return _cache["datos"]
    try:
        with engine_erp.connect() as cx:
            datos = {str(r[0]).lower(): int(r[1]) for r in cx.execute(text("SELECT codigo, version FROM fotos_version"))}
    except Exception:
        datos = _cache["datos"]           # tabla todavía inexistente o ERP caído: no insistir cada vez
    _cache["ts"], _cache["datos"] = ahora, datos
    return datos


def version(codigo) -> int:
    v = _versiones()
    return max(v.get("*", 0), v.get(str(codigo).lower(), 0))
