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
  var envio = 0, info = '';
  var entregaEnvio = document.querySelector('input[name=entrega][value=envio]').checked;
  if (entregaEnvio && sel && sel.value !== '0'){
    var o = sel.options[sel.selectedIndex];
    var precio = parseFloat(o.dataset.precio || '0');
    var gratis = parseFloat(o.dataset.gratis || '0');
    var minc   = parseFloat(o.dataset.min || '0');
    envio = (gratis && sub >= gratis) ? 0 : precio;
    if (envio === 0 && precio > 0) info = 'Envío gratis por superar ' + fmtPeso(gratis);
    if (minc && sub < minc) info = 'Compra mínima para esta zona: ' + fmtPeso(minc);
  }
  document.getElementById('r-envio').textContent = entregaEnvio ? fmtPeso(envio) : 'retiro sin costo';
  document.getElementById('r-total').textContent = fmtPeso(sub + envio);
  var ei = document.getElementById('envio-info'); if (ei) ei.textContent = info;
}
function fmtPeso(n){ return '$' + Math.round(n).toLocaleString('es-AR'); }
function iniciarCheckout(){ toggleEntrega(); }

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
