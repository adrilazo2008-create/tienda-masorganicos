/* Atribución de pedidos a anuncios: guarda utm_* y fbclid de la URL en cookie Y localStorage
   (30 días) y los agrega como campos ocultos al formulario del checkout.
   - Una URL sin parámetros nunca pisa lo guardado; solo una URL nueva con parámetros lo reemplaza.
   - El navegador interno de Instagram pierde el estado fácilmente: por eso las dos copias.
   Es un respaldo de la sesión del servidor (atribucion.py): si esto falla, el pedido igual
   se atribuye con lo que haya en la sesión. Nada de acá puede romper la página. */
(function () {
  var CLAVES = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid'];
  var NOMBRE = 'mo_atrib';
  var DIAS = 30;

  function desdeUrl() {
    var out = {}, qs;
    try { qs = new URLSearchParams(location.search); } catch (e) { return out; }
    CLAVES.forEach(function (k) {
      var v = (qs.get(k) || '').trim();
      if (v) out[k] = v.slice(0, 200);
    });
    return out;
  }

  function vigente(o) {
    return o && typeof o === 'object' && o.ts && (Date.now() - o.ts) < DIAS * 86400000;
  }

  function leerCookie() {
    try {
      var m = document.cookie.match(new RegExp('(?:^|; )' + NOMBRE + '=([^;]*)'));
      var o = m ? JSON.parse(decodeURIComponent(m[1])) : null;
      return vigente(o) ? o : null;
    } catch (e) { return null; }
  }

  function leerLocal() {
    try {
      var o = JSON.parse(localStorage.getItem(NOMBRE) || 'null');
      return vigente(o) ? o : null;
    } catch (e) { return null; }
  }

  function guardar(o) {
    try { localStorage.setItem(NOMBRE, JSON.stringify(o)); } catch (e) {}
    try {
      var dom = /(^|\.)masorganicos\.com\.ar$/.test(location.hostname) ? '; domain=.masorganicos.com.ar' : '';
      document.cookie = NOMBRE + '=' + encodeURIComponent(JSON.stringify(o)) + dom +
        '; path=/; max-age=' + (DIAS * 86400) + '; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : '');
    } catch (e) {}
  }

  function actual() {
    var nuevo = desdeUrl();
    if (Object.keys(nuevo).length) {
      nuevo.ts = Date.now();
      guardar(nuevo);
      return nuevo;
    }
    var o = leerCookie() || leerLocal();
    if (o && !leerCookie()) guardar(o);      // se perdió una de las dos copias: se repone
    return o || {};
  }

  function poblar(form) {
    var o = actual();
    CLAVES.forEach(function (k) {
      var inp = form.querySelector('input[name="' + k + '"]');
      if (!inp) {
        inp = document.createElement('input');
        inp.type = 'hidden'; inp.name = k;
        form.appendChild(inp);
      }
      inp.value = o[k] || '';
    });
  }

  try {
    actual();
    var iniciar = function () {
      var f = document.getElementById('form-checkout');
      if (!f) return;
      poblar(f);
      f.addEventListener('submit', function () { poblar(f); }, true);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
    else iniciar();
  } catch (e) {}
})();
