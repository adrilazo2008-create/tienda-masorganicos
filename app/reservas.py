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
            # Excepciones por producto (tabla que crea `conectar`); si todavia
            # no existe, no hay ninguna.
            try:
                excluidos = frozenset(int(r[0]) for r in cx.execute(text(
                    "SELECT producto_id FROM reservas_productos_excluidos"
                )))
            except Exception:
                excluidos = frozenset()
            ids = ids - excluidos
    except Exception:
        ids = frozenset()
    _cache_siempre.update(t=ahora, ids=ids)
    return ids


def es_reserva_siempre(producto_id: int) -> bool:
    return int(producto_id) in productos_reserva_siempre()


# Si el producto es una RESERVA FIJA del cliente (tabla `reservas_recurrentes`, la administra `conectar`), pedirlo por la web
# NO es una reserva extra: ya la tiene. Ventana (dias) en la que se considera "la reserva de esta semana".
VENTANA_FIJA_DIAS = 8


def _regla_fija(cx, producto_id: int, cliente_codigo: int | None, telefono: int | None):
    """Regla fija activa del cliente para ese producto (o None). Se busca por cliente y, si el pedido no tiene cliente ERP
    vinculado, por teléfono."""
    try:
        if cliente_codigo:
            fila = cx.execute(text(
                "SELECT id, cantidad FROM reservas_recurrentes WHERE activa = 1 AND producto_id = :p AND cliente_codigo = :c "
                "ORDER BY id LIMIT 1"), dict(p=producto_id, c=cliente_codigo)).first()
            if fila:
                return fila
        if telefono:
            return cx.execute(text(
                "SELECT id, cantidad FROM reservas_recurrentes WHERE activa = 1 AND producto_id = :p AND telefono = :t "
                "ORDER BY id LIMIT 1"), dict(p=producto_id, t=telefono)).first()
    except Exception:
        return None   # tablas/columnas de las reservas fijas todavia no existen: se comporta como siempre
    return None


def crear(*, producto_id: int, producto_nombre: str, cliente_codigo: int | None,
          nombre: str, telefono: int | None, cantidad: Decimal,
          pedido_grupo_id: int | None, tipo_entrega: str | None = None) -> int:
    """`tipo_entrega`: 'envio' | 'retiro' | None (se toma de grupos.retira en el
    pedido que originó la reserva). `origen` queda fijo en 'tienda' -- estas
    reservas siempre vienen de un pedido online, a diferencia de las que se
    cargan a mano desde `conectar` (ahi el origen es el usuario que la cargo).

    Reserva fija (2026-10-19, caso Rocío Andrada con su leche semanal): si el cliente tiene una regla fija para ese producto,
    el pedido NO suma una reserva más:
      * si ya existe la reserva de la semana de esa regla (generada por el job de los sábados, sin pedido asignado) se la
        vincula a este pedido (queda «dentro del pedido», no repite en «tiene reservado») y solo se crea una reserva nueva
        por lo que EXCEDA a la fija;
      * si todavía no existe, la reserva que crea este pedido queda marcada como la de la regla (`regla_recurrente_id`), así el
        job semanal no genera otra encima."""
    _asegurar_tabla()
    now = datetime.now()
    cantidad = Decimal(cantidad)
    with engine_erp.begin() as cx:
        regla_id = None
        regla = _regla_fija(cx, producto_id, cliente_codigo, telefono)
        if regla is not None and pedido_grupo_id:
            regla_id = int(regla[0])
            try:
                abierta = cx.execute(text(
                    "SELECT id, cantidad FROM reservas WHERE regla_recurrente_id = :r AND pedido_grupo_id IS NULL "
                    "AND estado IN ('pendiente', 'encargado', 'recibido') AND creado_en >= NOW() - INTERVAL :d DAY "
                    "ORDER BY creado_en DESC LIMIT 1"), dict(r=regla_id, d=VENTANA_FIJA_DIAS)).first()
            except Exception:
                abierta = None
                regla_id = None
            if abierta is not None:
                cx.execute(text(
                    "UPDATE reservas SET pedido_grupo_id = :g, tipo_entrega = COALESCE(:t, tipo_entrega), actualizado_en = :n "
                    "WHERE id = :id AND pedido_grupo_id IS NULL"), dict(g=pedido_grupo_id, t=tipo_entrega, n=now, id=int(abierta[0])))
                sobra = cantidad - Decimal(abierta[1])
                if sobra <= 0:
                    return int(abierta[0])
                cantidad, regla_id = sobra, None        # lo que excede a la fija sigue siendo una reserva normal
        # Reserva ya anotada por el cliente (2026-10-22, caso Sartori): si el cliente ya tenia una reserva abierta de ese
        # producto y despues lo pide por la web, el renglon del pedido ES esa reserva (se acordo de lo que tenia
        # reservado): se la vincula al pedido en vez de crear otra, y solo se crea una nueva por lo que EXCEDA.
        if pedido_grupo_id and cantidad > 0 and (cliente_codigo or telefono):
            try:
                cond, par = [], dict(p=producto_id)
                if cliente_codigo:
                    cond.append("cliente_codigo = :c"); par["c"] = cliente_codigo
                if telefono:
                    cond.append("telefono = :t"); par["t"] = telefono
                previas = cx.execute(text(
                    "SELECT id, cantidad FROM reservas WHERE producto_id = :p AND pedido_grupo_id IS NULL "
                    "AND COALESCE(es_extra, 0) = 0 AND estado IN ('pendiente', 'encargado', 'recibido') "
                    "AND (" + " OR ".join(cond) + ") ORDER BY creado_en, id"), par).fetchall()
            except Exception:
                previas = []
            primera = None
            for pr in previas:
                if cantidad <= 0:
                    break
                cx.execute(text(
                    "UPDATE reservas SET pedido_grupo_id = :g, tipo_entrega = COALESCE(:t, tipo_entrega), actualizado_en = :n "
                    "WHERE id = :id AND pedido_grupo_id IS NULL"), dict(g=pedido_grupo_id, t=tipo_entrega, n=now, id=int(pr[0])))
                primera = primera or int(pr[0])
                cantidad -= Decimal(pr[1])
            if cantidad <= 0:
                return primera
        cols = "producto_id, producto_nombre, cliente_codigo, nombre, telefono, cantidad, tipo_entrega, pedido_grupo_id, origen, estado, creado_en"
        vals = ":pid, :pnombre, :ccod, :nombre, :tel, :cant, :tipo, :grupo, 'tienda', 'pendiente', :now"
        if regla_id is not None:
            cols += ", regla_recurrente_id"; vals += ", :regla"
        res = cx.execute(text(f"INSERT INTO reservas ({cols}) VALUES ({vals})"),
                         dict(pid=producto_id, pnombre=producto_nombre[:191], ccod=cliente_codigo,
                              nombre=nombre[:191], tel=telefono, cant=cantidad, tipo=tipo_entrega,
                              grupo=pedido_grupo_id, now=now, regla=regla_id))
        return int(res.lastrowid)
