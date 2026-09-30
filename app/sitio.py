"""Sitio institucional + blog de Más Orgánicos.

El blog no usa base de datos ni panel: cada nota es un archivo Markdown en
`app/blog/`. Para publicar una nota nueva se agrega el .md y se hace deploy.

Formato de cada archivo  (app/blog/2026-09-10-mi-nota.md):

    ---
    titulo: Título de la nota
    fecha: 2026-09-10
    resumen: Una o dos líneas que se ven en el listado y en redes.
    portada: quinta.jpg          # opcional, archivo en {IMG_BASE}/blog/
    autor: Más Orgánicos         # opcional
    borrador: true               # opcional, la oculta del sitio
    ---

    Acá va el cuerpo en **Markdown** normal: títulos, listas, links, imágenes…

El slug (la parte de la URL) sale del nombre del archivo, sacándole la fecha:
`2026-09-10-mi-nota.md`  ->  `/blog/mi-nota`.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import markdown

from .catalogo import _cacheado

_BLOG = Path(__file__).resolve().parent / "blog"
_TTL = 120  # segundos; se refresca solo al rato o al reiniciar la app

_MESES = ("", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _fecha_larga(d: date) -> str:
    return f"{d.day} de {_MESES[d.month]} de {d.year}"


def _parsear(ruta: Path) -> dict | None:
    txt = ruta.read_text(encoding="utf-8").lstrip()
    meta: dict[str, str] = {}
    cuerpo = txt
    if txt.startswith("---"):
        cierre = txt.find("\n---", 3)
        if cierre != -1:
            cabecera = txt[3:cierre]
            cuerpo = txt[cierre + 4:].lstrip("\n")
            for linea in cabecera.splitlines():
                if ":" in linea:
                    k, v = linea.split(":", 1)
                    meta[k.strip().lower()] = v.strip()

    if str(meta.get("borrador", "")).lower() in ("1", "true", "si", "sí"):
        return None

    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", ruta.stem)
    try:
        f = datetime.strptime(meta.get("fecha", ""), "%Y-%m-%d").date()
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", ruta.stem)
        f = date(int(m[1]), int(m[2]), int(m[3])) if m else date.today()

    md = markdown.Markdown(extensions=["extra", "sane_lists", "smarty"])
    return {
        "slug": slug,
        "titulo": meta.get("titulo") or slug.replace("-", " ").capitalize(),
        "fecha": f,
        "fecha_iso": f.isoformat(),
        "fecha_larga": _fecha_larga(f),
        "resumen": meta.get("resumen", ""),
        "portada": meta.get("portada", ""),
        "autor": meta.get("autor", "Más Orgánicos"),
        "html": md.convert(cuerpo),
    }


def _todas() -> list[dict]:
    if not _BLOG.exists():
        return []
    notas = [n for n in (_parsear(p) for p in _BLOG.glob("*.md")) if n]
    notas.sort(key=lambda n: n["fecha"], reverse=True)
    return notas


def posts() -> list[dict]:
    return _cacheado("blog:index", _TTL, _todas)


def post(slug: str) -> dict | None:
    return next((n for n in posts() if n["slug"] == slug), None)
