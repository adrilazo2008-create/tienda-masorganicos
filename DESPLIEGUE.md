# Despliegue — HECHO ✅

La tienda está online en **https://tienda.masorganicos.com.ar**

- `masorganicos.online` (Ferozo) NO se tocó — sigue siendo la de producción.
- La nueva corre en Nuthost, cPanel "Setup Python App", Python 3.11.16.
- **Modo seguro**: `PERMITIR_ESCRIBIR_PEDIDOS=0` → el checkout funciona pero **no graba pedidos**.

## Config del server (para referencia)

| | |
|---|---|
| Subdominio | `tienda.masorganicos.com.ar` (docroot propio `/home3/iebbbhrt/tienda.masorganicos.com.ar`) |
| App root | `public_html/claude2026/tienda` |
| Python App URL | `tienda.masorganicos.com.ar` (sin subpath) |
| Startup file | `passenger_wsgi.py` · Entry point | `application` |
| Virtualenv | `/home3/iebbbhrt/virtualenv/public_html/claude2026/tienda/3.11/` |
| `.env` del server | `public_html/claude2026/tienda/.env` (IMG_BASE_URL apunta a las fotos ya subidas) |
| FTP | host `167.250.5.60`, user `claude2026@masorganicos.com.ar` |
| cPanel | user `iebbbhrt` |

## Cómo actualizar la tienda (redeploy)

**Por Git (lo normal):**
1. `git push origin main` (sube a GitHub — repo público `adrilazo2008-create/tienda-masorganicos`).
2. cPanel → **Git Version Control** → repo `tienda` → **Administrar** → pestaña **Pull or Deploy**
   → **Update from Remote** → **Deploy HEAD Commit**.
3. El `.cpanel.yml` copia `app/` + `passenger_wsgi.py` + `requirements.txt` a
   `public_html/claude2026/tienda/` y reinicia Passenger solo (via `tmp/restart.txt`).

**Si cambió `requirements.txt`** (dependencias nuevas): además de lo de arriba, ir a
**Setup Python App** → la app → escribir `requirements.txt` en el campo → **Run Pip Install** → **Restart**.

**Repo del server**: `/home3/iebbbhrt/repositories/tienda` (rama `main`).
El `.env` NO está en git y no se toca en el deploy.

⚠️ **`passenger_wsgi.py`**: si alguna vez se **recrea** la app desde cero, cPanel lo pisa con un stub
propio (que rompe con recursión infinita). Hay que volver a subir el `passenger_wsgi.py` de este repo.

⚠️ **Caché NGINX**: la cuenta tiene "NGINX Caching" activo. La app ya manda `Cache-Control: no-store`
para que no la cachee, pero si ves contenido viejo: cPanel → inicio → **NGINX Caching → Clear Cache**.

## Para que empiece a grabar pedidos de verdad

Editar `public_html/claude2026/tienda/.env` (por FTP o File Manager):
cambiar `PERMITIR_ESCRIBIR_PEDIDOS=0` → `PERMITIR_ESCRIBIR_PEDIDOS=1`, y **REINICIAR** la app.
Desde ese momento cada pedido confirmado se inserta en `grupos` + `transacciones` y lo levanta el VB6.

## Cambiar los valores de envío

Todos viven en **una sola tabla: `zonas`** (base `iebbbhrt_prueba_paginaweb`), columnas:

| Columna | Qué es |
|---|---|
| `precio` | costo de envío normal |
| `descuento` | % de descuento el día que se reparte esa zona |
| `mim_compra` | compra mínima para despachar |
| `envio_gratis` | subtotal a partir del cual el envío es gratis |
| `titulo` / `activo` | nombre y si está vigente |

Editar por **cPanel → phpMyAdmin → tabla `zonas`**, o pedirle a Claude
("cambiá el envío de Pacheco a $X"). El cambio se refleja solo en: la tabla de
`/envios`, el cálculo del checkout, y el verificador de zona ("¿llegamos a tu zona?").

El **mapa de Google (My Maps)** ahora solo define las **formas** de las zonas.
Si se redibuja una zona ahí, hay que re-exportar los polígonos a
`app/data/zonas_poligonos.json` (script en `_handoff/` o pedirle a Claude).

**Barrios / countries** (Nordelta, barrios privados): `app/data/barrios.json`.
Cada fila = `{match: "texto en minúscula", id_zona: N, etiqueta: "lo que va en Localidad"}`.
El checkout, si la dirección tipeada contiene ese `match`, asigna esa zona sin geocodificar.
Para sumar barrios: editar ese archivo o pedirle a Claude ("agregá el barrio X a Nordelta").

## Barra de anuncio superior

Franja verde arriba de todo, en todas las páginas, descartable (se recuerda por
navegador). El texto sale de la tabla **`genericos`**, fila con
`titulo = 'BARRA_ANUNCIO'`:

- `texto`   → el aviso (se le quitan las etiquetas HTML automáticamente).
- `linkMapa` → link opcional. Formato `url | texto del link` (ej: `/envios | Ver zonas`).
- `activo`  → `1` la muestra, `0` la apaga.

Si esa fila no existe o está inactiva, cae al fallback en `app/data/home.json`
(clave `anuncio`). Editar el texto en phpMyAdmin no necesita deploy.

> Ojo: `masorganicos.online` (tienda vieja) también lee `genericos`. La fila
> `BARRA_ANUNCIO` está excluida de los avisos de la home nueva; verificar que la
> tienda vieja no la muestre como aviso suelto.

## Pendientes menores

- Borrar 2 filas de prueba en la base (usuario `ClaudeTest`): ver HALLAZGOS_SESION_2.md §8.5.
- Limpiar los textos viejos de la tabla `genericos` (avisos de la home con HTML antiguo).
- 51 productos sin foto (de 428) — completar imágenes.
