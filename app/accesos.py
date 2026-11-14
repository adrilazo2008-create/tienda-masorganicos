"""Registro de qué clientes con sesión iniciada entraron a la tienda y cuándo.

Dos tablas, una fila por día:
- `accesos_clientes`: por cliente logueado (primera y última hora, páginas).
- `accesos_visitantes`: por dispositivo/navegador (`visitante_id`, el UUID de la
  cookie de sesión), logueado o no. Sirve para contar visitantes ANÓNIMOS: un
  dispositivo cuenta como anónimo ese día si en ningún momento inició sesión.
  Es por dispositivo, no por persona (la misma persona con celular y PC cuenta
  dos). Se descartan robots/rastreadores por user-agent.
Lo lee `conectar` (pantalla "Accesos a la tienda"). Las visitas internas (cookie `mo_interno=1`, que se pone entrando
una vez con `?interno=1`) se ignoran. Nunca debe romper ni demorar una página:
se escribe en segundo plano y cualquier error se traga.
"""
from __future__ import annotations

import threading

from sqlalchemy import text

from .db import engine_tienda

_tabla_lista = False

_ROBOTS = ("bot", "crawl", "spider", "slurp", "facebookexternalhit", "preview", "monitor",
           "headless", "lighthouse", "curl", "wget", "python-requests", "httpclient", "uptime")


def _asegurar_tabla() -> None:
    global _tabla_lista
    if _tabla_lista:
        return
    with engine_tienda.begin() as cx:
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS accesos_clientes (
                fecha DATE NOT NULL,
                user_id INT NOT NULL,
                primera DATETIME NOT NULL,
                ultima DATETIME NOT NULL,
                paginas INT NOT NULL DEFAULT 1,
                PRIMARY KEY (fecha, user_id)
            )
        """))
        cx.execute(text("""
            CREATE TABLE IF NOT EXISTS accesos_visitantes (
                fecha DATE NOT NULL,
                visitante_id CHAR(36) NOT NULL,
                logueado TINYINT NOT NULL DEFAULT 0,
                primera DATETIME NOT NULL,
                ultima DATETIME NOT NULL,
                paginas INT NOT NULL DEFAULT 1,
                PRIMARY KEY (fecha, visitante_id)
            )
        """))
        # 2026-11-14: de qué sitio es la visita ('web' = masorganicos.com.ar, 'tienda') y si el dispositivo llegó a la
        # tienda desde la web (Referer). La web y la tienda son dos dominios (dos cookies): el mismo dispositivo tiene un
        # visitante_id en cada uno. Las filas anteriores quedan con sitio NULL (no se sabe).
        columnas = {r[0].lower() for r in cx.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'accesos_visitantes'"))}
        if "sitio" not in columnas:
            cx.execute(text("ALTER TABLE accesos_visitantes ADD COLUMN sitio VARCHAR(8) NULL"))
        if "desde_web" not in columnas:
            cx.execute(text("ALTER TABLE accesos_visitantes ADD COLUMN desde_web TINYINT NOT NULL DEFAULT 0"))
    _tabla_lista = True


_HOSTS_WEB = {"masorganicos.com.ar", "www.masorganicos.com.ar"}


def _sitio_y_origen(request):
    """('web' | 'tienda', llegó_desde_la_web: 0/1) según el dominio de la visita y el Referer."""
    host = (request.headers.get("host") or "").split(":")[0].lower()
    sitio = "web" if host in _HOSTS_WEB else "tienda"
    ref = (request.headers.get("referer") or "").lower()
    desde_web = 0
    if sitio == "tienda" and ref:
        try:
            from urllib.parse import urlparse
            desde_web = 1 if (urlparse(ref).hostname or "") in _HOSTS_WEB else 0
        except Exception:
            desde_web = 0
    return sitio, desde_web


def _escribir(user_id, visitante_id, sitio=None, desde_web=0) -> None:
    try:
        _asegurar_tabla()
        with engine_tienda.begin() as cx:
            if user_id:
                cx.execute(text("""
                    INSERT INTO accesos_clientes (fecha, user_id, primera, ultima, paginas)
                    VALUES (CURDATE(), :u, NOW(), NOW(), 1)
                    ON DUPLICATE KEY UPDATE ultima = NOW(), paginas = paginas + 1
                """), {"u": user_id})
            if visitante_id:
                cx.execute(text("""
                    INSERT INTO accesos_visitantes (fecha, visitante_id, logueado, primera, ultima, paginas, sitio, desde_web)
                    VALUES (CURDATE(), :v, :l, NOW(), NOW(), 1, :s, :d)
                    ON DUPLICATE KEY UPDATE ultima = NOW(), paginas = paginas + 1,
                                            logueado = GREATEST(logueado, :l),
                                            sitio = COALESCE(sitio, :s), desde_web = GREATEST(desde_web, :d)
                """), {"v": visitante_id, "l": 1 if user_id else 0, "s": sitio, "d": desde_web})
    except Exception:
        pass


def registrar(request, cliente) -> None:
    """Llamar al renderizar una página completa (GET, no HTMX) con el cliente
    de la sesión (o None si es un visitante anónimo)."""
    if request.method != "GET":
        return
    if request.headers.get("HX-Request") or request.cookies.get("mo_interno") == "1":
        return
    ua = (request.headers.get("user-agent") or "").lower()
    if not ua or any(r in ua for r in _ROBOTS):
        return
    try:
        from .navegacion import visitante_id
        vid = visitante_id(request.session)
    except Exception:
        vid = None
    if cliente is None and not vid:
        return
    try:
        sitio, desde_web = _sitio_y_origen(request)
    except Exception:
        sitio, desde_web = None, 0
    threading.Thread(target=_escribir, args=(cliente.id if cliente else None, vid, sitio, desde_web),
                     daemon=True).start()
