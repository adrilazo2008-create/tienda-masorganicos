"""Tienda MasOrgánicos — aplicación web (FastAPI + Jinja2 + HTMX).

Arranque local:   uvicorn app.main:app --reload
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import carrito as carrito_mod
from . import catalogo, clientes, contenido, descuentos, pedidos, zonas
from .config import get_settings
from .formato import cantidad as fmt_cantidad
from .formato import pesos

BASE_DIR = Path(__file__).resolve().parent
S = get_settings()

# Versión de los assets: cambia cuando cambian css/js -> rompe el caché del navegador.
def _asset_ver() -> str:
    try:
        mt = max((BASE_DIR / "static" / p).stat().st_mtime
                 for p in ("css/estilo.css", "js/tienda.js",
                           "js/verificador-zona.js", "data/zonas_reparto.geojson"))
        return str(int(mt))
    except OSError:
        return "1"

ASSET_VER = _asset_ver()

app = FastAPI(title="Tienda MasOrgánicos")
app.add_middleware(SessionMiddleware, secret_key=S.secret_key, max_age=60 * 60 * 24 * 30)


@app.middleware("http")
async def _cache_headers(request: Request, call_next):
    resp = await call_next(request)
    p = request.url.path
    if p.startswith("/static/") or p.startswith("/img/"):
        # las URLs de estáticos llevan ?v=... -> se pueden cachear fuerte
        resp.headers["Cache-Control"] = "public, max-age=604800"
    else:
        # el HTML es dinámico y por-sesión: que ningún proxy lo cachee
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Fotos: en local desde _migracion/fotos ; en prod IMG_BASE_URL es una URL absoluta.
_fotos_local = BASE_DIR.parent / "_migracion" / "fotos"
if S.img_base_url.startswith("/") and _fotos_local.exists():
    app.mount("/img", StaticFiles(directory=_fotos_local), name="img")

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["pesos"] = pesos
templates.env.globals["fmt_cantidad"] = fmt_cantidad
templates.env.globals["IMG_BASE"] = S.img_base_url
templates.env.globals["V"] = ASSET_VER
templates.env.globals["img_producto"] = (
    lambda codigo: f"{S.img_base_url}/producto/{codigo}.jpg" if codigo
    else "/static/img/sinfoto.svg"
)
templates.env.globals["img_etiqueta"] = (
    lambda archivo: f"{S.img_base_url}/etiquetas/{archivo}"
)
templates.env.globals["WHATSAPP"] = "5491155046740"


def _cliente_actual(request: Request):
    cid = request.session.get("cliente_id")
    return clientes.obtener(cid) if cid else None


def ctx(request: Request, **extra):
    car = carrito_mod.resolver(request.session)
    base = dict(
        rubros=catalogo.rubros(),
        carrito_n=car.cantidad_items,
        cliente=_cliente_actual(request),
        entorno=S.entorno,
    )
    base.update(extra)
    return base


def render(request: Request, plantilla: str, **extra):
    return templates.TemplateResponse(request, plantilla, ctx(request, **extra))


# --------------------------------------------------------------------------- páginas

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render(request, "home.html",
                  destacados=catalogo.listar(solo_destacados=True, limite=12),
                  carrousel=contenido.carrousel(),
                  avisos=contenido.avisos())


@app.get("/catalogo", response_class=HTMLResponse)
def ver_catalogo(request: Request, categoria: Optional[int] = None,
                 rubro: Optional[int] = None, q: Optional[str] = None):
    productos = catalogo.listar(categoria_id=categoria, rubro_id=rubro, busqueda=q)
    rubros = catalogo.rubros()
    rubro_actual = next((r for r in rubros if r["id"] == rubro), None)
    cat_actual = None
    if categoria:
        for r in rubros:
            cat_actual = next((c for c in r["categorias"] if c["id"] == categoria), None)
            if cat_actual:
                rubro_actual = r
                break
    if cat_actual:
        titulo = cat_actual["nombre"]
    elif rubro_actual:
        titulo = rubro_actual["nombre"]
    elif q:
        titulo = f'“{q}”'
    else:
        titulo = "Todos los productos"
    return render(request, "catalogo.html", productos=productos, rubros=rubros,
                  rubro_actual=rubro_actual, categoria_actual=cat_actual,
                  busqueda=q or "", titulo=titulo)


@app.get("/producto/{producto_id}", response_class=HTMLResponse)
def ver_producto(request: Request, producto_id: int):
    p = catalogo.obtener(producto_id)
    if not p:
        return RedirectResponse("/catalogo", status_code=303)
    relacionados = [x for x in catalogo.listar(categoria_id=p.categoria_id, limite=8)
                    if x.id != p.id][:6]
    return render(request, "producto.html", p=p, relacionados=relacionados)


@app.get("/faq", response_class=HTMLResponse)
def ver_faq(request: Request):
    return render(request, "faq.html", faq=contenido.faq())


@app.get("/envios", response_class=HTMLResponse)
def ver_envios(request: Request):
    return render(request, "envios.html", zonas=zonas.zonas(), sucursales=zonas.sucursales())


# --------------------------------------------------------------------------- carrito

@app.post("/carrito/agregar")
def carrito_agregar(request: Request, producto_id: int = Form(...),
                    cantidad: str = Form("1"), observacion: str = Form("")):
    carrito_mod.agregar(request.session, producto_id, cantidad, observacion)
    if request.headers.get("HX-Request"):
        n = carrito_mod.resolver(request.session).cantidad_items
        return HTMLResponse(
            f'<span id="carrito-badge" class="badge" aria-live="polite" '
            f'aria-label="{n} productos en el carrito" hx-swap-oob="true">{n}</span>'
            f'<p class="toast-ok" role="status">Agregado al carrito</p>')
    return RedirectResponse("/catalogo", status_code=303)


@app.get("/carrito", response_class=HTMLResponse)
def ver_carrito(request: Request):
    return render(request, "carrito.html", car=carrito_mod.resolver(request.session))


@app.post("/carrito/actualizar")
def carrito_actualizar(request: Request, indice: int = Form(...), cantidad: str = Form(...)):
    carrito_mod.actualizar(request.session, indice, cantidad)
    return RedirectResponse("/carrito", status_code=303)


@app.post("/carrito/quitar")
def carrito_quitar(request: Request, indice: int = Form(...)):
    carrito_mod.quitar(request.session, indice)
    return RedirectResponse("/carrito", status_code=303)


# --------------------------------------------------------------------------- checkout

@app.get("/checkout", response_class=HTMLResponse)
def checkout(request: Request):
    car = carrito_mod.resolver(request.session)
    if car.vacio:
        return RedirectResponse("/catalogo", status_code=303)
    return render(request, "checkout.html", car=car, zonas=zonas.zonas(),
                  sucursales=zonas.sucursales(), permitir_escribir=S.permitir_escribir_pedidos)


@app.post("/checkout/identificar", response_class=HTMLResponse)
def checkout_identificar(request: Request, telefono: str = Form(...)):
    c = clientes.buscar_por_telefono(telefono)
    dir_ppal = None
    if c:
        request.session["checkout_cliente_id"] = c.id
        dirs = clientes.direcciones(c.id)
        dir_ppal = dirs[0] if dirs else None
    return render(request, "_checkout_identidad.html",
                  existe=c is not None, cliente_encontrado=c, telefono=telefono,
                  direccion_ppal=dir_ppal)


@app.post("/checkout/confirmar", response_class=HTMLResponse)
def checkout_confirmar(
    request: Request,
    nombre: str = Form(""), apellido: str = Form(""),
    telefono: str = Form(...), email: str = Form(""),
    entrega: str = Form("envio"),
    id_zona: int = Form(0), id_sucursal: int = Form(0),
    direccion: str = Form(""), altura: str = Form(""), localidad: str = Form(""),
    info_adicional: str = Form(""),
    pago: str = Form("efectivo"),
    codigo_descuento: str = Form(""), observacion: str = Form(""),
):
    car = carrito_mod.resolver(request.session)
    if car.vacio:
        return RedirectResponse("/catalogo", status_code=303)

    graba = S.permitir_escribir_pedidos

    # validar zona antes de escribir nada
    z = None
    if entrega != "retira":
        z = zonas.zona(id_zona)
        if not z:
            return render(request, "checkout.html", car=car, zonas=zonas.zonas(),
                          sucursales=zonas.sucursales(), error="Elegí una zona de envío.",
                          permitir_escribir=graba)

    # cliente
    cli = clientes.buscar_por_telefono(telefono) or (
        clientes.buscar_por_email(email) if email else None)
    if graba:
        if cli:
            clientes.actualizar(cli.id, nombre=nombre or None, apellido=apellido or None,
                                email=email or None)
            cli = clientes.obtener(cli.id)
        else:
            cli = clientes.crear(nombre, apellido, telefono, email)
    elif not cli:
        # modo prueba y cliente nuevo: cliente ficticio, no se escribe
        cli = clientes.Cliente(id=0, nombre=nombre or "Cliente", apellido=apellido or "",
                               telefono=clientes.normalizar_telefono(telefono),
                               email=email, tiene_pin=False)

    id_dir, id_zona_envio, precio_envio = 0, 0, Decimal("0.00")
    if entrega == "retira":
        id_sucursal = id_sucursal or 1
    else:
        id_sucursal = 0
        id_zona_envio = z.id
        precio_envio = zonas.costo_envio(z, car.subtotal)
        if graba:
            id_dir = clientes.guardar_direccion(cli.id, direccion, int(altura or 0),
                                                localidad, z.id, info_adicional)

    d = descuentos.validar(codigo_descuento)
    cod = d.codigo if d else ""

    p = pedidos.PedidoNuevo(
        cliente_id=cli.id,
        items=[pedidos.LineaPedido(
            producto_id=l.producto.id, cantidad=l.cantidad,
            precio_unitario=l.producto.precio, unidad_id=l.producto.unidad_id,
            observacion=l.observacion) for l in car.lineas],
        efectivo=(pago == "efectivo"),
        id_sucursal=id_sucursal, id_direccion_envio=id_dir, id_zona_envio=id_zona_envio,
        precio_envio=precio_envio, codigo_descuento=cod, observacion=observacion,
    )

    numero = None
    if graba:
        numero = pedidos.crear(p)
        carrito_mod.vaciar(request.session)
        request.session["cliente_id"] = cli.id
    return render(request, "checkout_ok.html", numero=numero, pedido=p, cliente=cli,
                  simulado=not S.permitir_escribir_pedidos)


# --------------------------------------------------------------------------- mi cuenta

@app.get("/cuenta", response_class=HTMLResponse)
def cuenta(request: Request):
    c = _cliente_actual(request)
    if not c:
        return render(request, "cuenta_login.html")
    return render(request, "cuenta.html", pedidos_cli=pedidos.historial(c.id),
                  direcciones=clientes.direcciones(c.id))


@app.post("/cuenta/entrar", response_class=HTMLResponse)
def cuenta_entrar(request: Request, telefono: str = Form(...)):
    c = clientes.buscar_por_telefono(telefono)
    if c:
        request.session["cliente_id"] = c.id
        return RedirectResponse("/cuenta", status_code=303)
    return render(request, "cuenta_login.html",
                  error="No encontramos pedidos con ese celular. Revisá el número o hacé tu primer pedido.")


@app.get("/cuenta/salir")
def cuenta_salir(request: Request):
    request.session.pop("cliente_id", None)
    return RedirectResponse("/", status_code=303)


# --------------------------------------------------------------------------- otros

@app.post("/newsletter")
def newsletter(request: Request, email: str = Form(...)):
    ok = contenido.suscribir_newsletter(email)
    if request.headers.get("HX-Request"):
        return HTMLResponse('<p class="ok-box">¡Listo! Te vas a enterar de las novedades.</p>'
                            if ok else '<p class="err">Revisá el email.</p>')
    return RedirectResponse("/", status_code=303)


@app.get("/salud")
def salud():
    return {"ok": True, "entorno": S.entorno, "escribe_pedidos": S.permitir_escribir_pedidos}
