"""Contenido editable de la tienda (carrousel, textos, FAQ) — base de la tienda."""
from __future__ import annotations

import json
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
            "SELECT texto FROM genericos WHERE activo = 1 ORDER BY id")).all()
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
