"""Atribución de pedidos a anuncios (Meta Ads).

La landing manda utm_source/utm_medium/utm_campaign/utm_content y fbclid en la URL
de cada enlace a la tienda. Acá se guardan en la sesión al entrar y, al confirmar
un pedido, se graban en `grupos` (columnas utm_* y fbclid) para que `conectar`
muestre de qué anuncio vino cada pedido.

Es "último anuncio de la sesión": si la persona compra otro día o desde otro
dispositivo sin pasar por el anuncio, el pedido queda sin atribución. Nada de acá
puede romper el checkout: todo error se traga.
"""
from __future__ import annotations

import time

from sqlalchemy import text

from .db import engine_tienda

CLAVES = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "fbclid")
_MAX = {"utm_source": 100, "utm_medium": 100, "utm_campaign": 100, "utm_content": 100, "fbclid": 255}
_VIGENCIA_DIAS = 30           # la sesión dura 2 años: no atribuir un pedido de hace meses
_columnas_listas = False


def capturar(request) -> None:
    """Llamar al renderizar una página completa. Guarda los parámetros de la URL
    en la sesión (los más nuevos pisan a los anteriores)."""
    try:
        if request.method != "GET" or request.headers.get("HX-Request"):
            return
        qs = request.query_params
        datos = {k: qs.get(k, "").strip()[:_MAX[k]] for k in CLAVES if qs.get(k, "").strip()}
        if datos:
            datos["ts"] = int(time.time())
            request.session["atrib"] = datos
    except Exception:
        pass


def _asegurar_columnas() -> None:
    global _columnas_listas
    if _columnas_listas:
        return
    with engine_tienda.begin() as cx:
        existentes = {r[0] for r in cx.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'grupos'"))}
        for k in CLAVES:
            if k not in existentes:
                cx.execute(text(f"ALTER TABLE grupos ADD COLUMN {k} VARCHAR({_MAX[k]}) NULL"))
    _columnas_listas = True


def guardar(grupo_id, atrib) -> None:
    """Graba la atribución en el pedido recién creado. Nunca levanta excepción."""
    try:
        if not grupo_id or not atrib:
            return
        if time.time() - int(atrib.get("ts") or 0) > _VIGENCIA_DIAS * 86400:
            return
        valores = {k: (atrib.get(k) or None) for k in CLAVES}
        if not any(valores.values()):
            return
        _asegurar_columnas()
        sets = ", ".join(f"{k} = :{k}" for k in CLAVES)
        with engine_tienda.begin() as cx:
            # solo si el pedido todavía no tiene atribución (un reintento no la pisa)
            cx.execute(text(f"UPDATE grupos SET {sets} WHERE id = :id "
                            "AND utm_source IS NULL AND fbclid IS NULL"),
                       {**valores, "id": int(grupo_id)})
    except Exception:
        pass
