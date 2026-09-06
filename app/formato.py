"""Helpers de presentación."""
from decimal import Decimal


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
