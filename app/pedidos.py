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

import time
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

_RESERVA_CACHE: dict[str, tuple] = {}
_RESERVA_TTL = 60  # segundos


def stock_reservado() -> dict[int, Decimal]:
    """Cuánto de cada producto está en pedidos web ya grabados (`grupos.status=0`,
    la cola 'Nuevo' del VB6) pero todavía no bajado al sistema de escritorio.
    `catalogo` lo resta del stock del ERP para no mostrar como disponible algo
    que en la práctica ya está comprometido. Cacheado 60s."""
    ahora = time.monotonic()
    hit = _RESERVA_CACHE.get("r")
    if hit and ahora - hit[0] < _RESERVA_TTL:
        return hit[1]
    sql = """
        SELECT t.producto_id AS pid, SUM(t.cantidad) AS cant
        FROM transacciones t
        JOIN grupos g ON g.id = t.grupo
        WHERE g.status = 0 AND g.activo = 1
        GROUP BY t.producto_id
    """
    val: dict[int, Decimal] = {}
    with engine_tienda.connect() as cx:
        for r in cx.execute(text(sql)):
            try:
                val[int(r.pid)] = Decimal(str(r.cant or 0))
            except (TypeError, ValueError, ArithmeticError):
                continue
    _RESERVA_CACHE["r"] = (ahora, val)
    return val


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


def _firma(items: list[LineaPedido]) -> list[tuple[int, float]]:
    return sorted((li.producto_id, round(float(li.cantidad), 2)) for li in items)


def pedido_reciente_igual(cliente_id: int, items: list[LineaPedido], minutos: int = 5) -> Optional[int]:
    """Si este cliente YA tiene un pedido creado en los últimos `minutos` con
    exactamente los mismos productos y cantidades, devuelve su id.

    Es la red de seguridad final contra pedidos duplicados: el token de
    sesión (ver checkout_confirmar) solo detecta el reenvío EXACTO de la
    misma carga de /checkout (doble clic). Si la persona recarga la página,
    vuelve atrás o abre el checkout de nuevo y confirma con el mismo
    carrito, eso genera un token distinto y el token no lo agarra — pero
    esto sí, porque compara contra lo que quedó grabado en la base."""
    if not items:
        return None
    firma = _firma(items)
    with engine_tienda.connect() as cx:
        candidatos = cx.execute(text("""
            SELECT id FROM grupos
            WHERE cliente = :cliente_id
              AND created_at >= DATE_SUB(NOW(), INTERVAL :minutos MINUTE)
              AND activo = 1
            ORDER BY id DESC
            LIMIT 5
        """), {"cliente_id": cliente_id, "minutos": minutos}).all()
        for row in candidatos:
            filas = cx.execute(text(
                "SELECT producto_id, cantidad FROM transacciones WHERE grupo = :g"
            ), {"g": row.id}).all()
            firma_existente = sorted((int(f.producto_id), round(float(f.cantidad), 2)) for f in filas)
            if firma_existente == firma:
                return int(row.id)
    return None


def _ocultar_anteriores_del_cliente(cliente_id: int, grupo_nuevo_id: int, minutos: int = 10) -> int:
    """Si este cliente tiene OTROS pedidos recién creados (mismos `minutos`),
    se asume que este pedido nuevo los reemplaza — agregó, sacó o cambió
    algo y volvió a cerrar — y se ocultan los anteriores (status=2,
    activo=0), para que a la tienda le llegue SOLO el definitivo sin que
    haya que compararlos a mano. No se borra nada: quedan igual en la base,
    solo salen de la cola del sistema de escritorio."""
    with engine_tienda.begin() as cx:
        r = cx.execute(text("""
            UPDATE grupos
            SET status = 2, activo = 0
            WHERE cliente = :cliente_id
              AND id <> :nuevo
              AND created_at >= DATE_SUB(NOW(), INTERVAL :minutos MINUTE)
              AND activo = 1
        """), {"cliente_id": cliente_id, "nuevo": grupo_nuevo_id, "minutos": minutos})
        return r.rowcount


def crear(p: PedidoNuevo) -> int:
    """Inserta el pedido y devuelve el nº de grupo. Transacción atómica.

    Antes de grabar, chequea que no sea un duplicado EXACTO de algo que este
    mismo cliente ya mandó hace unos minutos (`pedido_reciente_igual`) — si
    lo es, devuelve el id del pedido existente SIN insertar uno nuevo.

    Si no es exacto pero igual hay un pedido MÁS VIEJO reciente del mismo
    cliente (cambió de idea, sacó o agregó algo y volvió a confirmar), este
    pedido nuevo se toma como el definitivo y el anterior se oculta solo
    (`_ocultar_anteriores_del_cliente`) — así no queda en la tienda la
    versión vieja del pedido para revisar a mano."""
    if not p.items:
        raise ValueError("El pedido no tiene items.")
    dup = pedido_reciente_igual(p.cliente_id, p.items)
    if dup:
        return dup
    with engine_tienda.begin() as cx:
        grupo_id = _insertar(cx, p)
    _ocultar_anteriores_del_cliente(p.cliente_id, grupo_id)
    return grupo_id


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


def habituales(cliente_id: int, limite: int = 20) -> list[int]:
    """producto_id de lo que este cliente ya compró, los más frecuentes primero.
    Junta TODOS sus pedidos (tienda nueva y la vieja masorganicos.online)."""
    sql = """
        SELECT t.producto_id AS pid, COUNT(*) AS veces, MAX(g.created_at) AS ult
        FROM transacciones t
        JOIN grupos g ON g.id = t.grupo
        WHERE g.cliente = :c AND g.activo = 1
        GROUP BY t.producto_id
        ORDER BY veces DESC, ult DESC
        LIMIT :lim
    """
    out: list[int] = []
    with engine_tienda.connect() as cx:
        for r in cx.execute(text(sql), {"c": cliente_id, "lim": limite}):
            try:
                out.append(int(r.pid))
            except (TypeError, ValueError):
                continue
    return out


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
