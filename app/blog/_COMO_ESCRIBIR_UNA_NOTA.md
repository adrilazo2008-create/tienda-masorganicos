---
borrador: true
titulo: Cómo escribir una nota (este archivo no se publica)
fecha: 2026-01-01
---

Para publicar una nota nueva:

1. Creá un archivo en esta carpeta con el nombre  `AAAA-MM-DD-titulo-corto.md`
   (ej. `2026-10-01-recetas-de-zapallo.md`). La fecha del nombre y la URL salen de ahí.
2. Arriba de todo va el bloque entre `---` con los datos:

   ```
   ---
   titulo: El título que se ve en la página
   fecha: 2026-10-01
   resumen: Una o dos líneas para el listado y para cuando se comparte en redes.
   portada: zapallo.jpg      (opcional; el archivo va en el servidor, en assets/img/blog/)
   autor: Más Orgánicos      (opcional)
   borrador: true            (opcional; mientras esté, la nota NO se publica)
   ---
   ```

3. Debajo, el cuerpo en Markdown normal:
   - `## Subtítulo`
   - `**negrita**`, `*cursiva*`
   - listas con `-`
   - links: `[texto](https://...)`
   - imágenes: `![](/img/blog/foto.jpg)`

4. Guardar, `git commit`, `git push` y desplegar como siempre. La nota aparece sola.

Para **despublicar** una nota: agregale `borrador: true` en el bloque de arriba
(no hace falta borrar el archivo).
