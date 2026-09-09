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
function stepCarrito(btn, dir){
  stepCant(btn, dir);                       // el input es hermano dentro de .cant
  if (btn.form) btn.form.submit();
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
    var ql = q.toLowerCase();
    for (var b = 0; b < barrios.length; b++){
      if (ql.indexOf(barrios[b].match) !== -1){
        form.localidad.value = barrios[b].etiqueta;
        var nro0 = (q.match(/\b(\d{1,5})\b/) || [])[1];
        if (nro0) form.altura.value = nro0;
        if (fijarZona(barrios[b].id_zona,
              'Barrio reconocido: ' + barrios[b].etiqueta +
              '. Completá calle / lote / casa. Revisá la zona.')) {
          btn.disabled = false; btn.textContent = 'Detectar';
          return;
        }
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

        var zid = 0;
        for (var i = 0; i < polis.length; i++){
          if (pip(lng, lat, polis[i].geometry.coordinates[0])){ zid = polis[i].properties.id_zona || 0; break; }
        }
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

// toasts: quitar cada uno después de unos segundos
document.body.addEventListener('htmx:afterSwap', function(e){
  if (e.detail && e.detail.target && e.detail.target.id === 'toasts'){
    var t = e.detail.target.firstElementChild;
    if (t && !t.dataset.timed){
      t.dataset.timed = '1';
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
  var i = 0, timer = null;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ir(n){
    i = (n + slides.length) % slides.length;
    track.scrollTo({ left: slides[i].offsetLeft, behavior: reduce ? 'auto' : 'smooth' });
    dots.forEach(function(d, k){ d.setAttribute('aria-selected', k === i ? 'true' : 'false'); });
  }
  function arrancar(){ if (!reduce) timer = setInterval(function(){ ir(i + 1); }, 5000); }
  function parar(){ clearInterval(timer); }

  car.querySelector('.carrusel-nav.prev').addEventListener('click', function(){ ir(i - 1); parar(); arrancar(); });
  car.querySelector('.carrusel-nav.next').addEventListener('click', function(){ ir(i + 1); parar(); arrancar(); });
  dots.forEach(function(d, k){ d.addEventListener('click', function(){ ir(k); parar(); arrancar(); }); });

  // sincronizar dots cuando el usuario hace swipe
  var st;
  track.addEventListener('scroll', function(){
    clearTimeout(st);
    st = setTimeout(function(){
      var n = Math.round(track.scrollLeft / track.clientWidth);
      if (n !== i){ i = n; dots.forEach(function(d, k){ d.setAttribute('aria-selected', k === i ? 'true' : 'false'); }); }
    }, 120);
  });

  car.addEventListener('mouseenter', parar);
  car.addEventListener('mouseleave', arrancar);
  car.addEventListener('focusin', parar);
  arrancar();
});

// checkout: evitar doble submit y hacer foco en el primer error
document.addEventListener('DOMContentLoaded', function(){
  var f = document.getElementById('form-checkout');
  if (f) f.addEventListener('submit', function(){
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
