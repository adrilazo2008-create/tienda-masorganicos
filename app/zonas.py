"""Zonas de envío y sucursales de retiro (base de la tienda)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

from .db import engine_tienda


@dataclass(frozen=True)
class Zona:
    id: int
    titulo: str
    precio: Decimal          # costo de envío
    minimo_compra: Decimal   # compra mínima para despachar a esta zona
    envio_gratis: Decimal    # a partir de este subtotal el envío es gratis


@dataclass(frozen=True)
class Sucursal:
    id: int
    descripcion: str
    direccion: str
    altura: int
    ciudad: str


def zonas() -> list[Zona]:
    sql = """SELECT id_zona, titulo, precio, mim_compra, envio_gratis
             FROM zonas WHERE activo = 1 ORDER BY titulo"""
    with engine_tienda.connect() as cx:
        return [
            Zona(int(r.id_zona), r.titulo.strip(), Decimal(str(r.precio)),
                 Decimal(str(r.mim_compra)), Decimal(str(r.envio_gratis)))
            for r in cx.execute(text(sql))
        ]


def zona(id_zona: int) -> Optional[Zona]:
    return next((z for z in zonas() if z.id == id_zona), None)


def sucursales() -> list[Sucursal]:
    sql = """SELECT id_sucursal, descripcion, direccion, altura, ciudad
             FROM sucursal WHERE activo = 1 ORDER BY descripcion"""
    with engine_tienda.connect() as cx:
        return [
            Sucursal(int(r.id_sucursal), r.descripcion.strip(), r.direccion.strip(),
                     int(r.altura or 0), (r.ciudad or "").strip())
            for r in cx.execute(text(sql))
        ]


def costo_envio(z: Zona, subtotal: Decimal) -> Decimal:
    if z.envio_gratis and subtotal >= z.envio_gratis:
        return Decimal("0.00")
    return z.precio
