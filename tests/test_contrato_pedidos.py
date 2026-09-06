"""Verifica que un pedido escrito por la tienda cumple el contrato que lee el VB6.

El VB6 (Sub CargapedidoMO) hace, en esencia:
    SELECT * FROM grupos WHERE id = <n>
    SELECT * FROM transacciones WHERE grupo = <n> ORDER BY id
    SELECT * FROM users WHERE id = grupos.cliente
    -- si id_dirEnvio<>0:  SELECT * FROM direccion WHERE id_direccion = grupos.id_dirEnvio
    -- si id_sucursal<>0:  SELECT * FROM sucursal  WHERE id_sucursal  = grupos.id_sucursal

Los tests insertan un pedido de prueba y hacen ROLLBACK: no dejan basura en la base.
"""
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.db import engine_tienda
from app.pedidos import LineaPedido, PedidoNuevo, _insertar, STATUS_NUEVO


COLUMNAS_GRUPOS_QUE_LEE_VB6 = {
    "cliente", "efectivo", "retira", "id_sucursal", "id_dirEnvio", "id_zonaEnvio",
    "precioEnvio", "codigoDescuento", "status", "created_at", "observacion", "observacion2",
}
COLUMNAS_TRANSACCIONES_QUE_LEE_VB6 = {
    "grupo", "producto_id", "cantidad", "precio", "id_unidadMedidaProducto", "observacion",
}


def _columnas(tabla):
    with engine_tienda.connect() as cx:
        return {r[0] for r in cx.execute(text(f"SHOW COLUMNS FROM {tabla}"))}


def test_existen_las_columnas_del_contrato():
    assert COLUMNAS_GRUPOS_QUE_LEE_VB6 <= _columnas("grupos")
    assert COLUMNAS_TRANSACCIONES_QUE_LEE_VB6 <= _columnas("transacciones")


def _cliente_de_prueba(cx):
    r = cx.execute(text("SELECT id FROM users WHERE activo = 1 ORDER BY id DESC LIMIT 1")).first()
    return int(r.id)


@pytest.fixture
def pedido(tmp_path):
    return PedidoNuevo(
        cliente_id=0,  # se completa en el test
        items=[
            LineaPedido(producto_id=2600, cantidad=Decimal("2"), precio_unitario=Decimal("4600"),
                        unidad_id=90000001, observacion="prueba"),
            LineaPedido(producto_id=2593, cantidad=Decimal("1.5"), precio_unitario=Decimal("6000"),
                        unidad_id=90000003),
        ],
        efectivo=True, id_sucursal=0, id_direccion_envio=0, id_zona_envio=7,
        precio_envio=Decimal("6000.00"), codigo_descuento="", observacion="pedido de test",
    )


def test_insert_pedido_forma_correcta(pedido):
    with engine_tienda.connect() as cx:
        trans = cx.begin()
        try:
            pedido.cliente_id = _cliente_de_prueba(cx)
            grupo_id = _insertar(cx, pedido)

            g = cx.execute(text("SELECT * FROM grupos WHERE id = :id"), {"id": grupo_id}).first()
            assert g is not None
            assert int(g.status) == STATUS_NUEVO
            assert int(g.cliente) == pedido.cliente_id
            assert int(g.efectivo) == 1
            assert Decimal(str(g.precioEnvio)) == Decimal("6000.00")
            assert int(g.id_zonaEnvio) == 7
            assert g.observacion == "pedido de test"
            assert g.observacion2 == ""

            lineas = cx.execute(
                text("SELECT * FROM transacciones WHERE grupo = :g ORDER BY id"),
                {"g": grupo_id}).all()
            assert len(lineas) == 2
            # producto_id es TEXTO y debe poder castearse a int (mprimas.id)
            for l in lineas:
                assert str(l.producto_id).isdigit()
                assert int(l.id_unidadMedidaProducto) in (90000001, 90000003, 90000004, 90000011)
            assert Decimal(str(lineas[0].precio)) == Decimal("4600.00")
            assert Decimal(str(lineas[1].cantidad)) == Decimal("1.50")
        finally:
            trans.rollback()


def test_join_como_lo_hace_el_vb6(pedido):
    """El SELECT de la vista pedidosWebMO (que usa la grilla del VB6) no debe romperse."""
    with engine_tienda.connect() as cx:
        trans = cx.begin()
        try:
            pedido.cliente_id = _cliente_de_prueba(cx)
            grupo_id = _insertar(cx, pedido)
            fila = cx.execute(text("SELECT * FROM pedidosWebMO WHERE id = :id"),
                              {"id": grupo_id}).first()
            assert fila is not None
            assert fila.estado == "Nuevo"
            assert Decimal(str(fila.Valorr)) == Decimal("2") * 4600 + Decimal("1.5") * 6000
        finally:
            trans.rollback()
