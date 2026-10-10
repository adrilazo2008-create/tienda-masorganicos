/* Consentimiento de cookies de medición, compartido entre masorganicos.com.ar y
   tienda.masorganicos.com.ar: se guarda en una cookie del dominio raíz (1 año) y
   en localStorage como respaldo. Valores: 'si' | 'no' | '' (sin elegir). */
window.moConsent = {
  get: function () {
    var m = document.cookie.match(/(?:^|; )mo-cookies=(si|no)(?:;|$)/);
    if (m) return m[1];
    try { var v = localStorage.getItem('mo-cookies'); if (v === 'si' || v === 'no') return v; } catch (e) {}
    return '';
  },
  _cookie: function (valor, edad) {
    var dom = /(^|\.)masorganicos\.com\.ar$/.test(location.hostname) ? '; domain=.masorganicos.com.ar' : '';
    document.cookie = 'mo-cookies=' + valor + dom + '; path=/; max-age=' + edad +
      '; SameSite=Lax' + (location.protocol === 'https:' ? '; Secure' : '');
  },
  set: function (v) {
    this._cookie(v, 31536000);
    try { localStorage.setItem('mo-cookies', v); } catch (e) {}
  },
  clear: function () {
    this._cookie('', 0);
    try { localStorage.removeItem('mo-cookies'); } catch (e) {}
  }
};
