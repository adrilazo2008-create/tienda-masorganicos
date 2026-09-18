"""Clientes de la tienda (tabla `users` en iebbbhrt_prueba_paginaweb).

Identificación de baja fricción: el cliente se identifica SOLO por celular. No hay
contraseña ni PIN; todo se coordina después por WhatsApp. `hash_pin` / `verificar_pin`
quedan por si en el futuro se quiere proteger "Mis pedidos" con un código.

El sistema de escritorio (VB6) busca al cliente en el ERP por `users.telefono` y luego por
`users.email`. Por eso lo único importante es dejar esos dos campos bien cargados.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import bcrypt
from sqlalchemy import bindparam, text

from .db import engine_erp, engine_tienda

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
    entran en un INT. Se saca un prefijo 54 / 549 / 0 si viene, y se
    normalizan las dos costumbres viejas de cargar un celular de AMBA:
      - "11 15 5504-6740"  (área + 15 completo)      -> se saca el 15
      - "15 5504-6740"     (solo la marca "es celu",
                             sin código de área)       -> el 15 pasa a ser 11
    para que todos los números nuevos se guarden en la forma moderna
    ("11 5504-6740"). Ver `_variante_11_15` para reconocer a alguien que ya
    estaba cargado en una de las formas viejas.
    """
    d = re.sub(r"\D", "", valor or "")
    if d.startswith("549"):
        d = d[3:]
    elif d.startswith("54"):
        d = d[2:]
    d = d.lstrip("0")
    if d[:2] == "11" and d[2:4] == "15":
        d = d[:2] + d[4:]
    elif d[:2] == "15":
        d = "11" + d[2:]
    if not d:
        return 0
    n = int(d)
    return n if n <= _INT_MAX else int(d[-9:])  # fallback defensivo


def _variante_11_15(tel: int) -> Optional[int]:
    """La otra forma del mismo número: en la base conviven celulares de AMBA
    cargados con código de área ("11 5504-6740") y cargados a la vieja usanza,
    marcando "es un celu" en vez del área ("15 5504-6740"). Las dos terminan
    siendo un número de 10 dígitos que empieza con 11 o con 15.
    `buscar_por_telefono` prueba las dos para no dejar de reconocer a alguien
    solo porque quedó cargado de la forma vieja."""
    d = str(tel)
    if d.startswith("11"):
        return int("15" + d[2:])
    if d.startswith("15"):
        return int("11" + d[2:])
    return None


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
    cliente_codigo: Optional[int] = None

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()


def _fila(r) -> Cliente:
    return Cliente(int(r.id), (r.nombre or "").strip(), (r.apellido or "").strip(),
                   int(r.telefono or 0), (r.email or "").strip(),
                   bool(r.password and str(r.password).startswith("$2")),
                   int(r.cliente_codigo) if getattr(r, "cliente_codigo", None) else None)


def buscar_por_telefono(telefono: str) -> Optional[Cliente]:
    tel = normalizar_telefono(telefono)
    if not tel:
        return None
    variante = _variante_11_15(tel)
    tels = [tel, variante] if variante else [tel]
    sql = text(
        "SELECT id,nombre,apellido,telefono,email,password,cliente_codigo FROM users "
        "WHERE telefono IN :ts AND activo = 1 ORDER BY id DESC LIMIT 1"
    ).bindparams(bindparam("ts", expanding=True))
    with engine_tienda.connect() as cx:
        r = cx.execute(sql, {"ts": tels}).first()
    return _fila(r) if r else None


def _partir_nombre(razon_social: str) -> tuple[str, str]:
    """'Sandra Granata' -> ('Sandra', 'Granata'). La ficha del ERP no separa
    nombre y apellido, es un solo campo de texto libre; separamos por la
    primera palabra nomás, a falta de algo mejor."""
    partes = (razon_social or "").strip().split(None, 1)
    if len(partes) == 2:
        return partes[0], partes[1]
    return (partes[0] if partes else "", "")


def buscar_en_erp(telefono: str) -> Optional[dict]:
    """Si alguien ya es cliente (compró antes en el local, o está cargado en
    el sistema de escritorio) pero nunca hizo un pedido por la web, no está
    en `users` y `buscar_por_telefono` no lo encuentra — tendría que volver a
    escribir todos sus datos como si fuera la primera vez.

    Esto busca en `clientes` del ERP (la ficha que usa el sistema de
    escritorio) por los últimos 8 dígitos del celular: `Telefonos`/`Celular`
    son texto libre (con o sin código de área, con "/" si hay más de uno,
    etc.), así que comparar solo la punta evita quedar afuera por el formato.

    Devuelve un dict {nombre, apellido, email, direccion, localidad} para
    sugerir/precargar el formulario, o None si no hay coincidencia. No se usa
    para nada más (no reemplaza a `users`, no se guarda solo): recién se crea
    el cliente de la tienda cuando complete el pedido, como siempre.
    """
    tel = normalizar_telefono(telefono)
    if not tel:
        return None
    ultimos8 = str(tel)[-8:]
    if len(ultimos8) < 8:
        return None
    sql = text("""
        SELECT RazonSocial, EMail, Direccion, Localidad
        FROM clientes
        WHERE (Telefonos LIKE :t OR Celular LIKE :t) AND RazonSocial <> ''
        ORDER BY Codigo DESC LIMIT 1
    """)
    with engine_erp.connect() as cx:
        r = cx.execute(sql, {"t": f"%{ultimos8}%"}).first()
    if not r or not (r.RazonSocial or "").strip():
        return None
    nombre, apellido = _partir_nombre(r.RazonSocial)
    return {
        "nombre": nombre,
        "apellido": apellido,
        "email": (r.EMail or "").strip(),
        "direccion": (r.Direccion or "").strip(),
        "localidad": (r.Localidad or "").strip(),
    }


def buscar_por_email(email: str) -> Optional[Cliente]:
    email = (email or "").strip().lower()
    if not email:
        return None
    sql = "SELECT id,nombre,apellido,telefono,email,password,cliente_codigo FROM users WHERE LOWER(email) = :e AND activo = 1 LIMIT 1"
    with engine_tienda.connect() as cx:
        r = cx.execute(text(sql), {"e": email}).first()
    return _fila(r) if r else None


def obtener(cliente_id: int) -> Optional[Cliente]:
    sql = "SELECT id,nombre,apellido,telefono,email,password,cliente_codigo FROM users WHERE id = :id LIMIT 1"
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
                      principal: bool = True, barrio: str = "", lote: str = "") -> int:
    if principal:
        with engine_tienda.begin() as cx:
            cx.execute(text("UPDATE direccion SET principal = 0 WHERE id_cliente = :c"),
                       {"c": cliente_id})
    sql = text("""
        INSERT INTO direccion (id_cliente, direccion, altura, codigoPostal, id_zona,
                               localidad, infoAdicional, principal, activo, barrio, lote)
        VALUES (:c, :dir, :alt, :cp, :zona, :loc, :info, :ppal, 1, :barrio, :lote)
    """)
    with engine_tienda.begin() as cx:
        res = cx.execute(sql, dict(c=cliente_id, dir=direccion.strip(), alt=int(altura or 0),
                                   cp=int(codigo_postal or 0), zona=id_zona,
                                   loc=localidad.strip(), info=info_adicional.strip(),
                                   ppal=1 if principal else 0,
                                   barrio=barrio.strip() or None, lote=lote.strip() or None))
        return int(res.lastrowid)


def direcciones(cliente_id: int) -> list[dict]:
    sql = """SELECT id_direccion, direccion, altura, localidad, id_zona, infoAdicional, principal, barrio, lote
             FROM direccion WHERE id_cliente = :c AND activo = 1 ORDER BY principal DESC, id_direccion DESC"""
    with engine_tienda.connect() as cx:
        return [dict(id=int(r.id_direccion), direccion=r.direccion, altura=r.altura,
                     localidad=r.localidad, id_zona=r.id_zona, info=r.infoAdicional,
                     principal=bool(r.principal), barrio=r.barrio, lote=r.lote)
                for r in cx.execute(text(sql), {"c": cliente_id})]


# --------------------------------------------------------------------------- ERP (clientes)

def _concatenar_direccion_erp(direccion: str, altura, barrio: str, lote: str) -> str:
    import re as _re
    calle = (direccion or "").strip()
    barrio = (barrio or "").strip()
    altura_s = str(altura).strip() if altura else ""
    if altura_s and altura_s != "0" and not _re.search(rf"\b{_re.escape(altura_s)}\b\s*$", calle):
        calle = f"{calle} {altura_s}".strip()
    partes = [p for p in (calle, barrio) if p]
    if lote:
        partes.append(f"Lote {lote}")
    return ", ".join(partes)


def _buscar_codigo_erp(telefono: int, email: str) -> Optional[int]:
    """Busca en `clientes` (ERP) por telefono/email normalizados. Devuelve el
    Codigo SOLO si hay exactamente un candidato (ver matchear_clientes.py:
    con 2+ candidatos no se auto-vincula, queda para revision manual)."""
    candidatos: set[int] = set()
    tel = str(telefono) if telefono else ""
    variante = _variante_11_15(telefono) if telefono else None
    tels = [t for t in (tel, str(variante) if variante else None) if t]
    with engine_erp.connect() as cx:
        if tels:
            rows = cx.execute(text(
                "SELECT Codigo FROM clientes WHERE Telefonos IN :ts OR Celular IN :ts"
            ).bindparams(bindparam("ts", expanding=True)), {"ts": tels})
            candidatos |= {r.Codigo for r in rows}
        if email:
            rows = cx.execute(text(
                "SELECT Codigo FROM clientes WHERE LOWER(EMail) = :e"
            ), {"e": email.strip().lower()})
            candidatos |= {r.Codigo for r in rows}
    return next(iter(candidatos)) if len(candidatos) == 1 else None


def _crear_cliente_erp(nombre: str, apellido: str, telefono: int, email: str) -> int:
    """Da de alta un cliente nuevo en `clientes` (ERP) con los datos de la
    tienda. Solo completa nombre/telefono/email/direccion: el resto de los
    campos contables quedan en los valores por defecto seguros (no se
    inventa condicion de IVA, lista de precio, etc.)."""
    razon_social = f"{nombre} {apellido}".strip() or "Cliente tienda web"
    with engine_erp.begin() as cx:
        siguiente = cx.execute(text("SELECT COALESCE(MAX(Codigo), 0) + 1 FROM clientes")).scalar()
        cx.execute(text("""
            INSERT INTO clientes
                (Codigo, RazonSocial, Telefonos, Celular, EMail, Activo,
                 Provincia, Pais, Zona, Tiva, TipoCliente, Categoria, Rubro,
                 CondicionVenta, ListaPrecio, FechaCreacion, ComoLlego)
            VALUES
                (:cod, :razon, :tel, :tel, :mail, 1,
                 0, 0, 0, 0, 0, 120000004, 0,
                 0, 0, NOW(), 'Tienda web')
        """), dict(cod=siguiente, razon=razon_social, tel=str(telefono) if telefono else None,
                    mail=email or None))
    return int(siguiente)


def sincronizar_erp(cli: Cliente, direccion: str, altura, localidad: str,
                    barrio: str, lote: str, info_adicional: str) -> None:
    """Al confirmar un pedido: si el cliente todavia no tiene `cliente_codigo`,
    intenta vincularlo (o darlo de alta) en el ERP; despues, si hay direccion
    de envio, la vuelca en `clientes` (Direccion+Localidad+Contacto) para que
    el sistema de escritorio siempre tenga la mas reciente.

    Nunca debe romper el checkout: cualquier error queda solo logueado."""
    try:
        codigo = cli.cliente_codigo
        if not codigo:
            codigo = _buscar_codigo_erp(cli.telefono, cli.email)
            if not codigo:
                codigo = _crear_cliente_erp(cli.nombre, cli.apellido, cli.telefono, cli.email)
            with engine_tienda.begin() as cx:
                cx.execute(text("UPDATE users SET cliente_codigo=:cod WHERE id=:id"),
                           {"cod": codigo, "id": cli.id})

        if not (direccion or "").strip() and not (barrio or "").strip():
            return  # retiro en sucursal, o sin direccion cargada: nada que sincronizar

        nueva_direccion = _concatenar_direccion_erp(direccion, altura, barrio, lote)
        with engine_erp.begin() as cx:
            cx.execute(text("""
                UPDATE clientes SET
                    Direccion = :dir,
                    Localidad = COALESCE(NULLIF(:loc, ''), Localidad),
                    Contacto  = COALESCE(NULLIF(:info, ''), Contacto)
                WHERE Codigo = :cod
            """), dict(dir=nueva_direccion, loc=(localidad or "").strip(),
                       info=(info_adicional or "").strip(), cod=codigo))
    except Exception:
        import logging
        logging.getLogger(__name__).exception("No se pudo sincronizar el cliente %s con el ERP", cli.id)
