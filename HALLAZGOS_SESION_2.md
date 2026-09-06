# Hallazgos sesión 2 — relevamiento a fondo antes de programar

Fecha: 2026-09-06. Autor: Claude Code (compu de Adriana).
Complementa a `BRIEFING_TIENDA_NUEVA.md`. Todo esto está verificado contra la base de datos real y el código VB6.

---

## 0. Cómo se conectó

Credenciales usadas (MySQL en Nuthost):

```
host 167.250.5.60  puerto 3306  user iebbbhrt_operador
```

Funcionan desde acá con `pymysql`. El usuario `iebbbhrt_operador` ve todas las bases y puede
leer/escribir. Los scripts de inspección quedaron en el scratchpad de la sesión (no en el repo).

---

## 1. Cuál es la base VIVA de la tienda — CONFIRMADO

Hay dos bases con esquema parecido. **No son intercambiables.**

| Base | Rol real | Evidencia |
|---|---|---|
| **`iebbbhrt_prueba_paginaweb`** | **La tienda que está en producción HOY.** | Pedidos continuos: ~140/mes hasta hoy (último 2026-09-04). Carritos ~2000/mes (último 2026-09-05). 2153 pedidos, 3655 usuarios, 25906 líneas. |
| `iebbbhrt_paginaweb` | Base Laravel **vieja/abandonada**. | Solo 38 pedidos, el último de 2025-10. Esquema de `carritos` más viejo (sin `tiempoCreado`). La tabla `users` todavía recibe algún alta suelta (probablemente formularios viejos), pero pedidos no entran hace casi un año. |

`iebbbhrt_paginawebtest` quedó congelada en 2021. Las otras (`iebbbhrt_prueba_masorganicos`, etc.) no se tocaron.

**Confirmación cruzada con el VB6:** en `Modulos/entorno.bas:101` está hardcodeado
`nBaseWebMO = "iebbbhrt_prueba_paginaweb"`. O sea: el sistema de escritorio lee los pedidos web
de esa base. Coincide con lo que dijo Adriana.

➡️ **La tienda nueva escribe y lee de `iebbbhrt_prueba_paginaweb`.** Conviene renombrarla algún día
a algo sin "prueba", pero eso toca el VB6 y no es urgente.

---

## 2. Contrato de compatibilidad con el sistema de escritorio (VB6) — RESUELTO

### Qué botón usa Adriana
`frmPedidos.frm` → botón **`cmdPedidosWebMO`** → llama a `Sub CargapedidoMO` (línea 4527).

### Qué lee exactamente ese código

El importador **NO usa** las vistas `pedidosWebMO` / `pedidoscarrito` / `carrito_abandonado` para
traer los datos del pedido. Esas vistas son solo para la **grilla de selección** (elegir qué pedido
importar). Los datos reales los saca de las tablas base:

**`grupos`** (cabecera del pedido) — una fila por pedido:

| Columna | Tipo | Qué significa / qué espera el VB6 |
|---|---|---|
| `id` | bigint AI | Nº de pedido. AUTO_INCREMENT hoy en 21853. |
| `cliente` | bigint | FK a `users.id`. |
| `efectivo` | int | 0 = paga con método de pago / 1 = efectivo. El VB6 lo lee como `Efectivo`. |
| `retira` | int | **Poco confiable** (muchos pedidos con envío tienen `retira=1`). El VB6 **ignora esto** y decide por `id_sucursal` / `id_dirEnvio`. |
| `id_sucursal` | int | `<>0` → el cliente RETIRA en esa sucursal (`sucursal.id_sucursal`). `0` → es envío. |
| `id_dirEnvio` | int | `<>0` → FK a `direccion.id_direccion` (envío a domicilio). |
| `id_zonaEnvio` | int | FK a `zonas.id_zona`. Define la leyenda de reparto. |
| `precioEnvio` | decimal(10,2) | Costo de envío calculado. El VB6 lo usa tal cual. |
| `codigoDescuento` | varchar(30) | Texto del cupón (o `''`). Si viene, el VB6 busca en `codigos_descuento` por `codigo` y aplica `porcentaje` como bonificación general. |
| `status` | int | **0 = Nuevo, 1 = Preparación/Importado, 2 = Facturado.** El VB6 avisa "ya fue importado" si `status=1`. La tienda nueva graba **`status=0`**. |
| `created_at` | timestamp | Fecha del pedido. |
| `observacion` | varchar(500) | Observaciones generales del cliente. |
| `observacion2` | varchar(500) | "Faltantes" (lo maneja el VB6, la web manda `''`). |
| `factura`, `aceptobolsas`, `activo`, `updated_at` | — | Defaults (`0`, `0`/`1`, `1`, `NULL`). |

**`transacciones`** (renglones) — una fila por producto del pedido:

| Columna | Tipo | Qué espera el VB6 |
|---|---|---|
| `id` | bigint AI | — |
| `grupo` | bigint | FK a `grupos.id`. |
| `producto_id` | varchar(191) | **Es `mprimas.id`** (el id numérico del maestro de artículos en `iebbbhrt_masorganicos`), guardado como texto. NO es el `Codigo`. Verificado: `SELECT ... FROM mprimas WHERE id = producto_id` matchea siempre; por `Codigo` no matchea nunca. |
| `cantidad` | double(8,2) | — |
| `precio` | double(8,2) | Precio unitario al momento de la compra (= `mprimas.Precio1`, ver punto 4). El VB6 respeta el precio del maestro y si difiere deja una nota "Pr:xxx" en el renglón. |
| `id_unidadMedidaProducto` | int | En los pedidos reales aparecen valores tipo `90000001`, `90000003`. A confirmar el catálogo de unidades (probablemente `parametros`), pero la tienda nueva puede copiar el valor que ya usa la web actual por producto. |
| `observacion` | varchar(191) | Observación por renglón (lo que el cliente escribe en "Observación"). |
| `porcentaje`, `activo`, `created_at`, `updated_at` | — | Defaults (`0`, `1`, fecha, `NULL`). |

Además el VB6 busca al cliente así (en la base del ERP `iebbbhrt_masorganicos`, tabla `clientes`):
primero por `telefonos = users.telefono`, si no lo encuentra por `Email = users.email`, y si tampoco,
lo trata como **cliente nuevo** (lo carga a mano). O sea: la tienda nueva **no necesita** crear el
cliente en el ERP; solo tiene que dejar `users.telefono` y `users.email` bien cargados.

### Vistas creadas el 5/9/2026 por Claude-Code-de-escritorio
`pedidosWebMO`, `pedidosWebF`, `pedidoscarrito`, `productoPedido`, `carrito_abandonado`. Son
**solo de lectura para las grillas** del VB6 y para reportes. Están bien como están; no hace falta
rehacerlas ni la tienda nueva depende de ellas. `pedidosWebMO` ya mapea `status` 0/1/2 a
"Nuevo/Preparación/Facturado" y calcula el total como `sum(cantidad*precio)`.

➡️ **Contrato para la tienda nueva:** al confirmar un pedido, insertar 1 fila en `grupos`
(`status=0`) + N filas en `transacciones` (con `producto_id = mprimas.id`), creando/actualizando
antes la fila de `users` y, si es envío, la de `direccion`. Nada más. El VB6 lo levanta igual que hoy.

---

## 3. Alcance de `MiCuenta` / login — PROPUESTA

Datos reales: **~3655 usuarios, ~1 alta por día**. La tabla `users` tiene `password` (hash bcrypt,
84 chars) pero **`telefono` está casi siempre en 0** en las altas recientes y `direccion`/`localidad`
suelen venir `NULL` (la dirección real vive en la tabla `direccion`).

Lo que pediste: login con contraseña simple, y que al agregar al carrito se le proponga loguearse
**o** dejar datos de primera compra (nombre, apellido, celular, mail) sin que sea una fricción.

**Propuesta concreta:**

1. **Carrito sin login.** El carrito vive en el navegador (cookie/localStorage) + una copia en la
   tabla `carritos` si querés seguir midiendo abandono. Agregar productos nunca pide login.
2. **Identificación recién en el checkout**, en un solo paso:
   - Campo **celular** (o mail). Si ya existe un `users` con ese celular/mail → "¡Hola de nuevo!"
     y sigue. Opcionalmente pide una clave corta solo si el cliente quiere ver su historial.
   - Si no existe → formulario corto: nombre, apellido, celular, mail. Se crea el `users` en el acto
     con una contraseña autogenerada (o la que el cliente elija, opcional).
3. **"Mi cuenta" liviana:** con el celular + clave corta (4–6 dígitos) el cliente ve su historial de
   pedidos y sus direcciones guardadas. Nada de DNI ni datos sensibles.
4. **Direcciones:** se guardan en `direccion` ligadas al `users`; en la próxima compra se ofrecen
   como botones ("Enviar a: Arribeños 1611, Benavidez").

Esto respeta el esquema actual (no hay que migrar nada) y elimina la fricción. Reconstruir el
`MiCuenta` completo del ASP.NET (recuperar contraseña por mail, verificación, etc.) **no vale la pena**
para el volumen que hay.

**Falta que confirmes:** ¿querés que el cliente *pueda* poner una contraseña propia en la primera
compra, o preferís que sea 100% sin contraseña y la "clave" sea siempre el celular + un PIN que le
llega por WhatsApp/mail?

---

## 4. Catálogo: de dónde salen los productos — RESUELTO

El catálogo **no está en `iebbbhrt_prueba_paginaweb`**. Sale del ERP `iebbbhrt_masorganicos`,
tabla **`mprimas`** (1269 filas). Campos que importan para la web:

| Campo | Uso en la tienda |
|---|---|
| `id` | Clave que se guarda en `transacciones.producto_id`. |
| `Codigo` | Clave del **nombre de archivo de la foto** (ver abajo). |
| `Descripcion` | Nombre del producto. |
| `detalle` | Descripción larga / ingredientes (se muestra en la card). |
| `Precio1` | **Precio de venta web.** Verificado contra 15 pedidos recientes: `transacciones.precio == mprimas.Precio1` siempre. (`PreLista` es el precio sin margen, NO usar.) |
| `tasaIva` | 10.5 / 21 — informativo. |
| `categoria` | int → `categorias.CodigoUnificado` (`Descripcion` = nombre de la categoría). ~45 categorías: VERDURAS DE HOJA, HORTALIZAS, FRUTAS FRESCAS, LACTEOS, CARNE, HARINAS, INFUSIONES, TINTURAS MADRE, LIMPIEZA, etc. |
| `destacado` | tinyint → "Productos Destacados" de la home. |
| `Activo` | varchar(2): `'SI'` / `'NO'`. Solo `'SI'` se vende. |
| `noweb` | tinyint: `-1` (verdadero, Access) = **NO mostrar en web**, `0` = sí. |

**Productos vendibles en la web hoy:** `noweb = 0 AND Activo = 'SI'` → **428 productos**.

Stock: vista **`Stock`** = `SUM(movstock.Cantidad) GROUP BY Codigo`. Da el stock físico total por
código. Sirve para mostrar "sin stock" / ocultar, pero ojo: el negocio ya avisa "precio y stock
sujetos a cambios al preparar el pedido", así que el stock web puede ser orientativo.

Vistas útiles ya existentes en `iebbbhrt_masorganicos`: `mprimasWeb` (todo mprimas + `rubro_web`),
`categorias`, `rubros`, `ListArticulos` (con nombres legibles de rubro/unidad/proveedor + `Precio1`).

**Fotos de producto:** no están en la base. Son archivos `<Codigo>.jpg` en el hosting:
- Sitio actual (Ferozo `w360183`): `/public_html/assets/img/producto/<Codigo>.jpg`
- Sitio viejo (DonWeb `masorganicos.com.ar`): `/PublicWeb/img/Productos/<Codigo>.jpg`
- (credenciales FTP están en el VB6, `frmMprimas.frm` ~línea 3236 y 3260)

➡️ Hay que **bajar esa carpeta de fotos por FTP** y servirla desde Nuthost. Item de migración.

---

## 5. Estado actual de masorganicos.online (lo que confirma la auditoría)

Home revisada en vivo:
- El "hero" es un bloque **"Zonas y valores de envío"**, sin botón de compra ni propuesta de valor.
- Abajo, **"Productos Destacados"** con cards que ya traen cantidad + observación + "sumar al carrito"
  inline (bien) pero **sin foto visible en el texto**, sin precio tachado, sin etiquetas.
- **Cero señales de confianza / prueba social** antes del scroll (coincide con ConvertMate).
- Catálogo (`Producto/BusquedaProducto.aspx`) carga los productos por **AJAX** (`.asmx`) — por eso el
  crawler de ConvertMate "no vio precios": es un falso positivo técnico, los precios están.
- Pie de página con toda la info de pago (Efectivo, Transferencia, Débito, Crédito, Cuenta DNI,
  Mercado Pago — **nada se cobra en el sitio**) y zonas de reparto. WhatsApp de contacto: 11 5504 6740.
- Menú con 9 categorías (ConvertMate recomienda 5–7 agrupando).

Contenido editable que ya vive en `iebbbhrt_prueba_paginaweb` y conviene reusar:
`carrousel` (9 slides, 4 activas), `genericos` (textos de la home / avisos de feriado),
`faq_preguntas`+`faq_respuestas` (11), `etiquetas` (Sin TACC, Vegano, Gluten Free, Orgánico,
Agroecológico, Pastoril) + `etiquetas_producto`, `newsletter` (459 mails), `zonas` (17, con precio,
mínimo de compra y umbral de envío gratis), `codigos_descuento` (4, ej. primera compra 20% en frutas
y verduras).

---

## 6. Decisiones que faltan (para que definas)

1. **Contraseña en primera compra**: ¿el cliente puede elegir una, o va 100% sin contraseña
   (celular + PIN por WhatsApp/mail para ver historial)? — punto 3.
2. **Dominio**: ¿`masorganicos.online` pasa a apuntar a Nuthost cuando esté lista? ¿Qué hacemos con
   `masorganicos.com.ar`? ¿Fecha tentativa de baja de Ferozo? (La tienda nueva puede convivir en un
   subdominio tipo `tienda.masorganicos.com.ar` mientras se prueba.)
3. **Stock**: ¿mostramos stock/agotado en la web usando la vista `Stock`, o no mostramos stock y
   dejamos el aviso de "sujeto a confirmación"?
4. **`id_unidadMedidaProducto`**: confirmar el catálogo de unidades (esos `9000000x`). Lo puedo
   sacar de `parametros` en la próxima corrida.
5. **Contenido/imágenes**: ¿tenés acceso FTP actual a Ferozo para bajar `/public_html/assets/img/producto/`,
   o uso las credenciales que están en el VB6?

## 7. Próximo paso propuesto (cuando dstés de acuerdo)

1. Cerrar puntos del 6.
2. Traer el catálogo de unidades y un dump de `parametros` relevante.
3. Bajar la carpeta de fotos.
4. Recién ahí: definir stack Python (propongo **FastAPI + SQLAlchemy + Jinja2/HTMX**, corriendo como
   "Setup Python App" en cPanel de Nuthost) y estructura del proyecto, con un módulo `pedidos` que
   implemente el contrato del punto 2 y tests que verifiquen la forma de `grupos`/`transacciones`.

---

## 8. Decisiones tomadas (sesión 3) + lo que se resolvió

### 8.1 Login / cuentas — DEFINIDO
- Carrito 100% sin login (cookie + copia opcional en `carritos`).
- Identificación **recién en el checkout**, un solo paso: campo **celular**.
  - Si el celular ya existe en `users` → "¡Hola de nuevo!", sigue. Para ver historial se le pide su PIN.
  - Si no existe → nombre, apellido, celular, mail + **PIN de 4 dígitos opcional** ("para seguir tus
    pedidos la próxima; si no querés, lo salteás"). Si lo saltea, se genera uno y el acceso al
    historial es por **PIN enviado por WhatsApp/mail al momento** (OTP).
- "Mi cuenta" liviana: celular + PIN → historial de pedidos + direcciones guardadas. Sin DNI.
- Recomendación de menor fricción (elegida): **PIN de 4 dígitos, opcional en la 1ª compra, con OTP
  como respaldo.** No se pide contraseña de 8-20 como ahora.
- `users.password`: se sigue guardando un hash bcrypt del PIN (columna ya existe), así el esquema no cambia.

### 8.2 Dominio — DEFINIDO
- La tienda nueva se levanta en **`masorganicos.com.ar`** (hoy sin uso, ya es el dominio principal del
  cPanel de Nuthost). **No se toca `masorganicos.online`** (sigue vigente en Ferozo hasta que la nueva
  esté probada y aprobada). Migración de dominio final = decisión futura.

### 8.3 Stock — DEFINIDO
- Se muestran **todos los productos `Activo='SI'` y `noweb=0`** (~428 hoy).
- **No se oculta por stock.** Solo un **cartelito suave** cuando hay pocas unidades
  ("Pocas unidades — sujeto a confirmación"). Umbral propuesto: `Stock < 3` (hoy 129 productos
  caerían ahí; 48 están en ≤0 pero igual se muestran con el cartel). Nunca bloquea la compra.
- El control de stock del local todavía tiene fallas operativas conocidas → el sitio no promete stock.

### 8.4 Unidades de medida — RESUELTO
`transacciones.id_unidadMedidaProducto` = `mprimas.Unidad` = `parametros` con `Parametro=9`:

| CodigoUnificado | Descripción |
|---|---|
| 90000001 | UN (unidad) |
| 90000003 | KG |
| 90000004 | LT |
| 90000011 | PQTE (paquete) |

En los pedidos reales solo se usan UN (9690) y KG (16168), y algún PQTE (48). La tienda nueva
**copia `mprimas.Unidad` tal cual** a `transacciones.id_unidadMedidaProducto`. Para KG el input de
cantidad admite fracciones `,25 ,5 ,75` (como hoy).

### 8.5 Fotos + sitio actual — EN PROCESO
Credenciales FTP (de `frmMprimas.frm`): host `w360183.ferozo.com`, user `w360183@w360183.ferozo.com`.
- **Fotos de producto:** `/public_html/assets/img/producto/` → **1366 archivos `<Codigo>.jpg`, ~47.5 MB.**
  Bajándose a `C:\MO-IA\tienda\_migracion\fotos\producto\`. También se bajan `carrousel`, `logo`,
  `icono`, `quienessomos`.
- **Markup del sitio ASP.NET actual** (sin DLLs) bajado a `C:\MO-IA\tienda\_migracion\sitio_actual\`
  (52 archivos: `.aspx`, `.master`, `.asmx`, `.js`, `.css`, `Web.config`). El C# sigue sin fuente,
  pero el markup + JS ya muestra toda la UX: carrito con modal envío/retiro, código de descuento,
  "Confirmar pedido", registro con validación de contraseña, `MiCuenta` (Login, SigIn,
  RecuperoContrasenia, Pedidos, Direcciones, DetalleCuenta).
- Imágenes referenciadas por `Codigo` (confirmado en `CarritoCompra.aspx`: `Eval("Codigo")` → nombre
  de archivo).
- **Falta:** credenciales de subida a Nuthost (cPanel/FTP/SSH). Las de MySQL ya las tengo; para
  copiar las fotos y desplegar la app necesito el acceso al hosting.

### 8.6 Nuevas decisiones pendientes
1. **Acceso al hosting Nuthost** (cPanel usuario/clave, o FTP, o SSH) para subir fotos y desplegar.
2. **Sitio viejo `masorganicos.com.ar` en DonWeb**: ¿ese dominio hoy apunta a Nuthost o a DonWeb?
   En el cPanel de Nuthost figura como dominio principal, pero conviene confirmar el DNS real.
3. OK del stack propuesto (FastAPI + SQLAlchemy + Jinja2 + HTMX) antes de armar el esqueleto.
