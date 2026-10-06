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
     `URL_TIENDA_PUBLICA=https://tienda.masorganicos.com.ar` — **ojo con el
     nombre**, el campo en `config.py` es `url_tienda_publica`, no
     `url_tienda` (pydantic-settings arma el nombre de la variable de
     entorno a partir del nombre exacto del campo) — si se pone
     `URL_TIENDA` a secas queda silenciosamente vacío (`extra="ignore"`
     no tira error) y los links "Ir a la tienda" del sitio institucional
     quedan relativos en vez de apuntar al subdominio. Verificado con un
     test rápido de `pydantic_settings.BaseSettings` (más todo lo demás
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

## 2026-10-01 — Tienda "inteligente": cross-sell real + receta de la semana (en curso)

Adriana quiere que la tienda deje de ser solo catálogo y empiece a vender
más sola: cross-sell/upsell basado en lo que cada visitante mira o compra,
y algún gancho visual (ícono animado) tipo "receta de la semana" para que
abran algo más que el catálogo. Pidió explícitamente **no** pagar un SaaS
de personalización (Nosto, Dynamic Yield, Algolia Recommend, etc.) — son
caros para esta escala y mandarían datos de clientes a un tercero justo
después de independizarnos de Donweb. Se decidió construir todo adentro de
`tienda`, con SQL simple sobre la base propia, sin ML ni librerías nuevas.

**1. Cross-sell real, ya implementado y verificado en datos reales
(28.835 líneas de `transacciones`):** `pedidos.comprados_junto_a(ids)`
calcula, por cada producto del carrito, qué otros productos aparecieron
más veces en el MISMO pedido histórico (`JOIN transacciones` contra sí
misma por `grupo`, excluyendo el mismo producto) — "frecuentemente
comprados juntos", no una lista fija. Ejemplo probado: Zanahorias →
Limones, Tomate perita, Calabaza, Papa, Peras.

Se integró en `/carrito` (`main.py`, `_sugeridos_carrito()`) con esta
prioridad, sin repetir productos entre niveles ni con lo ya en el carrito:
1. `_habituales()` — lo que ESE cliente ya compró antes (si está
   identificado). Ya existía.
2. Cross-sell nuevo — sirve también para visitante anónimo/nuevo sin
   historial propio, porque mira TODO el histórico de pedidos.
3. `catalogo.destacados()` — relleno genérico, solo si todavía falta.

Cacheado por producto individual (`cross:{id}`, TTL 180s) y no por
combinación de carrito completo — a propósito, para que el cache no
crezca sin límite con cada carrito distinto y se reaproveche entre
carritos que compartan productos.

**2. "Receta de la semana", implementada y probada en local (falta
pushear/deployar):** Adriana eligió la Variante A (franja chica, discreta,
arriba del hero) con el ícono de libro (lo balancea con una animación
suave) y el punto naranja que titila — descartó la ollita y otras 2
alternativas que se le mostraron. Arrancamos con el tipo de enlace PDF
(deja preparado Instagram y blog para más adelante; blog queda sin usar
hasta reactivar el sitio institucional, hoy pausado).

Se maneja 100% desde `/admin/receta` (mismo panel con contraseña única que
ya existía, nuevo ítem de menú en `admin_base.html`), sin tocar la base de
datos — mismo patrón que "Avisos"/"Carrusel" (JSON en `app/data/`, ver
`contenido.py` → `receta_semana()` / `receta_semana_admin()` /
`guardar_receta_semana()`). El formulario (`admin_receta.html`) tiene: un
switch "Mostrar la receta de la semana en la home" (si está apagado, o si
falta título/archivo, `receta_semana()` devuelve vacío y la tarjeta no
aparece en ningún lado — guardado como prioridad: nunca romper la home por
un campo a medio cargar), título, selector de tipo de enlace (pdf /
instagram / blog), subida del PDF (reusa `_guardar_archivo()` y
`_dir_imagenes()` que ya usaba el carrusel, ahora contra la subcarpeta
`recetas/`) y un campo de URL para Instagram/blog.

La tarjeta vive en `home.html` justo después del hero (`.receta-semana` en
`estilo.css`), con el ícono de libro, el punto naranja animado (`rsPunto`,
`prefers-reduced-motion` respetado) y el texto de la acción cambia solo
según `tipo_link` ("Descargar PDF" vs "Ver en Instagram"). Probado en
local con un PDF real subido a mano: el switch prende/apaga la tarjeta
correctamente y el link resuelve bien contra `{IMG_BASE}/recetas/`.

Detalle técnico que vale la pena recordar: la home real de la tienda
(`home.html`, donde vive esta tarjeta) solo se ve cuando
`LANDING_HOME=false` — con `true` (como está hoy en el `.env` local, igual
que en el dominio `masorganicos.com.ar`), `/` sirve `landing.html` en su
lugar y esta tarjeta no se renderiza ahí. Para probarla en local hubo que
apagar `LANDING_HOME` temporalmente. En producción esto se ve en el
deploy de la tienda propiamente dicha (`tienda.masorganicos.com.ar`), no
en la landing institucional.

---

## Convención adoptada (2026-09-28): esta bitácora

Adriana armó la skill `bitacora-proyecto-code` desde Cowork (vive del lado
de claude.ai, no la reconoce el `Skill` tool de Claude Code en este
entorno) para que **todos** sus proyectos con Claude Code mantengan un
`BITACORA.md` así: cronología de decisiones/parámetros/ajustes
conversados, no diffs de código. Replicar este mismo criterio (archivo
`BITACORA.md` en la raíz) en `conectar`, `dashboard`, `finanzas` y `stock`
a medida que se trabaje en cada uno.

---

## 2026-10-01 — Incidente: la tienda entera cayó al deployar (no fue el cross-sell/receta)

Al deployar el commit de cross-sell + receta de la semana, la tienda
quedó totalmente caída (Passenger: "Web application could not be
started") en `tienda.masorganicos.com.ar` — no solo la pantalla nueva,
**todo el sitio**, incluido el catálogo. Diagnóstico completo, para que
quede claro que no fue el feature nuevo:

**Causa real:** el commit `25b5599` ("Landing institucional", de otra
sesión/actividad, 2026-09-30) agregó `import markdown` a nivel de módulo
en `app/sitio.py` (lo usa el blog para convertir `.md` a HTML) y sumó
`markdown==3.7` a `requirements.txt`. Pero `.cpanel.yml` **no corre
`pip install`** en el deploy (solo copia `app/`, `passenger_wsgi.py` y
`requirements.txt`) — así que ese paquete nunca se instaló en el
virtualenv de producción. Nadie lo notó porque nadie había vuelto a
deployar desde el 29/09 (último commit probado: `090c757`) hasta hoy: mi
deploy fue el primero en traer `25b5599`, y como `main.py` importa
`sitio` incondicionalmente, el `ModuleNotFoundError` reventó el arranque
de **toda** la app, no solo del blog.

**Cómo se encontró:** `passenger_wsgi.py` ya tenía (de antes, commit
`ad57bdb`) un `try/except` que escribe el traceback real en
`$DEPLOYPATH/startup_error.log` cuando falla el arranque — muy útil
porque Passenger normalmente solo muestra una pantalla genérica "algo
salió mal" sin detalle. Se leyó ese archivo vía la API `UAPI
Fileman::get_file_content` (`fetch` desde la consola del navegador ya
logueado en cPanel) cuando la navegación manual por el File Manager
resultó demasiado inestable para encontrar el archivo a tiempo.

**Secuencia de la resolución (todo vía cPanel Git Version Control, Update
from Remote + Deploy HEAD Commit):**
1. Revert del commit de cross-sell/receta (`0c63020`) ante la duda inicial
   — PERO el sitio siguió caído después de deployar el revert, lo que
   probó que el feature nuevo no era la causa.
2. Encontrado el `ModuleNotFoundError` real en `startup_error.log`.
3. Hotfix (`517d785`): el `import markdown` se movió de nivel de módulo
   a adentro de `sitio._parsear()` — así, si el paquete falta, solo
   falla `/blog` al pedirse, no el arranque de toda la tienda. Se
   re-aplicó el revert del revert (cross-sell + receta quedaron activos).
4. Verificado en producción: home, `/carrito` y `/admin/receta` responden
   bien.

**Lección para el ecosistema:** cualquier commit que agregue una
dependencia nueva a `requirements.txt` de `tienda` necesita, además del
deploy de Git, un `pip install -r requirements.txt` manual en el
virtualenv de producción — `.cpanel.yml` no lo hacía solo.

**Fix permanente (commit `f095093`):** se agregó al `.cpanel.yml` una
tarea que corre
`/home3/iebbbhrt/virtualenv/public_html/claude2026/tienda/3.11/bin/pip install -r $DEPLOYPATH/requirements.txt`
en cada deploy, para que esto no se repita — se confirmó que ese es el
`pip` real del virtualenv de producción (encontrado vía `UAPI
Fileman::list_files`, sin necesitar SSH). Ya está pusheado a GitHub.

**Pendiente — el pull de este último commit quedó trabado en cPanel:**
"Update from Remote" trajo bien los commits anteriores (desde el
incidente hasta `517d785`), pero a partir de ahí `refs/remotes/origin/main`
en el repo de cPanel sí avanzó hasta `f095093` (confirmado leyendo
`.git/FETCH_HEAD` y `.git/refs/remotes/origin/main` directo por
`UAPI Fileman::get_file_content`), **pero `refs/heads/main` (la rama
local que de verdad se deploya) se quedó pisada en `517d785`** pese a
varios reintentos, tanto por la UI como llamando directo a
`execute/VersionControl/update`. No se pudo determinar la causa exacta
sin acceso a shell/SSH (podría ser un conflicto local en el working copy
del repo de cPanel). **La tienda sigue funcionando bien igual** — el
`pip install` nuevo todavía no se aplicó, pero tampoco hace falta: hoy
`/blog` simplemente da 500 si se lo pide (ver fix de `sitio.py` arriba),
sin afectar el resto del sitio. Para terminar esto: la próxima vez que
alguien entre a cPanel → Git Version Control → tienda → Pull or Deploy,
probar "Update from Remote" de nuevo (puede que ya funcione solo) y
recién ahí "Deploy HEAD Commit"; si sigue sin avanzar, revisar con SSH
si el working copy del repo en `/home3/iebbbhrt/repositories/tienda`
tiene cambios locales sin commitear que bloqueen el fast-forward.

---

## 2026-10-01 — Deploy trabado resuelto + landing activada en producción

Cierre de los dos pendientes de la sección anterior, mismo día.

**Deploy trabado:** se resolvió solo, reintentando "Update from Remote" +
"Deploy HEAD Commit" desde la pantalla de manage del repo (`Git Version
Control → tienda → Pull or Deploy`) — como ya se sospechaba, bastaba con
reintentar. `refs/heads/main` avanzó hasta `1e3ba07` y el deploy corrió el
`pip install` nuevo del `.cpanel.yml` sin errores. Confirmado que
`markdown` quedó instalado en el virtualenv de producción: `/blog` dejó
de dar 500 y ahora lista las notas correctamente.

**Landing activada en `tienda.masorganicos.com.ar` (que es donde apunta
`masorganicos.com.ar` desde el incidente del 2026-09-30):** se agregó
`LANDING_HOME=true` al `.env` de producción (no está en git — vive solo
en el servidor, a propósito, como el resto de credenciales de ese
archivo). Se usó el editor de código de cPanel File Manager (no una
escritura ciega por API) para no arriesgar los secrets ya presentes en
el archivo. Nota para la próxima vez: el toolbar de File Manager tiene
"Editar" y "Permisos" muy pegados — conviene seleccionar el archivo y
usar el buscador de elementos antes de clickear por coordenadas, porque
un click mal calculado abre "Cambiar permisos" en vez del editor.

Como Passenger solo lee `.env` al arrancar el proceso, hubo que forzar un
reinicio tocando `tmp/restart.txt` (mismo mecanismo que usa el propio
`.cpanel.yml` en cada deploy) — un primer intento de "guardar sin
cambios" no alcanzó (el editor no sube el archivo si no detecta contenido
distinto), hubo que efectivamente cambiar el contenido para que el mtime
se actualizara.

Verificado en producción: `/` muestra la landing con el botón "Ir a la
tienda", `/catalogo` y el resto de la tienda siguen funcionando sin
cambios (el toggle `LANDING_HOME` solo afecta la home).

---

## 2026-10-01 — Popup de bienvenida administrable + campos del panel más grandes

Pedido de Adriana: una imagen/propaganda al entrar que el cliente cierra con
una X, activable o no desde el panel.

**Decisiones:**
- Mismo patrón que Receta/Avisos: JSON en `app/data/popup_home.json`, sin
  tocar la base. Se maneja desde `/admin/popup`.
- Solo imagen (sin video por ahora). Se sube a `{IMG_BASE}/popup/`. Link
  opcional al tocarla.
- Se activa/apaga con un switch general, y con dos casillas se elige dónde
  sale: **landing** (`masorganicos.com.ar`) y/o **home de la tienda**. Ojo:
  mientras producción tenga `LANDING_HOME=true`, la home del catálogo no se
  ve en `/`, así que ahí hay que tildar "landing".
- Frecuencia: una vez por visita (default, `sessionStorage`), una sola vez
  por persona (`localStorage`; cada guardado cambia `version`, así un popup
  nuevo vuelve a salir) o cada vez.
- Se muestra recién cuando la imagen cargó (nunca un popup vacío); cierra
  con X, click afuera o Esc. Apagado/sin imagen → no se renderiza nada.
- Parcial `_popup.html`, incluido en `home.html` y `landing.html`.

**Panel:** los inputs/textarea/select del admin no tenían estilo (tamaño
mínimo del navegador). Se agregó CSS en `admin_base.html`: ancho completo
(máx. 640px), más relleno, textarea alto y redimensionable. Afecta a todas
las pantallas del admin salvo la tabla de Zonas.

**Aprendizaje de testing local:** el server del puerto 8010 (con `--reload`)
vigilaba otra carpeta y no recargaba cambios de este repo; y el `.env` local
tiene `LANDING_HOME=true`, así que para ver la home de la tienda hay que
correr con `LANDING_HOME=false`.

---

## 2026-10-02 — Fix: tienda.masorganicos.com.ar mostraba la landing

Adriana notó que `tienda.masorganicos.com.ar` (y `www.tienda.…`) llevaba a la
landing en vez de a la tienda. **Causa:** el 2026-10-01 se puso
`LANDING_HOME=true` en el `.env` de producción para que `masorganicos.com.ar`
muestre la landing, pero landing y tienda comparten el mismo despliegue y el
mismo `.env`, así que el interruptor afectaba a los dos dominios.

**Fix:** `home()` en `main.py` ahora sirve la landing solo si
`LANDING_HOME=true` **y** el host no empieza con `tienda.` / `www.tienda.`.
Sin cambios de `.env`. Probado con curl y distintos `Host`. Consecuencia
buena: la casilla "En la home de la tienda" del popup ahora sí se ve en
producción.

---

## 2026-10-02 — Landing en su propio dominio (masorganicos.com.ar) + deploy que no pisa el panel

Adriana eligió que `masorganicos.com.ar` muestre la landing y `tienda.*` la
tienda. **Hallazgo en cPanel:** `masorganicos.com.ar` (document root
`public_html`) ya tenía una app Passenger propia en
`public_html/claude2026/landing` (con `.env` correcto: `LANDING_HOME=true`,
`URL_WEB`, `URL_TIENDA_PUBLICA`, token CAPI) pero con una copia VIEJA del
código (sin `sitio.py` ni la landing nueva), y una regla en
`public_html/.htaccess` (`RewriteRule ^/?$ … tienda…`) que redirigía la raíz a
`tienda.*`. Por eso la landing "se veía" solo porque ese redirect caía en
tienda con `LANDING_HOME=true` (ver fix del mismo día en `main.py`).

**Cambios:**
- `.cpanel.yml` ahora despliega a **las dos apps** (tienda y landing) con un
  script compartido `deploy/desplegar.sh <carpeta> <pip>`.
- El script **respalda y restaura los JSON editables desde /admin**
  (`carrusel_home`, `home`, `integraciones`, `receta_semana`, `popup_home`):
  antes, cada deploy los pisaba con la copia del repo (habría apagado el popup
  y la receta en cada deploy). El resto de `app/data/` sí se actualiza.
- **Hecho (2026-10-02, con autorización de Adriana):** se sacaron de
  `public_html/.htaccess` las dos líneas (`RewriteCond %{HTTP_HOST} ^.*$` +
  `RewriteRule ^/?$ … tienda…`) que redirigían la raíz de `masorganicos.com.ar`
  a `tienda.*`. Respaldo del archivo original: `public_html/.htaccess.bak-redirect`.
  Verificado: `masorganicos.com.ar/` sirve la landing sin redirigir. **Ojo:**
  el 301 viejo queda cacheado en navegadores que ya lo vieron (hay que probar
  con otra URL, ej. `/?x=1`, o ventana privada).

---

## 2026-10-03 — Reservas automáticas para proveedores marcados "siempre reservar"

**Pedido (Adriana):** leche y yogures de cabra y de la recría se piden para la
entrega fresca de la próxima semana, pero si el producto tiene stock la tienda
no generaba fila en `reservas` (solo lo hacía para Granja agotado). Caso
concreto: Claudia Balcaza pidió un yogur natural con stock y había que
tratarlo como reserva igual.

**Decisión:** transparente para el cliente (lo agrega al carrito y compra
normal, sin cartel "Agotado" ni botón "Reservar"); internamente se registra
igual que cualquier reserva. Se marca **por proveedor** (más fácil que por
producto).

**Cómo quedó:**
- Tabla `reservas_proveedores (proveedor_codigo)` en el ERP, creada y
  administrada desde `conectar` (pantalla Reservas). Si no existe todavía, la
  tienda asume que no hay ninguno marcado (no rompe nada).
- `reservas.productos_reserva_siempre()` trae los ids de producto de esos
  proveedores (join `mprimas.Proveedor`), con cache de 60 s para no consultar
  la base en cada línea del carrito; `es_reserva_siempre(id)`.
- `catalogo.es_reserva(producto)` = (agotado y Granja) **o** proveedor
  marcado. Reemplaza la condición vieja en los tres lugares donde se decidía:
  `pedidos.agregar_item` (editar un pedido), y en `main.py` tanto la marca de
  la observación de cada línea como el loop que llama a `reservas.crear`
  al confirmar el checkout.
- La observación de la línea queda "RESERVA (entrega próxima del proveedor)"
  cuando hay stock (`TEXTO_RESERVA_PROXIMA_ENTREGA`), distinta de "RESERVA
  (sin stock, encargar a proveedor)", para que en la comanda/VB6 no diga que
  falta stock cuando no es así.
- Un fallo al crear la reserva sigue sin romper el checkout (queda en
  `errores.log`, igual que antes).

**Ojo:** requiere deploy manual por cPanel, y que Adriana marque los
proveedores en `conectar`. Los pedidos hechos antes no se reservan solos.
**Sin probar contra la base real** al momento de escribir esto.

## 2026-10-04 — Combos/bolsones con plantilla: sin cartel de stock

Los artículos que tienen plantilla de composición (tabla `combo_componentes` del
ERP, la mantiene `stock`: bolsones, combo ensalada, etc. — hoy 9) **se arman al
momento de la venta**, así que no tienen stock propio y nunca mostraban un
número útil. Adriana pidió que no muestren "Pocas unidades" ni "Agotado": están
disponibles o no (según `Activo` / `noweb`), nada más.

- `catalogo.Producto.es_combo` (se marca al cargar el catálogo con
  `_codigos_combo()`); `agotado` y `poco_stock` dan siempre falso para combos y
  `_filtrar_por_stock` no los saca de la tienda aunque su stock sea 0, sea cual
  sea su rubro (antes dependía de que fueran de Verduras/Frutas).
- Si falla la consulta de `combo_componentes`, la tienda se comporta como antes.
- Verificado con el catálogo real: los 9 combos salen con `agotado=False` y
  `poco_stock=False`.
- Deploy manual en cPanel (Update from Remote + Deploy HEAD Commit).

## 2026-10-05 — Cambios a partir del informe de Clarity (25/9–4/10)

Informe armado con Cowork (~100 sesiones con carrito + 11 grabaciones).
Resuelto en código:
- **Carrito +/−:** antes cada clic hacía `form.submit()` (recarga completa; con
  red lenta los clics parecían muertos). Ahora `stepCarrito` espera 450 ms tras
  el último clic y manda UN pedido por HTMX; `/carrito/actualizar` y
  `/carrito/quitar` devuelven badge + cuerpo del carrito por OOB (sin recarga).
  Verificado: 5 clics rápidos → cantidad 6, sin recarga de página.
- **Tarjeta:** el texto de detalle (cortado con "…") ahora es un link a la ficha.
- **Host único:** el redirect 301 ahora cubre `www.tienda.*` → `tienda.*`
  (además de http → https, que ya estaba). Pendiente confirmar en producción
  que carrito/sesión persisten tras el redirect.
- **Navegador interno de Instagram/Facebook:** aviso arriba ("abrí en
  Chrome/Safari"), cerrable; en Android el checkout ya escapaba a Chrome.
- **Búsqueda sin resultado:** si el producto existe pero está sin stock → "Agotado
  hoy: …" + botón de WhatsApp; si no existe, mensaje + WhatsApp. Los términos
  quedan en la tabla nueva `busquedas_sin_resultado` (`termino`, `agotado`,
  `creado_en`; se crea sola).
- **Clarity:** `?interno=1` marca el navegador como visita interna (tag
  `visita=interna`; `?interno=0` lo quita); eventos `agregar_al_carrito` y
  `pedido_confirmado` (en `/checkout/ok`, no en modo prueba). Solo si la persona
  aceptó cookies (igual que antes).
No tocado (decisión de Adriana / investigación): costo de envío antes del
carrito, pantalla de zonas (alguien cargó datos dos veces), recarga cada ~5 min
(no se encontró ningún `setInterval`/refresh en la tienda; hipótesis: pestaña en
segundo plano o extensión), pedido completo de prueba dentro de Instagram.

### 2026-10-05 (después) — "¿Cuánto sale el envío a tu zona?"
Idea de Adriana para el punto de costo de envío: link chico debajo de "Agregar
al carrito" (ficha de producto) y en el resumen del carrito. Abre un campo para
barrio/dirección; detecta la zona (barrios conocidos → si no, geocodificación +
polígonos, igual que el checkout) y muestra precio a coordinar, precio el día de
reparto, envío gratis desde, compra mínima, todo de la tabla `zonas`
(`/envios/zonas.json`). Si no la encuentra: link a `/envios` (lista de zonas y
valores) y a WhatsApp. Recuerda la zona en el navegador (`mo-zona`). Evento
Clarity `consulta_envio_abrir`. Probado en local: Nordelta (barrio), Vicente
López (geocodificada) y dirección inexistente (cae al mensaje de ayuda).

### 2026-10-05 (más tarde) — Fix: zona mal detectada ("pacheco" → CABA Norte)
Causas encontradas probando "pacheco" en la consulta de envío:
1. Nominatim tomaba "pacheco" como la calle homónima de Villa Urquiza (CABA).
2. **Polígonos superpuestos:** el de "Pacheco" está dentro del grande de "Don
   Torcuato" y el código tomaba el *primero* que contenía el punto. Ahora gana el
   de menor área (`zonaMasEspecifica` en `tienda.js`; mismo criterio en
   `verificador-zona.js`, /envios y landing). Corrige también el checkout.
Reglas de la consulta de envío: 1) barrio conocido (`barrios.json`); 2) texto que
coincide con título de zona(s) — si hay varias (Pacheco / Pacheco Barrios
Privados) se listan todas; 3) con número de altura se geocodifica; 4) sin número
y sin coincidencia NO se geocodifica (devuelve el centro del partido, zona
arbitraria) y se pide calle y altura.
Pendiente: `zonas.geojson` solo trae 10 polígonos de 17 zonas (faltan, p. ej., la
13 Martínez/Olivos/Vicente López y la 5 Nordelta): esas zonas solo se detectan
por barrio/título; direcciones de Vicente López caen en "Virreyes, Beccar, San
Isidro".

### 2026-10-05 (noche) — `barrios.json` ampliado (localidades + barrios privados de Pacheco)
Idea de Adriana: resolver primero por la tabla de barrios y recién después por
el mapa. Quedó así (consulta de envío y checkout): 1) `barrios.json`, 2) título
de zona, 3) mapa solo con altura. `barrioCoincidente()` en `tienda.js`: sin
tildes, gana la coincidencia más larga, soporta `excluir` (ej. "tigre" no vale si
dice "pacheco"). Entradas nuevas (26 → 46): Benavidez/Maschwitz → 7; Garín/
Tortuguitas/Ricardo Rojas → 8; Dique Luján → 9; Tigre/San Fernando → 4; Martínez/
Olivos/Vicente López → 13; barrios privados de Pacheco → 2 (Pacheco Golf Club,
Santa Bárbara, Talar del Lago 1 y 2, Barrancas de Santa María y San José, Solares
del Talar, Laguna del Sol). **Cambio:** "Santa Bárbara" pasó de zona 5 (Nordelta) a
2 por pedido de Adriana. "Talar del Lago" a secas sigue en zona 17.
"Talar" solo → muestra Talar y Talar (cercano al local).

### 2026-10-05 — Búsquedas sin resultado con cliente
`registrar_busqueda_sin_resultado` guarda también, si hay cliente logueado,
`user_id`, `cliente_codigo`, `nombre` y `telefono` (columnas agregadas con ALTER
la primera vez). Se lee desde `conectar` → "Búsquedas sin resultado".

### 2026-10-05 — Registro de accesos de clientes logueados
Nuevo `app/accesos.py` + tabla `accesos_clientes` (`fecha`, `user_id`, `primera`,
`ultima`, `paginas`; PK fecha+user_id). Se llama desde `render()` (páginas GET
completas, no HTMX) con el cliente de la sesión; escribe en un hilo aparte y
traga cualquier error (nunca demora ni rompe una página). Se ignoran visitas con
cookie `mo_interno=1` (la pone `tienda.js` al entrar con `?interno=1`; `?interno=0`
la saca). Se lee desde `conectar` → "Accesos a la tienda".

### 2026-10-05 — Contador de visitantes anónimos
`accesos.py` ahora también escribe `accesos_visitantes` (`fecha`, `visitante_id` =
UUID de la cookie de sesión, `logueado`, `primera`, `ultima`, `paginas`). Un
dispositivo es "anónimo" ese día si nunca inició sesión (`logueado` = GREATEST).
Por dispositivo, no por persona. Se descartan robots (user-agent), visitas HTMX e
internas (`mo_interno=1`). Lo muestra `conectar` → "Accesos a la tienda" (totales
y desglose por día).

### 2026-10-05 (prueba real desde Instagram, Android)
Adriana probó un pedido completo en el navegador interno de Instagram (Android).
Hallazgos y arreglos:
1. **El escape forzado a Chrome al confirmar era dañino:** Instagram muestra "Estás
   saliendo de nuestra app", el botón quedaba en "Enviando…" (el `onsubmit` inline lo
   deshabilita antes de que corra el JS), y al continuar abría Chrome con otra sesión
   (cookies separadas; cayó en el cliente SBREDES) y sin carrito. **Se eliminó**
   `escaparSiEsWebviewMeta()`: ahora el pedido se hace dentro de Instagram (que es la
   prueba que faltaba) y el aviso del banner queda como sugerencia. Además
   `pageshow` destraba el botón si se vuelve a la página.
2. **Se podía confirmar un envío sin calle ni barrio:** ahora el servidor lo rechaza
   ("…completá la calle o el barrio"; alcanza con uno de los dos, la altura no es obligatoria). Había quedado guardada una dirección vacía
   (user 4530, ADRIANA LAZO) que el checkout mostraba como "dirección guardada"
   vacía: `clientes.direcciones()` ahora ignora las direcciones sin calle ni barrio.
3. **Consulta de envío para clientes logueados:** si el cliente tiene dirección guardada
   con zona, se muestra directamente el costo de SU zona y el botón pasa a "¿Enviás a
   otra dirección?" (`zona_cliente()` en `main.py`).
Pendiente: repetir la prueba completa dentro de Instagram con estos cambios.
Decisión (Adriana): el costo de envío de un cliente logueado con zona guardada se
muestra SOLO en el carrito; en las fichas de producto la consulta aparece únicamente
para quien no está logueado o no tiene zona guardada.

### 2026-10-05 — Email como contacto de respaldo
Pedido de Adriana: un cliente real dejó un teléfono por el que no se pudo contactar
por WhatsApp y no había otra vía. El campo de email ya existía pero era opcional y
decía "para enviarte el resumen" (la tienda no manda resúmenes) y, vacío, se grababa
un email falso `sinmail_<tel>@masorganicos.local` (6 usuarios hoy; 2 pedidos del
05/10). Ahora: etiqueta "Email (opcional)" + aviso "lo usamos solo si no logramos
comunicarnos con vos por WhatsApp"; un cliente reconocido cuyo email falte o sea
`sinmail*` ve el campo (visible) en vez del hidden; el sugerido no precarga el falso.
Sigue siendo opcional a propósito (no frenar pedidos).

### 2026-10-05 (noche) — Prueba completa en Instagram: OK (pedido #22330)
Pedido #22330 hecho de punta a punta dentro del navegador de Instagram (Android):
cliente 4530, zona Pacheco, envío "el día" $1.500, dirección Zapiola 1422. Quedó
oculto como prueba (`status=2, activo=0`, sin borrar). De la prueba salieron dos
mejoras: 1) el aviso de "falta dirección" aparecía arriba de la página y la persona
no lo veía → ahora `confirmarCheckout()` valida zona y calle/barrio en el
navegador y muestra el aviso pegado al botón (el servidor sigue validando);
2) el desplegable de zona mostraba "Título — envío $X" largo y confuso en el celular →
ahora solo el nombre de la zona (el costo ya se ve en el resumen al elegirla); los
títulos cortados por el `varchar(45)` (p. ej. "CABA Norte (Devoto, Villa del
Parque, Villa C") se muestran sin el paréntesis abierto (`zonas._titulo_limpio`).
