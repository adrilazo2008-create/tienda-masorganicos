# Tienda MasOrgánicos (reconstrucción)

Tienda online nueva de masorganicos, en Python. Reemplaza el ASP.NET de `masorganicos.online`.
Contexto completo: [`BRIEFING_TIENDA_NUEVA.md`](BRIEFING_TIENDA_NUEVA.md) y
[`HALLAZGOS_SESION_2.md`](HALLAZGOS_SESION_2.md).

## Stack
FastAPI · SQLAlchemy Core · Jinja2 · HTMX. Sin build, sin JS pesado.

## Cómo correr en local

```bash
python -m pip install -r requirements.txt
copy .env.example .env      # y completar las contraseñas reales
python -m uvicorn app.main:app --reload --port 8010
```

Abrir http://localhost:8010

- Las **fotos** en local se sirven desde `_migracion/fotos/` (montadas en `/img`).
- Con `PERMITIR_ESCRIBIR_PEDIDOS=0` (default) el checkout **simula**: no escribe nada
  en la base. Poner `=1` para grabar pedidos de verdad.

## Estructura

| Archivo | Qué hace |
|---|---|
| `app/main.py` | Rutas web (páginas, carrito, checkout, cuenta). |
| `app/catalogo.py` | Lee productos del ERP `iebbbhrt_masorganicos` (`mprimas`). |
| `app/pedidos.py` | **Contrato con el VB6**: escribe `grupos` + `transacciones`. |
| `app/clientes.py` | Alta/búsqueda de `users` + direcciones. PIN de 4 dígitos (bcrypt). |
| `app/zonas.py` | Zonas de envío y sucursales. |
| `app/descuentos.py` | Validación de códigos de descuento. |
| `app/carrito.py` | Carrito en sesión (cookie), sin login. |
| `app/contenido.py` | Carrousel, avisos, FAQ, newsletter. |
| `app/db.py` | Dos engines: `engine_tienda` y `engine_erp`. |
| `tests/` | Verifican que el pedido cumple el contrato del VB6 (insert + rollback). |

## Las dos bases

- `iebbbhrt_prueba_paginaweb` — **la tienda** (pedidos, usuarios, zonas, contenido). VIVA.
- `iebbbhrt_masorganicos` — el **ERP** (catálogo: `mprimas`, `categorias`, `Stock`).

## Contrato con el sistema de escritorio (VB6)

Al confirmar un pedido se inserta **1 fila en `grupos`** (`status=0`) + **N en `transacciones`**
(`producto_id` = `mprimas.id`), previo alta/actualización de `users` y, si es envío, `direccion`.
El botón `cmdPedidosWebMO` del VB6 lo levanta igual que hoy. Ver `app/pedidos.py`.

## Despliegue

En producción: **https://tienda.masorganicos.com.ar** (cPanel Passenger, Nuthost, Python 3.11).

Flujo de actualización:
1. `git push origin main` (sube a GitHub).
2. En cPanel → **Git Version Control** → repo `tienda` → **Administrar** → **Pull or Deploy**
   → **Update from Remote** → **Deploy HEAD Commit**.
3. El `.cpanel.yml` copia `app/` + `passenger_wsgi.py` + `requirements.txt` a la carpeta de la app
   y reinicia Passenger (via `tmp/restart.txt`).

El `.env` del server NO está en git y no se toca en cada deploy.
Ver `DESPLIEGUE.md` para el detalle completo.

## Tests

```bash
python -m pytest -q
```
