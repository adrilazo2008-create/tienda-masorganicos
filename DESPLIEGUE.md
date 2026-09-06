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

1. Subir por FTP los archivos cambiados a `/claude2026/tienda/` (normalmente algo de `app/`).
2. cPanel → **Setup Python App** → la app `tienda.masorganicos.com.ar` → **REINICIAR**.
3. Si cambiaste `requirements.txt`: en esa pantalla, **Run Pip Install** (con `requirements.txt`) y después **Restart**.

⚠️ **`passenger_wsgi.py`**: si alguna vez se **recrea** la app desde cero, cPanel lo pisa con un stub
propio (que rompe con recursión infinita). Hay que volver a subir el `passenger_wsgi.py` de este repo.

⚠️ **Caché NGINX**: la cuenta tiene "NGINX Caching" activo. La app ya manda `Cache-Control: no-store`
para que no la cachee, pero si ves contenido viejo: cPanel → inicio → **NGINX Caching → Clear Cache**.

## Para que empiece a grabar pedidos de verdad

Editar `public_html/claude2026/tienda/.env` (por FTP o File Manager):
cambiar `PERMITIR_ESCRIBIR_PEDIDOS=0` → `PERMITIR_ESCRIBIR_PEDIDOS=1`, y **REINICIAR** la app.
Desde ese momento cada pedido confirmado se inserta en `grupos` + `transacciones` y lo levanta el VB6.

## Pendientes menores

- Borrar 2 filas de prueba en la base (usuario `ClaudeTest`): ver HALLAZGOS_SESION_2.md §8.5.
- Limpiar los textos viejos de la tabla `genericos` (avisos de la home con HTML antiguo).
- 51 productos sin foto (de 428) — completar imágenes.
