"""Panel de administración: zonas y envíos, avisos, destacados, carrusel de
la home y el Pixel de Meta.

Protegido con UNA contraseña compartida (`ADMIN_PASSWORD` en el .env), no es
un sistema de usuarios — alcanza para poder delegarle esta tarea a alguien
sin darle acceso a phpMyAdmin ni tener que pedírselo todo a Claude. Para
cortarle el acceso a alguien, se cambia la contraseña.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import catalogo, contenido, zonas
from .config import get_settings
from .formato import pesos

S = get_settings()
router = APIRouter(prefix="/admin")

_BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=_BASE_DIR / "templates")
templates.env.globals["pesos"] = pesos


def _logueado(request: Request) -> bool:
    return bool(request.session.get("admin"))


def _render(request: Request, plantilla: str, **extra) -> HTMLResponse:
    ctx = {"request": request, "logueado": _logueado(request),
           "mensaje": request.session.pop("admin_msg", None)}
    ctx.update(extra)
    return templates.TemplateResponse(request, plantilla, ctx)


def _num(form, clave: str, default: str = "0") -> Decimal:
    try:
        return Decimal(str(form.get(clave, default)).replace(",", ".") or "0")
    except InvalidOperation:
        return Decimal("0")


def _dir_imagenes(subcarpeta: str) -> Path:
    """Carpeta física donde vive `{IMG_BASE}/<subcarpeta>/`, para poder guardar
    ahí un archivo subido desde el admin.

    En local, IMG_BASE_URL es "/img" y esos archivos viven en _migracion/fotos/.
    En producción, IMG_BASE_URL es una URL absoluta a OTRO dominio
    (masorganicos.com.ar) pero en la MISMA cuenta/filesystem: la carpeta
    `claude2026/assets/img/` vive al lado de `claude2026/tienda/` (esta app)."""
    if S.img_base_url.startswith("/"):
        d = _BASE_DIR.parent / "_migracion" / "fotos" / subcarpeta
    else:
        d = _BASE_DIR.parent.parent / "assets" / "img" / subcarpeta
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _guardar_archivo(subida, carpeta: Path) -> str:
    """Guarda un archivo subido (UploadFile) en `carpeta`, con su nombre
    original saneado. Devuelve el nombre final, o "" si no vino ningún archivo."""
    nombre = getattr(subida, "filename", "") or ""
    if not nombre:
        return ""
    nombre = re.sub(r"[^A-Za-z0-9._-]", "_", Path(nombre).name)
    contenido = await subida.read()
    if not contenido:
        return ""
    (carpeta / nombre).write_bytes(contenido)
    return nombre


# --------------------------------------------------------------------------- acceso

@router.get("/", response_class=HTMLResponse)
def admin_home(request: Request):
    return RedirectResponse("/admin/zonas" if _logueado(request) else "/admin/login")


@router.get("/login", response_class=HTMLResponse)
def admin_login(request: Request):
    if _logueado(request):
        return RedirectResponse("/admin/zonas")
    return _render(request, "admin_login.html")


@router.post("/login", response_class=HTMLResponse)
def admin_login_post(request: Request, clave: str = Form(...)):
    if clave == S.admin_password:
        request.session["admin"] = True
        return RedirectResponse("/admin/zonas", status_code=303)
    return _render(request, "admin_login.html", error="Contraseña incorrecta.")


@router.get("/salir")
def admin_salir(request: Request):
    request.session.pop("admin", None)
    return RedirectResponse("/admin/login", status_code=303)


# --------------------------------------------------------------------------- zonas

@router.get("/zonas", response_class=HTMLResponse)
def admin_zonas(request: Request):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _render(request, "admin_zonas.html", zonas=zonas.todas_las_zonas())


@router.post("/zonas")
async def admin_zonas_guardar(request: Request):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    form = await request.form()
    for z in zonas.todas_las_zonas():
        if f"precio_{z.id}" not in form:
            continue  # no vino en el POST (no debería pasar, pero por las dudas)
        zonas.actualizar_zona(
            z.id,
            precio=_num(form, f"precio_{z.id}"),
            descuento=int(_num(form, f"descuento_{z.id}")),
            mim_compra=_num(form, f"mim_compra_{z.id}"),
            envio_gratis=_num(form, f"envio_gratis_{z.id}"),
            activo=f"activo_{z.id}" in form,
        )
    request.session["admin_msg"] = "Zonas actualizadas."
    return RedirectResponse("/admin/zonas", status_code=303)


# --------------------------------------------------------------------------- avisos

@router.get("/avisos", response_class=HTMLResponse)
def admin_avisos(request: Request):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _render(request, "admin_avisos.html",
                  barra=contenido.barra_anuncio_admin(), avisos=contenido.avisos_admin())


@router.post("/anuncio")
def admin_anuncio_guardar(request: Request, texto: str = Form(""), link: str = Form(""),
                          link_texto: str = Form(""), activo: str = Form(None)):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    contenido.guardar_barra_anuncio(texto, link, link_texto, activo is not None)
    request.session["admin_msg"] = "Barra de anuncio actualizada."
    return RedirectResponse("/admin/avisos", status_code=303)


@router.post("/avisos/nuevo")
def admin_aviso_nuevo(request: Request, texto: str = Form("")):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    contenido.crear_aviso(texto)
    request.session["admin_msg"] = "Aviso agregado."
    return RedirectResponse("/admin/avisos", status_code=303)


@router.post("/avisos/{aviso_id}")
def admin_aviso_guardar(request: Request, aviso_id: int, texto: str = Form(""),
                        activo: str = Form(None)):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    contenido.guardar_aviso(aviso_id, texto, activo is not None)
    request.session["admin_msg"] = "Aviso actualizado."
    return RedirectResponse("/admin/avisos", status_code=303)


# --------------------------------------------------------------------------- destacados

@router.get("/destacados", response_class=HTMLResponse)
def admin_destacados(request: Request, q: str = ""):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    q = (q or "").strip()
    resultados = catalogo.listar(busqueda=q, limite=30) if q else []
    return _render(request, "admin_destacados.html", q=q,
                  actuales=catalogo.destacados(60), resultados=resultados)


@router.post("/destacados/{producto_id}")
def admin_destacado_set(request: Request, producto_id: int, valor: int = Form(...),
                        q: str = Form("")):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    catalogo.set_destacado(producto_id, bool(valor))
    return RedirectResponse(f"/admin/destacados?q={q}", status_code=303)


# --------------------------------------------------------------------------- carrusel

@router.get("/carrusel", response_class=HTMLResponse)
def admin_carrusel(request: Request):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _render(request, "admin_carrusel.html", slides=contenido.carrusel_home())


@router.post("/carrusel")
async def admin_carrusel_guardar(request: Request):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    form = await request.form()
    actuales = contenido.carrusel_home()
    carpeta = _dir_imagenes("carrousel")

    async def _armar(prefijo: str) -> dict | None:
        img = str(form.get(f"img_{prefijo}", "")).strip()
        subida = form.get(f"archivo_{prefijo}")
        if subida is not None:
            nombre = await _guardar_archivo(subida, carpeta)
            if nombre:
                img = nombre  # el archivo subido manda, aunque el campo de texto diga otra cosa
        if not img:
            return None
        slide = {"img": img, "alt": str(form.get(f"alt_{prefijo}", "")).strip()}
        modo = str(form.get(f"modo_{prefijo}", "catalogo"))
        if modo == "ninguno":
            slide["link"] = ""
        elif modo == "custom":
            slide["link"] = str(form.get(f"link_{prefijo}", "")).strip()
        # modo == "catalogo": no se guarda "link" -> usa el default (/catalogo)
        return slide

    nuevos = []
    for i in range(len(actuales)):
        if f"borrar_{i}" in form:
            continue
        slide = await _armar(str(i))
        if slide:
            nuevos.append(slide)
    nueva = await _armar("nueva")
    if nueva:
        nuevos.append(nueva)
    contenido.guardar_carrusel_home(nuevos)
    request.session["admin_msg"] = "Carrusel actualizado."
    return RedirectResponse("/admin/carrusel", status_code=303)


# --------------------------------------------------------------------------- pixel

@router.get("/pixel", response_class=HTMLResponse)
def admin_pixel(request: Request):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    return _render(request, "admin_pixel.html", pixel_id=contenido.meta_pixel_id())


@router.post("/pixel")
def admin_pixel_guardar(request: Request, pixel_id: str = Form("")):
    if not _logueado(request):
        return RedirectResponse("/admin/login", status_code=303)
    contenido.guardar_meta_pixel_id(pixel_id)
    request.session["admin_msg"] = "Pixel actualizado."
    return RedirectResponse("/admin/pixel", status_code=303)
