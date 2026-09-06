# Briefing: reconstrucción de masorganicos.online

Este documento resume todo lo relevado hasta ahora sobre el proyecto de rehacer la tienda online de MasOrgánicos, para que Claude Code (en la compu de escritorio) pueda retomarlo sin perder contexto. Pegá este archivo en la carpeta del proyecto y decile a Claude Code que lo lea antes de arrancar.

## Objetivo del proyecto

Rehacer masorganicos.online: mejorarla comercialmente (hoy tiene un diagnóstico de conversión de 25/100 según una auditoría externa de ConvertMate) y cambiar la tecnología vieja por algo que Adriana pueda mantener y ampliar ella misma con Claude Code, sin depender de un desarrollador externo.

## Diagnóstico original (ConvertMate, auditoría gratuita del 5/9/2026)

Puntaje 25/100. Hallazgos críticos más relevantes:

- Sin botón de compra visible en el hero de la home.  
- Cero señales de confianza (sellos, certificaciones, prensa) antes del scroll.  
- Cero prueba social (testimonios, ratings, contador de clientes).  
- Catálogo (página de colecciones): el diagnóstico no detectó tarjetas de producto con precio — a confirmar si es un problema real o que el crawler no esperó la carga vía AJAX.  
- Performance mobile mala: LCP 6.8s, FCP 4.4s, score 61/100.  
- Menú con 9 categorías (recomendado 5-7), sin barra de anuncio/incentivo, sin sección "cómo funciona".

Nota: ConvertMate es una agencia de CRO real, pero el diagnóstico es también un lead magnet con tácticas de venta (escasez de cupos, testimonios) — separar el hallazgo técnico real del gancho comercial.

## Estado actual del sitio (lo que se está reemplazando)

- Tecnología: ASP.NET WebForms, C\#, en capas compiladas (`MasOrganicos.BLL.dll`, `.DAL.dll`, `.Entidad.dll`, `.UI.dll`). **No existe el código fuente (.cs)** — solo los binarios compilados están en el hosting. No se puede recuperar la lógica original.  
- Estructura de páginas: `Index.aspx` (home), `QuienesSomos`, `FAQ`, `ZonasyValoresEnvio`, `Producto/BusquedaProducto.aspx` \+ `InfoProducto.aspx` (catálogo), `Compra/CarritoCompra.aspx`, `Servicios/BusquedaProductoService.asmx` (web service AJAX para buscar productos), `MiCuenta/*` (login, direcciones, historial de pedidos, recuperar contraseña — sistema de cuentas completo).  
- Hosting actual: Ferozo/DonWeb (Windows/IIS), plan que corre .NET Framework 4.7 Modo Clásico. Ese mismo hosting también tiene PHP 8.3 FastCGI disponible, pero **se decidió no usar este hosting para la tienda nueva**.  
- La tienda NO procesa pagos online. El pedido se graba en la base y se levanta desde el sistema de escritorio (desarrollado en VB6 por Adriana) para el resto del proceso.

## Decisión de arquitectura tomada

- **La tienda nueva la programa Claude Code, en Python.**  
- **Se aloja en el hosting de Nuthost**, no en Ferozo. Nuthost tiene cPanel Linux moderno (Jupiter, WHM 108\) con: Setup Python App, Setup Node.js App, MultiPHP Manager, SSH, Git, phpMyAdmin, MySQL local. Solo 4.6% de disco y 3% de CPU usados — sobra margen.  
- Dominio principal que aparece en ese cPanel: `masorganicos.com.ar` (dominio viejo, distinto del `masorganicos.online` actual en Ferozo) — falta decidir cómo se apunta el dominio definitivo a la tienda nueva.  
- La base de datos **se queda donde está** (en Nuthost, no hace falta migrarla — ya está en el mismo lugar donde se aloja la tienda nueva, lo cual de hecho resuelve el problema de tener la infraestructura desparramada entre proveedores).  
- Fuera de alcance por ahora: pagos online (no se usan) y migrar la base a otro proveedor (ya está en el lugar correcto).

## Bases de datos relevadas (MySQL, en Nuthost)

Hay varias bases con nombres parecidos en el servidor — cuidado de no confundirlas: `iebbbhrt_paginaweb`, `iebbbhrt_paginawebtest`, `iebbbhrt_prueba_masorganico`, `iebbbhrt_prueba_paginaweb`, `iebbbhrt_masorganicos`, entre otras.

**`iebbbhrt_prueba_paginaweb`** — CONFIRMADA por Adriana como la base real y viva de la tienda (a pesar del nombre "prueba"), con datos de clientes reales y actuales. 28 tablas, \~105 mil filas. Tablas clave:

- `carritos` (tabla base real, no vista): `id`, `producto_id`, `cliente` (numérico), `unidadMedidaProducto`, `cantidad`, `observacion`, `porcentaje`, `tiempoCreado`, `activo`. Esto es el corazón de cómo se registran los pedidos hoy.  
- `users`, `direccion`, `zonas`, `sucursal`, `codigos_descuento`, `codigos_postales`, `newsletter`, `faq_preguntas`/`faq_respuestas`, `carrousel`, `contacto_stock`, `etiquetas`/`etiquetas_producto`, `grupos`, `transacciones`, `roles`/`role_user`.  
- Hay 6 vistas (`pedidosweb`, `pedidoscarrito`, `pedidosWebF`, `pedidosWebMO`, `carrito_abandonado`, `productoPedido`) creadas el 5/9/2026 \~23:28 por el usuario MySQL `iebbbhrt_operador@10.0.15.60` (IP interna de Nuthost) — confirmado que es trabajo de Claude Code de escritorio con acceso a la base, no de un tercero. Revisar si conviene reusar estas vistas o rehacerlas mejor entendidas desde cero.

**`iebbbhrt_masorganicos`** — la base de fondo, el ERP completo que usa el sistema de escritorio VB6 para TODO el negocio (no solo la web): 125 tablas, \~2.7 millones de filas, 378 MB. Clientes, cuentas corrientes (`cptescli`), caja (`cierre_caja`), comisiones, stock, ventas, etc. El catálogo de productos no vive en una tabla simple "producto": se resuelve con vistas como `ListArticulos` y `Stock` (pendiente de inspeccionar su definición SQL completa para saber qué columnas exponen).

## Restricción crítica de compatibilidad

El pedido que arme la tienda nueva tiene que quedar en un formato que el sistema de escritorio (VB6) pueda seguir levantando igual que hoy. Antes de tocar cualquier tabla de pedidos hay que:

1. Entender exactamente qué tabla/vista lee hoy el sistema de escritorio para procesar pedidos web (no asumir que son las vistas creadas ayer — confirmar con el código VB6 o preguntándole a Adriana).  
2. Diseñar la escritura de pedidos nuevos para que sea 100% compatible con eso, o coordinar explícitamente un cambio en ambos lados si hace falta modificarlo.

## Decisiones pendientes (para arrancar la próxima sesión)

1. **Alcance de `MiCuenta`**: ¿los clientes realmente usan cuentas con login, direcciones guardadas e historial de pedidos, o la mayoría compra sin loguearse? Esto define si se reconstruye ese sistema completo o se simplifica.  
2. **Vistas de `ListArticulos` y `Stock`** en `iebbbhrt_masorganicos`: inspeccionar su definición SQL completa para saber qué columnas exponen (precio, stock, categoría, imagen) y si son suficientes para armar el catálogo del sitio nuevo tal cual están.  
3. **Cómo apuntar el dominio**: decidir si `masorganicos.online` pasa a apuntar a Nuthost, qué pasa con `masorganicos.com.ar`, y cuándo/cómo se da de baja Ferozo.  
4. **Diseño de la nueva tabla/flujo de pedidos**, respetando la restricción de compatibilidad de arriba.

## Cómo seguir

Con este contexto, Claude Code en la compu de Adriana debería poder:

- Conectarse a `iebbbhrt_prueba_paginaweb` y `iebbbhrt_masorganicos` vía SSH/Python para inspeccionar en detalle las vistas `ListArticulos`, `Stock`, y las tablas de pedidos.  
- Confirmar con Adriana (o revisando el código VB6 si lo tiene) qué tabla exacta usa hoy el sistema de escritorio para levantar pedidos web.  
- Recién ahí, empezar a diseñar el esquema de datos y la estructura del proyecto Python nuevo.

