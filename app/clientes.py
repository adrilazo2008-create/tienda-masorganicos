"""Clientes de la tienda (tabla `users` en iebbbhrt_prueba_paginaweb).

Identificación de baja fricción:
- El cliente se identifica por celular (o email).
- PIN de 4 dígitos OPCIONAL. Se guarda hasheado en `users.password` (la columna ya existe).
- Si no pone PIN, para ver su historial se usa un código de un solo uso (OTP) -> otro módulo.

El sistema de escritorio (VB6) busca al cliente en el ERP por `users.telefono` y luego por
`users.email`. Por eso lo único importante es dejar esos dos campos bien cargados.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import bcrypt
from sqlalchemy import text

from .db import engine_tienda

_INT_MAX = 2147483647  # límite de la columna telefono INT(11) con signo


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(str(pin).encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _check_pin(pin: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(str(pin).encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def normalizar_telefono(valor: str) -> int:
    """'11 5504-6740' -> 1155046740. Devuelve 0 si no hay dígitos usables.

    Las zonas de reparto son todas AMBA/GBA/CABA (área 11), así que 10 dígitos
    entran en un INT. Se saca un prefijo 54 / 549 / 0 si viene.
    """
    d = re.sub(r"\D", "", valor or "")
    if d.startswith("549"):
        d = d[3:]
    elif d.startswith("54"):
        d = d[2:]
    d = d.lstrip("0")
    if not d:
        return 0
    n = int(d)
    return n if n <= _INT_MAX else int(d[-9:])  # fallback defensivo


def _slug_name(nombre: str, apellido: str, email: str) -> str:
    base = (email.split("@")[0] if email else f"{nombre}.{apellido}").strip().lower()
    return re.sub(r"[^a-z0-9._-]", "", base)[:180] or "cliente"


@dataclass(frozen=True)
class Cliente:
    id: int
    nombre: str
    apellido: str
    telefono: int
    email: str
    tiene_pin: bool

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()


def _fila(r) -> Cliente:
    return Cliente(int(r.id), (r.nombre or "").strip(), (r.apellido or "").strip(),
                   int(r.telefono or 0), (r.email or "").strip(),
                   bool(r.password and str(r.password).startswith("$2")))


def buscar_por_telefono(telefono: str) -> Optional[Cliente]:
    tel = normalizar_telefono(telefono)
    if not tel:
        return None
    sql = "SELECT id,nombre,apellido,telefono,email,password FROM users WHERE telefono = :t AND activo = 1 ORDER BY id DESC LIMIT 1"
    with engine_tienda.connect() as cx:
        r = cx.execute(text(sql), {"t": tel}).first()
    return _fila(r) if r else None


def buscar_por_email(email: str) -> Optional[Cliente]:
    email = (email or "").strip().lower()
    if not email:
        return None
    sql = "SELECT id,nombre,apellido,telefono,email,password FROM users WHERE LOWER(email) = :e AND activo = 1 LIMIT 1"
    with engine_tienda.connect() as cx:
        r = cx.execute(text(sql), {"e": email}).first()
    return _fila(r) if r else None


def obtener(cliente_id: int) -> Optional[Cliente]:
    sql = "SELECT id,nombre,apellido,telefono,email,password FROM users WHERE id = :id LIMIT 1"
    with engine_tienda.connect() as cx:
        r = cx.execute(text(sql), {"id": cliente_id}).first()
    return _fila(r) if r else None


def verificar_pin(cliente_id: int, pin: str) -> bool:
    sql = "SELECT password FROM users WHERE id = :id LIMIT 1"
    with engine_tienda.connect() as cx:
        r = cx.execute(text(sql), {"id": cliente_id}).first()
    if not r or not r.password or not str(r.password).startswith("$2"):
        return False
    try:
        return _check_pin(pin, r.password)
    except ValueError:
        return False


def crear(nombre: str, apellido: str, telefono: str, email: str,
          pin: Optional[str] = None) -> Cliente:
    """Crea el `users`. Si ya existe uno con ese email, lo devuelve (y actualiza el tel)."""
    email = (email or "").strip()
    existente = buscar_por_email(email) if email else None
    if existente:
        actualizar(existente.id, nombre=nombre, apellido=apellido, telefono=telefono, pin=pin)
        return obtener(existente.id)  # type: ignore

    tel = normalizar_telefono(telefono)
    pwd = hash_pin(pin) if pin else ""
    now = datetime.now()
    sql = text("""
        INSERT INTO users (name, nombre, apellido, dni, email, telefono, password,
                           background, created_at, updated_at, activo)
        VALUES (:name, :nombre, :apellido, 0, :email, :telefono, :password,
                'white', :now, :now, 1)
    """)
    with engine_tienda.begin() as cx:
        res = cx.execute(sql, dict(
            name=_slug_name(nombre, apellido, email), nombre=nombre.strip(),
            apellido=apellido.strip(), email=email or f"sinmail_{tel}@masorganicos.local",
            telefono=tel, password=pwd, now=now))
        nuevo_id = res.lastrowid
    return obtener(int(nuevo_id))  # type: ignore


def actualizar(cliente_id: int, *, nombre: Optional[str] = None, apellido: Optional[str] = None,
               telefono: Optional[str] = None, email: Optional[str] = None,
               pin: Optional[str] = None) -> None:
    sets, params = [], {"id": cliente_id}
    if nombre:
        sets.append("nombre = :nombre"); params["nombre"] = nombre.strip()
    if apellido:
        sets.append("apellido = :apellido"); params["apellido"] = apellido.strip()
    if telefono:
        t = normalizar_telefono(telefono)
        if t:
            sets.append("telefono = :telefono"); params["telefono"] = t
    if email:
        sets.append("email = :email"); params["email"] = email.strip()
    if pin:
        sets.append("password = :password"); params["password"] = hash_pin(pin)
    if not sets:
        return
    sets.append("updated_at = :now"); params["now"] = datetime.now()
    with engine_tienda.begin() as cx:
        cx.execute(text(f"UPDATE users SET {', '.join(sets)} WHERE id = :id"), params)


def guardar_direccion(cliente_id: int, direccion: str, altura: int, localidad: str,
                      id_zona: int, info_adicional: str = "", codigo_postal: int = 0,
                      principal: bool = True) -> int:
    if principal:
        with engine_tienda.begin() as cx:
            cx.execute(text("UPDATE direccion SET principal = 0 WHERE id_cliente = :c"),
                       {"c": cliente_id})
    sql = text("""
        INSERT INTO direccion (id_cliente, direccion, altura, codigoPostal, id_zona,
                               localidad, infoAdicional, principal, activo)
        VALUES (:c, :dir, :alt, :cp, :zona, :loc, :info, :ppal, 1)
    """)
    with engine_tienda.begin() as cx:
        res = cx.execute(sql, dict(c=cliente_id, dir=direccion.strip(), alt=int(altura or 0),
                                   cp=int(codigo_postal or 0), zona=id_zona,
                                   loc=localidad.strip(), info=info_adicional.strip(),
                                   ppal=1 if principal else 0))
        return int(res.lastrowid)


def direcciones(cliente_id: int) -> list[dict]:
    sql = """SELECT id_direccion, direccion, altura, localidad, id_zona, infoAdicional, principal
             FROM direccion WHERE id_cliente = :c AND activo = 1 ORDER BY principal DESC, id_direccion DESC"""
    with engine_tienda.connect() as cx:
        return [dict(id=int(r.id_direccion), direccion=r.direccion, altura=r.altura,
                     localidad=r.localidad, id_zona=r.id_zona, info=r.infoAdicional,
                     principal=bool(r.principal)) for r in cx.execute(text(sql), {"c": cliente_id})]
