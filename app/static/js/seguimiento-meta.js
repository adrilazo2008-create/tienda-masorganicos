/* Seguimiento de la landing para Meta Ads (se carga en las páginas del sitio, no en la tienda).
   1) Guarda utm_* y fbclid de la URL de entrada y los agrega a TODOS los enlaces a la tienda,
      para saber de qué anuncio vino cada pedido.
   2) Eventos del Pixel: Lead (enlaces a la tienda) y ClickWhatsApp (enlaces a wa.me).
      Solo se disparan si la persona aceptó las cookies (si no, fbq no existe y no pasa nada).
   3) Cookie _fbc a partir de fbclid, en el dominio raíz, para que la tienda la lea.
      Solo se escribe con consentimiento (la llama cargarPixel). */
(function () {
  var CLAVES = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'fbclid'];
  var ALM = 'mo-atribucion';

  function leerUrl() {
    var out = {}, qs;
    try { qs = new URLSearchParams(location.search); } catch (e) { return out; }
    CLAVES.forEach(function (k) { var v = qs.get(k); if (v) out[k] = v; });
    return out;
  }

  /* Los de la URL actual pisan a los guardados; si la persona navega por el sitio
     (sin parámetros en la URL) se siguen usando los de la entrada. */
  function atribucion() {
    var guardado = {};
    try { guardado = JSON.parse(sessionStorage.getItem(ALM) || '{}') || {}; } catch (e) {}
    var actual = leerUrl();
    if (Object.keys(actual).length) {
      guardado = actual;
      try { sessionStorage.setItem(ALM, JSON.stringify(guardado)); } catch (e) {}
    }
    return guardado;
  }

  function esTienda(a) {
    return a && a.hostname && /^(www\.)?tienda\./.test(a.hostname);
  }
  function esWhatsapp(a) {
    return a && a.hostname && /(^|\.)wa\.me$|(^|\.)whatsapp\.com$/.test(a.hostname);
  }

  function decorar(a, attr) {
    var u;
    try { u = new URL(a.href); } catch (e) { return; }
    Object.keys(attr).forEach(function (k) { u.searchParams.set(k, attr[k]); });
    a.href = u.toString();
  }

  function decorarTodos() {
    var attr = atribucion();
    if (!Object.keys(attr).length) return;
    document.querySelectorAll('a[href]').forEach(function (a) {
      if (esTienda(a)) decorar(a, attr);
    });
  }

  function rastrear(tipo, nombre) {
    try { if (window.fbq) window.fbq(tipo, nombre); } catch (e) {}
  }

  document.addEventListener('click', function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href]');
    if (!a) return;
    if (esTienda(a)) { decorar(a, atribucion()); rastrear('track', 'Lead'); }
    else if (esWhatsapp(a)) rastrear('trackCustom', 'ClickWhatsApp');
  }, true);

  /* _fbc = fb.1.<ms>.<fbclid>, mismo formato que genera el Pixel. Dominio raíz para
     que lo lea tienda.masorganicos.com.ar. No pisa una _fbc del mismo fbclid. */
  window.moGuardarFbc = function () {
    var fbclid = leerUrl().fbclid || atribucion().fbclid;
    if (!fbclid) return;
    if (document.cookie.split('; ').some(function (c) {
      return c.indexOf('_fbc=') === 0 && c.slice(-fbclid.length) === fbclid;
    })) return;
    var host = location.hostname, dom = '';
    if (/(^|\.)masorganicos\.com\.ar$/.test(host)) dom = '; domain=.masorganicos.com.ar';
    document.cookie = '_fbc=fb.1.' + Date.now() + '.' + encodeURIComponent(fbclid) +
      dom + '; path=/; max-age=7776000; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : '');
  };

  atribucion();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', decorarTodos);
  else decorarTodos();
})();
