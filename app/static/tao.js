'use strict';
(() => {
  const state = {user: null, csrf: '', cases: [], current: null, tab: 'matrix', selected: null, companyFilter: '', stageFilter: '', docs: [], audit: [], users: [], busy: false};
  const root = document.querySelector('#tao-app');
  const editor = document.querySelector('#editor');
  const labels = {related: 'Kapcsolt', not_related: 'Nem kapcsolt', undetermined: 'Nem dönthető el'};
  const familyLabels = {spouse:'Házastárs', lineal:'Egyeneságbeli rokon', adoptive:'Örökbefogadó szülő / gyermek', step:'Mostohaszülő / gyermek', foster:'Nevelőszülő / gyermek', sibling:'Testvér (féltestvér is)', partner:'Élettárs – nem közeli hozzátartozó', other:'Egyéb hozzátartozó – külön vizsgálat'};
  const controlLabels = {appointments:'Vezetők / felügyelőbizottsági tagok többségének megválasztási vagy visszahívási joga', voting_agreement:'Más tagokkal kötött szavazási megállapodás'};
  const answers = [['unknown','Tisztázandó'], ['yes','Igen'], ['no','Nem']];
  const answerLabel = value => Object.fromEntries(answers)[value] || 'Tisztázandó';
  const membershipLabel = value => ({member:'Igazolt tag / részvényes',not_member:'Nem tag / részvényes',unknown:'Tagi jogállás tisztázandó'})[value];
  const entityTypes = [['company','Vállalkozás'],['managed_assets','Elkülönült kezelt vagyon'],['permanent_establishment','Tao-telephely']];
  const peTypes = [['foreign_business_domestic_pe','Külföldi vállalkozó belföldi Tao-telephelye'],['taxpayer_foreign_pe','Adózó külföldi Tao-telephelye'],['other_foreign_business_pe','Külföldi vállalkozó további telephelye']];
  const modes = {ownership_default: 'Tulajdon = szavazat', explicit: 'Dokumentált szavazat', expert: 'Szakértői felülbírálat', unknown: 'Ismeretlen szavazat'};
  const tabs = {matrix: 'Mátrix', data: 'Adatok', documents: 'Dokumentumok', review: 'Ellenőrzés'};
  const paths = {
    network: 'M12 5v8M5 19l7-6 7 6M12 5a3 3 0 1 0 0-6 3 3 0 0 0 0 6M5 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6M19 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6',
    file: 'M14 2H5v20h14V7zM14 2v5h5M8 12h8M8 16h8',
    grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
    building: 'M4 21h16M6 21V3h12v18M9 7h1M14 7h1M9 11h1M14 11h1M10 21v-5h4v5',
    check: 'M5 12l4 4L19 6',
    close: 'M6 6l12 12M6 18L18 6',
    download: 'M12 3v12M7 10l5 5 5-5M4 16v5h16v-5',
    shield: 'M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6zM8 12l3 3 5-6',
    plus: 'M12 5v14M5 12h14',
    edit: 'M3 21l4-1L21 6l-3-3L4 17zM15 6l3 3',
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.file}"/></svg>`;
  const button = (label, action, cls = '', attributes = '', image = '') => `<button type="button" class="${cls}" data-action="${action}" ${attributes}>${image ? icon(image) : ''}${label}</button>`;
  const badge = (label, cls = '') => `<span class="badge ${cls}">${esc(label)}</span>`;
  const pairKey = (a, b) => JSON.stringify([a, b].sort());
  const staff = () => state.user && state.user.role !== 'client';
  const reviewer = () => ['admin', 'reviewer'].includes(state.user?.role);
  const today = () => new Date().toLocaleDateString('sv-SE', {timeZone: 'Europe/Budapest'});
  const names = () => Object.fromEntries([...state.current.data.companies, ...state.current.data.persons].map(c => [c.id, c.name]));
  const statusLabel = status => ({draft: 'Tervezet', approved_complete: 'Jóváhagyott', approved_partial: 'Jóváhagyott · részleges', approved: 'Jóváhagyott', intake: 'Adatbekérés'}[status] || status);

  async function api(path, options = {}) {
    const headers = {'X-CSRF-Token': state.csrf, ...(options.headers || {})};
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    const response = await fetch('/api' + path, {...options, headers});
    let result;
    try {result = await response.json();} catch {result = {};}
    if (!response.ok) {
      const fields = result.errors?.map(e => `${e.field}: ${e.message}`).join('\n');
      const error = new Error(fields || (typeof result.detail === 'string' ? result.detail : 'A kérés nem sikerült.'));
      error.status = response.status;
      throw error;
    }
    return result;
  }

  function toast(message) {
    const node = document.querySelector('#toast');
    node.textContent = message;
    node.style.display = 'block';
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => {node.style.display = 'none';}, 6500);
  }

  function shell(content) {
    root.innerHTML = `<header class="topbar"><div class="topbar-inner"><a class="brand" href="/tao">${icon('network')}<span>Kapcsolati műhely</span></a><nav class="top-nav" aria-label="Szolgáltatások">${button('Tao-ügyek', 'dashboard', 'active')}<a class="button" href="/">KKV-minősítés</a></nav><div class="account"><small>${esc(state.user.name)}</small>${button('Kilépés', 'logout')}</div></div></header><main id="main" class="workspace">${content}</main>${state.current && staff() ? `<nav class="mobile-nav" aria-label="Tao-vizsgálat nézetei">${Object.entries(tabs).map(([key, label]) => button(`${icon({matrix: 'grid', data: 'building', documents: 'file', review: 'shield'}[key])}<span>${label}</span>`, 'tab', state.tab === key ? 'active' : '', `data-tab="${key}"`)).join('')}</nav>` : ''}`;
  }

  function showLogin(setup) {
    root.innerHTML = `<main id="main" class="auth panel"><a class="brand" href="/tao">${icon('network')}Kapcsolati műhely</a><h1>${setup ? 'Hozd létre a munkateret' : 'Bejelentkezés'}</h1><p class="muted">A Tao- és KKV-vizsgálatok közös belépése.</p><form id="login-form" data-setup="${setup}">${setup ? field('Teljes név', 'name', '', 'text', 'required minlength="2" autocomplete="name"') : ''}${field('Felhasználónév', 'username', '', 'text', 'required minlength="3" autocomplete="username"')}${field('Jelszó', 'password', '', 'password', `required ${setup ? 'minlength="12"' : ''} autocomplete="${setup ? 'new-password' : 'current-password'}"`)}<p class="error" id="login-error" hidden></p><button class="primary" type="submit">${setup ? 'Munkatér létrehozása' : 'Belépés'}</button></form><p class="small muted">Ugyanaz a fiók használható mindkét szolgáltatáshoz.</p></main>`;
  }

  function dashboard() {
    state.current = null;
    shell(`<div class="heading"><div><h1>Tao-kapcsoltsági vizsgálatok</h1><p class="sub">Cégpárok, források és indokolt szakértői döntések.</p></div>${staff() ? `<div class="actions"><a class="button" href="/pdf-import?module=tao">OPTEN PDF-import</a>${button('Mintavizsgálat', 'demo')}${button('Új Tao-vizsgálat', 'new', 'primary', '', 'plus')}</div>` : ''}</div><nav class="services" aria-label="Szolgáltatásválasztó"><span class="active">Tao-kapcsoltság</span><a href="/">KKV-minősítés</a></nav>${state.cases.length ? `<div class="cards">${state.cases.map(c => `<button class="case-card" data-action="open" data-id="${esc(c.id)}"><strong>${esc(c.title)}</strong><span>${esc(c.client || 'Megbízó még nincs megadva')} · ${esc(c.as_of)}</span><span>${badge(statusLabel(c.status), c.status.startsWith('approved') ? 'approved' : 'amber')}</span></button>`).join('')}</div>` : `<section class="panel empty"><h2>Még nincs Tao-vizsgálat</h2><p>Hozz létre egy ügyet a vizsgált vállalkozásokkal.</p>${staff() ? button('Új Tao-vizsgálat', 'new', 'primary', '', 'plus') : ''}</section>`}`);
  }

  async function openCase(cid) {
    state.current = await api('/tao/cases/' + cid);
    state.docs = await api(`/tao/cases/${cid}/documents`);
    if (staff()) state.audit = await api(`/tao/cases/${cid}/audit`);
    renderCase();
  }

  function renderCase() {
    const c = state.current;
    if (c.client_view) {
      shell(`<div class="heading"><div><h1>${esc(c.title)}</h1><p>${esc(c.as_of)} · ${esc(statusLabel(c.status))}</p></div>${button('Vissza az ügyekhez', 'dashboard')}</div><section class="panel">${c.version ? `<h2>Jóváhagyott állásfoglalás</h2><div class="actions">${button('Word', 'export', '', 'data-kind="docx"', 'download')}${button('PDF', 'export', 'primary', 'data-kind="pdf"', 'download')}</div>` : '<p>A szakértői vizsgálat előkészítése folyamatban van.</p>'}</section>`);
      return;
    }
    const calc = c.calculation;
    const body = {matrix: matrixView, data: dataView, documents: documentsView, review: reviewView}[state.tab] || matrixView;
    shell(`<div class="heading"><div><button class="subtle" data-action="dashboard">← Vissza az ügyekhez</button><h1>${esc(c.data.title)}</h1><p class="sub">${esc(c.data.client || 'Tao szerinti vizsgálat')} · ${esc(c.data.as_of)} · ${c.version}. verzió ${badge(statusLabel(c.status), c.status.startsWith('approved') ? 'approved' : 'amber')}</p></div><div class="actions">${button('Ügyadatok', 'settings', '', '', 'edit')}${button('XLSX', 'export', '', 'data-kind="xlsx"', 'download')}${button('Word', 'export', '', 'data-kind="docx"', 'download')}${button('PDF', 'export', 'primary', 'data-kind="pdf"', 'download')}</div></div><nav class="services" aria-label="Szolgáltatásválasztó"><span class="active">Tao-kapcsoltság</span><a href="/">KKV-minősítés</a></nav><nav class="tabs" aria-label="Tao-vizsgálat nézetei">${Object.entries(tabs).map(([key, name]) => button(name, 'tab', state.tab === key ? 'active' : '', `data-tab="${key}"`)).join('')}</nav>${c.status === 'draft' ? `<div class="notice ${calc.law_profile_present ? '' : 'amber'}"><strong>Előzetes eredmény</strong><p class="small">A jogi minősítés indokolt szakértői döntésből készül. ${!calc.law_profile_present ? 'Az alkalmazandó jogi időállapot és forrás még ellenőrizendő.' : 'A véglegesítéshez külön szakértői jóváhagyás szükséges.'}</p></div>` : ''}<div id="case-content">${body()}</div>`);
  }

  function filteredRows() {
    return state.current.calculation.rows.filter(r => (!state.companyFilter || r.first === state.companyFilter || r.second === state.companyFilter) && (!state.stageFilter || r.stage === state.stageFilter));
  }

  function matrixView() {
    const c = state.current;
    const rows = filteredRows();
    const selected = rows.find(r => pairKey(r.first, r.second) === state.selected) || rows[0];
    if (selected) state.selected = pairKey(selected.first, selected.second);
    const lookup = Object.fromEntries(c.calculation.rows.map(r => [pairKey(r.first, r.second), r]));
    const cols = c.data.companies;
    const cell = r => {
      const symbol = r.result === 'related' ? '↔' : r.result === 'not_related' ? '—' : ['voting_signal','control_signal','special_signal'].includes(r.stage) ? '↗' : r.stage === 'awaiting_declaration' ? '▤' : '?';
      const cls = (['voting_signal','control_signal','special_signal'].includes(r.stage) ? 'signal ' : r.stage === 'missing_data' ? 'missing ' : '') + (state.selected === pairKey(r.first, r.second) ? 'selected' : '');
      const index = c.calculation.rows.indexOf(r);
      const label = `${r.first_name} – ${r.second_name}: ${r.label}; ${r.stage_label}${c.status === 'draft' ? '; előzetes' : ''}`;
      return `<button class="${cls}" data-action="pair" data-index="${index}" aria-label="${esc(label)}" title="${esc(label)}">${symbol}</button>`;
    };
    return `<div class="stats"><div class="stat"><strong>${cols.length}</strong><small>vizsgált vállalkozás</small></div><div class="stat"><strong>${c.calculation.total_pairs}</strong><small>cégpár</small></div><div class="stat"><strong>${c.calculation.stages.voting_signal + (c.calculation.stages.control_signal || 0) + (c.calculation.stages.special_signal || 0)}</strong><small>kapcsoltsági jelzés</small></div><div class="stat"><strong>${c.calculation.stages.awaiting_declaration}</strong><small>nyilatkozatra vár</small></div></div><div class="columns"><section class="panel"><div class="panel-title"><h2>Kapcsoltsági mátrix</h2>${badge(c.status === 'draft' ? 'Előzetes eredmény' : statusLabel(c.status), c.status === 'draft' ? 'teal' : 'approved')}</div><div class="filters"><label>Vizsgált cég<select id="company-filter"><option value="">Minden vállalkozás</option>${cols.map(v => `<option value="${esc(v.id)}" ${state.companyFilter === v.id ? 'selected' : ''}>${esc(v.name)}</option>`).join('')}</select></label><label>Következő lépés<select id="stage-filter"><option value="">Minden állapot</option>${[['voting_signal', 'Szavazati jelzés'], ['control_signal', 'Igazolt irányítás'], ['special_signal','Telephelyi jelzés'], ['awaiting_declaration', 'Nyilatkozatra vár'], ['missing_data', 'Hiányzó adat'], ['unreviewed', 'Iratellenőrzés'], ['management_review', 'Irányítás tisztázandó'], ['expert', 'Szakértői döntés'], ['expert_draft', 'Döntés megerősítésre vár']].map(([key, label]) => `<option value="${key}" ${state.stageFilter === key ? 'selected' : ''}>${label}</option>`).join('')}</select></label></div><div class="matrix-wrap" tabindex="0" role="region" aria-label="Görgethető kapcsoltsági mátrix"><table class="matrix"><thead><tr><th scope="col">Vállalkozás</th>${cols.map(v => `<th scope="col">${esc(v.name)}</th>`).join('')}</tr></thead><tbody>${cols.map(a => `<tr><th scope="row">${esc(a.name)}</th>${cols.map(b => `<td>${a.id === b.id ? '—' : cell(lookup[pairKey(a.id, b.id)])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="legend"><span>↗ Kapcsoltsági jelzés</span><span>▤ Nyilatkozatra vár</span><span>? Ellenőrizendő</span></div><div class="pairs" aria-label="Cégpárok listája">${rows.map(r => `<button class="pair-button ${state.selected === pairKey(r.first, r.second) ? 'selected' : ''}" data-action="pair" data-index="${c.calculation.rows.indexOf(r)}"><div><strong>${esc(r.first_name)} ↔ ${esc(r.second_name)}</strong><small class="muted">${esc(r.label)}</small></div>${badge(r.stage_label, r.stage === 'missing_data' ? 'amber' : 'teal')}</button>`).join('') || '<p class="muted">A szűrésnek nincs megfelelő cégpárja.</p>'}</div></section><aside class="panel detail" id="pair-detail" tabindex="-1">${selected ? detailView(selected) : '<h2>Nincs kiválasztott cégpár</h2><p>Módosítsd a szűrést.</p>'}</aside></div>`;
  }

  function detailView(row) {
    const evidence = row.evidence;
    const factNames = names();
    return `<h2>${esc(row.first_name)} ↔ ${esc(row.second_name)}</h2>${badge(row.stage_label, ['missing_data','management_review'].includes(row.stage) ? 'amber' : 'teal')}<p><strong>${esc(row.label)}</strong>${state.current.status === 'draft' ? ' · előzetes' : ''}</p><p>${esc(row.reason)}</p>${row.basis ? `<p class="small"><strong>Jogalap:</strong> ${esc(row.basis)}</p>` : ''}${row.signals.length ? `<hr><h3>Kapcsoltsági jelzések</h3><ul>${row.signals.map(v => `<li>${esc(v)}</li>`).join('')}</ul>` : ''}${row.influence_calculations?.length ? `<h3>Szavazati befolyás számítása</h3>${row.influence_calculations.map(v => `<p class="small"><strong>${esc(v.owner_name || factNames[v.owner])} → ${esc(factNames[v.company])}: ${esc(v.value)}</strong><br>${esc(v.basis)} · ${v.majority ? 'Több mint 50%' : 'Többség nem igazolt'}<br>Felhasznált kapcsolatok: ${v.fact_ids.map(id => {const f = row.facts.find(f => f.id === id); return f ? esc(factNames[f.owner]) + ' → ' + esc(factNames[f.company]) : '';}).filter(Boolean).join('; ')}</p>`).join('')}` : ''}${row.missing.length ? `<h3>Tisztázandó</h3><ul>${row.missing.map(v => `<li>${esc(v)}</li>`).join('')}</ul>` : ''}${row.assumptions.length ? `<h3>Feltételezések</h3><ul>${row.assumptions.map(v => `<li>${esc(v)}</li>`).join('')}</ul>` : ''}${evidence.source ? `<hr><h3>A döntés forrása</h3><p>${esc(evidence.source)}${evidence.page ? ` · ${evidence.page}. oldal` : ''}</p>${evidence.quote ? `<blockquote>${esc(evidence.quote)}</blockquote>` : ''}${evidence.document_id ? `<a class="button" href="/api/tao/cases/${esc(state.current.id)}/documents/${esc(evidence.document_id)}">Forrásirat letöltése</a>` : ''}` : ''}${controlDetail(row, factNames)}${specialDetail(row, factNames)}${row.family_facts?.length ? `<hr><h3>Rokonság igazoló forrásai</h3>${row.family_facts.map(f => `<p class="small"><strong>${esc(factNames[f.first])} ↔ ${esc(factNames[f.second])}</strong><br>${esc(familyLabels[f.relationship])}<br>${esc(f.evidence.source)}${f.evidence.page ? ' · ' + esc(f.evidence.page) + '. oldal' : ''}${f.evidence.quote ? '<br>' + esc(f.evidence.quote) : ''}</p>`).join('')}` : ''}${row.facts.length ? `<hr><h3>Felhasznált szavazati adatok</h3>${row.facts.map(f => `<p class="small">${esc(factNames[f.owner])} → ${esc(factNames[f.company])}<br>${esc(modes[f.vote_mode])}<br>${esc(f.evidence.source || 'Forrás még nincs megadva')}${f.evidence.page ? ` · ${f.evidence.page}. oldal` : ''}</p>`).join('')}` : ''}<hr>${button('Minősítés rögzítése', 'decision', 'primary', '', 'edit')}`;
  }

  function dataView() {
    const d = state.current.data;
    const actor = names();
    return `<section class="panel"><div class="panel-title"><h2>Vállalkozások</h2>${button('Vállalkozás felvétele', 'company', 'accent', '', 'plus')}</div>${d.companies.map(v => `<div class="row"><div><strong>${esc(v.name)}</strong><p class="small muted">${esc(v.registration || 'Cégazonosító még nincs megadva')}</p>${badge(v.registry_reviewed_on === d.as_of ? 'Cégjegyzéki adatok ellenőrizve' : 'Cégjegyzéki ellenőrzésre vár', v.registry_reviewed_on === d.as_of ? 'teal' : 'amber')}</div>${button('Szerkesztés', 'company', '', `data-id="${esc(v.id)}"`, 'edit')}</div>`).join('')}</section><section class="panel"><div class="panel-title"><h2>Természetes személyek</h2>${button('Személy felvétele', 'person', 'accent', '', 'plus')}</div>${d.persons.map(p => `<div class="row"><div><strong>${esc(p.name)}</strong><p class="small muted">${esc(p.notes)}</p></div>${button('Szerkesztés', 'person', '', `data-id="${esc(p.id)}"`, 'edit')}</div>`).join('') || '<p class="muted">Még nincs személy rögzítve.</p>'}<p class="small muted">A rokonságot külön, forrással és időponttal rögzítsd. Névazonosság önmagában nem bizonyít kapcsolatot.</p></section><section class="panel"><div class="panel-title"><h2>Hozzátartozói viszonyok</h2>${button('Rokonság rögzítése', 'family', 'accent', '', 'plus')}</div><p class="small muted">Csak igazolt, a vizsgálati napon fennálló közeli hozzátartozói viszonyból készül összeszámítás. A rokonsági lánc nem bizonyít további rokonságot.</p>${(d.family_facts || []).map(f => `<div class="row"><div><strong>${esc(actor[f.first])} ↔ ${esc(actor[f.second])}</strong><p class="small">${esc(familyLabels[f.relationship])}</p>${badge(f.confirmed ? 'Forrással igazolt' : 'Igazolásra vár', f.confirmed ? 'teal' : 'amber')}<p class="small muted">${esc(f.valid_from || 'Kezdőnap nem ismert')} – ${esc(f.valid_to || 'Végdátum nincs megadva')} · Ellenőrzött nap: ${esc(f.reviewed_as_of || 'nincs')}<br>${esc(f.evidence.source || 'Forrás nincs megadva')}</p></div>${button('Szerkesztés', 'family', '', `data-id="${esc(f.id)}"`, 'edit')}</div>`).join('') || '<p class="muted">Még nincs rögzített rokonsági adat.</p>'}</section><section class="panel"><div class="panel-title"><h2>Tulajdon és szavazat</h2>${button('Kapcsolat felvétele', 'voting', 'primary', '', 'plus')}</div>${d.voting_facts.map(f => `<div class="row"><div><strong>${esc(actor[f.owner])} → ${esc(actor[f.company])}</strong><p class="small">Tőke: ${esc(f.capital ?? 'ismeretlen')} ${f.capital !== null ? '%' : ''} · ${esc(modes[f.vote_mode])}${f.vote_bound === 'over_half' ? ' · >50%' : f.votes !== null ? ' · ' + esc(f.votes) + '%' : ''}</p><p class="small muted">${esc(f.valid_from || 'Kezdőnap nem ismert')} – ${esc(f.valid_to || 'Végdátum nincs megadva')} · Vizsgálati napra ellenőrizve: ${esc(f.reviewed_as_of || 'nincs')}<br>${esc(f.evidence.source || 'Forrás nincs megadva')}</p></div>${button('Szerkesztés', 'voting', '', `data-id="${esc(f.id)}"`, 'edit')}</div>`).join('') || '<p class="muted">Ismert tulajdoni arányból jelölt szavazati alapérték képezhető. Hiányzó arányból nem számolunk nullát vagy egyenlő részeket.</p>'}</section>${controlPanels(d, actor)}${specialPanels(d, actor)}`;
  }

  function proof(f) {
    return `<p class="small">${esc(f.reason || '')}</p><p class="small muted">${esc(f.evidence.source || 'Forrás nincs megadva')}${f.evidence.page ? ' · ' + esc(f.evidence.page) + '. oldal' : ''}<br>${esc(f.valid_from || 'Kezdőnap nem ismert')} – ${esc(f.valid_to || 'Végdátum nincs megadva')} · Ellenőrzött nap: ${esc(f.reviewed_as_of || 'nincs')}</p>${f.evidence.quote ? '<blockquote>' + esc(f.evidence.quote) + '</blockquote>' : ''}`;
  }
  function controlPanels(d, actor) {
    return `<section class="panel"><div class="panel-title"><h2>Meghatározó befolyási jogok</h2>${button('Irányítási jog rögzítése','control','accent','','plus')}</div><p class="small muted">A Ptk. szerinti joghoz tagi / részvényesi jogállás is szükséges. A szavazási megállapodásnak együtt több mint 50% szavazatot kell biztosítania.</p>${(d.control_facts || []).map(f => `<div class="row"><div><strong>${esc(actor[f.owner])} → ${esc(actor[f.company])}</strong><p>${esc(controlLabels[f.kind])}</p><p class="small">${esc(membershipLabel(f.membership))} · Jogcím fennáll: ${esc(answerLabel(f.condition))}${f.kind === 'voting_agreement' ? ' · Közös szavazat: ' + (f.aligned_bound === 'over_half' ? '>50%' : esc(f.aligned_votes ?? 'ismeretlen') + (f.aligned_votes != null ? '%' : '')) : ''}</p>${badge(f.confirmed ? 'Forrással ellenőrzött' : 'Ellenőrzésre vár',f.confirmed ? 'teal':'amber')}${proof(f)}</div>${button('Szerkesztés','control','',`data-id="${esc(f.id)}"`,'edit')}</div>`).join('') || '<p class="muted">Még nincs rögzített irányítási jog.</p>'}</section><section class="panel"><div class="panel-title"><h2>Ügyvezetés és döntő irányítás</h2>${button('Ügyvezetési tény rögzítése','management','accent','','plus')}</div><p class="small muted">Az azonos vezető önmagában nem elegendő: az üzleti ÉS pénzügyi politikára vonatkozó döntő befolyást is igazolni kell.</p>${(d.management_facts || []).map(f => `<div class="row"><div><strong>${esc(actor[f.first])} ↔ ${esc(actor[f.second])}</strong><p class="small">Vezető(k): ${f.managers.map(id => esc(actor[id])).join(', ')}<br>Ügyvezetési egyezőség: ${esc(answerLabel(f.common_management))} · Üzleti döntő befolyás: ${esc(answerLabel(f.business_control))} · Pénzügyi döntő befolyás: ${esc(answerLabel(f.financial_control))}</p>${badge(f.confirmed ? 'Forrással ellenőrzött' : 'Ellenőrzésre vár',f.confirmed ? 'teal':'amber')}${proof(f)}</div>${button('Szerkesztés','management','',`data-id="${esc(f.id)}"`,'edit')}</div>`).join('') || '<p class="muted">Még nincs rögzített ügyvezetési tény.</p>'}</section>`;
  }
  function controlDetail(row, actor) {
    return `${row.control_calculations?.length ? '<hr><h3>Meghatározó befolyás útvonalai</h3>' + row.control_calculations.map(v => '<p class="small"><strong>' + v.route.map(id => esc(actor[id])).join(' → ') + '</strong><br>' + esc(v.basis) + '</p>').join('') : ''}${row.control_facts?.length ? '<hr><h3>Irányítási jogok forrásai</h3>' + row.control_facts.map(f => '<strong>' + esc(actor[f.owner]) + ' → ' + esc(actor[f.company]) + '</strong><p class="small">' + esc(controlLabels[f.kind]) + ' · ' + esc(membershipLabel(f.membership)) + ' · Jogcím: ' + esc(answerLabel(f.condition)) + '</p>' + proof(f)).join('') : ''}${row.management_facts?.length ? '<hr><h3>Ügyvezetési tények forrásai</h3>' + row.management_facts.map(f => '<p class="small">Vezető(k): ' + f.managers.map(id => esc(actor[id])).join(', ') + '<br>Egyezőség: ' + esc(answerLabel(f.common_management)) + ' · Üzleti döntő befolyás: ' + esc(answerLabel(f.business_control)) + ' · Pénzügyi döntő befolyás: ' + esc(answerLabel(f.financial_control)) + '</p>' + proof(f)).join('') : ''}`;
  }

  function specialPanels(d, actor) {
    return `<section class="panel"><div class="panel-title"><h2>Tao-telephelyek</h2>${button('Telephelyi tény rögzítése','pe','accent','','plus')}</div><p class="small muted">A Tao szerinti telephelyi jogállást külön kell igazolni. A cégjegyzéki telephelycím önmagában nem elegendő. A szervezeteknél előbb válaszd ki a Tao-telephely típust.</p>${(d.establishment_facts || []).map(f=>`<div class="row"><div><strong>${esc(actor[f.principal])} → ${esc(actor[f.establishment])}</strong><p>${esc(Object.fromEntries(peTypes)[f.kind])} · Jogállás: ${esc(answerLabel(f.tax_status))}</p>${proof(f)}</div>${button('Szerkesztés','pe','',`data-id="${esc(f.id)}"`,'edit')}</div>`).join('')}</section><section class="panel"><div class="panel-title"><h2>Bizalmi vagyonkezelés</h2>${button('BVK-tény rögzítése','trust','accent','','plus')}</div><p class="small muted">A vagyonkezelő, vagyonrendelő és kedvezményezett szerepe külön adat. A szerep önmagában nem jelent irányítási jogot. A szavazatok BVK-jogállását a szavazati sorban is jelöld.</p>${(d.trust_facts || []).map(f=>`<div class="row"><div><strong>${esc(f.name)}</strong><p class="small">Vagyonkezelő: ${f.trustees.map(id=>esc(actor[id])).join(', ')}<br>Érintett részesedések: ${f.holdings.map(id=>esc(actor[id])).join(', ')}</p>${proof(f)}</div>${button('Szerkesztés','trust','',`data-id="${esc(f.id)}"`,'edit')}</div>`).join('')}</section>`;
  }
  function specialDetail(row, actor) {
    return `${row.establishment_facts?.length ? '<h3>Telephelyi források</h3>'+row.establishment_facts.map(f=>'<p>'+esc(actor[f.principal])+' → '+esc(actor[f.establishment])+' · '+esc(Object.fromEntries(peTypes)[f.kind])+'</p>'+proof(f)).join('') : ''}${row.trust_facts?.length ? '<h3>BVK-források</h3>'+row.trust_facts.map(f=>'<strong>'+esc(f.name)+'</strong>'+proof(f)).join('') : ''}`;
  }
  function peEditor(id) {
    const d=state.current.data,f=(d.establishment_facts || []).find(f=>f.id===id) || {};
    const estates=d.companies.filter(c=>c.entity_type==='permanent_establishment');
    if(!estates.length){toast('Előbb rögzíts egy Tao-telephely típusú szervezetet a Vállalkozások résznél.');return;}
    showEditor('Tao-telephely',`${select('Fővállalkozás','principal',f.principal || d.companies[0].id,d.companies.map(c=>[c.id,c.name]))}${select('Tao-telephely','establishment',f.establishment || estates[0].id,estates.map(c=>[c.id,c.name]))}${select('Jogviszony','kind',f.kind || peTypes[0][0],peTypes)}${select('Az adójogi telephelyi jogállás fennáll','tax_status',f.tax_status || 'unknown',answers)}${factDates(f)}${area('Adójogi tényállás és indok','reason',f.reason)}${evidenceFields(f.evidence)}${check('Az adójogi telephelyi minőséget és a fővállalkozás jogállását ellenőriztem.','confirmed',f.confirmed)}`,async p=>{
      const next=copy();next.establishment_facts ||= [];upsert(next.establishment_facts,{id:id || crypto.randomUUID(),principal:p.principal,establishment:p.establishment,kind:p.kind,tax_status:p.tax_status,valid_from:nullable(p.valid_from),valid_to:nullable(p.valid_to),reviewed_as_of:nullable(p.reviewed_as_of),reason:p.reason,evidence:evidenceInput(p),confirmed:!!p.confirmed});await save(next);
    },id ? async()=>{const next=copy();next.establishment_facts=next.establishment_facts.filter(f=>f.id!==id);await save(next);} : null);
  }
  function trustEditor(id) {
    const d=state.current.data,f=(d.trust_facts || []).find(f=>f.id===id) || {}, actors=[...d.companies,...d.persons];
    const groups=[['trustees','Vagyonkezelők',actors],['settlors','Vagyonrendelők',actors],['beneficiaries','Kedvezményezettek (ha ismertek)',actors],['holdings','Érintett részesedések – vállalkozások',d.companies]];
    showEditor('Bizalmi vagyonkezelés',`${field('Kezelt vagyon / szerződés megnevezése','name',f.name,'text','required maxlength="200"')}${select('Elkülönült kezelt vagyon, ha külön szereplőként rögzítve','asset_entity',f.asset_entity || '',[['','Nincs külön szereplő'],...d.companies.filter(c=>c.entity_type==='managed_assets').map(c=>[c.id,c.name])])}${groups.map(([key,label,items])=>'<fieldset class="field full"><legend>'+label+'</legend>'+items.map(a=>check(esc(a.name),key+'-'+encodeURIComponent(a.id),(f[key] || []).includes(a.id))).join('')+'</fieldset>').join('')}${factDates(f)}${area('Vagyonelkülönítés és tényleges joggyakorlás értékelése','reason',f.reason)}${evidenceFields(f.evidence)}${check('A tényleges szavazati és irányítási jogokat külön értékeltem; a megfelelő tényeknél rögzítettem.','rights_reviewed',f.rights_reviewed)}${check('A szerepeket és a szerződéses forrást ellenőriztem.','confirmed',f.confirmed)}`,async p=>{
      const next=copy();next.trust_facts ||= [];const fact={id:id || crypto.randomUUID(),name:p.name,asset_entity:nullable(p.asset_entity),valid_from:nullable(p.valid_from),valid_to:nullable(p.valid_to),reviewed_as_of:nullable(p.reviewed_as_of),reason:p.reason,evidence:evidenceInput(p),rights_reviewed:!!p.rights_reviewed,confirmed:!!p.confirmed};
      for(const [key,,items] of groups)fact[key]=items.filter(a=>p[key+'-'+encodeURIComponent(a.id)]).map(a=>a.id);
      upsert(next.trust_facts,fact);await save(next);
    },id ? async()=>{const next=copy();next.trust_facts=next.trust_facts.filter(f=>f.id!==id);await save(next);} : null);
  }

  function documentsView() {
    return `<section class="panel"><h2>Forrásiratok</h2><p class="muted">Az eredeti fájl megmarad. A tényeket és az oldalszámokat az Adatok és a Mátrix nézetben rögzítheted.</p><form id="upload-form"><div class="field"><label for="files">Dokumentumok kiválasztása</label><input id="files" name="files" type="file" multiple required accept=".pdf,.docx,.xlsx,.png,.jpg,.jpeg,.txt"><small>Fájlonként legfeljebb 20 MB. Új irat érkezése újraellenőrzést indít.</small></div><button class="primary" type="submit">Feltöltés</button></form>${state.docs.map(d => `<div class="row"><div><strong>${esc(d.filename)}</strong><p class="small muted">${Math.ceil(d.size / 1024)} KB · ${esc(d.created.slice(0, 10))}</p>${badge(d.reviewed_at ? 'Feldolgozott forrás' : 'Ellenőrzésre vár', d.reviewed_at ? 'teal' : 'amber')}</div><div class="actions"><a class="button" href="/api/tao/cases/${esc(state.current.id)}/documents/${esc(d.id)}">Letöltés</a>${!d.reviewed_at ? button('Feldolgoztam', 'review-document', '', `data-id="${esc(d.id)}"`) : ''}</div></div>`).join('') || '<p class="muted">Még nincs feltöltött dokumentum.</p>'}</section>`;
  }

  function reviewView() {
    const c = state.current;
    const calc = c.calculation;
    return `<section class="panel"><div class="panel-title"><h2>Szakértői ellenőrzés</h2>${badge(statusLabel(c.status), c.status.startsWith('approved') ? 'approved' : 'amber')}</div><p>${calc.counts.related} kapcsolt, ${calc.counts.not_related} nem kapcsolt és <strong>${calc.counts.undetermined} nem eldöntött cégpár</strong>.</p>${!calc.complete ? '<div class="notice"><strong>Részleges állásfoglalás is átadható</strong><p>A nem eldöntött párok és a vizsgálat korlátai az exportban is megmaradnak.</p></div>' : ''}<p>Jogi időállapot: ${esc(c.data.law_date || 'nincs rögzítve')}<br>Forrás: ${esc(c.data.law_source || 'nincs rögzítve')}</p>${button('Vizsgálati keret és jogi forrás', 'settings', 'accent')}${reviewer() && c.status === 'draft' ? `<form id="approval-form" class="forms"><label class="check"><input type="checkbox" name="relationships" required><span>A kapcsolati tényeket, forrásokat és szakértői döntéseket ellenőriztem.</span></label><label class="check"><input type="checkbox" name="rules" required><span>Az alkalmazandó jogi időállapotot és a vizsgálat céljára vonatkozó szabályokat ellenőriztem.</span></label><label class="check"><input type="checkbox" name="scope" required><span>A vállalt vizsgálati kört és a feltételezéseket ellenőriztem.</span></label><label class="check"><input type="checkbox" name="partial" ${!calc.complete ? 'checked' : ''}><span>Kifejezetten részleges állásfoglalást hagyok jóvá.</span></label>${area('Korlátok / jóváhagyási megjegyzés', 'note', '', !calc.complete ? 'required' : '')}<p id="approval-error" class="error" hidden></p><button type="submit" class="primary">${icon('shield')} Szakértői jóváhagyás</button></form>` : !reviewer() ? '<p class="muted">A jóváhagyást jóváhagyó szakértő vagy adminisztrátor végezheti el.</p>' : ''}</section><section class="panel"><h2>Verziók és napló</h2><div class="actions">${button('Mentett verziók', 'versions')}</div><div class="audit">${state.audit.map(v => `<div class="row"><div><strong>${esc(v.actor)}</strong><p>${esc(v.details || v.action)}</p><small>${esc(v.created)} · ${esc(v.action)}</small></div></div>`).join('')}</div></section>`;
  }

  function field(label, name, value = '', type = 'text', attrs = '', help = '') {
    return `<div class="field"><label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" ${attrs}>${help ? `<small>${help}</small>` : ''}</div>`;
  }
  function area(label, name, value = '', attrs = '') {
    return `<div class="field full"><label for="f-${name}">${label}</label><textarea id="f-${name}" name="${name}" ${attrs}>${esc(value)}</textarea></div>`;
  }
  function select(label, name, value, options) {
    return `<div class="field"><label for="f-${name}">${label}</label><select id="f-${name}" name="${name}">${options.map(([id, title]) => `<option value="${esc(id)}" ${String(value) === String(id) ? 'selected' : ''}>${esc(title)}</option>`).join('')}</select></div>`;
  }
  function check(label, name, value = false) {
    return `<label class="check"><input type="checkbox" name="${name}" ${value ? 'checked' : ''}><span>${label}</span></label>`;
  }
  function showEditor(title, content, onSubmit, remove = null) {
    editor.innerHTML = `<form id="editor-form"><div class="dialog-heading"><h2 id="editor-title">${esc(title)}</h2>${button(icon('close'), 'close', '', 'aria-label="Bezárás"')}</div><div class="dialog-body"><p class="error" id="editor-error" hidden></p><div class="form-grid">${content}</div></div><div class="dialog-footer">${remove ? button('Eltávolítás', 'remove', 'danger') : ''}${button('Mégse', 'close')}<button class="primary" type="submit">Mentés</button></div></form>`;
    showEditor.submit = onSubmit;
    showEditor.remove = remove;
    editor.showModal();
  }
  const formObject = form => Object.fromEntries(new FormData(form));
  const nullable = value => value || null;
  const percent = value => value.trim() ? value.trim().replace(',', '.') : null;
  const copy = () => structuredClone(state.current.data);
  const upsert = (items, value, key = 'id') => {
    const index = items.findIndex(v => v[key] === value[key]);
    if (index < 0) items.push(value); else items[index] = value;
  };
  async function save(data) {
    const c = state.current;
    await api('/tao/cases/' + c.id, {method: 'PUT', body: {data, version: c.version, client_user_id: c.client_user_id}});
    await openCase(c.id);
    toast('Új verzió mentve. A korábbi jóváhagyott állásfoglalás megmaradt.');
  }

  function newCase() {
    showEditor('Új Tao-vizsgálat', `${field('Vizsgálat neve', 'title', '', 'text', 'required maxlength="200"')}${field('Megbízó', 'client')}${field('Vizsgálati nap', 'as_of', today(), 'date', 'required')}${area('Vizsgált vállalkozások – soronként egy név', 'companies', '', 'required')}`, async p => {
      const companies = p.companies.split('\n').map(v => v.trim()).filter(Boolean).map(name => ({id: crypto.randomUUID(), name}));
      if (companies.length < 2) throw new Error('Legalább két vállalkozást adj meg.');
      const r = await api('/tao/cases', {method: 'POST', body: {data: {title: p.title, client: p.client, as_of: p.as_of, companies}}});
      state.tab = 'matrix';
      state.companyFilter = state.stageFilter = '';
      state.selected = null;
      await openCase(r.id);
    });
  }

  async function settings() {
    const d = state.current.data;
    state.users = await api('/users');
    const clients = [['', 'Nincs ügyfélfiók'], ...state.users.filter(v => v.role === 'client').map(v => [v.id, v.name])];
    showEditor('Vizsgálati keret', `${field('Vizsgálat neve', 'title', d.title, 'text', 'required')}${field('Megbízó', 'client', d.client)}${field('Vizsgálati nap', 'as_of', d.as_of, 'date', 'required')}${field('Jogi időállapot napja', 'law_date', d.law_date, 'date')}${area('Ellenőrzött jogi forrás / időállapot hivatkozása', 'law_source', d.law_source)}${area('Történeti alkalmazhatóság indoka eltérő időállapotnál','law_applicability',d.law_applicability || '')}${area('Vizsgálati cél', 'purpose', d.purpose)}${area('Vállalt vizsgálati kör és korlátai', 'scope', d.scope)}${area('Feltételezések', 'assumptions', d.assumptions)}${select('Hozzárendelt ügyfélfiók', 'client_user_id', state.current.client_user_id || '', clients)}`, async p => {
      const data = copy();
      for (const key of ['title', 'client', 'as_of', 'law_source', 'law_applicability', 'purpose', 'scope', 'assumptions']) data[key] = p[key];
      data.law_date = nullable(p.law_date);
      await api('/tao/cases/' + state.current.id, {method: 'PUT', body: {data, version: state.current.version, client_user_id: nullable(p.client_user_id)}});
      await openCase(state.current.id);
    });
  }

  function companyEditor(id) {
    const c = state.current.data.companies.find(v => v.id === id) || {};
    showEditor('Vállalkozás adatai', `${field('Vállalkozás neve', 'name', c.name, 'text', 'required maxlength="200"')}${field('Cégjegyzékszám / azonosító', 'registration', c.registration)}${select('Szervezet típusa','entity_type',c.entity_type || 'company',entityTypes)}${area('Cégjegyzéki adatellenőrzés forrása', 'registry_source', c.registry_source)}<div class="field full">${check('A cégjegyzéki adatokat a kiválasztott vizsgálati napra ellenőriztem.', 'registry_reviewed', c.registry_reviewed_on === state.current.data.as_of)}<small>Ez nem zárja ki automatikusan a rokonságot vagy más irányítási jogot.</small></div>`, async p => {
      const data = copy();
      upsert(data.companies, {id: id || crypto.randomUUID(), name: p.name, registration: p.registration, entity_type:p.entity_type, registry_source: p.registry_source, registry_reviewed_on: p.registry_reviewed ? data.as_of : null});
      await save(data);
    });
  }

  function personEditor(id) {
    const p = state.current.data.persons.find(v => v.id === id) || {};
    showEditor('Természetes személy', `${field('Teljes név', 'name', p.name, 'text', 'required maxlength="200"')}${area('Megkülönböztető adat / forrás / megjegyzés', 'notes', p.notes)}`, async values => {
      const data = copy();
      upsert(data.persons, {id: id || crypto.randomUUID(), name: values.name, notes: values.notes});
      await save(data);
    });
  }

  function evidenceFields(evidence = {}) {
    return `${area('Forrás megnevezése / nyilatkozat', 'source', evidence.source)}${select('Kapcsolódó feltöltött irat', 'document_id', evidence.document_id || '', [['', 'Nincs kiválasztott irat'], ...state.docs.map(v => [v.id, v.filename])])}${field('Oldalszám', 'page', evidence.page, 'number', 'min="1" max="10000"')}${area('Forrásidézet', 'quote', evidence.quote)}`;
  }
  const evidenceInput = p => ({source: p.source, document_id: nullable(p.document_id), page: p.page ? Number(p.page) : null, quote: p.quote});

  function familyEditor(id) {
    const data = state.current.data;
    if (data.persons.length < 2) {toast('Előbb legalább két természetes személyt rögzíts.'); return;}
    const f = (data.family_facts || []).find(v => v.id === id) || {};
    const people = data.persons.map(v => [v.id, v.name]);
    showEditor('Hozzátartozói viszony', `${select('Első személy', 'first', f.first || people[0][0], people)}${select('Második személy', 'second', f.second || people[1][0], people)}${select('Viszony típusa', 'relationship', f.relationship || 'spouse', Object.entries(familyLabels))}${field('Érvényesség kezdete', 'valid_from', f.valid_from, 'date')}${field('Vége – ettől a naptól nem hatályos', 'valid_to', f.valid_to, 'date')}${field('Ha a kezdőnap hiányzik: ellenőrzött vizsgálati nap', 'reviewed_as_of', f.reviewed_as_of || data.as_of, 'date')}${evidenceFields(f.evidence)}<div class="field full">${check('A személyazonosságot és a hozzátartozói viszonyt a megadott forrás alapján ellenőriztem.', 'confirmed', f.confirmed)}</div>`, async p => {
      const next = copy();
      next.family_facts ||= [];
      upsert(next.family_facts, {id:id || crypto.randomUUID(), first:p.first, second:p.second,
        relationship:p.relationship, valid_from:nullable(p.valid_from), valid_to:nullable(p.valid_to),
        reviewed_as_of:nullable(p.reviewed_as_of), evidence:evidenceInput(p), confirmed:!!p.confirmed});
      await save(next);
    }, id ? async () => {
      const next = copy(); next.family_facts = next.family_facts.filter(v => v.id !== id); await save(next);
    } : null);
  }

  function factDates(f) {
    return `${field('Érvényesség kezdete','valid_from',f.valid_from,'date')}${field('Vége – ettől a naptól nem hatályos','valid_to',f.valid_to,'date')}${field('Ha a kezdőnap hiányzik: ellenőrzött vizsgálati nap','reviewed_as_of',f.reviewed_as_of || state.current.data.as_of,'date')}`;
  }
  function controlEditor(id) {
    const d=state.current.data, f=(d.control_facts || []).find(v=>v.id===id) || {};
    const actors=[...d.companies,...d.persons].map(v=>[v.id,v.name]);
    showEditor('Meghatározó befolyási jog', `${select('Befolyással rendelkező','owner',f.owner || actors[0][0],actors)}${select('Célvállalkozás','company',f.company || d.companies[1].id,d.companies.map(v=>[v.id,v.name]))}${select('Jogcím','kind',f.kind || 'appointments',Object.entries(controlLabels))}${select('Tagi / részvényesi jogállás','membership',f.membership || 'unknown',[['unknown','Tisztázandó'],['member','Tag / részvényes'],['not_member','Nem tag / részvényes']])}${select('A választott jogcím feltétele fennáll','condition',f.condition || 'unknown',answers)}<div id="agreement-votes" class="field full">${select('Szavazati adat pontossága','aligned_bound',f.aligned_bound || 'exact',[['exact','Pontos százalék'],['over_half','Dokumentáltan több mint 50%']])}${field('Megállapodás szerinti összes szavazat (%)','aligned_votes',f.aligned_votes,'text','inputmode="decimal"','A jogosult és a vele azonosan szavazó / rajta keresztül szavazó tagok együtt. A saját szavazatot csak egyszer számold.')}</div>${factDates(f)}${area('Jogosultság és tényleges tartalom indoka','reason',f.reason)}${evidenceFields(f.evidence)}<div class="field full">${check('A tagi jogállást, a jogcím tartalmát és a forrást ellenőriztem.','confirmed',f.confirmed)}</div>`,async p=>{
      const next=copy();next.control_facts ||= [];
      upsert(next.control_facts,{id:id || crypto.randomUUID(),owner:p.owner,company:p.company,kind:p.kind,membership:p.membership,
        condition:p.condition,aligned_bound:p.kind==='voting_agreement' ? p.aligned_bound : 'exact',aligned_votes:p.kind==='voting_agreement' && p.aligned_bound !== 'over_half' ? percent(p.aligned_votes) : null,
        valid_from:nullable(p.valid_from),valid_to:nullable(p.valid_to),reviewed_as_of:nullable(p.reviewed_as_of),
        reason:p.reason,evidence:evidenceInput(p),confirmed:!!p.confirmed});await save(next);
    },id ? async()=>{const next=copy();next.control_facts=next.control_facts.filter(f=>f.id!==id);await save(next);} : null);
    toggleControlFields();
  }
  function toggleControlFields() {
    const kind=editor.querySelector('[name=kind]');if(!kind)return;
    editor.querySelector('#agreement-votes').hidden=kind.value!=='voting_agreement';
    editor.querySelector('[name=aligned_votes]').disabled=editor.querySelector('[name=aligned_bound]').value==='over_half';
  }
  function managementEditor(id) {
    const d=state.current.data,f=(d.management_facts || []).find(v=>v.id===id) || {};
    const actors=[...d.companies,...d.persons];
    showEditor('Ügyvezetés és döntő irányítás', `${select('Első vállalkozás','first',f.first || d.companies[0].id,d.companies.map(v=>[v.id,v.name]))}${select('Második vállalkozás','second',f.second || d.companies[1].id,d.companies.map(v=>[v.id,v.name]))}<div class="field full"><span>Közös vezető(k) / ügyvezetést ellátó szereplők</span>${actors.map(a=>check(esc(a.name),'manager-'+encodeURIComponent(a.id),(f.managers || []).includes(a.id))).join('')}</div>${select('Az ügyvezetési egyezőség igazolt','common_management',f.common_management || 'unknown',answers)}${select('Döntő befolyás az üzleti politikában','business_control',f.business_control || 'unknown',answers)}${select('Döntő befolyás a pénzügyi politikában','financial_control',f.financial_control || 'unknown',answers)}${factDates(f)}${area('Tényleges döntési rend és indok','reason',f.reason)}${evidenceFields(f.evidence)}<div class="field full">${check('A vezetők azonosságát, a tényleges döntési rendet és a forrást ellenőriztem.','confirmed',f.confirmed)}</div>`,async p=>{
      const next=copy();next.management_facts ||= [];
      const managers=actors.filter(a=>p['manager-'+encodeURIComponent(a.id)]).map(a=>a.id);
      upsert(next.management_facts,{id:id || crypto.randomUUID(),first:p.first,second:p.second,managers,
        common_management:p.common_management,business_control:p.business_control,financial_control:p.financial_control,
        valid_from:nullable(p.valid_from),valid_to:nullable(p.valid_to),reviewed_as_of:nullable(p.reviewed_as_of),
        reason:p.reason,evidence:evidenceInput(p),confirmed:!!p.confirmed});await save(next);
    },id ? async()=>{const next=copy();next.management_facts=next.management_facts.filter(f=>f.id!==id);await save(next);} : null);
  }

  function votingEditor(id) {
    const data = state.current.data;
    const f = data.voting_facts.find(v => v.id === id) || {};
    const owners = [...data.companies, ...data.persons].map(v => [v.id, v.name]);
    showEditor('Tulajdon és szavazat', `${select('Tulajdonos / szavazati jogosult', 'owner', f.owner || data.companies[0].id, owners)}${select('Célvállalkozás', 'company', f.company || data.companies[1].id, data.companies.map(v => [v.id, v.name]))}${field('Tulajdoni arány (%)', 'capital', f.capital, 'text', 'inputmode="decimal"', 'Ismeretlen aránynál maradjon üres.')}${select('Szavazati adat kezelése', 'vote_mode', f.vote_mode || 'ownership_default', Object.entries(modes))}<div class="field full" id="vote-fields">${select('Szavazati adat pontossága', 'vote_bound', f.vote_bound || 'exact', [['exact', 'Pontos százalék'], ['over_half', 'Szavazat meghaladja az 50%-ot']])}${field('Szavazati arány (%)', 'votes', f.votes, 'text', 'inputmode="decimal"')}</div>${field('Érvényesség kezdete', 'valid_from', f.valid_from, 'date')}${field('Vége – ettől a naptól nem hatályos', 'valid_to', f.valid_to, 'date')}${field('Ha a kezdőnap hiányzik: ellenőrzött vizsgálati nap', 'reviewed_as_of', f.reviewed_as_of || data.as_of, 'date')}${field('Cégbírósági bejegyzés kelte', 'registered_on', f.registered_on, 'date')}${field('Törlés bejegyzésének kelte', 'deletion_registered_on', f.deletion_registered_on, 'date')}${area('Indok / szakértői felülbírálat indoka', 'reason', f.reason)}${select('A részesedés jogállása','capacity',f.capacity || 'own',[['own','Saját vagyon'],['trustee','Bizalmi vagyonkezelőként'],['unknown','Tisztázandó']])}${check('A BVK-szavazatok hozzárendelését a megadott indok és forrás alapján külön ellenőriztem.','attribution_reviewed',f.attribution_reviewed)}${evidenceFields(f.evidence)}`, async p => {
      const next = copy();
      const exact = ['explicit', 'expert'].includes(p.vote_mode);
      const fact = {id: id || crypto.randomUUID(), owner: p.owner, company: p.company, capital: percent(p.capital), vote_mode: p.vote_mode,
        vote_bound: exact ? p.vote_bound : 'exact', votes: exact && p.vote_bound === 'exact' ? percent(p.votes) : null,
        capacity:p.capacity,attribution_reviewed:!!p.attribution_reviewed,reason: p.reason, evidence: evidenceInput(p)};
      for (const key of ['valid_from', 'valid_to', 'reviewed_as_of', 'registered_on', 'deletion_registered_on']) fact[key] = nullable(p[key]);
      upsert(next.voting_facts, fact);
      await save(next);
    }, id ? async () => {
      const next = copy();
      next.voting_facts = next.voting_facts.filter(v => v.id !== id);
      await save(next);
    } : null);
    toggleVotingFields();
  }

  function toggleVotingFields() {
    const mode = editor.querySelector('[name=vote_mode]');
    if (!mode) return;
    const exact = ['explicit', 'expert'].includes(mode.value);
    editor.querySelector('#vote-fields').hidden = !exact;
    const votes = editor.querySelector('[name=votes]');
    votes.disabled = !exact || editor.querySelector('[name=vote_bound]').value === 'over_half';
  }

  function decisionEditor() {
    const row = state.current.calculation.rows.find(r => pairKey(r.first, r.second) === state.selected);
    if (!row) return;
    const d = state.current.data.decisions.find(v => pairKey(v.first, v.second) === state.selected && v.as_of === state.current.data.as_of) || {};
    showEditor(`${row.first_name} ↔ ${row.second_name}`, `<div class="field full"><p>Vizsgálati nap: <strong>${esc(state.current.data.as_of)}</strong></p><p class="small muted">A jogi minősítéshez a releváns jogalapot és a megerősített tényállást rögzítsd.</p></div>${select('Jogi minősítés', 'result', d.result || 'undetermined', Object.entries(labels))}${select('Ha nem dönthető el: következő lépés', 'stage', d.stage || 'unreviewed', [['unreviewed', 'Iratellenőrzésre vár'], ['awaiting_declaration', 'Nyilatkozatra vár'], ['missing_data', 'Hiányzó adat'], ['management_review', 'Közös vezetés – irányítás tisztázandó']])}${select('Jogalap csoportja – telephelyi továbbvezetéshez','legal_ground',d.legal_ground || 'unspecified',[['unspecified','Nincs besorolva'],['abc','Tao. 4. § 23. a)–c)'],['management','Ügyvezetés: f)'],['pe','Telephely: d)–e)'],['other','Más jogalap']])}${area('Jogalap – pontos rendelkezés / alpont', 'basis', d.basis)}${area('Szakértői indokolás', 'reason', d.reason)}${evidenceFields(d.evidence)}${area('Alkalmazott feltételezés', 'assumptions', d.assumptions)}${area('Hiányzó tény / következő lépés', 'missing', d.missing)}<div class="field full">${check('A rögzített döntés tényállását, indokát és forrását megerősítettem.', 'confirmed', d.confirmed)}${check('A negatív minősítéshez minden releváns jogalapot ellenőriztem a vállalt körben.', 'relevant_grounds_reviewed', d.relevant_grounds_reviewed)}</div>`, async p => {
      const next = copy();
      const value = {first: row.first, second: row.second, as_of: next.as_of, result: p.result, stage: p.stage,
        legal_ground:p.legal_ground,basis: p.basis, reason: p.reason, evidence: evidenceInput(p), assumptions: p.assumptions, missing: p.missing,
        confirmed: Boolean(p.confirmed), relevant_grounds_reviewed: Boolean(p.relevant_grounds_reviewed)};
      const index = next.decisions.findIndex(v => pairKey(v.first, v.second) === state.selected && v.as_of === next.as_of);
      if (index < 0) next.decisions.push(value); else next.decisions[index] = value;
      await save(next);
    });
  }

  async function demo() {
    const as_of = '2025-12-31';
    const companies = ['Alfa Finance', 'Alfa Holding', 'Alfa Advisory', 'Alfa System', 'Alfa Marketing', 'Alfa Software'].map((name, i) => ({id: 'c' + i, name}));
    const voting_facts = [
      {id: 'f1', owner: 'c0', company: 'c3', capital: '100', vote_mode: 'ownership_default', reviewed_as_of: as_of, evidence: {source: 'Fiktív mintairat – nem ügyféladat'}},
      {id: 'f2', owner: 'c1', company: 'c5', capital: '30', vote_mode: 'explicit', vote_bound: 'over_half', reviewed_as_of: as_of, evidence: {source: 'Fiktív mintairat – szavazati jelzés >50%'}},
    ];
    const result = await api('/tao/cases', {method: 'POST', body: {data: {title: 'Tao-mintavizsgálat', client: 'Fiktív mintaadatok', as_of, companies, voting_facts}}});
    state.tab = 'matrix';
    state.companyFilter = state.stageFilter = '';
    state.selected = null;
    await openCase(result.id);
  }

  async function download(kind) {
    const response = await fetch(`/api/tao/cases/${state.current.id}/report/${kind}`);
    if (!response.ok) {
      const value = await response.json();
      throw new Error(value.detail || 'Az export nem sikerült.');
    }
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `Tao_vizsgalat_v${state.current.version}.${kind}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  root.addEventListener('click', async event => {
    const node = event.target.closest('[data-action]');
    if (!node || node.disabled) return;
    try {
      switch (node.dataset.action) {
        case 'dashboard': state.cases = await api('/tao/cases'); dashboard(); break;
        case 'new': newCase(); break;
        case 'demo': await demo(); break;
        case 'open': state.selected = null; state.tab = 'matrix'; state.companyFilter = state.stageFilter = ''; await openCase(node.dataset.id); break;
        case 'tab': state.tab = node.dataset.tab; renderCase(); break;
        case 'pair': {
          const row = state.current.calculation.rows[Number(node.dataset.index)];
          state.selected = pairKey(row.first, row.second);
          renderCase();
          document.querySelector('#pair-detail')?.focus();
          break;
        }
        case 'settings': await settings(); break;
        case 'company': companyEditor(node.dataset.id); break;
        case 'pe': peEditor(node.dataset.id); break;
        case 'trust': trustEditor(node.dataset.id); break;
        case 'control': controlEditor(node.dataset.id); break;
        case 'management': managementEditor(node.dataset.id); break;
        case 'family': familyEditor(node.dataset.id); break;
        case 'person': personEditor(node.dataset.id); break;
        case 'voting': votingEditor(node.dataset.id); break;
        case 'decision': decisionEditor(); break;
        case 'export': node.disabled = true; await download(node.dataset.kind); node.disabled = false; break;
        case 'review-document': await api(`/tao/cases/${state.current.id}/documents/${node.dataset.id}/review`, {method: 'POST'}); await openCase(state.current.id); toast('A dokumentum feldolgozottként rögzítve.'); break;
        case 'versions': {
          const list = await api(`/tao/cases/${state.current.id}/versions`);
          showEditor('Mentett verziók', `<div class="field full">${list.map(v => `<p><strong>${v.version}. verzió</strong> · ${esc(v.created)} ${v.approved_at ? badge('Jóváhagyott', 'approved') : ''}<br><a class="button" href="/api/tao/cases/${esc(state.current.id)}/report/docx?version=${v.version}">Word megnyitása</a></p>`).join('')}</div>`, async () => {});
          break;
        }
        case 'logout': await api('/auth/logout', {method: 'POST'}); state.current = null; await boot(); break;
      }
    } catch (error) {
      node.disabled = false;
      toast(error.message);
    }
  });

  editor.addEventListener('change', event => {if(['kind','aligned_bound'].includes(event.target.name))toggleControlFields();});

  root.addEventListener('change', event => {
    if (event.target.id === 'company-filter') {state.companyFilter = event.target.value; renderCase();}
    if (event.target.id === 'stage-filter') {state.stageFilter = event.target.value; renderCase();}
  });

  root.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.target;
    const submit = form.querySelector('[type=submit]');
    submit.disabled = true;
    try {
      const values = formObject(form);
      if (form.id === 'login-form') {
        const setup = form.dataset.setup === 'true';
        const payload = {username: values.username, password: values.password};
        if (setup) payload.name = values.name;
        const r = await api(setup ? '/auth/setup' : '/auth/login', {method: 'POST', body: payload});
        state.user = r.user; state.csrf = r.csrf;
        state.cases = await api('/tao/cases'); dashboard();
      } else if (form.id === 'upload-form') {
        for (const file of form.querySelector('[name=files]').files) {
          const body = new FormData(); body.append('file', file);
          await api(`/tao/cases/${state.current.id}/documents`, {method: 'POST', body});
        }
        await openCase(state.current.id);
        toast('A forrásiratok feltöltve; a kapcsolati döntések újraellenőrzésre várnak.');
      } else if (form.id === 'approval-form') {
        await api(`/tao/cases/${state.current.id}/approve`, {method: 'POST', body: {version: state.current.version,
          relationships: Boolean(values.relationships), rules: Boolean(values.rules), scope: Boolean(values.scope), partial: Boolean(values.partial), note: values.note}});
        await openCase(state.current.id);
        toast('Az állásfoglalás jóváhagyott, változatlan pillanatképe elkészült.');
      }
    } catch (error) {
      const node = form.querySelector('.error');
      if (node) {node.textContent = error.message; node.hidden = false;} else toast(error.message);
    } finally {submit.disabled = false;}
  });

  editor.addEventListener('click', async event => {
    const node = event.target.closest('[data-action]');
    if (!node) return;
    if (node.dataset.action === 'close') editor.close();
    if (node.dataset.action === 'remove' && showEditor.remove) {
      node.disabled = true;
      try {await showEditor.remove(); editor.close();} catch (error) {toast(error.message); node.disabled = false;}
    }
  });
  editor.addEventListener('change', toggleVotingFields);
  editor.addEventListener('submit', async event => {
    event.preventDefault();
    const submit = editor.querySelector('[type=submit]');
    submit.disabled = true;
    try {await showEditor.submit(formObject(event.target)); editor.close();}
    catch (error) {const node = editor.querySelector('#editor-error'); node.textContent = error.message; node.hidden = false; node.scrollIntoView({block: 'nearest'});}
    finally {submit.disabled = false;}
  });

  async function boot() {
    try {
      const session = await api('/auth/me');
      state.user = session.user; state.csrf = session.csrf;
      state.cases = await api('/tao/cases');
      const cid = new URLSearchParams(location.search).get('case');
      if (cid) await openCase(cid); else dashboard();
    } catch (error) {
      if (error.status === 401) {
        try {showLogin((await api('/auth/status')).setup_required);} catch (failure) {root.innerHTML = `<main id="main" class="loading error">${esc(failure.message)}</main>`;}
      } else root.innerHTML = `<main id="main" class="loading error">${esc(error.message)}<p><a href="/tao">Újrapróbálás</a></p></main>`;
    }
  }
  boot();
})();
