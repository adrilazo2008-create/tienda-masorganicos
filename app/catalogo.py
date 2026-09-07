"""Lectura del catálogo desde el ERP (iebbbhrt_masorganicos).

Producto vendible en la web  ==  mprimas.noweb = 0  AND  mprimas.Activo = 'SI'
Precio de venta web          ==  mprimas.Precio1
Clave para el pedido         ==  mprimas.id   (se guarda en transacciones.producto_id)
Nombre de archivo de foto    ==  mprimas.Codigo  ->  <Codigo>.jpg

Estructura de categorías (2 niveles):
  rubro (VERDURAS, FRUTAS, ALMACEN, ...)  ->  categoría (VERDURAS DE HOJA, HORTALIZAS, ...)
  parametros P=32 = categorías (con Id_rubro)  ·  parametros P=33 = rubros
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Optional

from sqlalchemy import bindparam, text

from .db import engine_erp

# parametros con Parametro = 9
UNIDADES = {90000001: "UN", 90000003: "KG", 90000004: "LT", 90000011: "PQTE"}

# Debajo de este stock se muestra el cartel "pocas unidades / sujeto a confirmación".
STOCK_ALERTA = 3

# Orden de los rubros en el menú (Codigo del parámetro 33).
ORDEN_RUBROS = [1, 2, 3, 5, 4, 15, 14, 10, 16]

# etiquetas (iconos): id -> (nombre legible, orden de prioridad para mostrar)
ETIQUETAS = {
    4: ("Orgánico", 0), 5: ("Agroecológico", 1), 6: ("Pastoril", 2),
    1: ("Sin T.A.C.C.", 3), 3: ("Gluten Free", 4), 2: ("Vegano", 5),
}

_MINUS = {"de", "del", "la", "las", "el", "los", "y", "e", "o", "u",
          "con", "sin", "a", "al", "en", "para"}

# La base tiene los nombres en mayúscula sin tildes; se corrigen al mostrar.
_TILDES = {
    "Almacen": "Almacén", "Panificados": "Panificados", "Organico": "Orgánico",
    "Tinturas Madre": "Tinturas Madre", "Farmacia": "Farmacia",
    "Adaptogenos": "Adaptógenos", "Libreria": "Librería", "Limon": "Limón",
    "Articulos": "Artículos", "Condimentos": "Condimentos",
}


def titulo(txt: str) -> str:
    """'VERDURAS DE HOJA' -> 'Verduras de hoja'   ·   'SIN T.A.C.C.' -> 'Sin T.A.C.C.'"""
    txt = (txt or "").strip()
    if not txt:
        return ""
    palabras = []
    for i, w in enumerate(re.split(r"(\s+)", txt)):
        if not w.strip():
            palabras.append(w)
            continue
        low = w.lower().strip(".")
        if i > 0 and low in _MINUS:
            palabras.append(low)
        elif ("." in w) or w.upper() in {"TACC", "DNI", "XL", "XXL", "S/", "C/"}:
            palabras.append(w)
        else:
            cap = w[:1].upper() + w[1:].lower()
            palabras.append(_TILDES.get(cap, cap))
    return "".join(palabras)


@dataclass(frozen=True)
class Etiqueta:
    id: int
    nombre: str

    @property
    def archivo(self) -> str:
        return f"{self.id}.png"


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
    rubro_id: int
    rubro: str
    destacado: bool
    stock: float
    etiquetas: tuple = ()

    @property
    def unidad(self) -> str:
        return UNIDADES.get(self.unidad_id, "UN")

    @property
    def fraccionable(self) -> bool:
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
        COALESCE(rub.Codigo, 16) AS rubro_id,
        COALESCE(rub.Descripcion, 'Varios') AS rubro,
        (m.destacado = 1)        AS destacado,
        COALESCE(s.Stock, 0)     AS stock
FROM        mprimas    m
LEFT JOIN   categorias c   ON c.CodigoUnificado = m.categoria
LEFT JOIN   parametros rub ON rub.Parametro = 33 AND rub.Codigo = c.Id_rubro
LEFT JOIN   Stock      s   ON s.Codigo = m.Codigo
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
        categoria=titulo(r.categoria),
        rubro_id=int(r.rubro_id or 16),
        rubro=titulo(r.rubro),
        destacado=bool(r.destacado),
        stock=float(r.stock or 0),
    )


def _etiquetas_de(ids: list[int]) -> dict[int, tuple]:
    if not ids:
        return {}
    q = text("""
        SELECT ep.id_producto AS pid, ep.id_etiqueta AS eid
        FROM etiquetas_producto ep
        WHERE ep.activo = 1 AND ep.id_producto IN :ids
    """).bindparams(bindparam("ids", expanding=True))
    acc: dict[int, list] = {}
    with engine_erp.connect() as cx:
        for row in cx.execute(q, {"ids": ids}):
            info = ETIQUETAS.get(int(row.eid))
            if info:
                acc.setdefault(int(row.pid), []).append(Etiqueta(int(row.eid), info[0]))
    return {pid: tuple(sorted(v, key=lambda e: ETIQUETAS[e.id][1])) for pid, v in acc.items()}


def _con_etiquetas(prods: list[Producto]) -> list[Producto]:
    etq = _etiquetas_de([p.id for p in prods])
    return [replace(p, etiquetas=etq.get(p.id, ())) for p in prods]


def listar(categoria_id: Optional[int] = None, rubro_id: Optional[int] = None,
           busqueda: Optional[str] = None, solo_destacados: bool = False,
           limite: Optional[int] = None, con_etiquetas: bool = True) -> list[Producto]:
    sql = _SELECT
    params: dict = {}
    if categoria_id:
        sql += " AND m.categoria = :cat"
        params["cat"] = categoria_id
    if rubro_id:
        sql += " AND c.Id_rubro = :rub"
        params["rub"] = rubro_id
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
        prods = [_fila_a_producto(r) for r in cx.execute(text(sql), params)]
    return _con_etiquetas(prods) if con_etiquetas else prods


def obtener(producto_id: int) -> Optional[Producto]:
    with engine_erp.connect() as cx:
        r = cx.execute(text(_SELECT + " AND m.id = :id"), {"id": producto_id}).first()
    if not r:
        return None
    return _con_etiquetas([_fila_a_producto(r)])[0]


def obtener_varios(ids: list[int]) -> dict[int, Producto]:
    ids = [int(i) for i in ids]
    if not ids:
        return {}
    q = text(_SELECT + " AND m.id IN :ids").bindparams(bindparam("ids", expanding=True))
    with engine_erp.connect() as cx:
        prods = [_fila_a_producto(r) for r in cx.execute(q, {"ids": ids})]
    return {p.id: p for p in _con_etiquetas(prods)}


def categorias() -> list[dict]:
    """Categorías planas con al menos un producto web (compatibilidad)."""
    sql = """
        SELECT c.CodigoUnificado AS id, c.Descripcion AS nombre, COUNT(*) AS n
        FROM mprimas m JOIN categorias c ON c.CodigoUnificado = m.categoria
        WHERE m.noweb = 0 AND m.Activo = 'SI'
        GROUP BY c.CodigoUnificado, c.Descripcion
        ORDER BY c.Descripcion
    """
    with engine_erp.connect() as cx:
        return [dict(id=int(r.id), nombre=titulo(r.nombre), n=int(r.n))
                for r in cx.execute(text(sql))]


def rubros() -> list[dict]:
    """Rubros (nivel 1) con sus categorías (nivel 2), solo lo que tiene stock web."""
    sql_cat = """
        SELECT c.Id_rubro AS rid, c.CodigoUnificado AS cid, c.Descripcion AS nombre, COUNT(*) AS n
        FROM mprimas m JOIN categorias c ON c.CodigoUnificado = m.categoria
        WHERE m.noweb = 0 AND m.Activo = 'SI'
        GROUP BY c.Id_rubro, c.CodigoUnificado, c.Descripcion
    """
    sql_rub = "SELECT Codigo AS id, Descripcion AS nombre FROM parametros WHERE Parametro = 33"
    with engine_erp.connect() as cx:
        nombres = {int(r.id): titulo(r.nombre) for r in cx.execute(text(sql_rub))}
        porrub: dict[int, dict] = {}
        for r in cx.execute(text(sql_cat)):
            rid = int(r.rid or 16)
            d = porrub.setdefault(rid, {"id": rid, "nombre": nombres.get(rid, "Varios"),
                                        "n": 0, "categorias": []})
            d["n"] += int(r.n)
            d["categorias"].append(dict(id=int(r.cid), nombre=titulo(r.nombre), n=int(r.n)))
    orden = {rid: i for i, rid in enumerate(ORDEN_RUBROS)}
    salida = sorted(porrub.values(), key=lambda d: orden.get(d["id"], 99))
    for d in salida:
        d["categorias"].sort(key=lambda c: c["nombre"])
    return salida


def rubro_nombre(rubro_id: int) -> Optional[str]:
    for r in rubros():
        if r["id"] == rubro_id:
            return r["nombre"]
    return None
