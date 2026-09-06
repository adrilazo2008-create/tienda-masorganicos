"""Códigos de descuento (base de la tienda, tabla codigos_descuento)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from typing import Optional

from sqlalchemy import text

from .db import engine_tienda


@dataclass(frozen=True)
class Descuento:
    codigo: str
    porcentaje: Decimal
    nombre: str
    condiciones: str


def validar(codigo: str) -> Optional[Descuento]:
    """Devuelve el descuento si el código existe, está activo y vigente hoy."""
    codigo = (codigo or "").strip()
    if not codigo:
        return None
    sql = """SELECT codigo, porcentaje, nombre_beneficio, condiciones,
                    vigencia_desde, vigencia_hasta
             FROM codigos_descuento
             WHERE UPPER(codigo) = UPPER(:c) AND activo = 1
             LIMIT 1"""
    with engine_tienda.connect() as cx:
        r = cx.execute(text(sql), {"c": codigo}).first()
    if not r:
        return None
    hoy = date.today()
    if r.vigencia_desde and hoy < r.vigencia_desde:
        return None
    if r.vigencia_hasta and hoy > r.vigencia_hasta:
        return None
    return Descuento(r.codigo.strip(), Decimal(str(r.porcentaje)),
                     (r.nombre_beneficio or "").strip(), (r.condiciones or "").strip())
