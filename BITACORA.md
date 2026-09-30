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

## 2026-09-28/29 — Landing institucional en masorganicos.com.ar

Planificación larga en la carpeta `C:\MO-IA\Landing` (copy consolidado en
`Landing/COPY-LANDING.md`), después implementación acá. Objetivo de
Adriana: una landing "previa" para tráfico frío (Meta Ads), distinta del
home de catálogo de la tienda, con cada sección empujando a comprar.

**Arquitectura de dominios (aclarado por Adriana):**
- `www.masorganicos.com.ar` → hoy tiene la tienda vieja (ASP.NET,
  `PublicWeb/login`). La landing nueva la reemplaza.
- `www.tienda.masorganicos.com.ar` → esta app (FastAPI), ya en producción,
  es la que recibe todos los CTA de la landing.
- Mismo cPanel/hosting para ambos dominios — se resuelve con un **segundo
  despliegue Git** de este mismo repo a un document root distinto, no un
  proyecto aparte. El código reusa `sitio.py`/plantillas institucionales,
  que hasta ahora existían solo en el working tree, nunca comprometidas a
  git (confirmado al ver `git status`: `sitio.py`, `sitio_base.html`,
  `sitio_nosotros.html`, `blog_*.html`, `_pie.html`, `_pixel_head.html`
  aparecen como `??`, no como `M`).
- Diferenciación de contenido entre los dos despliegues: setting nuevo
  `LANDING_HOME` (`app/config.py`) — si es `true`, la ruta `/` sirve
  `landing.html` en vez de `home.html` (el catálogo). El deploy de
  `masorganicos.com.ar` necesita `LANDING_HOME=true` en su `.env`; el de
  `tienda.masorganicos.com.ar` lo deja en `false`/sin setear.

**9 bloques** (copy completo en `Landing/COPY-LANDING.md`): Hero (eje
frutas/verduras, granja/tambo como plus) → Problemas que resolvemos →
Cara humana (historia real de Adriana y su hermana Clau — diagnóstico de
salud, nodo UTT, heladeras en casa, primer local) → Cómo funciona (online
+ local de Pacheco, único local vigente — Benavidez cierra fin de
sep-2026) → Testimonios → Zona de cobertura → FAQ → Productores → Cierre.

**Decisiones de implementación:**
- Voz de copy regida por `prospección y ventas/MANUAL DE IDENTIDAD
  VERBAL.docx` (mentora cercana, nunca urgencia falsa, nunca "somos los
  mejores") — headline final elegida con Adriana tras descartar 2 rondas
  de opciones más genéricas del rubro.
- Bloque 5 (testimonios) queda **vacío a propósito**
  (`app/data/testimonios.json = []`, función `contenido.testimonios()`) —
  nunca completar con texto inventado; el bloque se oculta solo mientras
  esté vacío (`{% if testimonios %}`).
- Bloque 6 reusa el verificador de zona ya existente (`/envios`,
  `verificador-zona.js`, Leaflet) en vez de reinventar un widget nuevo;
  se agregó un `<details>` con el detalle de zonas/días como respaldo por
  si el geocoder no encuentra la dirección escrita.
- Fotos: banco nuevo en `Marketing/MO - Creativos (10-sep-2026)/otras
  fotos/` (más fresco que el que ya usa el carrusel de la tienda) — 4
  elegidas y copiadas a `_migracion/fotos/landing/` (mismo patrón que
  `/productores`, `/producto`). Detectado: el cartel físico del local dice
  "+Orgánicos" (isologo sin la palabra completa), convive a propósito con
  "Más Orgánicos" en todo lo escrito — no es un error a corregir.
- Pendientes antes de producción: reseñas reales (Bloque 5), foto del
  interior del local, foto de huevos, y que Adriana arme el segundo
  deploy Git en cPanel con su `.env` propio (`LANDING_HOME=true`,
  `URL_WEB`/`URL_TIENDA` apuntando a cada dominio).

---

## 2026-09-30 — Landing: preview local, ajustes de imagen/texto y primer commit

Sesión de revisión de la landing corriendo en local (`LANDING_HOME=true`,
`uvicorn --app-dir` sobre este repo desde `C:\MO-IA\Landing`, ver
`Landing/.claude/launch.json`). Adriana miró el resultado y pidió ajustes
puntuales; quedan aplicados y confirmados en el preview:

- **Hero (Bloque 1) rediseñado a dos columnas** — antes era solo texto
  sobre fondo degradado. Ahora tiene la foto de verduras a contraluz
  (`verduras-luz.jpg`, con tomates en primer plano) al lado del título,
  para que lo primero que se vea sea más atractivo. Esa foto estaba antes
  en el Bloque 3 ("Detrás de cada pedido"); ahí se puso en su lugar
  `hero-canasta.jpg` (una canasta de cosecha que ya estaba guardada sin
  usar). Layout nuevo: clases `.hero-landing`/`.hero-landing-texto`/
  `.hero-landing-img` en `landing.css`, se apila en mobile (`≤640px`).
- **Foto del local (Bloque 3) reemplazada dos veces:**
  1. La original mostraba una botella de yogurt de un proveedor (**La
     Recría**, marca visible) — se sacó porque no tiene sentido mostrar
     marca de un proveedor puntual (pueden cambiar, ver ya documentado
     más abajo en el FAQ del bloque 7).
  2. Reemplazo final: foto que mandó Adriana de la entrada del local
     (cartel "Alimentos Reales" + neón "+Orgánicos", con las flores de
     afuera) — es la que queda.
  - Se agregó también, dentro de la misma tarjeta, un link directo de
    WhatsApp con ícono al **11 2395-8723** (el celu del local), además
    del botón "Escribinos por WhatsApp" que ya estaba más abajo en el
    bloque — clase nueva `.local-whatsapp` en `landing.css`.
- **Texto del origen (Bloque 3, historia)** — a pedido de Adriana, se
  sacó la mención a "mi hermana Clau" de la primera frase ("Empezamos
  con mi hermana Clau, buscando comer mejor..." → "Empezamos, buscando
  comer mejor..."); el resto del párrafo (mención al equipo, "Clau como
  pionera") sigue más abajo sin tocar.
- **Botón "Ir a la tienda" del pie** — antes era un link de texto plano
  en el footer; ahora es un botón verde (misma clase `.btn-grande`) para
  que tenga la misma jerarquía visual que el resto de los CTA.
- **Bug de CSS encontrado y corregido:** el botón "Ir a la tienda" del
  encabezado (`.btn-tienda.btn-grande`) se veía con letra casi negra en
  vez de blanca — la regla `.cab-acc a` (clase+elemento, más específica)
  le ganaba a `.btn-grande` (una sola clase) sin importar el orden en el
  archivo. Se agregó `.cab-acc a.btn-tienda{color:#fff}` en `estilo.css`
  para forzarlo. Este bug es anterior a esta sesión (ya estaba en el nav
  institucional existente), recién se notó ahora al mirar la landing con
  atención.
- **Bug de caché encontrado y corregido:** `_asset_ver()` en `main.py`
  (el `?v=...` que se le pega a CSS/JS para romper caché del navegador)
  sólo miraba `estilo.css`/`tienda.js`/`verificador-zona.js` — no
  `landing.css`, así que un cambio de estilo en la landing no rompía el
  caché y quedaba invisible hasta reiniciar el server. Se agregó
  `landing.css` a esa lista. Además, las `<img>` de la landing no tenían
  ningún parámetro de versión — un cambio de foto (mismo nombre de
  archivo) quedaba cacheado indefinidamente en el navegador aunque el
  archivo en el server ya fuera otro. Se les agregó `?v={{ V }}` a las 4
  imágenes de `landing.html` para que sigan el mismo mecanismo.
- **Primer commit de la landing** — hasta ahora todo esto (`sitio.py`,
  `landing.html` y el resto de las plantillas institucionales) vivía sin
  commitear, según la vieja convención de "sitio institucional pausado,
  sacarlo antes de cada commit". Esa convención queda **obsoleta a partir
  de este commit**: la landing es justamente lo que se va a desplegar en
  `masorganicos.com.ar`, así que `sitio.py`, los globals
  `URL_WEB`/`URL_TIENDA` y las rutas `/nosotros` `/blog` `/blog/{slug}`
  quedan en el repo de forma permanente, no hay que volver a sacarlos.
- **Pendiente para Adriana antes de que esto se vea en producción:**
  1. Las 4 fotos de la landing (`_migracion/fotos/landing/*.jpg`) están
     gitignoradas (igual que el resto de `_migracion/`) — no viajan con
     el commit. Hay que subirlas a mano al mismo host de imágenes que ya
     usan `/productores` y `/producto` (`IMG_BASE_URL` de producción),
     dentro de una carpeta `landing/`.
  2. Armar el segundo deploy Git en cPanel apuntando al document root de
     `masorganicos.com.ar`, con su propio `.env`: `LANDING_HOME=true`,
     `URL_WEB=https://masorganicos.com.ar`,
     `URL_TIENDA=https://tienda.masorganicos.com.ar` (más todo lo demás
     que ya tiene el `.env` del deploy de la tienda — DB, WhatsApp, etc.).
  3. Reseñas reales (Bloque 5) y foto del interior/huevos siguen
     pendientes, sin fecha (no bloquean el deploy).

---

## 2026-09-29 — Hotfix: 500 en checkout al no elegir zona (regresión de Meta CAPI)

Una clienta escribió por WhatsApp con el carrito completo y un "código para
contarnos" (`1790689747` — resultó ser el timestamp que genera el handler
de error 500, `app/main.py`). Se bajó `app/logs/errores.log` por cPanel
File Manager y se encontró el traceback exacto a esa hora.

**Causa:** el commit de Meta Conversions API (2026-09-27/28) agregó
`{eventID: token|tojson}` al `fbq('track','InitiateCheckout', ...)` en
`checkout.html`. La rama de `checkout_confirmar()` que muestra "Elegí una
zona de envío" (cuando se confirma sin haber seleccionado zona) reusa ese
mismo template pero **no pasaba `token`** al re-renderizar — Jinja2 no
puede serializar un `Undefined` a JSON, tira `TypeError`, y eso se
capturaba como 500 genérico. Cualquiera que llegara a esa validación
(no eligió zona) se quedaba sin poder cerrar el pedido, sin selección de
producto de por medio — no es un caso raro.

**Fix:** pasar `token` en esa rama (igual que las otras dos), y además
blindar el template con `(token or '')|tojson` para que un problema de
tracking/analítica nunca vuelva a poder tirar abajo el checkout. Verificado
en producción con un POST simulando el caso exacto: `200` con el mensaje de
error en vez de `500`.

**Aprendizaje para la próxima vez que se toque `checkout.html`:** cualquier
variable nueva que se agregue a ese template (sobre todo dentro de un
`|tojson`) tiene que revisarse contra **las tres** ramas que renderizan
ese mismo template en `checkout_confirmar()`, no solo la ruta feliz.

---

## 2026-09-29 — Observación editable en cada línea del carrito

Adriana notó el caso más claro donde molestaba: al "Repetir pedido" desde
"Mi cuenta", las notas del pedido anterior se copian al carrito nuevo (a
propósito, para no perder ese dato) pero quedaban fijas — se mostraban como
texto de solo lectura (`<span class="cl-obs">`), sin forma de corregirlas o
borrarlas sin sacar la línea entera y volver a buscar el producto de cero.

**Fix:** cada línea del carrito tiene ahora su propio `<input>` de
observación (`_carrito_cuerpo.html`), en un `<form>` aparte del de
cantidad pero contra el mismo endpoint (`/carrito/actualizar`) — así
cambiar una no pisa a la otra. `carrito.actualizar()` distingue
`observacion=None` (no tocar, es el caso de las flechas +/- de cantidad)
de un string explícito (cambiarla, incluso a `""` para borrarla).
Verificado en producción: el valor persiste después de recargar la página
desde cero.

---

## Convención adoptada (2026-09-28): esta bitácora

Adriana armó la skill `bitacora-proyecto-code` desde Cowork (vive del lado
de claude.ai, no la reconoce el `Skill` tool de Claude Code en este
entorno) para que **todos** sus proyectos con Claude Code mantengan un
`BITACORA.md` así: cronología de decisiones/parámetros/ajustes
conversados, no diffs de código. Replicar este mismo criterio (archivo
`BITACORA.md` en la raíz) en `conectar`, `dashboard`, `finanzas` y `stock`
a medida que se trabaje en cada uno.
