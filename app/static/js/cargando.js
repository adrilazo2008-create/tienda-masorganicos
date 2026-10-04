/* Indicador "Procesando..." compartido por todos los proyectos de Mas Organicos.
 *
 * Copia identica en cada proyecto (static/cargando.js, o static/js/ en tienda);
 * la fuente es C:\MO-IA\_compartido\cargando.js -- si se cambia, copiarla a
 * todos. Sin dependencias.
 *
 * Aparece SOLO si algo tarda mas de DEMORA ms, asi no parpadea en lo rapido:
 *   - envio de formularios y clics en enlaces (la pagina se recarga)
 *   - pedidos en segundo plano: fetch, XMLHttpRequest (jQuery, HTMX, etc.)
 * Tambien define moConfirmar()/moAviso() y data-confirmar en formularios (dialogo
 * centrado, Enter acepta, Esc cancela) en lugar de confirm()/alert() nativos.
 * No bloquea la pantalla (pointer-events: none). Opt-out: data-sin-cargando
 * en el <a>/<form>. data-cargando-breve="Nombre" en un <a target=_blank> muestra
 * "Abriendo Nombre..." 6 s en la pestana de origen. Descargas (exportar/pdf/xlsx/csv, atributo download) se
 * ignoran porque la pagina no se recarga y el cartel quedaria colgado.
 */
(function () {
  if (window.__moCargando) return;
  window.__moCargando = true;

  var DEMORA = 400;        // ms antes de mostrar el cartel
  var AVISO_LARGO = 8000;  // ms: cambia el texto a "sigue procesando"
  var TOPE = 30000;        // ms: se oculta solo si algo quedo colgado
  var DESCARGA = /exportar|descargar|\.(xlsx?|csv|pdf|zip)(\?|$)/i;

  var pendientes = 0, navegando = false;
  var el = null, texto = null, tDemora = null, tAviso = null, tTope = null;

  function crear() {
    if (el || !document.body) return;
    var css = document.createElement('style');
    css.textContent =
      '#mo-cargando{position:fixed;top:50%;left:50%;transform:translate(-50%,-46%);' +
      'z-index:2147483000;display:flex;align-items:center;gap:.6rem;padding:.9rem 1.5rem;' +
      'background:#1a1a1a;color:#fff;border-radius:999px;font:600 16px/1.2 Arial,sans-serif;' +
      'box-shadow:0 4px 14px rgba(0,0,0,.35);opacity:0;visibility:hidden;pointer-events:none;' +
      'transition:opacity .15s,transform .15s,visibility .15s}' +
      '#mo-cargando.visible{opacity:1;visibility:visible;transform:translate(-50%,-50%)}' +
      '#mo-cargando i{width:22px;height:22px;border:2px solid rgba(255,255,255,.3);' +
      'border-top-color:#F5B800;border-radius:50%;animation:mo-giro .8s linear infinite}' +
      '@keyframes mo-giro{to{transform:rotate(360deg)}}' +
      'html.mo-ocupado,html.mo-ocupado *{cursor:progress}' +
      '@media print{#mo-cargando{display:none!important}}';
    document.head.appendChild(css);
    el = document.createElement('div');
    el.id = 'mo-cargando';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.innerHTML = '<i></i><span></span>';
    texto = el.lastChild;
    document.body.appendChild(el);
  }

  function mostrar(mensaje) {
    crear();
    if (!el) return;
    texto.textContent = mensaje || 'Procesando\u2026';
    el.classList.add('visible');
    document.documentElement.classList.add('mo-ocupado');
    clearTimeout(tAviso);
    if (!mensaje) tAviso = setTimeout(function () {
      texto.textContent = 'Sigue procesando, no cierres la p\u00e1gina\u2026';
    }, AVISO_LARGO);
    clearTimeout(tTope);
    tTope = setTimeout(ocultar, TOPE);
  }

  function ocultar() {
    clearTimeout(tDemora); tDemora = null;
    clearTimeout(tAviso); clearTimeout(tTope);
    navegando = false;
    if (el) el.classList.remove('visible');
    document.documentElement.classList.remove('mo-ocupado');
  }

  function actualizar() {
    if (pendientes > 0 || navegando) {
      if (!tDemora && !(el && el.classList.contains('visible'))) {
        tDemora = setTimeout(function () {
          tDemora = null;
          if (pendientes > 0 || navegando) mostrar();
        }, DEMORA);
      }
    } else {
      ocultar();
    }
  }

  // --- pedidos en segundo plano ---
  if (window.fetch) {
    var fetchOriginal = window.fetch;
    window.fetch = function (u) {
      if (typeof u === 'string' && u.indexOf('/sesion/ping') === 0) return fetchOriginal.apply(this, arguments);
      pendientes++; actualizar();
      var p = fetchOriginal.apply(this, arguments);
      var fin = function () { pendientes = Math.max(0, pendientes - 1); actualizar(); };
      p.then(fin, fin);
      return p;
    };
  }
  if (window.XMLHttpRequest) {
    var sendOriginal = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
      var xhr = this, contado = true;
      pendientes++; actualizar();
      xhr.addEventListener('loadend', function () {
        if (!contado) return;
        contado = false;
        pendientes = Math.max(0, pendientes - 1); actualizar();
      });
      return sendOriginal.apply(this, arguments);
    };
  }

  // --- navegacion (enlaces y formularios) ---
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || a.hasAttribute('data-sin-cargando') || a.hasAttribute('download')) return;
    // Enlaces que abren en pestana nueva (ej. el menu del portal): la pagina
    // nueva queda en blanco hasta que llega su HTML, asi que el aviso va en
    // esta pestana, por unos segundos.
    if (a.hasAttribute('data-cargando-breve')) {
      mostrar('Abriendo ' + (a.getAttribute('data-cargando-breve') || '') + '\u2026');
      clearTimeout(tTope); tTope = setTimeout(ocultar, 6000);
      return;
    }
    if (a.target && a.target !== '_self') return;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#' || /^(javascript|mailto|tel|whatsapp):/i.test(href)) return;
    if (a.origin !== location.origin || DESCARGA.test(a.pathname + a.search)) return;
    if (a.pathname === location.pathname && a.search === location.search && a.hash) return;
    navegando = true; actualizar();
  });

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (e.defaultPrevented || !f || f.hasAttribute('data-sin-cargando')) return;
    if (f.target && f.target !== '_self') return;
    if (DESCARGA.test(f.getAttribute('action') || '')) return;
    navegando = true; actualizar();
  });


  // --- dialogos propios (reemplazan confirm()/alert() nativos) ---
  // moConfirmar(msg) -> Promise<boolean>; moAviso(msg) -> Promise.
  // Enter acepta, Esc cancela. En formularios: data-confirmar="mensaje".
  var dlgCss = false;
  function colorPrincipal() {
    var b = document.querySelector('button.btn:not(.btn-secundario):not(.btn-sec), .btn-primary, form button[type=submit]');
    var c = b && getComputedStyle(b).backgroundColor;
    return (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') ? c : '#1f6b1f';
  }
  function dialogo(mensaje, conCancelar, txtSi) {
    return new Promise(function (resolve) {
      if (!document.body) { resolve(true); return; }
      if (!dlgCss) {
        dlgCss = true;
        var st = document.createElement('style');
        st.textContent =
          '.mo-dlg-fondo{position:fixed;inset:0;z-index:2147483100;background:rgba(0,0,0,.45);' +
          'display:flex;align-items:center;justify-content:center;padding:16px;animation:mo-dlg-in .12s ease-out}' +
          '.mo-dlg{background:#fff;color:#222;border-radius:12px;max-width:440px;width:100%;' +
          'padding:1.4rem 1.5rem 1.1rem;box-shadow:0 12px 40px rgba(0,0,0,.35);font:15px/1.45 Arial,sans-serif}' +
          '.mo-dlg p{margin:0 0 1.2rem;white-space:pre-line;word-wrap:break-word;max-height:60vh;overflow:auto}' +
          '.mo-dlg div{display:flex;justify-content:flex-end;gap:.6rem}' +
          '.mo-dlg button{font:600 14px Arial,sans-serif;padding:.55rem 1.3rem;border-radius:8px;cursor:pointer;' +
          'border:2px solid transparent}' +
          '.mo-dlg .mo-si{color:#fff}' +
          '.mo-dlg .mo-no{background:#eee;color:#333}' +
          '.mo-dlg button:focus{outline:none;box-shadow:0 0 0 3px rgba(245,184,0,.65)}' +
          '@keyframes mo-dlg-in{from{opacity:0}to{opacity:1}}' +
          '@media print{.mo-dlg-fondo{display:none!important}}';
        document.head.appendChild(st);
      }
      var previo = document.activeElement;
      var fondo = document.createElement('div');
      fondo.className = 'mo-dlg-fondo';
      var cuadro = document.createElement('div');
      cuadro.className = 'mo-dlg';
      cuadro.setAttribute('role', 'alertdialog');
      cuadro.setAttribute('aria-modal', 'true');
      var p = document.createElement('p'); p.textContent = mensaje;
      var fila = document.createElement('div');
      var si = document.createElement('button'); si.type = 'button'; si.className = 'mo-si';
      si.textContent = txtSi || 'Aceptar'; si.style.background = colorPrincipal();
      var no = null;
      if (conCancelar) {
        no = document.createElement('button'); no.type = 'button'; no.className = 'mo-no';
        no.textContent = 'Cancelar'; fila.appendChild(no);
      }
      fila.appendChild(si); cuadro.appendChild(p); cuadro.appendChild(fila);
      fondo.appendChild(cuadro); document.body.appendChild(fondo);
      var abierto = Date.now();
      function cerrar(r) {
        document.removeEventListener('keydown', tecla, true);
        fondo.remove();
        try { if (previo && previo.focus) previo.focus(); } catch (e) {}
        resolve(r);
      }
      function tecla(e) {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cerrar(false); }
        else if (e.key === 'Enter') {
          e.preventDefault(); e.stopPropagation();
          if (Date.now() - abierto > 150) cerrar(true);
        } else if (e.key === 'Tab') {
          e.preventDefault();
          if (no) (document.activeElement === si ? no : si).focus();
        }
      }
      document.addEventListener('keydown', tecla, true);
      si.addEventListener('click', function () { cerrar(true); });
      if (no) no.addEventListener('click', function () { cerrar(false); });
      fondo.addEventListener('mousedown', function (e) { if (e.target === fondo && no) cerrar(false); });
      si.focus();
    });
  }
  window.moConfirmar = function (mensaje, txtSi) { return dialogo(String(mensaje), true, txtSi); };
  window.moAviso = function (mensaje) { return dialogo(String(mensaje), false, 'Entendido'); };

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f || !f.getAttribute || !f.hasAttribute('data-confirmar') || f.__moOk) return;
    e.preventDefault(); e.stopImmediatePropagation();
    window.moConfirmar(f.getAttribute('data-confirmar')).then(function (ok) {
      if (!ok) return;
      f.__moOk = true;
      if (f.requestSubmit) f.requestSubmit(); else f.submit();
      f.__moOk = false;
    });
  }, true);

  // Volver con "atras" restaura la pagina desde cache con el cartel prendido.
  window.addEventListener('pageshow', function (e) { if (e.persisted) ocultar(); });
})();
