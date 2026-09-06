"""Lectura del catálogo desde el ERP (iebbbhrt_masorganicos).

Producto vendible en la web  ==  mprimas.noweb = 0  AND  mprimas.Activo = 'SI'
Precio de venta web          ==  mprimas.Precio1
Clave para el pedido         ==  mprimas.id   (se guarda en transacciones.producto_id)
Nombre de archivo de foto    ==  mprimas.Codigo  ->  <Codigo>.jpg
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import bindparam, text

from .db import engine_erp

# parametros con Parametro = 9
UNIDADES = {90000001: "UN", 90000003: "KG", 90000004: "LT", 90000011: "PQTE"}

# Debajo de este stock se muestra el cartel "pocas unidades / sujeto a confirmación".
STOCK_ALERTA = 3


@dataclass(frozen=True)
class Producto:
    id: int
    codigo: str
    nombre: str
    detalle: str
    precio: Decimal
    tasa_iva: float
    unidad_id: int
    categoria_id: int
    categoria: str
    destacado: bool
    stock: float

    @property
    def unidad(self) -> str:
        return UNIDADES.get(self.unidad_id, "UN")

    @property
    def fraccionable(self) -> bool:
        """KG y LT admiten cantidades con coma (0,25 / 0,5 / 0,75)."""
        return self.unidad in ("KG", "LT")

    @property
    def poco_stock(self) -> bool:
        return self.stock < STOCK_ALERTA


_SELECT = """
SELECT  m.id                     AS id,
        TRIM(m.Codigo)           AS codigo,
        m.Descripcion            AS nombre,
        COALESCE(m.detalle, '')  AS detalle,
        m.Precio1                AS precio,
        COALESCE(m.tasaIva, 21)  AS tasa_iva,
        COALESCE(m.Unidad, 90000001) AS unidad_id,
        COALESCE(m.categoria, 0) AS categoria_id,
        COALESCE(c.Descripcion, 'Varios') AS categoria,
        (m.destacado = 1)        AS destacado,
        COALESCE(s.Stock, 0)     AS stock
FROM        mprimas   m
LEFT JOIN   categorias c ON c.CodigoUnificado = m.categoria
LEFT JOIN   Stock      s ON s.Codigo = m.Codigo
WHERE   m.noweb = 0 AND m.Activo = 'SI'
"""


def _fila_a_producto(r) -> Producto:
    return Producto(
        id=int(r.id),
        codigo=str(r.codigo or "").strip(),
        nombre=(r.nombre or "").strip(),
        detalle=(r.detalle or "").strip(),
        precio=Decimal(str(r.precio or 0)),
        tasa_iva=float(r.tasa_iva or 21),
        unidad_id=int(r.unidad_id or 90000001),
        categoria_id=int(r.categoria_id or 0),
        categoria=(r.categoria or "Varios").strip(),
        destacado=bool(r.destacado),
        stock=float(r.stock or 0),
    )


def listar(categoria_id: Optional[int] = None, busqueda: Optional[str] = None,
           solo_destacados: bool = False, limite: Optional[int] = None) -> list[Producto]:
    sql = _SELECT
    params: dict = {}
    if categoria_id:
        sql += " AND m.categoria = :cat"
        params["cat"] = categoria_id
    if busqueda:
        sql += " AND (m.Descripcion LIKE :q OR m.detalle LIKE :q)"
        params["q"] = f"%{busqueda.strip()}%"
    if solo_destacados:
        sql += " AND m.destacado = 1"
    sql += " ORDER BY m.destacado DESC, m.Descripcion"
    if limite:
        sql += " LIMIT :lim"
        params["lim"] = int(limite)
    with engine_erp.connect() as cx:
        return [_fila_a_producto(r) for r in cx.execute(text(sql), params)]


def obtener(producto_id: int) -> Optional[Producto]:
    with engine_erp.connect() as cx:
        r = cx.execute(text(_SELECT + " AND m.id = :id"), {"id": producto_id}).first()
    return _fila_a_producto(r) if r else None


def obtener_varios(ids: list[int]) -> dict[int, Producto]:
    """Devuelve {id: Producto} para los ids pedidos (los que sigan siendo vendibles)."""
    ids = [int(i) for i in ids]
    if not ids:
        return {}
    q = text(_SELECT + " AND m.id IN :ids").bindparams(bindparam("ids", expanding=True))
    with engine_erp.connect() as cx:
        return {int(r.id): _fila_a_producto(r) for r in cx.execute(q, {"ids": ids})}


def categorias() -> list[dict]:
    """Categorías con al menos un producto vendible en la web."""
    sql = """
        SELECT c.CodigoUnificado AS id, c.Descripcion AS nombre, COUNT(*) AS n
        FROM mprimas m
        JOIN categorias c ON c.CodigoUnificado = m.categoria
        WHERE m.noweb = 0 AND m.Activo = 'SI'
        GROUP BY c.CodigoUnificado, c.Descripcion
        ORDER BY c.Descripcion
    """
    with engine_erp.connect() as cx:
        return [dict(id=int(r.id), nombre=r.nombre.strip(), n=int(r.n))
                for r in cx.execute(text(sql))]
