"""Punto de entrada para Phusion Passenger (cPanel · Setup Python App).

Passenger habla WSGI; FastAPI es ASGI. `a2wsgi` hace el puente.
El "Application Entry point" en cPanel debe ser:  application
"""
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from a2wsgi import ASGIMiddleware  # noqa: E402
from app.main import app as _asgi_app  # noqa: E402

application = ASGIMiddleware(_asgi_app)
