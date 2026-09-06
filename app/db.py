"""Dos conexiones separadas:

- `engine_tienda`  -> iebbbhrt_prueba_paginaweb  (pedidos, usuarios, zonas, contenido)
- `engine_erp`     -> iebbbhrt_masorganicos       (catálogo: mprimas, categorias, Stock)

Se usan con SQLAlchemy Core (consultas `text()`), no ORM: el esquema es heredado
y conviene tener el SQL a la vista.
"""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .config import get_settings

_s = get_settings()

engine_tienda: Engine = create_engine(
    _s.url_tienda(), pool_pre_ping=True, pool_recycle=280, future=True
)
engine_erp: Engine = create_engine(
    _s.url_erp(), pool_pre_ping=True, pool_recycle=280, future=True
)
