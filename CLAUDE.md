# Este proyecto es parte del ecosistema Más Orgánicos

Antes de trabajar acá, leé **`C:\MO-IA\CLAUDE.md`** — tiene el contexto
compartido con los demás proyectos de la carpeta (`conectar`, `dashboard`,
`finanzas`, `stock`): qué bases de datos se comparten, qué convenciones hay
que respetar (por ejemplo, `clientes.Telefonos` vs `Celular` en el ERP), y un
resumen de qué se hizo en cada uno.

Si algo de lo que trabajás acá afecta o le sirve a los otros proyectos (un
cambio de esquema en una base compartida, una convención nueva, un bug que
podría repetirse en otro lado), agregalo también en `C:\MO-IA\CLAUDE.md` y
commiteá ese cambio en el repo de esa carpeta (es un repo git aparte, propio
de la raíz del ecosistema).

## Cómo desplegar a producción (cPanel) — leer antes de pedirle nada a Adriana

El deploy de `tienda` **y** de `landing` es el mismo: un solo repo
(`tienda-masorganicos`, rama `main`) con un `.cpanel.yml` que copia los dos
sitios. Se hace a mano en cPanel, no hay deploy automático.

**Receta (funciona cuando se sigue en este orden):**
1. Commitear y hacer `git push` a `origin main` (sin esto cPanel no ve nada).
2. **Pedirle a Adriana el link de cPanel con la sesión abierta**, de la forma
   `https://mon11.servidoraweb.net:2083/cpsessXXXXXXXXXX/frontend/jupiter/index.html`.
   Es la única forma: el Chrome de Adriana no se puede "tomar" por pestaña, hay
   que abrir ese link en una pestaña propia con las herramientas
   `mcp__claude-in-chrome__*` (cargarlas con ToolSearch; `tabs_context_mcp`
   con `createIfEmpty: true`, luego `navigate`). No intentar loguearse ni
   pedir contraseñas.
3. Ir directo a
   `.../cpsessXXXXXXXXXX/frontend/jupiter/version_control/index.html`
   (ojo: es `version_control`, con guion bajo; `versioncontrol` da 404).
   Repo `tienda` -> **Administrar** -> pestaña **Pull or Deploy**.
4. **Update from Remote**, esperar el "Éxito" y verificar que el HEAD Commit
   mostrado sea el que se acaba de pushear.
5. **Deploy HEAD Commit**, y verificar que "Last Deployed SHA" sea ese commit.

**Trampas conocidas:**
- Los links `cpsess...` caducan: si da error o pide login, pedir uno nuevo.
- Los `screenshot` a veces dan timeout en cPanel: usar `get_page_text`/`find`.
- Si un click no responde, reintentar o abrir pestaña nueva.
- **"Deploy HEAD Commit" puede ser bloqueado por el clasificador de permisos
  de Claude Code** (modo auto) aunque Adriana haya pedido el deploy. Si pasa,
  no rodearlo: dejar hecho el "Update from Remote" y decirle a Adriana que
  toque ella ese botón (o que lo autorice expresamente en el chat). Para que
  no se repita, Adriana puede darle permiso a esa herramienta en la
  configuración de permisos de Claude Code.
