// ============================================================
// Dados
// ============================================================
// As 5 cidades principais espalhadas pelo país (San Lorenzo, Luque e Capiatá são maiores que algumas
// destas, mas ficam coladas em Asunción: no mapa do país os pins ficariam um em cima do outro).
const CIDADES = [
  {id: 'asuncion',             nome: 'Asunción',             lat: -25.300, lng: -57.600},
  {id: 'ciudad-del-este',      nome: 'Ciudad del Este',      lat: -25.515, lng: -54.640},
  {id: 'encarnacion',          nome: 'Encarnación',          lat: -27.340, lng: -55.880},
  {id: 'pedro-juan-caballero', nome: 'Pedro Juan Caballero', lat: -22.552, lng: -55.748},
  {id: 'concepcion',           nome: 'Concepción',           lat: -23.405, lng: -57.425},
];
CIDADES.push(...(window.CIDADES_EXTRA || []).map(c => ({...c, extra: true})));   // vagas reais em outras cidades
const VAGAS = window.VAGAS || [];
const OCUPACOES = window.OCUPACIONES || [];
const cidadeDe = id => CIDADES.find(c => c.id === id);
if (window.VAGAS_TESTE) document.getElementById('aviso-teste').hidden = false;
const nomeVaga = v => v.titulo || v.ocupacion;

const Z_VAGAS = 13;        // zoom em que os pins das vagas ficam a DIST px uns dos outros
const DIST = 46;           // distância mínima entre pins (px) nesse zoom: dá para clicar sem errar
const Z_MOSTRAR = 12.5;    // a partir deste zoom aparecem as vagas; abaixo, os pins das cidades

const selecionadas = new Set();   // ocupações escolhidas na busca
let atual = null;                 // vaga aberta no painel
let grupoAberto = null;           // lista aberta pelos cantos ('remoto' | 'sem')

const sem = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const passa = v => !selecionadas.size || selecionadas.has(v.ocupacion);
const grupoDe = v => v.remoto ? 'remoto' : (v.ciudad || 'sem');
const NOME_GRUPO = {remoto: 'Remoto', sem: 'Sin ciudad definida'};
const nomeGrupo = g => NOME_GRUPO[g] || cidadeDe(g).nome;

function el(tag, attrs, pai, texto) {
  const e = document.createElement(tag);
  for (const k in attrs || {}) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
  if (texto != null) e.textContent = texto;
  if (pai) pai.appendChild(e);
  return e;
}
function semente(txt) {   // número aleatório "fixo" por cidade: os pins não mudam de lugar a cada visita
  let h = 2166136261;
  for (const c of txt) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => { h += 0x6D2B79F5; let t = h; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
const PIN = (cor, furo = true) => '<svg viewBox="0 0 24 32" aria-hidden="true"><path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20C24 5.4 18.6 0 12 0z" fill="' + cor + '"/>' +
  (furo ? '<circle cx="12" cy="12" r="4.2" fill="#fff"/>' : '') + '</svg>';

// ============================================================
// Mapa
// ============================================================
const mapa = L.map('mapa', {zoomControl: false, zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 90, attributionControl: true});
L.control.zoom({position: 'topright'}).addTo(mapa);
mapa.attributionControl.setPrefix(false).addAttribution('Límites: <a href="https://www.geoboundaries.org" target="_blank" rel="noopener">geoBoundaries</a>');
L.geoJSON(GEO.departamentos, {style: {color: '#000', weight: 0.6, opacity: 0.16, fill: false}, interactive: false}).addTo(mapa);
const pais = L.geoJSON(GEO.pais, {style: {color: '#000', weight: 1.1, opacity: 1, fill: false}, interactive: false}).addTo(mapa);
const limites = pais.getBounds();
mapa.setMaxBounds(limites.pad(0.8));

// posição de cada vaga: espalhada ao acaso perto do centro da cidade, sempre a pelo menos DIST px das outras
function espalhar(cidade, vagas) {
  const rnd = semente(cidade.id), c = mapa.project([cidade.lat, cidade.lng], Z_VAGAS);
  let raio = DIST * (0.6 + 0.75 * Math.sqrt(vagas.length)), pts;
  for (;;) {
    pts = [];
    for (let t = 0; pts.length < vagas.length && t < 6000; t++) {
      const a = rnd() * 2 * Math.PI, r = raio * Math.sqrt(rnd());
      const p = {x: c.x + r * Math.cos(a), y: c.y + r * Math.sin(a)};
      if (pts.every(q => (q.x - p.x) ** 2 + (q.y - p.y) ** 2 >= DIST * DIST)) pts.push(p);
    }
    if (pts.length === vagas.length) break;
    raio *= 1.12;   // não coube: aumenta um pouco a zona
  }
  vagas.forEach((v, i) => { v.pos = mapa.unproject(L.point(pts[i].x, pts[i].y), Z_VAGAS); });
}

const camadaCidades = L.layerGroup().addTo(mapa);
const camadaVagas = L.layerGroup();
const marcadoresVaga = new Map();

function iconeCidade(c, n) {
  return L.divIcon({className: 'icone', iconSize: [30, 40], iconAnchor: [15, 40],
    html: '<div class="pin pin-cidade' + (c.extra ? ' extra' : '') + (n ? '' : ' vazia') + '">' + PIN('#111', false) + '<span class="qtd">' + n + '</span><span class="nome">' + c.nome + '</span></div>'});
}
const iconeVaga = sel => L.divIcon({className: 'icone', iconSize: [22, 30], iconAnchor: [11, 30],
  html: '<div class="pin pin-vaga' + (sel ? ' sel' : '') + '">' + PIN('#E4572E') + '</div>'});

CIDADES.forEach(c => {
  const doLugar = VAGAS.filter(v => v.ciudad === c.id && !v.remoto);
  espalhar(c, doLugar);
  c.marcador = L.marker([c.lat, c.lng], {icon: iconeCidade(c, doLugar.length), riseOnHover: true, keyboard: true, title: c.nome})
    .on('click', () => irParaCidade(c)).addTo(camadaCidades);
  // nome da cidade acima das vagas, quando o mapa está aproximado
  const topo = doLugar.length ? Math.max(...doLugar.map(v => v.pos.lat)) : c.lat;
  L.marker([topo, c.lng], {interactive: false, keyboard: false,
    icon: L.divIcon({className: 'icone', html: '<div class="rotulo-cidade">' + c.nome + '</div>', iconSize: [200, 20], iconAnchor: [100, 44]})}).addTo(camadaVagas);
  doLugar.forEach(v => {
    const m = L.marker(v.pos, {icon: iconeVaga(false), riseOnHover: true, keyboard: true, title: nomeVaga(v)})
      .on('click', () => selecionar(v));
    marcadoresVaga.set(v.id, m);
  });
});

function irParaCidade(c) {
  const pontos = VAGAS.filter(v => v.ciudad === c.id && passa(v) && v.pos).map(v => v.pos);
  if (pontos.length) mapa.flyToBounds(L.latLngBounds(pontos), {padding: [70, 70], maxZoom: 15, duration: 1.2});
  else mapa.flyTo([c.lat, c.lng], Z_VAGAS, {duration: 1.2});
}

function desenharPins() {
  const perto = mapa.getZoom() >= Z_MOSTRAR;
  if (perto && !mapa.hasLayer(camadaVagas)) { mapa.addLayer(camadaVagas); mapa.removeLayer(camadaCidades); }
  if (!perto && mapa.hasLayer(camadaVagas)) { mapa.removeLayer(camadaVagas); mapa.addLayer(camadaCidades); }
  CIDADES.forEach(c => c.marcador.setIcon(iconeCidade(c, VAGAS.filter(v => v.ciudad === c.id && !v.remoto && passa(v)).length)));
  VAGAS.forEach(v => {
    const m = marcadoresVaga.get(v.id);
    if (!m) return;
    const mostrar = passa(v);
    if (mostrar && !camadaVagas.hasLayer(m)) camadaVagas.addLayer(m);
    if (!mostrar && camadaVagas.hasLayer(m)) camadaVagas.removeLayer(m);
    m.setIcon(iconeVaga(atual === v));
    m.setZIndexOffset(atual === v ? 1000 : 0);
  });
  desenharCantos();
}
mapa.on('zoomend', desenharPins);
// cidades fora das 5 principais: nome só aparece com o mapa mais aproximado (no país inteiro, os nomes se atropelariam)
mapa.on('zoomend', () => document.getElementById('mapa').classList.toggle('nomes-extras', mapa.getZoom() >= 8));

// cantos: vagas remotas (esquerda) e sem cidade (direita)
const cantoRemoto = document.getElementById('canto-remoto'), cantoSem = document.getElementById('canto-sem');
function desenharCantos() {
  const nR = VAGAS.filter(v => v.remoto && passa(v)).length;
  const nS = VAGAS.filter(v => !v.remoto && !v.ciudad && passa(v)).length;
  cantoRemoto.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="#111" stroke-width="1.5"/>' +
    '<path d="M2 12h20M12 2c3 3 3 17 0 20M12 2c-3 3-3 17 0 20" fill="none" stroke="#111" stroke-width="1.5"/></svg><span>Remoto</span><b>' + nR + '</b>';
  cantoSem.innerHTML = PIN('#E4572E') + '<span>Sin ciudad</span><b>' + nS + '</b>';
  cantoRemoto.classList.toggle('vazio', !nR);
  cantoSem.classList.toggle('vazio', !nS);
}
cantoRemoto.onclick = () => abrirGrupo('remoto');
cantoSem.onclick = () => abrirGrupo('sem');

// ============================================================
// Painel (detalhe da vaga) e animação do mapa
// ============================================================
const painel = document.getElementById('painel');
const voltar = document.getElementById('voltar-mapa');
const caixaMapa = document.getElementById('mapa-caixa');
// Enquanto o mapa encolhe/cresce, o ponto "seguir" fica no centro: o mapa desliza junto com a animação.
let seguir = null;
new ResizeObserver(() => { mapa.invalidateSize({pan: false}); if (seguir) mapa.panTo(seguir, {animate: false}); }).observe(caixaMapa);
function esperarAnimacao(depois) {
  let feito = false;
  const fim = () => { if (feito) return; feito = true; caixaMapa.removeEventListener('transitionend', aoTerminar);
    seguir = null; mapa.invalidateSize({pan: false}); if (depois) depois(); };
  const aoTerminar = ev => { if (ev.target === caixaMapa) fim(); };
  caixaMapa.addEventListener('transitionend', aoTerminar);
  setTimeout(fim, 900);   // garantia, se o navegador não avisar o fim da animação
}
function abrirPainel(alvo, depois) {
  if (document.body.classList.contains('com-vaga')) { if (depois) depois(); return; }
  seguir = alvo || mapa.getCenter();
  document.body.classList.add('com-vaga');
  voltar.hidden = false;
  esperarAnimacao(depois);
}
function fecharPainel() {
  atual = null; grupoAberto = null;
  seguir = mapa.getCenter();
  document.body.classList.remove('com-vaga');
  voltar.hidden = true;
  desenharPins();
  esperarAnimacao();
}
voltar.onclick = fecharPainel;

function visiveisDoGrupo(g) { return VAGAS.filter(v => grupoDe(v) === g && passa(v)); }

function selecionar(v) {
  atual = v; grupoAberto = null;
  desenharPins();
  desenharVaga();
  if (!v.pos) { abrirPainel(null, () => mapa.flyToBounds(limites, {paddingTopLeft: [20, 50], paddingBottomRight: [120, 60], duration: 0.8})); return; }
  const perto = mapa.getZoom() >= Z_MOSTRAR && mapa.getBounds().contains(v.pos);
  abrirPainel(perto ? v.pos : null, () => {
    if (perto) mapa.panTo(v.pos, {duration: 0.5});
    else mapa.flyTo(v.pos, Math.max(mapa.getZoom(), 14), {duration: 1});
  });
}

function desenharVaga() {
  const v = atual, lista = visiveisDoGrupo(grupoDe(v)), i = lista.indexOf(v);
  painel.textContent = '';
  const mi = el('div', {class: 'painel-miolo'}, painel);
  const x = el('button', {class: 'fechar', type: 'button', 'aria-label': 'Cerrar'}, mi, '×');
  x.onclick = fecharPainel;
  el('div', {class: 'local'}, mi, [v.ciudadNombre || nomeGrupo(grupoDe(v)), v.remoto ? 'Remoto' : v.modalidad].filter(Boolean).join(' · '));
  el('h2', null, mi, nomeVaga(v));
  if (v.empresa) el('p', {class: 'empresa'}, mi, v.empresa);
  if (v.titulo && v.ocupacion !== 'Otras ocupaciones') el('p', {class: 'area-vaga'}, mi, 'Área: ' + v.ocupacion);
  if (v.link) {
    el('p', {class: 'instr'}, mi, 'Postulate en el sitio original:');
    const linha = el('div', {class: 'email-linha'}, mi);
    el('a', {href: v.link, target: '_blank', rel: 'noopener', class: 'link-original'}, linha, 'Ver la vacante ↗');
    const cp = el('button', {class: 'copiar', type: 'button'}, linha, 'Copiar link');
    cp.onclick = () => copiar(v.link, cp);
    const info = [v.fuente && 'Fuente: ' + v.fuente, v.publicado && 'Publicada: ' + v.publicado.split('-').reverse().join('/'),
                  v.vence && 'Vence: ' + v.vence.split('-').reverse().join('/')].filter(Boolean).join(' · ');
    if (info) el('p', {class: 'fonte-vaga'}, mi, info);
  }
  if (v.email) {
    el('p', {class: 'instr'}, mi, 'Enviá tu CV a:');
    const linha = el('div', {class: 'email-linha'}, mi);
    const a = el('a', {href: 'mailto:' + v.email + '?subject=' + encodeURIComponent('Postulación: ' + nomeVaga(v))}, linha);
    const [usuario, dominio] = v.email.split('@');   // se não couber, quebra no "@"
    a.append(usuario); a.appendChild(document.createElement('wbr')); a.append('@' + dominio);
    const cp = el('button', {class: 'copiar', type: 'button'}, linha, 'Copiar');
    cp.onclick = () => copiar(v.email, cp);
  }
  const nav = el('div', {class: 'navegar'}, mi);
  const ant = el('button', {type: 'button'}, nav, '← Anterior');
  el('span', null, nav, (i + 1) + ' de ' + lista.length + ' en ' + nomeGrupo(grupoDe(v)));
  const prox = el('button', {type: 'button'}, nav, 'Siguiente →');
  ant.disabled = i <= 0; prox.disabled = i < 0 || i >= lista.length - 1;
  ant.onclick = () => selecionar(lista[i - 1]);
  prox.onclick = () => selecionar(lista[i + 1]);
}

function abrirGrupo(g) {
  const lista = visiveisDoGrupo(g);
  if (!lista.length) return;
  atual = null; grupoAberto = g;
  desenharPins();
  painel.textContent = '';
  const mi = el('div', {class: 'painel-miolo'}, painel);
  const x = el('button', {class: 'fechar', type: 'button', 'aria-label': 'Cerrar'}, mi, '×');
  x.onclick = fecharPainel;
  el('div', {class: 'local'}, mi, lista.length + (lista.length === 1 ? ' vacante' : ' vacantes'));
  el('h2', null, mi, g === 'remoto' ? 'Trabajo remoto' : 'Sin ciudad definida');
  const ul = el('ul', {class: 'lista-vagas'}, mi);
  lista.forEach(v => { const b = el('button', {type: 'button'}, el('li', null, ul), nomeVaga(v)); el('span', null, b, v.empresa || 'Ver →'); b.onclick = () => selecionar(v); });
  abrirPainel(null, () => mapa.flyToBounds(limites, {paddingTopLeft: [20, 50], paddingBottomRight: [120, 60], duration: 0.8}));
}

function copiar(texto, botao) {
  const feito = () => { botao.textContent = '¡Copiado!'; botao.classList.add('ok'); setTimeout(() => { botao.textContent = 'Copiar'; botao.classList.remove('ok'); }, 1600); };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(texto).then(feito, () => copiarAntigo(texto, feito));
  else copiarAntigo(texto, feito);
}
function copiarAntigo(texto, feito) {   // navegadores sem a API (ou página aberta direto do arquivo)
  const t = el('textarea', {style: 'position:fixed;opacity:0'}, document.body); t.value = texto; t.select();
  try { document.execCommand('copy'); feito(); } finally { t.remove(); }
}

// ============================================================
// Busca: lista de ocupações (várias escolhas) + filtro a partir da 3ª letra
// ============================================================
const entrada = document.getElementById('entrada'), listaEl = document.getElementById('lista');
const chipsEl = document.getElementById('chips'), limpar = document.getElementById('limpar'), resumo = document.getElementById('resumo');
const contagem = {};
VAGAS.forEach(v => { contagem[v.ocupacion] = (contagem[v.ocupacion] || 0) + 1; });
let ativo = 0, itensVisiveis = [];

function desenharLista() {
  const txt = sem(entrada.value.trim());
  itensVisiveis = txt.length >= 3 ? OCUPACOES.filter(o => sem(o).includes(txt)) : OCUPACOES.slice();
  // ocupações com vagas primeiro, depois as demais (em ordem alfabética)
  itensVisiveis.sort((a, b) => (!contagem[a] - !contagem[b]) || a.localeCompare(b, 'es'));
  ativo = Math.min(ativo, Math.max(0, itensVisiveis.length - 1));
  listaEl.textContent = '';
  if (txt.length > 0 && txt.length < 3) el('li', {class: 'dica'}, listaEl, 'Escribí al menos 3 letras para filtrar');
  if (!itensVisiveis.length) el('li', {class: 'vazio'}, listaEl, 'Ninguna ocupación con "' + entrada.value.trim() + '"');
  itensVisiveis.forEach((o, i) => {
    const li = el('li', {role: 'option', id: 'op-' + i, 'aria-selected': String(selecionadas.has(o)), class: (i === ativo ? 'ativo ' : '') + (contagem[o] ? '' : 'zero')}, listaEl);
    el('span', {class: 'caixa'}, li);
    el('span', null, li, o);
    el('span', {class: 'n'}, li, contagem[o] ? contagem[o] + (contagem[o] === 1 ? ' vacante' : ' vacantes') : 'sin vacantes');
    li.onmousedown = ev => ev.preventDefault();   // não tira o foco do campo
    li.onclick = () => { ativo = i; alternar(o); };
  });
  entrada.setAttribute('aria-activedescendant', itensVisiveis.length ? 'op-' + ativo : '');
}
function abrirLista() { listaEl.hidden = false; entrada.setAttribute('aria-expanded', 'true'); desenharLista(); }
function fecharLista() { listaEl.hidden = true; entrada.setAttribute('aria-expanded', 'false'); }

function alternar(o) {
  if (selecionadas.has(o)) selecionadas.delete(o); else selecionadas.add(o);
  aplicarFiltro();
  desenharLista();
}
function desenharChips() {
  chipsEl.textContent = '';
  selecionadas.forEach(o => {
    const c = el('span', {class: 'chip'}, chipsEl, o);
    const x = el('button', {type: 'button', 'aria-label': 'Quitar ' + o}, c, '×');
    x.onclick = ev => { ev.stopPropagation(); selecionadas.delete(o); aplicarFiltro(); if (!listaEl.hidden) desenharLista(); };
  });
  limpar.hidden = !selecionadas.size && !entrada.value;
  entrada.placeholder = selecionadas.size ? 'Agregar otra ocupación…' : 'Buscá tu ocupación: vendedor, cocinero, chofer…';
}
function aplicarFiltro() {
  desenharChips();
  const n = VAGAS.filter(passa).length;
  resumo.textContent = selecionadas.size ? n + (n === 1 ? ' vacante' : ' vacantes') + ' en ' + selecionadas.size +
    (selecionadas.size === 1 ? ' ocupación' : ' ocupaciones') : VAGAS.length + ' vacantes en todo el país' +
    (window.COLETA ? ' · actualizado ' + window.COLETA.geradoEm : '');
  if (atual && !passa(atual)) fecharPainel();
  else if (atual) desenharVaga();
  else if (grupoAberto) { if (visiveisDoGrupo(grupoAberto).length) abrirGrupo(grupoAberto); else fecharPainel(); }
  desenharPins();
}
function zerar() {
  selecionadas.clear(); entrada.value = ''; ativo = 0;
  aplicarFiltro();
  if (!listaEl.hidden) desenharLista();
}

entrada.addEventListener('focus', abrirLista);
entrada.addEventListener('input', () => { ativo = 0; abrirLista(); limpar.hidden = !selecionadas.size && !entrada.value; });
entrada.addEventListener('keydown', ev => {
  if (ev.key === 'ArrowDown') { ev.preventDefault(); if (listaEl.hidden) abrirLista(); ativo = Math.min(ativo + 1, itensVisiveis.length - 1); desenharLista(); rolarAtivo(); }
  else if (ev.key === 'ArrowUp') { ev.preventDefault(); ativo = Math.max(ativo - 1, 0); desenharLista(); rolarAtivo(); }
  else if (ev.key === 'Enter') { ev.preventDefault(); if (itensVisiveis[ativo]) alternar(itensVisiveis[ativo]); }
  else if (ev.key === 'Escape') { fecharLista(); entrada.blur(); }
  else if (ev.key === 'Backspace' && !entrada.value && selecionadas.size) { selecionadas.delete([...selecionadas].pop()); aplicarFiltro(); desenharLista(); }
});
function rolarAtivo() { const a = listaEl.querySelector('.ativo'); if (a) a.scrollIntoView({block: 'nearest'}); }
document.getElementById('abrir').onclick = () => { if (listaEl.hidden) { entrada.focus(); abrirLista(); } else fecharLista(); };
document.getElementById('campo').addEventListener('click', ev => { if (ev.target.id === 'campo') entrada.focus(); });
limpar.onclick = zerar;
document.addEventListener('mousedown', ev => { if (!document.getElementById('busca').contains(ev.target)) fecharLista(); });

// ============================================================
// Início: o mapa aparece se afastando até mostrar o país inteiro
// ============================================================
const vistaPais = mapa.getBoundsZoom(limites, false, L.point(40, 40));
mapa.setMinZoom(Math.max(3, Math.floor(vistaPais) - 1));
mapa.setView(limites.getCenter(), vistaPais + 2.5, {animate: false});
aplicarFiltro();
requestAnimationFrame(() => setTimeout(() => mapa.flyToBounds(limites, {padding: [40, 40], duration: 1.8}), 150));
