"""Meta Conversions API (CAPI): complementa al Pixel del navegador ("Pixel
PaginaWeb MO") con los mismos eventos enviados server-side.

Por qué: una parte importante del tráfico llega desde el browser in-app de
Instagram/Facebook, que bloquea cookies y hace que el Pixel del navegador no
registre bien las conversiones ahí. Mandando el mismo evento también desde
acá, con el mismo `event_id` que usa la llamada de fbq() en el navegador,
Meta deduplica los dos automáticamente (no cuenta doble).

El token de acceso se genera en Meta Events Manager -> Pixel PaginaWeb MO ->
Configuración -> Conversions API -> Generar token de acceso manual. Nunca se
hardcodea ni se versiona: sale de la variable de entorno META_CAPI_TOKEN
(ver app/config.py). Vacía = CAPI desactivada, sin romper nada (sigue
funcionando el Pixel del navegador solo, como hasta ahora).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request

from fastapi import Request

from . import contenido
from .config import get_settings

S = get_settings()
_URL = "https://graph.facebook.com/v20.0/{pixel_id}/events"
_TIMEOUT = 4  # segundos: un problema de red de Meta nunca debe demorar el checkout
_LOG = logging.getLogger("tienda.errores")


def _hash(valor: str) -> str:
    return hashlib.sha256(valor.strip().lower().encode("utf-8")).hexdigest()


def _fbc_desde_click_id(request: Request) -> str:
    """Si no hay cookie _fbc (el browser in-app la bloquea) pero la URL trae
    fbclid (viene de un anuncio de Meta), se arma el mismo formato que
    generaría el Pixel: fb.1.<timestamp_ms>.<fbclid>."""
    fbclid = request.query_params.get("fbclid")
    if not fbclid:
        return ""
    return f"fb.1.{int(time.time() * 1000)}.{fbclid}"


def _user_data(request: Request, cliente=None) -> dict:
    ud: dict = {}
    if cliente is not None:
        email = getattr(cliente, "email", None)
        if email:
            ud["em"] = [_hash(email)]
        telefono = getattr(cliente, "telefono", None)
        if telefono:
            # mismo formato que WHATSAPP en main.py: 549 + área + número
            ud["ph"] = [_hash(f"549{telefono}")]
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    if ip:
        ud["client_ip_address"] = ip
    ua = request.headers.get("user-agent")
    if ua:
        ud["client_user_agent"] = ua
    fbp = request.cookies.get("_fbp")
    if fbp:
        ud["fbp"] = fbp
    fbc = request.cookies.get("_fbc") or _fbc_desde_click_id(request)
    if fbc:
        ud["fbc"] = fbc
    return ud


def _destinos() -> list[tuple[str, str]]:
    """Pares (pixel_id, token) a los que se manda cada evento. Un pixel sin token queda solo con el del
    navegador. Hoy: el pixel de siempre y, si está configurado, un segundo pixel (cuenta publicitaria USD)."""
    out: list[tuple[str, str]] = []
    p1, p2 = contenido.meta_pixel_id(), contenido.meta_pixel_id_2()
    if p1 and S.meta_capi_token:
        out.append((p1, S.meta_capi_token))
    if p2 and S.meta_capi_token_2:
        out.append((p2, S.meta_capi_token_2))
    return out


def es_host_local(request: Request) -> bool:
    """Pruebas en la PC (localhost): no deben contaminar las métricas de Meta."""
    host = (request.headers.get("host") or "").split(":")[0].lower()
    return host in ("localhost", "127.0.0.1", "[::1]") or host.endswith(".localhost")


def enviar_evento(event_name: str, event_id: str, request: Request,
                   custom_data: dict, cliente=None) -> None:
    """Manda un evento a la Conversions API con el mismo event_id que su
    contraparte del Pixel de navegador (deduplicación). Nunca rompe el
    checkout: cualquier falla (token no configurado, sin red, error de Meta)
    queda solo logueada."""
    destinos = _destinos()
    if not destinos or es_host_local(request):
        return
    # Quien tocó "Rechazar" en el cartel de cookies no manda nada a Meta (ni desde el navegador ni desde acá).
    # No tocar nada cuenta como aceptar. La cookie `mo-cookies` es del dominio raíz y llega a este servidor.
    if request.cookies.get("mo-cookies") == "no":
        return
    try:
        payload = json.dumps({
            "data": [{
                "event_name": event_name,
                "event_time": int(time.time()),
                "event_id": event_id,
                "event_source_url": str(request.url),
                "action_source": "website",
                "user_data": _user_data(request, cliente),
                "custom_data": custom_data,
            }],
        }).encode("utf-8")
    except Exception:
        _LOG.exception("Meta CAPI: no se pudo armar %s (event_id=%s)", event_name, event_id)
        return
    # Un envío por pixel (cada uno con su token): si uno falla, el otro igual sale.
    for pixel_id, token in destinos:
        try:
            req = urllib.request.Request(
                _URL.format(pixel_id=pixel_id) + f"?access_token={token}", data=payload,
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                resp.read()
        except Exception:
            _LOG.exception("Meta CAPI: no se pudo enviar %s al pixel %s (event_id=%s)", event_name, pixel_id, event_id)
