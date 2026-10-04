"""Reservas de productos agotados (Verduras/Frutas/Granja sin stock, que se
siguen mostrando en la tienda con cartel "Agotado").

Vive en la base del ERP (`iebbbhrt_masorganicos`), no en la de la tienda:
así el proyecto `stock` puede consultarla directo, sin conexión nueva.
Reemplaza la planilla de Google Sheets donde antes se anotaban a mano.

El pedido sigue su curso normal (grupos/transacciones, como cualquier otro) —
esto es solo el registro aparte para que el stock/compras tengan visibilidad
de qué hay que reponer y para quién."""
from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal

from sqlalchemy import text

from .db import engine_erp

ESTADOS = ("pendiente", "encargado", "entregado")


def _asegurar_tabla() -> None:
    with engine_erp.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS reservas (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                producto_id INT NOT NULL,
                producto_nombre VARCHAR(191) NOT NULL,
                cliente_codigo INT NULL,
                nombre VARCHAR(191) NOT NULL,
                telefono BIGINT NULL,
                cantidad DECIMAL(10,2) NOT NULL,
                tipo_entrega VARCHAR(10) NULL,
                pedido_grupo_id INT NULL,
                origen VARCHAR(100) NULL,
                estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',
                creado_en DATETIME NOT NULL,
                actualizado_en DATETIME NULL
            )
        """))


# Proveedores marcados "siempre reservar" (se administra desde `conectar`,
# pantalla Reservas): los productos de esos proveedores generan reserva en cada
# pedido aunque haya stock -- el cliente no lo ve, para el es una compra
# normal. Tabla `reservas_proveedores` (la crea `conectar`); si todavia no
# existe, simplemente no hay ninguno marcado. Cache corto para no consultar la
# base en cada producto del carrito.
_CACHE_TTL = 60
_cache_siempre: dict = {"t": 0.0, "ids": frozenset()}


def productos_reserva_siempre() -> frozenset:
    ahora = time.time()
    if ahora - _cache_siempre["t"] < _CACHE_TTL:
        return _cache_siempre["ids"]
    try:
        with engine_erp.connect() as cx:
            ids = frozenset(int(r[0]) for r in cx.execute(text(
                "SELECT m.id FROM mprimas m "
                "INNER JOIN reservas_proveedores rp ON rp.proveedor_codigo = m.Proveedor"
            )))
    except Exception:
        ids = frozenset()
    _cache_siempre.update(t=ahora, ids=ids)
    return ids


def es_reserva_siempre(producto_id: int) -> bool:
    return int(producto_id) in productos_reserva_siempre()


def crear(*, producto_id: int, producto_nombre: str, cliente_codigo: int | None,
          nombre: str, telefono: int | None, cantidad: Decimal,
          pedido_grupo_id: int | None, tipo_entrega: str | None = None) -> int:
    """`tipo_entrega`: 'envio' | 'retiro' | None (se toma de grupos.retira en el
    pedido que originó la reserva). `origen` queda fijo en 'tienda' -- estas
    reservas siempre vienen de un pedido online, a diferencia de las que se
    cargan a mano desde `conectar` (ahi el origen es el usuario que la cargo)."""
    _asegurar_tabla()
    now = datetime.now()
    with engine_erp.begin() as cx:
        res = cx.execute(text("""
            INSERT INTO reservas
                (producto_id, producto_nombre, cliente_codigo, nombre, telefono,
                 cantidad, tipo_entrega, pedido_grupo_id, origen, estado, creado_en)
            VALUES
                (:pid, :pnombre, :ccod, :nombre, :tel, :cant, :tipo, :grupo, 'tienda', 'pendiente', :now)
        """), dict(pid=producto_id, pnombre=producto_nombre[:191], ccod=cliente_codigo,
                    nombre=nombre[:191], tel=telefono, cant=Decimal(cantidad), tipo=tipo_entrega,
                    grupo=pedido_grupo_id, now=now))
        return int(res.lastrowid)
