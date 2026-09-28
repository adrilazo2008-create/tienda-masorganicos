# Bitácora del proyecto — tienda

Cronología de decisiones, parámetros y ajustes conversados con Claude Code.
Esto **no** reemplaza al historial de git (ahí están los diffs) — acá queda
el *por qué* y el *qué se decidió*, para no tener que releer toda la
conversación la próxima vez.

---

## 2026-09-24 — Verduras/Frutas mostraban "Agotado"/"Reservar" por error

Adriana pidió revisar por qué Verduras y Frutas seguían mostrando el cartel
"Agotado" y el botón "Reservar" cuando se quedan sin stock, cuando ese aviso
debería ser exclusivo de Granja/Tambo (únicos rubros con reposición real por
proveedor que Adriana consolida a mano).

**Decisión:** `RUBROS_SIN_AVISO_STOCK = {1, 2}` (Verduras, Frutas) en
`catalogo.py` — sin ningún aviso de stock, se muestran siempre como
cualquier producto activo. Solo Granja conserva el cartel/reserva.

---

## 2026-09-24/25 — Analítica: Microsoft Clarity

Pedido: poder ver por qué los clientes nuevos de la tienda recién lanzada
tienen fricción, sin depender de que se logueen.

**Decisión:** se sumó Microsoft Clarity (heatmaps + grabaciones de sesión),
gratis, gatillado solo si la persona acepta el aviso de cookies (mismo gate
que ya usaba el Pixel de Meta). Project ID: `ynmqxyg5i5` (Adriana lo creó
en clarity.microsoft.com, cuenta con su Google adrilazo2008@gmail.com).

---

## 2026-09-25 — Baja de Donweb (masorganicos.online)

Adriana avisó que va a dar de baja el servicio de Donweb (el sitio viejo,
`masorganicos.online`) y subir fotos solo a la tienda nueva de ahora en
más. La base de datos **nunca estuvo** en Donweb (aclaración de Adriana),
solo las fotos de producto y el sitio viejo en sí.

**Verificado:** la tienda nueva no depende de Donweb para nada — las fotos
se sirven desde `masorganicos.com.ar/claude2026/assets/...` (mismo hosting
cPanel). Se encontró que **`stock/app.py` sí subía cada foto a los dos
lados** (tienda nueva + Donweb/Ferozo) — se sacó esa segunda subida para
que no tire error de FTP contra un servidor que ya no existe.

Se agregó filtro `linkify` para que las URLs sueltas en la descripción de
un producto (ej. "más info en https://...") se muestren como links
clickeables en la ficha de producto.

---

## 2026-09-26/27 — Sesión larga + "Vistos recientemente"

Adriana planteó que la tienda no guarda datos sensibles ni de pago, así que
no tiene sentido hacer re-loguear seguido a un cliente que repite compra.
También quería poder personalizar la experiencia de clientes nuevos/
anónimos sin pedirles login.

**Decisiones:**
- Sesión de **2 años** (antes 30 días) — mientras no borre cookies, el
  cliente no vuelve a ver el login.
- Se arrancó a juntar navegación anónima: cookie de sesión con
  `visitante_id` (UUID), tabla `vistas_producto` en la base de la tienda.
  Sección "Vistos recientemente" en home y ficha de producto, para
  anónimos y logueados por igual. Base para, a futuro, sumar "otros
  clientes también vieron esto".

---

## 2026-09-27 — Diagnóstico técnico de Adriana (Clarity + Meta Ads)

Adriana guardó un documento propio (`tienda/# Diagnóstico técnico —
Tienda online.txt`, no versionado) con el análisis de por qué las campañas
de Meta Ads no estaban convirtiendo: 93 add-to-cart, 2-3 pedidos
confirmados. Encontró el error JS `stepCant is not defined` (14,89% de
dead clicks) y que ~57% del tráfico entra por el browser in-app de
Instagram/Facebook.

**Causa real encontrada:** `tienda.js` se cargaba con un `<script>` sin
`defer` al final de cada página (duplicado en 7 templates), mientras que
`htmx.min.js` sí usaba `defer` desde el `<head>`. En conexiones lentas
(típico del webview de Instagram) quedaba una ventana donde el usuario ya
podía tocar los botones pero las funciones todavía no existían.

**Decisiones:**
1. `tienda.js` centralizado en `base.html` con `defer`.
2. Redirect 301 de `http://` a `https://` a nivel app (Clarity mostraba el
   mismo catálogo en los dos esquemas, rompiendo cookies de sesión/carrito
   — no hay `.htaccess` versionado en este repo, Passenger/cPanel).
3. Al tocar "Confirmar pedido" desde el webview de Instagram/Facebook en
   **Android**, se abre la misma URL del checkout en Chrome vía `intent://`
   (con fallback), sin ningún aviso visible. **En iOS no hay forma
   confiable de forzar el navegador externo desde JS** (restricción de
   Apple/WebKit) — se decidió aceptar esa limitación y no hacer nada
   especial ahí.
4. El botón "Detectar" (buscador de dirección) se sacó de adentro del
   formulario de entrega — Adriana confirmó que es la **misma pieza
   reubicada** (no dos features separadas): ahora es una opción colapsada
   ("¿Llegamos a tu zona?") visible **solo para clientes sin sesión
   guardada** — un cliente recurrente ya tiene zona/dirección
   autocompletada desde sus datos guardados.

---

## 2026-09-27/28 — Meta Conversions API (CAPI), server-side

Pedido explícito de Adriana: complementar el Pixel del navegador ("Pixel
PaginaWeb MO") con eventos server-side, porque el webview de Instagram
bloquea cookies y el Pixel solo no registra bien ahí.

**Decisiones:**
- Eventos: `InitiateCheckout` (al entrar a `/checkout`) y `Purchase` (al
  confirmar el pedido).
- Deduplicación con el mismo `event_id` que ya usa la llamada de `fbq()`
  del navegador (el `token` del formulario de checkout para
  InitiateCheckout, `f"purchase-{numero}"` del pedido para Purchase) — así
  Meta reconoce que es un solo evento, no dos.
- Módulo nuevo `app/meta_capi.py`, solo librería estándar (`urllib`), sin
  agregar dependencias nuevas al proyecto.
- Token de acceso (`META_CAPI_TOKEN`) generado por Adriana en Meta Events
  Manager (Pixel PaginaWeb MO → Configuración → Conversions API → Generar
  token de acceso, con Dataset Quality API) — cargado directo en el `.env`
  de producción por cPanel File Manager, nunca en el repo.
- Pendiente: verificar en la pestaña "Test Events" del Events Manager que
  el evento server-side aparece deduplicado contra el del navegador.

---

## Convención adoptada (2026-09-28): esta bitácora

Adriana armó la skill `bitacora-proyecto-code` desde Cowork (vive del lado
de claude.ai, no la reconoce el `Skill` tool de Claude Code en este
entorno) para que **todos** sus proyectos con Claude Code mantengan un
`BITACORA.md` así: cronología de decisiones/parámetros/ajustes
conversados, no diffs de código. Replicar este mismo criterio (archivo
`BITACORA.md` en la raíz) en `conectar`, `dashboard`, `finanzas` y `stock`
a medida que se trabaje en cada uno.
