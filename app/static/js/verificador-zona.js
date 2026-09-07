/* Verificador de zona de reparto para /envios.
   Muestra las zonas (GeoJSON), geocodifica una dirección (Nominatim / OSM),
   pone un pin arrastrable y dice si cae dentro de alguna zona. */
function iniciarVerificadorZona() {
  var elMapa = document.getElementById('mapa-zonas');
  if (!elMapa || elMapa.dataset.listo) return;
  if (typeof L === 'undefined') { window.addEventListener('load', iniciarVerificadorZona); return; }
  elMapa.dataset.listo = '1';

  var CENTRO = [-34.47, -58.60];
  var mapa = L.map('mapa-zonas', { scrollWheelZoom: false }).setView(CENTRO, 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap'
  }).addTo(mapa);

  var poligonos = [];      // array de arrays de [lng,lat]
  var capaZonas = null;

  fetch(elMapa.dataset.geojson || '/envios/zonas.geojson')
    .then(function (r) { return r.json(); })
    .then(function (geo) {
      capaZonas = L.geoJSON(geo, {
        style: { color: '#2f7d31', weight: 2, fillColor: '#2f7d31', fillOpacity: 0.12 }
      }).addTo(mapa);
      try { mapa.fitBounds(capaZonas.getBounds().pad(0.05)); } catch (e) {}
      (geo.features || []).forEach(function (f) {
        if (f.geometry && f.geometry.type === 'Polygon') {
          poligonos.push({ anillo: f.geometry.coordinates[0], props: f.properties || {} });
        }
      });
    })
    .catch(function () {
      mostrar('No pudimos cargar el mapa. Escribinos por WhatsApp y coordinamos.', 'warn');
    });

  var marcador = null;
  var iconoPin = L.divIcon({
    className: 'pin-zona', html: '<span></span>',
    iconSize: [26, 26], iconAnchor: [13, 26]
  });

  var form = document.getElementById('form-zona');
  var input = document.getElementById('dir-zona');
  var btn = form.querySelector('button');
  var res = document.getElementById('zona-resultado');

  function geocodificar(q) {
    var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=ar&q='
      + encodeURIComponent(q);
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) { return (d && d.length) ? d[0] : null; });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = (input.value || '').trim();
    if (q.length < 4) { mostrar('Escribí tu dirección con la localidad.', 'warn'); return; }
    btn.disabled = true; btn.textContent = 'Buscando…';

    var conPais = q + ', Buenos Aires, Argentina';
    var sinAltura = q.replace(/\s*\d+\s*/, ' ').replace(/\s+/g, ' ').trim() + ', Buenos Aires, Argentina';

    geocodificar(conPais)
      .then(function (hit) {
        if (hit) {
          var lat = parseFloat(hit.lat), lng = parseFloat(hit.lon);
          ponerPin(lat, lng, false);
          mapa.setView([lat, lng], 14);
          evaluar(lat, lng);
          return;
        }
        // sin resultado exacto -> probar solo con la calle y la localidad
        return geocodificar(sinAltura).then(function (calle) {
          if (calle) {
            var la = parseFloat(calle.lat), lo = parseFloat(calle.lon);
            ponerPin(la, lo, false);
            mapa.setView([la, lo], 14);
            mostrar('Encontramos la calle pero no la altura exacta. Arrastrá el pin hasta tu casa y te confirmo.', 'warn');
          } else {
            mostrar('No encontramos esa dirección. Arrastrá el pin hasta tu casa, o escribinos por WhatsApp.', 'warn');
            ponerPin(CENTRO[0], CENTRO[1], true);
          }
        });
      })
      .catch(function () {
        mostrar('No pudimos verificar ahora. Arrastrá el pin hasta tu casa o escribinos por WhatsApp.', 'warn');
        ponerPin(CENTRO[0], CENTRO[1], true);
      })
      .finally(function () { btn.disabled = false; btn.textContent = 'Verificar'; });
  });

  function ponerPin(lat, lng, avisar) {
    if (marcador) { marcador.setLatLng([lat, lng]); }
    else {
      marcador = L.marker([lat, lng], { icon: iconoPin, draggable: true }).addTo(mapa);
      marcador.on('dragend', function () {
        var p = marcador.getLatLng();
        evaluar(p.lat, p.lng);
      });
    }
    if (avisar) {
      mapa.setView([lat, lng], 12);
    }
  }

  function plata(n) {
    return '$' + (n || 0).toLocaleString('es-AR');
  }

  function evaluar(lat, lng) {
    if (!poligonos.length) return;
    var zona = null;
    for (var i = 0; i < poligonos.length; i++) {
      if (puntoEnPoligono(lng, lat, poligonos[i].anillo)) { zona = poligonos[i].props; break; }
    }
    if (zona) {
      var p = [];
      if (zona.precio) {
        var linea = 'envío aprox. ' + plata(zona.precio);
        if (zona.precio_dia && zona.precio_dia < zona.precio) {
          linea += ' (' + plata(zona.precio_dia) + ' el día que repartimos tu zona)';
        }
        p.push(linea);
      }
      if (zona.minimo) p.push('pedido mínimo ' + plata(zona.minimo));
      if (zona.gratis) p.push('envío gratis desde ' + plata(zona.gratis));
      var detalle = p.length ? ' — ' + p.join(' · ') + '.' : '';
      mostrar('✅ ¡Sí, llegamos a tu zona!' + detalle +
        ' El costo exacto se calcula al hacer el pedido; coordinamos día y horario por WhatsApp.', 'ok');
    } else {
      mostrar('Esa dirección quedó fuera de las zonas de reparto habituales. Escribinos por WhatsApp así lo confirmamos — a veces llegamos igual.', 'warn');
    }
  }

  function mostrar(texto, tipo) {
    res.textContent = texto;
    res.className = 'verif-res ' + (tipo === 'ok' ? 'verif-ok' : 'verif-warn');
    res.hidden = false;
  }

  // ray casting; anillo = [[lng,lat], ...]
  function puntoEnPoligono(x, y, anillo) {
    var dentro = false;
    for (var i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
      var xi = anillo[i][0], yi = anillo[i][1];
      var xj = anillo[j][0], yj = anillo[j][1];
      var cruza = ((yi > y) !== (yj > y)) &&
        (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
      if (cruza) dentro = !dentro;
    }
    return dentro;
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', iniciarVerificadorZona);
} else {
  iniciarVerificadorZona();
}
