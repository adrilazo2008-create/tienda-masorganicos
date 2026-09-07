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

  fetch('/static/data/zonas_reparto.geojson')
    .then(function (r) { return r.json(); })
    .then(function (geo) {
      capaZonas = L.geoJSON(geo, {
        style: { color: '#2f7d31', weight: 2, fillColor: '#2f7d31', fillOpacity: 0.12 }
      }).addTo(mapa);
      try { mapa.fitBounds(capaZonas.getBounds().pad(0.05)); } catch (e) {}
      (geo.features || []).forEach(function (f) {
        if (f.geometry && f.geometry.type === 'Polygon') {
          poligonos.push(f.geometry.coordinates[0]);
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

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = (input.value || '').trim();
    if (q.length < 4) { mostrar('Escribí tu dirección con la localidad.', 'warn'); return; }
    btn.disabled = true; btn.textContent = 'Buscando…';
    var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=ar&q='
      + encodeURIComponent(q + ', Buenos Aires, Argentina');
    fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.length) {
          mostrar('No encontramos esa dirección. Probá con calle, altura y localidad, o movés el pin a mano.', 'warn');
          ponerPin(CENTRO[0], CENTRO[1], true);
          return;
        }
        var lat = parseFloat(data[0].lat), lng = parseFloat(data[0].lon);
        ponerPin(lat, lng, false);
        mapa.setView([lat, lng], 14);
        evaluar(lat, lng);
      })
      .catch(function () {
        mostrar('No pudimos verificar ahora. Movés el pin a tu casa o escribinos por WhatsApp.', 'warn');
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

  function evaluar(lat, lng) {
    if (!poligonos.length) return;
    var dentro = poligonos.some(function (anillo) { return puntoEnPoligono(lng, lat, anillo); });
    if (dentro) {
      mostrar('✅ ¡Sí, llegamos a tu zona! Armá tu pedido y coordinamos el día y horario de entrega por WhatsApp.', 'ok');
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
