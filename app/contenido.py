"""Contenido editable de la tienda (carrousel, textos, FAQ) — base de la tienda."""
from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy import text

from .db import engine_tienda

_DATA = Path(__file__).resolve().parent / "data"


def home_config() -> dict:
    """Config editable de la home (app/data/home.json)."""
    try:
        return json.loads((_DATA / "home.json").read_text(encoding="utf-8"))
    except OSError:
        return {}


def meta_pixel_id() -> str:
    """ID del Pixel de Meta (app/data/integraciones.json). Vacío = sin pixel."""
    try:
        data = json.loads((_DATA / "integraciones.json").read_text(encoding="utf-8"))
        return str(data.get("meta_pixel_id") or "").strip()
    except OSError:
        return ""


_TAGS = re.compile(r"<[^>]+>")


def anuncio() -> dict:
    """Barra de anuncio superior (site-wide).

    Fuente 1 (preferida): fila de `genericos` con titulo = 'BARRA_ANUNCIO' y activo = 1.
      - texto  -> el aviso (se le quitan las etiquetas HTML)
      - linkMapa -> link opcional; si es "url | texto" se parte en link + link_texto
      Para apagar la barra: activo = 0 en esa fila.
    Fuente 2 (fallback): app/data/home.json, clave "anuncio" {activo, texto, link, link_texto}.
    """
    try:
        with engine_tienda.connect() as cx:
            row = cx.execute(text(
                "SELECT texto, linkMapa FROM genericos "
                "WHERE activo = 1 AND titulo = 'BARRA_ANUNCIO' ORDER BY id LIMIT 1"
            )).first()
    except Exception:
        row = None

    if row and (row.texto or "").strip():
        texto = " ".join(_TAGS.sub(" ", row.texto).split()).strip()
        link, link_texto = (row.linkMapa or "").strip(), ""
        if "|" in link:
            link, link_texto = (p.strip() for p in link.split("|", 1))
        return {"texto": texto, "link": link, "link_texto": link_texto}

    a = home_config().get("anuncio") or {}
    if not a.get("activo") or not (a.get("texto") or "").strip():
        return {}
    return {
        "texto": a["texto"].strip(),
        "link": (a.get("link") or "").strip(),
        "link_texto": (a.get("link_texto") or "").strip(),
    }


def carrusel_home() -> list[dict]:
    """Imágenes del banner de la home ({img, alt}). Editar app/data/carrusel_home.json;
    los archivos van en {IMG_BASE}/carrousel/."""
    try:
        return json.loads((_DATA / "carrusel_home.json").read_text(encoding="utf-8"))
    except OSError:
        return []


def productores() -> list[dict]:
    """Productores/comercializadoras con los que trabaja Más Orgánicos.
    Se edita en app/data/productores.json ({nombre, logo}; logo opcional -> archivo
    en {IMG_BASE}/productores/)."""
    try:
        return json.loads((_DATA / "productores.json").read_text(encoding="utf-8"))
    except OSError:
        return []


def carrousel() -> list[dict]:
    sql = """SELECT nombreImg, titulo, subtitulo, link, tituloLink
             FROM carrousel WHERE activo = 1 ORDER BY id_imgCarousel"""
    with engine_tienda.connect() as cx:
        return [dict(imagen=r.nombreImg.strip(), titulo=(r.titulo or "").strip(),
                     subtitulo=(r.subtitulo or "").strip(), link=(r.link or "").strip(),
                     titulo_link=(r.tituloLink or "").strip())
                for r in cx.execute(text(sql))]


def avisos(limite: int = 2) -> list[str]:
    """Textos de `genericos` (avisos de la home: feriados, mínimos de envío, etc.)."""
    with engine_tienda.connect() as cx:
        rows = cx.execute(text(
            "SELECT texto FROM genericos WHERE activo = 1 "
            "AND titulo <> 'BARRA_ANUNCIO' ORDER BY id")).all()
    textos = [r.texto.strip() for r in rows if (r.texto or "").strip()]
    return textos[:limite]


def faq() -> list[dict]:
    sql = """
        SELECT p.titulo AS pregunta, r.respuesta AS respuesta
        FROM faq_preguntas p
        JOIN faq_respuestas r ON r.id_faq_pregunta = p.id_faq_pregunta AND r.activo = 1
        WHERE p.activo = 1
        ORDER BY p.orden, p.id_faq_pregunta
    """
    with engine_tienda.connect() as cx:
        return [dict(pregunta=r.pregunta.strip(), respuesta=r.respuesta.strip())
                for r in cx.execute(text(sql))]


def suscribir_newsletter(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    try:
        with engine_tienda.begin() as cx:
            cx.execute(text("INSERT IGNORE INTO newsletter (email, activo) VALUES (:e, 1)"),
                       {"e": email})
        return True
    except Exception:
        return False
