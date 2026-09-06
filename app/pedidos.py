"""Escritura y lectura de pedidos en iebbbhrt_prueba_paginaweb.

CONTRATO CON EL SISTEMA DE ESCRITORIO (VB6 · frmPedidos · botón cmdPedidosWebMO · Sub CargapedidoMO):

  El VB6 lee los pedidos web de las TABLAS BASE `grupos` y `transacciones` (no de las vistas).
  Un pedido nuevo de la tienda =
      1 fila en `grupos`  con status = 0  ("Nuevo")
    + N filas en `transacciones`  con producto_id = mprimas.id  (id numérico, como texto)
  El cliente debe existir en `users` con `telefono` y `email` cargados (el VB6 lo cruza
  contra el ERP por esos campos).

  Campos de `grupos` que mira el VB6:
    cliente, efectivo (0=m.pago / 1=efectivo), id_sucursal (<>0 => retira),
    id_dirEnvio (<>0 => envío a esa dirección), id_zonaEnvio, precioEnvio,
    codigoDescuento (texto; si viene, busca %  en codigos_descuento), created_at,
    observacion, observacion2 (faltantes: la web manda ''), status.

Nada más. NO hay que tocar el ERP ni las vistas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .db import engine_tienda

STATUS_NUEVO = 0
STATUS_IMPORTADO = 1
STATUS_FACTURADO = 2


@dataclass
class LineaPedido:
    producto_id: int          # mprimas.id
    cantidad: Decimal
    precio_unitario: Decimal   # = mprimas.Precio1 al momento de la compra
    unidad_id: int             # = mprimas.Unidad  (90000001 UN / 90000003 KG / ...)
    observacion: str = ""


@dataclass
class PedidoNuevo:
    cliente_id: int
    items: list[LineaPedido]
    efectivo: bool = True                 # True=efectivo, False=transferencia/débito/crédito/MP
    id_sucursal: int = 0                  # <>0 => retira en sucursal
    id_direccion_envio: int = 0           # <>0 => envío a esa direccion
    id_zona_envio: int = 0
    precio_envio: Decimal = Decimal("0.00")
    codigo_descuento: str = ""
    observacion: str = ""

    @property
    def retira(self) -> int:
        return 1 if self.id_sucursal else 0

    def subtotal(self) -> Decimal:
        return sum((li.cantidad * li.precio_unitario for li in self.items), Decimal("0"))

    def total(self) -> Decimal:
        return self.subtotal() + Decimal(self.precio_envio or 0)


def _insertar(cx: Connection, p: PedidoNuevo) -> int:
    now = datetime.now()
    g = cx.execute(text("""
        INSERT INTO grupos
            (cliente, efectivo, retira, id_sucursal, id_dirEnvio, id_zonaEnvio,
             precioEnvio, codigoDescuento, status, created_at, updated_at,
             factura, aceptobolsas, observacion, observacion2, activo)
        VALUES
            (:cliente, :efectivo, :retira, :suc, :dir, :zona,
             :envio, :cod, :status, :now, NULL,
             0, 0, :obs, '', 1)
    """), dict(
        cliente=p.cliente_id,
        efectivo=1 if p.efectivo else 0,
        retira=p.retira,
        suc=p.id_sucursal,
        dir=p.id_direccion_envio,
        zona=p.id_zona_envio,
        envio=Decimal(p.precio_envio or 0),
        cod=(p.codigo_descuento or "").strip(),
        status=STATUS_NUEVO,
        now=now,
        obs=(p.observacion or "")[:500],
    ))
    grupo_id = int(g.lastrowid)

    for li in p.items:
        cx.execute(text("""
            INSERT INTO transacciones
                (grupo, producto_id, cantidad, precio, id_unidadMedidaProducto,
                 observacion, created_at, updated_at, porcentaje, activo)
            VALUES
                (:grupo, :pid, :cant, :precio, :um, :obs, :now, NULL, 0, 1)
        """), dict(
            grupo=grupo_id,
            pid=str(li.producto_id),
            cant=Decimal(li.cantidad),
            precio=Decimal(li.precio_unitario),
            um=li.unidad_id,
            obs=(li.observacion or "")[:191],
            now=now,
        ))
    return grupo_id


def crear(p: PedidoNuevo) -> int:
    """Inserta el pedido y devuelve el nº de grupo. Transacción atómica."""
    if not p.items:
        raise ValueError("El pedido no tiene items.")
    with engine_tienda.begin() as cx:
        return _insertar(cx, p)


# ---------------------------------------------------------------- lectura / historial

@dataclass
class PedidoResumen:
    id: int
    fecha: datetime
    estado: str
    total: Decimal
    cantidad_items: int


_ESTADOS = {0: "Recibido", 1: "En preparación", 2: "Facturado"}


def historial(cliente_id: int, limite: int = 30) -> list[PedidoResumen]:
    sql = """
        SELECT g.id, g.created_at, g.status,
               COALESCE(SUM(t.cantidad * t.precio), 0) + g.precioEnvio AS total,
               COUNT(t.id) AS n
        FROM grupos g
        LEFT JOIN transacciones t ON t.grupo = g.id
        WHERE g.cliente = :c AND g.activo = 1
        GROUP BY g.id, g.created_at, g.status, g.precioEnvio
        ORDER BY g.id DESC
        LIMIT :lim
    """
    with engine_tienda.connect() as cx:
        return [
            PedidoResumen(int(r.id), r.created_at, _ESTADOS.get(int(r.status), "Recibido"),
                          Decimal(str(r.total or 0)), int(r.n))
            for r in cx.execute(text(sql), {"c": cliente_id, "lim": limite})
        ]


def detalle(pedido_id: int, cliente_id: Optional[int] = None) -> Optional[dict]:
    with engine_tienda.connect() as cx:
        g = cx.execute(text("SELECT * FROM grupos WHERE id = :id"), {"id": pedido_id}).first()
        if not g or (cliente_id is not None and int(g.cliente) != cliente_id):
            return None
        lineas = cx.execute(text(
            "SELECT producto_id, cantidad, precio, observacion FROM transacciones "
            "WHERE grupo = :id ORDER BY id"), {"id": pedido_id}).all()
    return {
        "id": int(g.id),
        "fecha": g.created_at,
        "estado": _ESTADOS.get(int(g.status), "Recibido"),
        "precio_envio": Decimal(str(g.precioEnvio or 0)),
        "codigo_descuento": g.codigoDescuento or "",
        "observacion": g.observacion or "",
        "lineas": [dict(producto_id=int(l.producto_id), cantidad=Decimal(str(l.cantidad)),
                        precio=Decimal(str(l.precio)), observacion=l.observacion or "")
                   for l in lineas],
    }
