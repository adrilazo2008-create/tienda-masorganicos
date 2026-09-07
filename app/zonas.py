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
    descuento: int = 0        # % de descuento del envío el día que repartimos la zona

    @property
    def precio_dia(self) -> Decimal:
        """Costo de envío el día que pasamos por la zona (con el descuento aplicado)."""
        if not self.descuento:
            return self.precio
        return (self.precio * (100 - self.descuento) / 100).quantize(Decimal("1"))


@dataclass(frozen=True)
class Sucursal:
    id: int
    descripcion: str
    direccion: str
    altura: int
    ciudad: str


def zonas() -> list[Zona]:
    sql = """SELECT id_zona, titulo, precio, mim_compra, envio_gratis, descuento
             FROM zonas WHERE activo = 1 ORDER BY titulo"""
    with engine_tienda.connect() as cx:
        return [
            Zona(int(r.id_zona), r.titulo.strip(), Decimal(str(r.precio)),
                 Decimal(str(r.mim_compra)), Decimal(str(r.envio_gratis)),
                 int(r.descuento or 0))
            for r in cx.execute(text(sql))
        ]


def poligonos_geojson() -> dict:
    """Polígonos de las zonas (del My Maps) + precios EN VIVO de la tabla `zonas`.

    Los precios salen siempre de la base -> un solo lugar para actualizarlos.
    """
    import json
    from pathlib import Path

    ruta = Path(__file__).resolve().parent / "data" / "zonas_poligonos.json"
    try:
        polis = json.loads(ruta.read_text(encoding="utf-8"))
    except OSError:
        return {"type": "FeatureCollection", "features": []}

    por_id = {z.id: z for z in zonas()}
    feats = []
    for p in polis:
        z = por_id.get(p["id_zona"])
        props = {}
        if z:
            titulo = z.titulo
            if "(" in titulo and ")" not in titulo:  # el varchar(45) cortó el paréntesis
                titulo = titulo.split("(")[0].strip()
            props = {
                "titulo": titulo,
                "precio": int(z.precio),
                "precio_dia": int(z.precio_dia),
                "minimo": int(z.minimo_compra),
                "gratis": int(z.envio_gratis),
            }
        feats.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [p["ring"]]},
        })
    return {"type": "FeatureCollection", "features": feats}


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
