"""Tienda MasOrgánicos — aplicación web (FastAPI + Jinja2 + HTMX).

Arranque local:   uvicorn app.main:app --reload
"""
from __future__ import annotations

import logging
import secrets
import time
import traceback
import urllib.parse
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import carrito as carrito_mod
from . import catalogo, clientes, contenido, descuentos, pedidos, reservas, rutas_admin, zonas
from .config import get_settings
from .formato import cantidad as fmt_cantidad
from .formato import pesos

BASE_DIR = Path(__file__).resolve().parent
S = get_settings()

# Versión de los assets: cambia cuando cambian css/js -> rompe el caché del navegador.
def _asset_ver() -> str:
    try:
        mt = max((BASE_DIR / "static" / p).stat().st_mtime
                 for p in ("css/estilo.css", "js/tienda.js", "js/verificador-zona.js"))
        return str(int(mt))
    except OSError:
        return "1"

ASSET_VER = _asset_ver()

app = FastAPI(title="Tienda MasOrgánicos")
app.add_middleware(SessionMiddleware, secret_key=S.secret_key, max_age=60 * 60 * 24 * 30)

# --------------------------------------------------------------------------- errores
# Log de errores 500 a un archivo dentro de la app (se puede bajar por FTP/File
# Manager). Antes, un error sin manejar tiraba la página en blanco de Passenger
# ("Internal Server Error") sin dejar rastro ni avisarle nada a la persona.
_LOG_DIR = BASE_DIR / "logs"
try:
    _LOG_DIR.mkdir(exist_ok=True)
    _error_handler = logging.FileHandler(_LOG_DIR / "errores.log", encoding="utf-8")
    _error_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger_errores = logging.getLogger("tienda.errores")
    logger_errores.setLevel(logging.ERROR)
    logger_errores.addHandler(_error_handler)
except OSError:
    logger_errores = logging.getLogger("tienda.errores")  # sin archivo (ej. sin permiso): al menos no explota

_PAGINA_ERROR_500 = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Uy, algo falló — Más Orgánicos</title>
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:#f4f6f0;
  color:#232620;margin:0;padding:2rem 1rem;line-height:1.55}}
.caja{{max-width:480px;margin:2rem auto;background:#fff;border:1px solid #e3e5dd;
  border-radius:14px;padding:1.8rem 1.6rem;text-align:center}}
h1{{font-size:1.3rem;color:#1f5423;margin:0 0 .6rem}}
p{{margin:.5rem 0}}
.wa{{display:inline-block;margin-top:1rem;background:#25d366;color:#fff;text-decoration:none;
  padding:.8rem 1.4rem;border-radius:999px;font-weight:600}}
.chico{{font-size:.82rem;color:#5d6158;margin-top:1.2rem}}
</style></head><body>
<div class="caja">
  <h1>Uy, algo falló de nuestro lado 😕</h1>
  <p>Tu pedido <b>no se guardó</b> y no se cobró nada.</p>
  <p>Hacé clic para enviarlo por WhatsApp y lo cerramos así, sin vueltas.</p>
  <a class="wa" href="{wa_url}" rel="noopener">Enviar</a>
  <p class="chico">Código para contarnos: {codigo}</p>
</div>
</body></html>"""


def _mensaje_whatsapp_error(request: Request, codigo: str) -> str:
    """Arma el texto del WhatsApp con lo que la persona tenía en el carrito,
    para que un error en el momento de cerrar el pedido no se lleve la venta:
    no tiene que volver a escribir todo de cero. Si algo falla acá (justo lo
    que rompió puede ser la base), se cae a un mensaje genérico sin trabar
    la pantalla de error."""
    mensaje = "Hola! Estaba haciendo un pedido y la página me tiró un error."
    try:
        car = carrito_mod.resolver(request.session)
        if car.lineas:
            items = "\n".join(
                f"- {fmt_cantidad(l.cantidad)} {l.producto.unidad} {l.producto.nombre}"
                + (f' ("{l.observacion}")' if l.observacion else "")
                for l in car.lineas
            )
            mensaje += f"\n\nEsto es lo que tenía en el carrito:\n{items}"
    except Exception:
        pass
    mensaje += f"\n\nCódigo para contarnos: {codigo}"
    mensaje += "\n\n¿Me ayudan a cerrarlo?"
    return mensaje


@app.exception_handler(Exception)
async def _error_500(request: Request, exc: Exception) -> HTMLResponse:
    codigo = f"{int(time.time())}"
    logger_errores.error(
        "500 en %s %s (código %s)\n%s",
        request.method, request.url.path, codigo, traceback.format_exc(),
    )
    mensaje = _mensaje_whatsapp_error(request, codigo)
    wa_url = "https://wa.me/5491155046740?text=" + urllib.parse.quote(mensaje)
    # Página mínima y autónoma (sin templates ni consultas a la base): si lo que
    # rompió fue justamente la base de datos, esta pantalla igual tiene que andar.
    return HTMLResponse(_PAGINA_ERROR_500.format(codigo=codigo, wa_url=wa_url), status_code=500)


@app.middleware("http")
async def _cache_headers(request: Request, call_next):
    resp = await call_next(request)
    p = request.url.path
    es_estatico = p.startswith("/static/") or p.startswith("/img/")
    if es_estatico and resp.status_code == 200:
        # las URLs de estáticos llevan ?v=... -> se pueden cachear fuerte.
        # OJO: solo en 200; un 404 cacheado 1 semana deja una imagen rota
        # aunque después se suba el archivo.
        resp.headers["Cache-Control"] = "public, max-age=604800"
    elif not es_estatico:
        # el HTML es dinámico y por-sesión: que ningún proxy lo cachee
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
    return resp
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(rutas_admin.router)

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


def _habituales(cli, limite: int, excluir=()) -> list:
    """Productos que el cliente suele comprar, listos para <_card.html>.
    Cacheado por cliente (se refresca a los ~3 min o al reiniciar la app)."""
    if not cli:
        return []
    from .catalogo import _cacheado

    def _resolver():
        ids = pedidos.habituales(cli.id, 24)
        d = catalogo.obtener_varios(ids)
        return [d[i] for i in ids if i in d]

    base = _cacheado(f"habituales:{cli.id}", 180, _resolver)
    excluir = set(excluir)
    return [p for p in base if p.id not in excluir][:limite]


def ctx(request: Request, **extra):
    car = carrito_mod.resolver(request.session)
    base = dict(
        rubros=catalogo.rubros(),
        carrito_n=car.cantidad_items,
        cliente=_cliente_actual(request),
        entorno=S.entorno,
        anuncio=contenido.anuncio(),
        meta_pixel=contenido.meta_pixel_id(),
    )
    base.update(extra)
    return base


def render(request: Request, plantilla: str, **extra):
    return templates.TemplateResponse(request, plantilla, ctx(request, **extra))


# --------------------------------------------------------------------------- páginas

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render(request, "home.html",
                  destacados=catalogo.destacados(12),
                  habituales=_habituales(_cliente_actual(request), 8),
                  slides=contenido.carrusel_home(),
                  home_cfg=contenido.home_config(),
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


@app.get("/privacidad", response_class=HTMLResponse)
def ver_privacidad(request: Request):
    return render(request, "privacidad.html")



# --------------------------------------------------------------------------- sitio + blog

@app.get("/nosotros", response_class=HTMLResponse)
def sitio_nosotros(request: Request):
    return render(request, "sitio_nosotros.html", pagina="nosotros",
                  productores=contenido.productores(),
                  home_cfg=contenido.home_config())


@app.get("/blog", response_class=HTMLResponse)
def sitio_blog(request: Request):
    return render(request, "blog_index.html", pagina="blog", posts=sitio.posts())


@app.get("/blog/{slug}", response_class=HTMLResponse)
def sitio_blog_post(request: Request, slug: str):
    nota = sitio.post(slug)
    if not nota:
        return RedirectResponse("/blog", status_code=303)
    otras = [n for n in sitio.posts() if n["slug"] != slug][:3]
    return render(request, "blog_post.html", pagina="blog", nota=nota, otras=otras)


# --------------------------------------------------------------------------- sitio + blog

@app.get("/nosotros", response_class=HTMLResponse)
def sitio_nosotros(request: Request):
    return render(request, "sitio_nosotros.html", pagina="nosotros",
                  productores=contenido.productores(),
                  home_cfg=contenido.home_config())


@app.get("/blog", response_class=HTMLResponse)
def sitio_blog(request: Request):
    return render(request, "blog_index.html", pagina="blog", posts=sitio.posts())


@app.get("/blog/{slug}", response_class=HTMLResponse)
def sitio_blog_post(request: Request, slug: str):
    nota = sitio.post(slug)
    if not nota:
        return RedirectResponse("/blog", status_code=303)
    otras = [n for n in sitio.posts() if n["slug"] != slug][:3]
    return render(request, "blog_post.html", pagina="blog", nota=nota, otras=otras)


@app.get("/envios", response_class=HTMLResponse)
def ver_envios(request: Request):
    return render(request, "envios.html", zonas=zonas.zonas(), sucursales=zonas.sucursales())


@app.get("/envios/zonas.geojson")
def envios_geojson():
    from fastapi.responses import JSONResponse
    return JSONResponse(zonas.poligonos_geojson(),
                        headers={"Cache-Control": "public, max-age=3600"})


@app.get("/envios/barrios.json")
def envios_barrios():
    import json
    from fastapi.responses import JSONResponse
    ruta = BASE_DIR / "data" / "barrios.json"
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except OSError:
        datos = []
    return JSONResponse(datos, headers={"Cache-Control": "public, max-age=3600"})


# --------------------------------------------------------------------------- carrito

@app.post("/carrito/agregar")
def carrito_agregar(request: Request, producto_id: int = Form(...),
                    cantidad: str = Form("1"), observacion: str = Form("")):
    carrito_mod.agregar(request.session, producto_id, cantidad, observacion)
    if request.headers.get("HX-Request"):
        car = carrito_mod.resolver(request.session)
        n = car.cantidad_items
        partes = [
            f'<span id="carrito-badge" class="badge" aria-live="polite" '
            f'aria-label="{n} productos en el carrito" hx-swap-oob="true">{n}</span>',
            '<p class="toast-ok" role="status">Agregado al carrito</p>',
        ]
        # Si el elemento que disparó el agregado vive dentro de #carrito-cuerpo
        # (viene de "Sumá a tu pedido" en /carrito), ese id ya existe en la
        # página: mandamos el cuerpo del carrito actualizado por OOB en vez de
        # recargar todo. Si el id no existe (catálogo, home, ficha de
        # producto), htmx simplemente ignora este fragmento de más.
        en_carrito = {l.producto.id for l in car.lineas}
        sug = _habituales(_cliente_actual(request), 6, excluir=en_carrito)
        if len(sug) < 6:
            ya = en_carrito | {p.id for p in sug}
            sug += [p for p in catalogo.destacados(12) if p.id not in ya][:6 - len(sug)]
        extra = ctx(request, car=car, umbral_envio=zonas.umbral_envio_gratis(), sugeridos=sug[:6])
        partes.append(templates.get_template("_carrito_cuerpo_oob.html").render(extra))
        return HTMLResponse("".join(partes))
    return RedirectResponse("/catalogo", status_code=303)


@app.get("/carrito", response_class=HTMLResponse)
def ver_carrito(request: Request):
    car, _, _ = carrito_mod.resolver_y_avisar(request.session)
    en_carrito = {l.producto.id for l in car.lineas}
    # sugerencias: primero los habituales del cliente, después completamos con
    # destacados (para que siempre haya "para descubrir", logueado o no).
    sug = _habituales(_cliente_actual(request), 6, excluir=en_carrito)
    if len(sug) < 6:
        ya = en_carrito | {p.id for p in sug}
        sug += [p for p in catalogo.destacados(12) if p.id not in ya][:6 - len(sug)]
    return render(request, "carrito.html", car=car,
                  umbral_envio=zonas.umbral_envio_gratis(),
                  sugeridos=sug[:6],
                  carrito_msg=request.session.pop("carrito_msg", None))


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
    car, _, eliminados = carrito_mod.resolver_y_avisar(request.session)
    if car.vacio and not eliminados:
        return RedirectResponse("/catalogo", status_code=303)
    cli = _cliente_actual(request)
    dirs = clientes.direcciones(cli.id) if cli else []
    return render(request, "checkout.html", car=car, zonas=zonas.zonas(),
                  sucursales=zonas.sucursales(), permitir_escribir=S.permitir_escribir_pedidos,
                  cliente_checkout=cli, cliente_encontrado=cli, existe=cli is not None,
                  direccion_ppal=dirs[0] if dirs else None, direcciones_cliente=dirs,
                  aviso_stock=request.session.pop("carrito_msg", None),
                  eliminados=eliminados, token=secrets.token_urlsafe(12))


@app.post("/checkout/identificar", response_class=HTMLResponse)
def checkout_identificar(request: Request, telefono: str = Form(...)):
    c = clientes.buscar_por_telefono(telefono)
    dirs = []
    sugerido = None
    if c:
        request.session["checkout_cliente_id"] = c.id
        dirs = clientes.direcciones(c.id)
    else:
        # todavía no pidió por la web, pero puede ya ser cliente (local/ERP)
        sugerido = clientes.buscar_en_erp(telefono)
    return render(request, "_checkout_identidad.html",
                  existe=c is not None, cliente_encontrado=c, telefono=telefono,
                  direccion_ppal=dirs[0] if dirs else None, direcciones_cliente=dirs,
                  sugerido=sugerido)


@app.post("/checkout/confirmar", response_class=HTMLResponse)
def checkout_confirmar(
    request: Request,
    nombre: str = Form(""), apellido: str = Form(""),
    telefono: str = Form(...), email: str = Form(""),
    entrega: str = Form("envio"),
    id_zona: int = Form(0), id_sucursal: int = Form(0),
    modalidad_envio: str = Form("coordinar"),
    direccion: str = Form(""), altura: str = Form(""), localidad: str = Form(""),
    barrio: str = Form(""), lote: str = Form(""),
    info_adicional: str = Form(""),
    pago: str = Form("efectivo"),
    codigo_descuento: str = Form(""), observacion: str = Form(""),
    token: str = Form(""),
):
    # Mismo envío de vuelta (doble clic, "atrás" del navegador, reintento por
    # lag): no duplicar el pedido, mostrar la confirmación que ya se generó.
    ya_hecho = request.session.get("checkout_token_hecho")
    if token and ya_hecho and ya_hecho.get("token") == token:
        request.session["pedido_ok"] = ya_hecho["pedido_ok"]
        return RedirectResponse("/checkout/ok", status_code=303)

    car, hubo_cambios, eliminados = carrito_mod.resolver_y_avisar(request.session)
    if car.vacio and not eliminados:
        return RedirectResponse("/catalogo", status_code=303)
    if hubo_cambios:
        # algo se quedó sin stock justo ahora, al confirmar: no completamos el
        # pedido a ciegas con menos productos de los que la persona ve en
        # pantalla. Se vuelve a mostrar el checkout (en la MISMA respuesta,
        # sin redirect, para no perder el detalle de qué se sacó) marcando
        # ese producto tachado en el resumen y con las dos opciones claras:
        # volver al carrito a reemplazarlo, o confirmar el resto tal cual.
        request.session.pop("carrito_msg", None)  # ya se muestra tachado en el resumen
        cli = _cliente_actual(request)
        dirs = clientes.direcciones(cli.id) if cli else []
        return render(request, "checkout.html", car=car, zonas=zonas.zonas(),
                      sucursales=zonas.sucursales(), permitir_escribir=S.permitir_escribir_pedidos,
                      cliente_checkout=cli, cliente_encontrado=cli, existe=cli is not None,
                      direccion_ppal=dirs[0] if dirs else None, direcciones_cliente=dirs,
                      eliminados=eliminados, token=secrets.token_urlsafe(12))

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
    obs_envio, modalidad_envio_guardada = "", ""
    if entrega == "retira":
        id_sucursal = id_sucursal or 1
    else:
        id_sucursal = 0
        id_zona_envio = z.id
        elige_dia = modalidad_envio == "dia"
        modalidad_envio_guardada = "dia" if elige_dia else "coordinar"
        precio_envio = zonas.costo_envio(z, car.subtotal, modalidad_envio_guardada)
        obs_envio = ("Envío el día de reparto de la zona" if elige_dia
                     else "Envío a coordinar día/horario")
        if graba:
            id_dir = clientes.guardar_direccion(cli.id, direccion, int(altura or 0),
                                                localidad, z.id, info_adicional,
                                                barrio=barrio, lote=lote)

    if graba:
        clientes.sincronizar_erp(cli, direccion, altura, localidad, barrio, lote, info_adicional)

    d = descuentos.validar(codigo_descuento)
    cod = d.codigo if d else ""

    # la modalidad de envío va PRIMERO; la aclaración que escribió la persona se conserva tal cual
    obs_cliente = observacion.strip()
    obs_final = obs_envio + (". " + obs_cliente if obs_cliente else "") if obs_envio else obs_cliente

    p = pedidos.PedidoNuevo(
        cliente_id=cli.id,
        items=[pedidos.LineaPedido(
            producto_id=l.producto.id, cantidad=l.cantidad,
            precio_unitario=l.producto.precio, unidad_id=l.producto.unidad_id,
            observacion=l.observacion) for l in car.lineas],
        efectivo=(pago == "efectivo"),
        id_sucursal=id_sucursal, id_direccion_envio=id_dir, id_zona_envio=id_zona_envio,
        precio_envio=precio_envio, codigo_descuento=cod, observacion=obs_final,
        modalidad_envio=modalidad_envio_guardada,
    )

    numero = None
    if graba:
        numero = pedidos.crear(p)
        for l in car.lineas:
            if l.producto.agotado:
                try:
                    reservas.crear(producto_id=l.producto.id, producto_nombre=l.producto.nombre,
                                    cliente_codigo=cli.cliente_codigo, nombre=cli.nombre_completo,
                                    telefono=cli.telefono, cantidad=l.cantidad,
                                    pedido_grupo_id=numero)
                except Exception:
                    logger_errores.exception("No se pudo crear la reserva del producto %s (pedido %s)",
                                              l.producto.id, numero)
        carrito_mod.vaciar(request.session)
        request.session["cliente_id"] = cli.id

    suc_nombre = ""
    if id_sucursal:
        suc_nombre = next((s.descripcion for s in zonas.sucursales() if s.id == id_sucursal), "")

    request.session["pedido_ok"] = {
        "numero": numero,
        "simulado": not graba,
        "cliente": cli.nombre_completo,
        "telefono": cli.telefono,
        "email": cli.email,
        "retira": bool(id_sucursal),
        "sucursal": suc_nombre,
        "envio": float(precio_envio),
        "envio_modalidad": obs_envio,
        "efectivo": pago == "efectivo",
        "descuento": cod,
        "items": [{"cant": float(l.cantidad), "nombre": l.producto.nombre,
                   "unidad": l.producto.unidad, "precio": float(l.producto.precio)}
                  for l in car.lineas],
        "subtotal": float(p.subtotal()),
        "total": float(p.total()),
    }
    if token:
        request.session["checkout_token_hecho"] = {
            "token": token, "pedido_ok": request.session["pedido_ok"],
        }
    return RedirectResponse("/checkout/ok", status_code=303)


@app.get("/checkout/ok", response_class=HTMLResponse)
def checkout_ok(request: Request):
    ok = request.session.pop("pedido_ok", None)
    if not ok:
        return RedirectResponse("/", status_code=303)
    return render(request, "checkout_ok.html", ok=ok)


# --------------------------------------------------------------------------- mi cuenta

@app.get("/cuenta", response_class=HTMLResponse)
def cuenta(request: Request):
    c = _cliente_actual(request)
    if not c:
        return render(request, "cuenta_login.html")
    return render(request, "cuenta.html", pedidos_cli=pedidos.historial(c.id, limite=5),
                  direcciones=clientes.direcciones(c.id),
                  habituales=_habituales(c, 12))


@app.get("/cuenta/pedido/{pedido_id}", response_class=HTMLResponse)
def cuenta_pedido(request: Request, pedido_id: int):
    c = _cliente_actual(request)
    if not c:
        return RedirectResponse("/cuenta", status_code=303)
    d = pedidos.detalle(pedido_id, c.id)
    if not d:
        return RedirectResponse("/cuenta", status_code=303)
    prods = catalogo.obtener_varios([l["producto_id"] for l in d["lineas"]])
    subtotal = sum((l["cantidad"] * l["precio"] for l in d["lineas"]), Decimal("0"))
    return render(request, "cuenta_pedido.html", p=d, prods=prods,
                  subtotal=subtotal, total=subtotal + d["precio_envio"])


def _render_pedido_editar(request: Request, pedido_id: int, cliente_id: int, error: str = ""):
    d = pedidos.detalle(pedido_id, cliente_id)
    if not d:
        return RedirectResponse("/cuenta", status_code=303)
    prods = catalogo.obtener_varios([l["producto_id"] for l in d["lineas"]])
    subtotal = sum((l["cantidad"] * l["precio"] for l in d["lineas"]), Decimal("0"))
    return render(request, "_pedido_editar_cuerpo.html", p=d, prods=prods,
                  subtotal=subtotal, total=subtotal + d["precio_envio"], error=error)


@app.get("/cuenta/pedido/{pedido_id}/editar", response_class=HTMLResponse)
def cuenta_pedido_editar(request: Request, pedido_id: int):
    c = _cliente_actual(request)
    if not c:
        return RedirectResponse("/cuenta", status_code=303)
    d = pedidos.detalle(pedido_id, c.id)
    if not d:
        return RedirectResponse("/cuenta", status_code=303)
    if not d["editable"]:
        return RedirectResponse(f"/cuenta/pedido/{pedido_id}", status_code=303)
    prods = catalogo.obtener_varios([l["producto_id"] for l in d["lineas"]])
    subtotal = sum((l["cantidad"] * l["precio"] for l in d["lineas"]), Decimal("0"))
    return render(request, "cuenta_pedido_editar.html", p=d, prods=prods,
                  subtotal=subtotal, total=subtotal + d["precio_envio"], error="")


@app.get("/cuenta/pedido/{pedido_id}/editar/buscar", response_class=HTMLResponse)
def cuenta_pedido_editar_buscar(request: Request, pedido_id: int, q: str = ""):
    c = _cliente_actual(request)
    if not c or not pedidos.puede_editar(pedido_id, c.id):
        return HTMLResponse("")
    resultados = catalogo.listar(busqueda=q, limite=8) if q.strip() else []
    return render(request, "_pedido_editar_buscar.html", pedido_id=pedido_id, q=q, resultados=resultados)


@app.post("/cuenta/pedido/{pedido_id}/editar/agregar", response_class=HTMLResponse)
def cuenta_pedido_editar_agregar(request: Request, pedido_id: int, producto_id: int = Form(...),
                                  cantidad: str = Form("1"), observacion: str = Form("")):
    c = _cliente_actual(request)
    if not c:
        return RedirectResponse("/cuenta", status_code=303)
    error = ""
    try:
        pedidos.agregar_item(pedido_id, c.id, producto_id, carrito_mod._norm_cant(cantidad), observacion)
    except pedidos.PedidoNoEditable:
        error = "Este pedido ya se empezó a preparar — para cambios, escribinos por WhatsApp."
    except pedidos.ProductoNoDisponible:
        error = "Ese producto ya no está disponible."
    return _render_pedido_editar(request, pedido_id, c.id, error)


@app.post("/cuenta/pedido/{pedido_id}/editar/quitar", response_class=HTMLResponse)
def cuenta_pedido_editar_quitar(request: Request, pedido_id: int, transaccion_id: int = Form(...)):
    c = _cliente_actual(request)
    if not c:
        return RedirectResponse("/cuenta", status_code=303)
    error = ""
    try:
        pedidos.quitar_item(pedido_id, c.id, transaccion_id)
    except pedidos.PedidoNoEditable:
        error = "Este pedido ya se empezó a preparar — para cambios, escribinos por WhatsApp."
    except pedidos.PedidoQuedariaVacio:
        error = "No podés sacar el último producto — si querés cancelar el pedido, escribinos por WhatsApp."
    return _render_pedido_editar(request, pedido_id, c.id, error)


@app.post("/cuenta/pedido/{pedido_id}/editar/cantidad", response_class=HTMLResponse)
def cuenta_pedido_editar_cantidad(request: Request, pedido_id: int, transaccion_id: int = Form(...),
                                   cantidad: str = Form("1")):
    c = _cliente_actual(request)
    if not c:
        return RedirectResponse("/cuenta", status_code=303)
    error = ""
    try:
        pedidos.cambiar_cantidad(pedido_id, c.id, transaccion_id, carrito_mod._norm_cant(cantidad))
    except pedidos.PedidoNoEditable:
        error = "Este pedido ya se empezó a preparar — para cambios, escribinos por WhatsApp."
    return _render_pedido_editar(request, pedido_id, c.id, error)


@app.post("/cuenta/pedido/{pedido_id}/repetir")
def cuenta_pedido_repetir(request: Request, pedido_id: int):
    c = _cliente_actual(request)
    if not c:
        return RedirectResponse("/cuenta", status_code=303)
    d = pedidos.detalle(pedido_id, c.id)
    if not d:
        return RedirectResponse("/cuenta", status_code=303)
    disponibles = catalogo.obtener_varios([l["producto_id"] for l in d["lineas"]])
    agregados = sin_stock = 0
    for l in d["lineas"]:
        if l["producto_id"] in disponibles:
            carrito_mod.agregar(request.session, l["producto_id"], l["cantidad"], l["observacion"])
            agregados += 1
        else:
            sin_stock += 1
    msg = f"Sumamos {agregados} producto{'s' if agregados != 1 else ''} de tu pedido #{pedido_id} al carrito."
    if sin_stock:
        msg += f" {sin_stock} no está{'n' if sin_stock != 1 else ''} disponible{'s' if sin_stock != 1 else ''} ahora."
    request.session["carrito_msg"] = msg
    return RedirectResponse("/carrito", status_code=303)


@app.post("/cuenta/entrar", response_class=HTMLResponse)
def cuenta_entrar(request: Request, telefono: str = Form(...)):
    c = clientes.buscar_por_telefono(telefono)
    if c:
        request.session["cliente_id"] = c.id
        return RedirectResponse("/cuenta", status_code=303)
    # todavía no pidió por la web, pero puede ya ser cliente (local/ERP): no
    # tiene pedidos para mostrar, pero al menos la reconocemos y la invitamos
    # a hacer el primero en vez de decirle "no te encontramos".
    sugerido = clientes.buscar_en_erp(telefono)
    if sugerido and sugerido["nombre"]:
        return render(request, "cuenta_login.html", telefono=telefono, mostrar_catalogo=True,
                      saludo=f"¡Hola {sugerido['nombre']}! Ya te conocemos, pero todavía no "
                             f"hiciste ningún pedido por acá.")
    return render(request, "cuenta_login.html", telefono=telefono,
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
