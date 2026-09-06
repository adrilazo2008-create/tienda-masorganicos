"""Carrito en sesión (sin login).

Se guarda en la cookie de sesión como lista de {producto_id, cantidad, observacion}.
Los precios y nombres se resuelven siempre contra el catálogo en vivo al mostrar/confirmar,
nunca se confía en lo guardado en la cookie.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from . import catalogo
from .catalogo import Producto

CLAVE = "carrito"


def _leer(session) -> list[dict]:
    items = session.get(CLAVE)
    return items if isinstance(items, list) else []


def _guardar(session, items: list[dict]) -> None:
    session[CLAVE] = items


def _norm_cant(valor) -> Decimal:
    try:
        d = Decimal(str(valor).replace(",", "."))
    except Exception:
        d = Decimal("1")
    if d <= 0:
        d = Decimal("1")
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def agregar(session, producto_id: int, cantidad, observacion: str = "") -> None:
    items = _leer(session)
    cant = _norm_cant(cantidad)
    for it in items:
        if it["producto_id"] == producto_id and it.get("observacion", "") == (observacion or ""):
            it["cantidad"] = str(_norm_cant(Decimal(it["cantidad"]) + cant))
            _guardar(session, items)
            return
    items.append({"producto_id": int(producto_id), "cantidad": str(cant),
                  "observacion": (observacion or "").strip()[:191]})
    _guardar(session, items)


def actualizar(session, indice: int, cantidad) -> None:
    items = _leer(session)
    if 0 <= indice < len(items):
        items[indice]["cantidad"] = str(_norm_cant(cantidad))
        _guardar(session, items)


def quitar(session, indice: int) -> None:
    items = _leer(session)
    if 0 <= indice < len(items):
        items.pop(indice)
        _guardar(session, items)


def vaciar(session) -> None:
    session.pop(CLAVE, None)


@dataclass
class LineaCarrito:
    indice: int
    producto: Producto
    cantidad: Decimal
    observacion: str

    @property
    def subtotal(self) -> Decimal:
        return (self.cantidad * self.producto.precio).quantize(Decimal("0.01"))


@dataclass
class Carrito:
    lineas: list[LineaCarrito]

    @property
    def vacio(self) -> bool:
        return not self.lineas

    @property
    def cantidad_items(self) -> int:
        return len(self.lineas)

    @property
    def subtotal(self) -> Decimal:
        return sum((l.subtotal for l in self.lineas), Decimal("0.00"))


def resolver(session) -> Carrito:
    items = _leer(session)
    if not items:
        return Carrito(lineas=[])
    prods = catalogo.obtener_varios([it["producto_id"] for it in items])
    lineas: list[LineaCarrito] = []
    limpio: list[dict] = []
    for i, it in enumerate(items):
        p = prods.get(it["producto_id"])
        if not p:
            continue  # producto que dejó de estar disponible: se cae del carrito
        lineas.append(LineaCarrito(
            indice=len(lineas), producto=p,
            cantidad=Decimal(it["cantidad"]), observacion=it.get("observacion", "")))
        limpio.append(it)
    if len(limpio) != len(items):
        _guardar(session, limpio)
    return Carrito(lineas=lineas)
