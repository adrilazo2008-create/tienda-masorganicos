// catálogo mobile: centrar el rubro activo en la fila deslizable
(function(){
  var fila = document.querySelector('.rubros-chips.compacta');
  if (!fila) return;
  var act = fila.querySelector('a.act');
  if (act && act.scrollIntoView) act.scrollIntoView({inline: 'center', block: 'nearest'});
})();

// + / - de cantidad, con soporte para fracciones (KG/LT)
function stepCant(btn, dir){
  var inp = btn.parentElement.querySelector('input');
  var step = parseFloat(inp.dataset.step || '1');
  var min  = parseFloat(inp.dataset.min || '1');
  var v = parseFloat((inp.value || '1').toString().replace(',', '.'));
  if (isNaN(v)) v = min;
  v = Math.round((v + step * dir) * 100) / 100;
  if (v < min) v = min;
  inp.value = Number.isInteger(v) ? v : String(v).replace('.', ',');
}

// + / - en el carrito: ajusta la cantidad y guarda (submit del form)
// Espera 450 ms después del último clic (varios clics seguidos = un solo
// pedido) y actualiza el carrito por HTMX, sin recargar la página.
var _tCarrito = {};
function stepCarrito(btn, dir){
  stepCant(btn, dir);                       // el input es hermano dentro de .cant
  var f = btn.form;
  if (!f) return;
  var idx = (f.querySelector('input[name=indice]') || {}).value;
  clearTimeout(_tCarrito[idx]);
  _tCarrito[idx] = setTimeout(function(){
    var form = document.body.contains(f) ? f : null;
    if (!form) return;
    if (window.htmx && form.requestSubmit) form.requestSubmit(); else form.submit();
  }, 450);
}

// + / - en un form con hx-post (ej. editar pedido): igual que stepCarrito pero
// con requestSubmit(), que sí dispara el evento "submit" que htmx intercepta
// (form.submit() nativo no lo dispara y termina navegando la página entera).
function stepCantHTMX(btn, dir){
  stepCant(btn, dir);
  if (btn.form) btn.form.requestSubmit();
}

// Busca el barrio/localidad conocido (barrios.json) dentro de lo que escribió la
// persona: sin importar tildes ni mayúsculas, gana la coincidencia más larga
// ("talar del lago 1" antes que "talar del lago") y se respeta "excluir"
// (ej. "tigre" no vale si también dice "pacheco").
function barrioCoincidente(barrios, q){
  var n = function(t){ return String(t).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); };
  var ql = n(q), mejor = null;
  for (var b = 0; b < barrios.length; b++){
    var x = barrios[b];
    if (!x.id_zona || ql.indexOf(x.match) === -1) continue;
    if ((x.excluir || []).some(function(e){ return ql.indexOf(e) !== -1; })) continue;
    if (!mejor || x.match.length > mejor.match.length) mejor = x;
  }
  return mejor;
}

// Zonas superpuestas (ej. "Pacheco" dentro del polígono grande de "Don
// Torcuato"): se elige la de menor área que contiene el punto, no la primera.
function zonaMasEspecifica(polis, lng, lat, pip){
  var mejor = 0, mejorArea = Infinity;
  for (var i = 0; i < polis.length; i++){
    var ring = polis[i].geometry.coordinates[0];
    if (!pip(lng, lat, ring)) continue;
    var a = 0;
    for (var k = 0, j = ring.length - 1; k < ring.length; j = k++) a += ring[j][0] * ring[k][1] - ring[k][0] * ring[j][1];
    a = Math.abs(a / 2);
    if (a < mejorArea){ mejorArea = a; mejor = polis[i].properties.id_zona || 0; }
  }
  return mejor;
}

// checkout: mostrar/ocultar bloques y recalcular total
function toggleEntrega(){
  var envio = document.querySelector('input[name=entrega][value=envio]').checked;
  document.getElementById('bloque-envio').hidden = !envio;
  document.getElementById('bloque-retira').hidden = envio;
  recalcularEnvio();
}
function recalcularEnvio(){
  var sel = document.querySelector('select[name=id_zona]');
  var subEl = document.getElementById('r-subtotal');
  var sub = parseFloat(subEl.dataset.v || '0');
  var envio = 0, info = '', detalle = '';
  var entregaEnvio = document.querySelector('input[name=entrega][value=envio]').checked;
  var modBox = document.getElementById('modalidad-envio');
  var eligeModalidad = false;

  if (entregaEnvio && sel && sel.value !== '0'){
    var o = sel.options[sel.selectedIndex];
    var precio = parseFloat(o.dataset.precio || '0');
    var gratis = parseFloat(o.dataset.gratis || '0');
    var minc   = parseFloat(o.dataset.min || '0');
    var diapre = parseFloat(o.dataset.diaprecio || '0') || precio;

    // "a coordinar" = SIEMPRE precio completo, nunca gratis.
    // "el día de la zona" = sin cargo si supera el valor de envío gratis; si no, precio del día.
    var costoCoord = precio;
    var costoDia = (gratis && sub >= gratis) ? 0 : diapre;
    eligeModalidad = costoDia < costoCoord;   // solo ofrecemos elegir si "el día" conviene

    var modalidad = 'coordinar';
    var mr = document.querySelector('input[name=modalidad_envio]:checked');
    if (mr && eligeModalidad) modalidad = mr.value;
    envio = (modalidad === 'dia') ? costoDia : costoCoord;

    if (minc && sub < minc) info = 'Compra mínima para esta zona: ' + fmtPeso(minc);
    else if (modalidad === 'dia' && envio === 0) info = 'Envío sin cargo el día que repartimos tu zona.';
    else if (eligeModalidad && costoDia === 0) info = 'Elegí “el día que pasamos por tu zona” y el envío es sin cargo.';

    var msg = (o.dataset.mensaje || '').trim();
    if (msg) detalle = msg + '.';

    var od = document.getElementById('opt-dia');
    var oc = document.getElementById('opt-coord');
    if (oc) oc.textContent = 'Día y horario a coordinar — ' + fmtPeso(precio);
    if (od) od.textContent = 'El día que pasamos por tu zona — ' + (costoDia === 0 ? 'sin cargo' : fmtPeso(diapre));
  }
  if (modBox) modBox.hidden = !eligeModalidad;

  document.getElementById('r-envio').textContent = entregaEnvio ? fmtPeso(envio) : 'retiro sin costo';
  document.getElementById('r-total').textContent = fmtPeso(sub + envio);
  var ei = document.getElementById('envio-info'); if (ei) ei.textContent = info;
  var zd = document.getElementById('zona-detalle'); if (zd) zd.textContent = detalle.trim();
}
function fmtPeso(n){ return '$' + Math.round(n).toLocaleString('es-AR'); }
function iniciarCheckout(){ toggleEntrega(); iniciarBuscaZona(); }

// checkout: buscar dirección -> autocompletar zona + calle/altura/localidad
function iniciarBuscaZona(){
  var inp = document.getElementById('cz-dir');
  var btn = document.getElementById('cz-btn');
  var msg = document.getElementById('cz-msg');
  var sel = document.getElementById('sel-zona');
  var form = document.getElementById('form-checkout');
  if (!inp || !btn || !sel || !form || inp.dataset.listo) return;
  inp.dataset.listo = '1';

  var polis = [];
  fetch('/envios/zonas.geojson').then(function(r){ return r.json(); }).then(function(geo){
    (geo.features || []).forEach(function(f){
      if (f.geometry && f.geometry.type === 'Polygon') polis.push(f);
    });
  }).catch(function(){});

  var barrios = [];
  fetch('/envios/barrios.json').then(function(r){ return r.json(); })
    .then(function(d){ barrios = d || []; }).catch(function(){});

  function limpiarDireccion(){
    form.direccion.value = '';
    form.altura.value = '';
    form.localidad.value = '';
  }
  function fijarZona(zid, textoOk){
    if (zid && tieneOpcion(zid)){
      sel.value = String(zid);
      recalcularEnvio();
      msg.textContent = textoOk;
      return true;
    }
    return false;
  }

  function pip(x, y, ring){
    var dentro = false;
    for (var i = 0, j = ring.length - 1; i < ring.length; j = i++){
      var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) dentro = !dentro;
    }
    return dentro;
  }
  function tieneOpcion(v){
    for (var i = 0; i < sel.options.length; i++) if (sel.options[i].value == v) return true;
    return false;
  }
  function opcionTexto(v){
    for (var i = 0; i < sel.options.length; i++)
      if (sel.options[i].value == v) return sel.options[i].text.split(' — ')[0];
    return '';
  }

  function buscar(){
    var q = (inp.value || '').trim();
    if (q.length < 4){ msg.textContent = 'Escribí tu dirección con la localidad.'; return; }
    limpiarDireccion();
    sel.value = '0'; recalcularEnvio();

    // 1) ¿es un barrio / country conocido? (Nordelta, barrios privados, etc.)
    var bar = barrioCoincidente(barrios, q);
    if (bar){
      form.localidad.value = bar.etiqueta;
      var nro0 = (q.match(/\b(\d{1,5})\b/) || [])[1];
      if (nro0) form.altura.value = nro0;
      if (fijarZona(bar.id_zona,
            'Barrio reconocido: ' + bar.etiqueta +
            '. Completá calle / lote / casa. Revisá la zona.')) {
        btn.disabled = false; btn.textContent = 'Detectar';
        return;
      }
    }

    // 2) geocodificar la dirección
    btn.disabled = true; btn.textContent = 'Buscando…';
    var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=1&countrycodes=ar&q='
      + encodeURIComponent(q + ', Buenos Aires, Argentina');
    fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (!d || !d.length){
          msg.textContent = 'No encontramos esa dirección. Completá calle, altura y localidad, y elegí la zona en la lista.';
          return;
        }
        var h = d[0], lat = parseFloat(h.lat), lng = parseFloat(h.lon), a = h.address || {};
        if (a.road) form.direccion.value = a.road;
        var nro = a.house_number || (q.match(/\b(\d{1,5})\b/) || [])[1];
        if (nro) form.altura.value = nro;
        var loc = a.city || a.town || a.village || a.suburb || a.city_district || a.municipality || '';
        if (loc) form.localidad.value = loc;

        var zid = zonaMasEspecifica(polis, lng, lat, pip);
        var ok = fijarZona(zid, 'Zona detectada: ' + opcionTexto(zid) +
              '. Revisá que sea correcta y ajustá si hace falta.');
        if (!ok){
          msg.textContent = 'Completamos tu dirección, pero no pudimos detectar la zona — elegila en la lista.';
        }
      })
      .catch(function(){ msg.textContent = 'No pudimos buscar ahora. Elegí la zona en la lista.'; })
      .finally(function(){ btn.disabled = false; btn.textContent = 'Detectar'; });
  }

  btn.addEventListener('click', buscar);
  inp.addEventListener('keydown', function(e){ if (e.key === 'Enter'){ e.preventDefault(); buscar(); } });
}

// toasts: quitar cada uno después de unos segundos + evento AddToCart (Meta)
document.body.addEventListener('htmx:afterSwap', function(e){
  if (e.detail && e.detail.target && e.detail.target.id === 'toasts'){
    var t = e.detail.target.firstElementChild;
    if (t && !t.dataset.timed){
      t.dataset.timed = '1';
      if (window.fbq) fbq('track', 'AddToCart');
      if (window.clarity) clarity('event', 'agregar_al_carrito');
      setTimeout(function(){ t.style.opacity = '0'; setTimeout(function(){ t.remove(); }, 220); }, 2600);
    }
  }
});

// carrusel de la home: scroll-snap + auto-avance + dots
document.addEventListener('DOMContentLoaded', function(){
  var track = document.getElementById('carrusel-track');
  if (!track) return;
  var car = track.closest('.carrusel');
  var slides = track.children;
  var dots = car.querySelectorAll('.carrusel-dots button');
  var i = 0, timer = null, animando = 0;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function marcarDots(){
    dots.forEach(function(d, k){ d.setAttribute('aria-selected', k === i ? 'true' : 'false'); });
  }
  function ir(n){
    i = (n + slides.length) % slides.length;
    // durante el scroll programado, ignoramos el listener de scroll (si no,
    // lee una posición intermedia y corrompe el índice).
    clearTimeout(animando); animando = setTimeout(function(){ animando = 0; }, 500);
    track.scrollTo({ left: i * track.clientWidth, behavior: reduce ? 'auto' : 'smooth' });
    marcarDots();
  }
  function arrancar(){ if (!reduce) timer = setInterval(function(){ ir(i + 1); }, 5000); }
  function parar(){ clearInterval(timer); }

  car.querySelector('.carrusel-nav.prev').addEventListener('click', function(){ ir(i - 1); parar(); arrancar(); });
  car.querySelector('.carrusel-nav.next').addEventListener('click', function(){ ir(i + 1); parar(); arrancar(); });
  dots.forEach(function(d, k){ d.addEventListener('click', function(){ ir(k); parar(); arrancar(); }); });

  // sincronizar dots cuando el usuario hace swipe (no cuando scrollea ir())
  var st;
  track.addEventListener('scroll', function(){
    clearTimeout(st);
    st = setTimeout(function(){
      if (animando) return;
      var n = Math.round(track.scrollLeft / track.clientWidth);
      if (n >= 0 && n < slides.length && n !== i){ i = n; marcarDots(); }
    }, 140);
  });

  car.addEventListener('mouseenter', parar);
  car.addEventListener('mouseleave', arrancar);
  car.addEventListener('focusin', parar);
  arrancar();
});

// checkout: si venimos del browser in-app de Instagram/Facebook en Android,
// escapar a Chrome antes de cerrar el pedido (ese webview es la causa de la
// mayoría de los errores JS/postMessage que reportó Clarity). En iOS no hay
// forma confiable de forzar el navegador externo desde JS (restricción de
// Apple/WebKit), así que ahí se sigue el flujo normal dentro de la app.
// Se abre siempre en la MISMA url de checkout, para que la persona la
// termine de cerrar ya en Chrome — no hay forma de pasarle el carrito de un
// navegador a otro (son cookies de sesión separadas), pero adentro del
// webview el pedido no estaba llegando a cerrarse de todos modos.
function escaparSiEsWebviewMeta(){
  var ua = navigator.userAgent || '';
  var esWebviewMeta = /Instagram|FBAN|FBAV|FB_IAB/i.test(ua);
  var esAndroid = /Android/i.test(ua);
  if (!esWebviewMeta || !esAndroid) return false;
  var url = location.href;
  var sinEsquema = url.replace(/^https?:\/\//, '');
  var fallback = encodeURIComponent(url);
  location.href = 'intent://' + sinEsquema + '#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=' + fallback + ';end';
  return true;
}

// checkout: evitar doble submit y hacer foco en el primer error
document.addEventListener('DOMContentLoaded', function(){
  var f = document.getElementById('form-checkout');
  if (f) f.addEventListener('submit', function(e){
    if (escaparSiEsWebviewMeta()){ e.preventDefault(); return; }
    var b = document.getElementById('btn-confirmar');
    if (b){ b.disabled = true; b.textContent = 'Enviando…'; }
  });
  var err = document.getElementById('checkout-error') || document.getElementById('login-error');
  if (err) err.focus();
});

/* volver a la lista en el mismo punto -------------------------------------- */
(function(){
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

  var esLista = location.pathname === '/' || location.pathname.indexOf('/catalogo') === 0;
  var clave = 'scroll:' + location.pathname + location.search;

  function guardarScroll(){
    try { sessionStorage.setItem(clave, String(window.pageYOffset)); } catch (e) {}
  }

  if (!esLista) return;

  // marcar al entrar a una ficha de producto desde esta lista
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[href*="/producto/"]');
    if (a){ guardarScroll(); try { sessionStorage.setItem('volverLista', '1'); } catch (x) {} }
  });
  var tId;
  window.addEventListener('scroll', function(){
    clearTimeout(tId); tId = setTimeout(guardarScroll, 200);
  }, { passive: true });
  window.addEventListener('pagehide', guardarScroll);

  // restaurar el scroll si volvemos de una ficha de producto
  try {
    var volviendo = sessionStorage.getItem('volverLista') === '1' ||
                    /\/producto\//.test(document.referrer || '');
    var y = sessionStorage.getItem(clave);
    sessionStorage.removeItem('volverLista');
    if (volviendo && y){
      var yy = parseInt(y, 10);
      window.scrollTo(0, yy);
      requestAnimationFrame(function(){ window.scrollTo(0, yy); });
      setTimeout(function(){ window.scrollTo(0, yy); }, 150);
    }
  } catch (e) {}
})();

// botón "← Volver" de la ficha de producto
function volverALista(e){
  if (e && e.preventDefault) e.preventDefault();
  var ref = document.referrer || '';
  if (ref.indexOf(location.origin) === 0 && history.length > 1) history.back();
  else location.href = '/catalogo';
}

// ficha de producto: al agregar al carrito, volver a lo que estabas viendo
document.addEventListener('DOMContentLoaded', function(){
  var f = document.querySelector('form.prod-add');
  if (!f) return;
  f.addEventListener('htmx:afterRequest', function(e){
    if (e.detail && e.detail.successful) setTimeout(volverALista, 900);
  });
});

// Navegador interno de Instagram/Facebook: avisar antes de que arme el pedido.
// (~43% de las visitas llegan ahí y casi ningún pedido termina; en Android el
// checkout ya escapa a Chrome, pero iOS no tiene forma de forzarlo.)
document.addEventListener('DOMContentLoaded', function(){
  var ua = navigator.userAgent || '';
  if (!/Instagram|FBAN|FBAV|FB_IAB/i.test(ua)) return;
  try { if (sessionStorage.getItem('aviso-webview-cerrado')) return; } catch(e){}
  var esIos = /iPhone|iPad|iPod/i.test(ua);
  var d = document.createElement('div');
  d.className = 'aviso-webview';
  d.setAttribute('role', 'note');
  d.innerHTML = '<p><b>Para comprar más fácil:</b> abrí esta página en ' +
    (esIos ? 'Safari (tocá los <b>···</b> o el ícono de compartir y elegí “Abrir en Safari”)'
           : 'Chrome (tocá los <b>⋮</b> y elegí “Abrir en el navegador”)') + '.</p>' +
    '<button type="button" aria-label="Cerrar aviso">×</button>';
  d.querySelector('button').addEventListener('click', function(){
    d.remove(); try { sessionStorage.setItem('aviso-webview-cerrado', '1'); } catch(e){}
  });
  document.body.insertBefore(d, document.body.firstChild);
  if (window.clarity) clarity('set', 'navegador', 'instagram_facebook');
});

// Clarity: etiquetar visitas internas. Entrar una vez con ?interno=1 las marca
// en este navegador (?interno=0 la quita). Se aplica apenas Clarity carga.
(function(){
  try {
    var m = /[?&]interno=([01])/.exec(location.search);
    if (m) localStorage.setItem('mo-interno', m[1]);
    if (m) document.cookie = 'mo_interno=' + m[1] + '; path=/; max-age=' + (m[1] === '1' ? 63072000 : 0) + '; SameSite=Lax';
  } catch(e){}
})();
window.etiquetarClarity = function(){
  if (!window.clarity) return;
  var interno = false;
  try { interno = localStorage.getItem('mo-interno') === '1'; } catch(e){}
  clarity('set', 'visita', interno ? 'interna' : 'cliente');
  if (interno) clarity('upgrade', 'visita_interna');
};

// "¿Cuánto sale el envío a tu zona?" (ficha de producto y carrito): detecta la
// zona por barrio conocido o por geocodificación (misma lógica que el
// checkout) y muestra el costo de la tabla `zonas`. Si no la encuentra,
// manda a la lista de zonas y valores (/envios). Recuerda la zona elegida.
(function(){
  var datos = null, polis = null, barrios = null;
  function cargar(){
    if (datos) return Promise.resolve();
    return Promise.all([
      fetch('/envios/zonas.json').then(function(r){ return r.json(); }),
      fetch('/envios/zonas.geojson').then(function(r){ return r.json(); }),
      fetch('/envios/barrios.json').then(function(r){ return r.json(); }).catch(function(){ return []; })
    ]).then(function(r){
      datos = r[0]; barrios = r[2] || [];
      polis = ((r[1] || {}).features || []).filter(function(f){ return f.geometry && f.geometry.type === 'Polygon'; });
    });
  }
  function pip(x, y, ring){
    var d = false;
    for (var i = 0, j = ring.length - 1; i < ring.length; j = i++){
      var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) d = !d;
    }
    return d;
  }
  function pesos(n){ return '$' + Math.round(n).toLocaleString('es-AR'); }
  function esc(t){ var d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

  function mostrarZona(res, zid){
    var z = datos[String(zid)];
    if (!z) return noEncontrada(res);
    try { localStorage.setItem('mo-zona', String(zid)); } catch(e){}
    var h = '<b>' + esc(z.titulo) + '</b><br>' +
      'Envío con día y horario a coordinar: <b>' + pesos(z.precio) + '</b>.<br>' +
      'El día que repartimos tu zona: <b>' + (z.precio_dia ? pesos(z.precio_dia) : 'sin cargo') + '</b>' +
      (z.gratis ? ' (sin cargo desde ' + pesos(z.gratis) + ')' : '') + '.';
    if (z.mensaje) h += '<br><small>' + esc(z.mensaje) + '</small>';
    if (z.minimo) h += '<br><small>Compra mínima en tu zona: ' + pesos(z.minimo) + '.</small>';
    res.innerHTML = h;
  }
  function sinTildes(t){ return String(t).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  function mostrarVarias(res, ids){
    var h = 'Hay más de una zona con ese nombre — el costo depende de dónde estés:<ul class="ce-lista">';
    ids.forEach(function(k){
      var z = datos[k];
      h += '<li><b>' + esc(z.titulo) + '</b>: ' + pesos(z.precio) + ' a coordinar · ' +
           (z.precio_dia ? pesos(z.precio_dia) : 'sin cargo') + ' el día de reparto</li>';
    });
    res.innerHTML = h + '</ul>Escribí tu <b>calle y altura</b> (ej. “Av. Hipólito Yrigoyen 1200, Pacheco”) ' +
      'y te decimos cuál es la tuya.';
  }
  function noEncontrada(res){
    res.innerHTML = 'No pudimos ubicar tu zona. Probá con calle y altura, o <a href="/envios">mirá la lista de zonas y valores</a> ' +
      'o <a href="https://wa.me/5491155046740" target="_blank" rel="noopener">consultanos por WhatsApp</a>.';
  }

  function buscar(q, res, btn){
    var bar = barrioCoincidente(barrios, q);
    if (bar) return mostrarZona(res, bar.id_zona);
    // Nombre de localidad que coincide con el título de una o más zonas
    // ("Pacheco" -> Pacheco / Pacheco (Barrios Privados)): no hace falta mapa.
    if (!/\d/.test(q) && q.length >= 4){
      var qn = sinTildes(q);
      var hits = Object.keys(datos).filter(function(k){ return sinTildes(datos[k].titulo).indexOf(qn) !== -1; });
      if (hits.length === 1) return mostrarZona(res, hits[0]);
      if (hits.length > 1) return mostrarVarias(res, hits);
    }
    // Sin número no geocodificamos: devuelve el centro del partido/localidad y
    // puede caer en una zona equivocada. Mejor pedir calle y altura.
    if (!/\d/.test(q)){
      res.innerHTML = 'No reconocimos ese nombre. Escribí tu <b>calle y altura</b> con la localidad ' +
        '(ej. “Av. Hipólito Yrigoyen 1200, Pacheco”), o <a href="/envios">mirá la lista de zonas y valores</a>.';
      return;
    }
    btn.disabled = true;
    var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&countrycodes=ar&q=' +
      encodeURIComponent(q + ', Buenos Aires, Argentina');
    var tieneAltura = /\d/.test(q);
    fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function(r){ return r.json(); })
      .then(function(d){
        // Sin número es una localidad/barrio ("Pacheco"): una calle homónima
        // (ej. calle Pacheco de Villa Urquiza) daría la zona equivocada.
        if (d && !tieneAltura) d = d.filter(function(h){ return h.category !== 'highway'; });
        if (!d || !d.length) return noEncontrada(res);
        var lat = parseFloat(d[0].lat), lng = parseFloat(d[0].lon);
        var zid = zonaMasEspecifica(polis, lng, lat, pip);
        zid ? mostrarZona(res, zid) : noEncontrada(res);
      })
      .catch(function(){ noEncontrada(res); })
      .finally(function(){ btn.disabled = false; });
  }

  function iniciar(){
    document.querySelectorAll('#consulta-envio:not([data-listo])').forEach(function(box){
      box.dataset.listo = '1';
      var abrir = box.querySelector('.ce-abrir'), panel = box.querySelector('.ce-panel');
      var form = box.querySelector('.ce-form'), inp = box.querySelector('.ce-dir');
      var res = box.querySelector('.ce-res'), btn = form.querySelector('button');
      abrir.addEventListener('click', function(){
        panel.hidden = !panel.hidden;
        abrir.setAttribute('aria-expanded', String(!panel.hidden));
        if (panel.hidden) return;
        if (window.clarity) clarity('event', 'consulta_envio_abrir');
        cargar().then(function(){
          var guardada = '';
          try { guardada = localStorage.getItem('mo-zona') || ''; } catch(e){}
          if (guardada && !res.innerHTML) mostrarZona(res, guardada);
        });
        inp.focus();
      });
      form.addEventListener('submit', function(e){
        e.preventDefault();
        var q = (inp.value || '').trim();
        if (q.length < 3){ res.textContent = 'Escribí tu barrio o dirección con la localidad.'; return; }
        res.textContent = 'Buscando…';
        cargar().then(function(){ buscar(q, res, btn); });
      });
    });
  }
  document.addEventListener('DOMContentLoaded', iniciar);
  document.body.addEventListener('htmx:afterSwap', iniciar);   // el carrito se re-dibuja por HTMX
})();
