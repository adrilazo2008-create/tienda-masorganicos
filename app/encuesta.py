"""Encuesta "¿Cómo nos conociste?" que se ofrece una sola vez, en la pantalla de pedido enviado,
solo a clientes nuevos. La lee `conectar` (pantalla "Cómo nos conocieron").

Tabla `como_nos_conocio` (base de la tienda): una fila por usuario (`user_id` único: no se vuelve a
preguntar). `respuesta` = instagram | facebook | recomendacion | google | whatsapp | local | otro | omitido
("omitido" = cerró el cartel sin contestar; cuenta como ya preguntado pero no como dato).

Cliente nuevo = el pedido que acaba de hacer es el primero: ningún pedido web anterior activo y,
si ya está vinculado al ERP, ningún comprobante de venta (FC/PT) previo. Nada de esto puede romper
la confirmación del pedido: cualquier error se traga y simplemente no se muestra el cartel.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from .db import engine_erp, engine_tienda

log = logging.getLogger(__name__)

RESPUESTAS = ("anuncio", "perfil_instagram", "instagram", "facebook", "recomendacion", "google", "whatsapp",
              "local", "otro", "omitido")   # instagram/facebook/whatsapp/local: respuestas de la versión anterior
_tabla_lista = False


def _asegurar_tabla() -> None:
    global _tabla_lista
    if _tabla_lista:
        return
    with engine_tienda.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS como_nos_conocio (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                cliente_codigo INT NULL,
                grupo_id INT NULL,
                respuesta VARCHAR(30) NOT NULL,
                texto VARCHAR(120) NULL,
                creado_en DATETIME NOT NULL,
                UNIQUE KEY uq_user (user_id)
            )
        """))
    _tabla_lista = True


def debe_preguntar(grupo_id: int) -> bool:
    """True si el pedido `grupo_id` es el primero de un cliente que nunca contestó."""
    try:
        _asegurar_tabla()
        with engine_tienda.connect() as cx:
            g = cx.execute(text("SELECT cliente FROM grupos WHERE id = :g"), {"g": grupo_id}).first()
            if not g or not g.cliente:
                return False
            uid = int(g.cliente)
            if cx.execute(text("SELECT 1 FROM como_nos_conocio WHERE user_id = :u"), {"u": uid}).first():
                return False
            if cx.execute(text("SELECT 1 FROM grupos WHERE cliente = :u AND id < :g AND activo = 1 LIMIT 1"),
                          {"u": uid, "g": grupo_id}).first():
                return False
            cod = cx.execute(text("SELECT cliente_codigo FROM users WHERE id = :u"), {"u": uid}).scalar()
        if cod:
            with engine_erp.connect() as cx:
                if cx.execute(text("SELECT 1 FROM cptescli WHERE Cliente = :c AND TipoCpte IN ('FC','PT') LIMIT 1"),
                              {"c": cod}).first():
                    return False
        return True
    except Exception:
        log.exception("encuesta.debe_preguntar")
        return False


TEXTO_AVISO_WHATSAPP = "Tu número de WhatsApp va a ser utilizado para contactarte."


def registrar_aviso_whatsapp(grupo_id: int) -> None:
    """Deja constancia (una sola vez por cliente) de que se le mostró el aviso de que su WhatsApp se usa para
    contactarlo (sin limitarlo a la entrega, a pedido de Adriana): es el consentimiento que se pide para escribirle desde el sistema
    (tabla `aviso_whatsapp`, base de la tienda; la puede leer `conectar`). Nunca rompe la confirmación del pedido."""
    try:
        with engine_tienda.begin() as cx:
            cx.execute(text("""
                CREATE TABLE IF NOT EXISTS aviso_whatsapp (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    cliente_codigo INT NULL,
                    grupo_id INT NULL,
                    telefono VARCHAR(20) NULL,
                    texto VARCHAR(255) NOT NULL,
                    mostrado_en DATETIME NOT NULL,
                    UNIQUE KEY uq_user (user_id)
                )
            """))
            g = cx.execute(text("SELECT cliente FROM grupos WHERE id = :g"), {"g": grupo_id}).first()
            if not g or not g.cliente:
                return
            u = cx.execute(text("SELECT cliente_codigo, telefono FROM users WHERE id = :u"), {"u": int(g.cliente)}).first()
            cx.execute(text("""
                INSERT IGNORE INTO aviso_whatsapp (user_id, cliente_codigo, grupo_id, telefono, texto, mostrado_en)
                VALUES (:u, :c, :g, :t, :x, NOW())
            """), {"u": int(g.cliente), "c": u.cliente_codigo if u else None, "g": grupo_id,
                   "t": str(u.telefono) if u and u.telefono else None, "x": TEXTO_AVISO_WHATSAPP})
    except Exception:
        log.exception("encuesta.registrar_aviso_whatsapp")


def guardar(user_id: int, grupo_id: int, respuesta: str, texto: str = "") -> bool:
    """Graba la respuesta (una sola por usuario). El pedido debe ser de ese usuario."""
    if respuesta not in RESPUESTAS or not user_id:
        return False
    try:
        _asegurar_tabla()
        with engine_tienda.begin() as cx:
            ok = cx.execute(text("SELECT 1 FROM grupos WHERE id = :g AND cliente = :u"),
                            {"g": grupo_id, "u": user_id}).first()
            if not ok:
                return False
            cod = cx.execute(text("SELECT cliente_codigo FROM users WHERE id = :u"), {"u": user_id}).scalar()
            cx.execute(text("""
                INSERT IGNORE INTO como_nos_conocio (user_id, cliente_codigo, grupo_id, respuesta, texto, creado_en)
                VALUES (:u, :c, :g, :r, :t, NOW())
            """), {"u": user_id, "c": cod, "g": grupo_id, "r": respuesta,
                   "t": (texto.strip()[:120] or None) if respuesta == "otro" else None})
        return True
    except Exception:
        log.exception("encuesta.guardar")
        return False
