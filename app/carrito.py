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
    pid = int(producto_id)
    obs_nueva = (observacion or "").strip()[:191]
    # Se junta en una sola línea si es el mismo producto y las observaciones
    # coinciden o alguna está vacía. Solo quedan líneas separadas si ambas
    # tienen una nota distinta (ej. "bien maduro" vs "bien verde").
    for it in items:
        if it["producto_id"] != pid:
            continue
        obs_it = it.get("observacion", "")
        if obs_it == obs_nueva or not obs_it or not obs_nueva:
            it["cantidad"] = str(_norm_cant(Decimal(it["cantidad"]) + cant))
            if obs_nueva and not obs_it:
                it["observacion"] = obs_nueva
            _guardar(session, items)
            return
    items.append({"producto_id": pid, "cantidad": str(cant), "observacion": obs_nueva})
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
    car, _ = _resolver(session)
    return car


def resolver_y_avisar(session) -> tuple[Carrito, bool]:
    """Como resolver(), pero además devuelve `True` si algún producto se cayó
    del carrito EN ESTE LLAMADO (se quedó sin stock justo ahora). Se usa en
    /checkout al confirmar, para no completar un pedido a ciegas con menos
    productos de los que la persona ve en pantalla."""
    return _resolver(session)


def _resolver(session) -> tuple[Carrito, bool]:
    items = _leer(session)
    if not items:
        return Carrito(lineas=[]), False
    prods = catalogo.obtener_varios([it["producto_id"] for it in items])
    lineas: list[LineaCarrito] = []
    limpio: list[dict] = []
    faltantes: list[int] = []
    for it in items:
        p = prods.get(it["producto_id"])
        if not p:
            faltantes.append(it["producto_id"])  # se quedó sin stock / dejó de estar disponible
            continue
        lineas.append(LineaCarrito(
            indice=len(lineas), producto=p,
            cantidad=Decimal(it["cantidad"]), observacion=it.get("observacion", "")))
        limpio.append(it)
    if len(limpio) != len(items):
        _guardar(session, limpio)
    if faltantes:
        # se avisa SIEMPRE que algo se cae (no solo desde /checkout): así el
        # aviso queda esperando en la sesión y se muestra la próxima vez que
        # la persona mire /carrito o /checkout, sin importar en qué otra
        # página (home, catálogo...) se detectó la falta de stock primero.
        nombres = catalogo.nombres_por_id(faltantes)
        vistos = [nombres.get(pid, "un producto") for pid in faltantes]
        verbo = "Se quitó" if len(vistos) == 1 else "Se quitaron"
        session["carrito_msg"] = f"{verbo} de tu pedido, se quedó sin stock: {', '.join(vistos)}."
    return Carrito(lineas=lineas), bool(faltantes)
