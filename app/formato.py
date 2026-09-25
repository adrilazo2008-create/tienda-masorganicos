"""Helpers de presentación."""
import re
from decimal import Decimal

from markupsafe import Markup, escape

_URL_RE = re.compile(r"(https?://[^\s<]+)")


def pesos(valor) -> str:
    """12500 -> '$12.500'   ·   1234.5 -> '$1.234,50'"""
    try:
        d = Decimal(str(valor))
    except Exception:
        return "$0"
    entero = int(d.to_integral_value(rounding="ROUND_DOWN"))
    dec = (d - entero) * 100
    s = f"{entero:,}".replace(",", ".")
    if dec:
        return f"${s},{int(dec):02d}"
    return f"${s}"


def cantidad(valor) -> str:
    d = Decimal(str(valor))
    if d == d.to_integral_value():
        return str(int(d))
    return f"{d.normalize()}".replace(".", ",")


def linkify(texto: str) -> Markup:
    """Convierte las URLs sueltas de un texto (ej. en la descripción de un
    producto: "más info en https://...") en links clickeables, sin tocar el
    resto del texto. Escapa todo primero para no abrir paso a HTML/XSS desde
    un campo que se carga desde el ERP."""
    partes = []
    ultimo = 0
    for m in _URL_RE.finditer(texto or ""):
        url = m.group(1).rstrip(".,;:)")
        partes.append(escape(texto[ultimo:m.start()]))
        partes.append(Markup('<a href="{0}" target="_blank" rel="noopener noreferrer">{0}</a>').format(url))
        ultimo = m.start() + len(url)
    partes.append(escape(texto[ultimo:] if texto else ""))
    return Markup("").join(partes)
