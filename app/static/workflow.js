'use strict';

function recalculationNotice(){
  return S.dirty?`<div class="banner amber">${icon('alert')}<div><strong>Újraszámítás szükséges.</strong><p>Módosítottad az adatokat. A látható számítás és az ellenőrzések még a legutóbbi mentésből származnak.</p><p>A friss eredményhez kattints a <strong>Mentés</strong> gombra.</p></div></div>`:'';
}
function calculationCompleteness(calc,year){
  const checks=groupedChecks(calc.blockers.filter(b=>!b.year||b.year===year?.year));
  if(!checks.length&&year?.complete)return '';
  return `<div class="banner amber" id="preliminary-calculation">${icon('alert')}<div><strong>Előzetes számítás · ${checks.length} rendezendő kérdés</strong><p>${year?.complete?'A számszerű adatok rendelkezésre állnak, de a jelzett forrásokat és kapcsolati döntéseket még ellenőrizni kell.':'Az ismert és beszámítható adatok részösszege látható. A hiányzó adatokat nem tekintjük nullának; végleges méretkategória még nem állapítható meg.'}</p><ul>${checks.slice(0,3).map(b=>`<li>${esc(b.title||b.message)}</li>`).join('')}</ul>${button('Hiányok és teendők megnyitása','tab','small','data-tab="review"','arrow')}</div></div>`;
}

function reviewChecks(blockers=S.calc.blockers){return S.reviewScope==='all'?blockers:blockers.filter(b=>!b.year||b.year===S.year);}
function groupedChecks(blockers=S.calc.blockers){
  const groups=new Map();
  blockers.forEach((b,index)=>{
    const key=[b.code,b.target||'',b.message.replace(/^\d{4}:\s*/, '')].join('|');
    if(!groups.has(key))groups.set(key,{...b,index:S.calc.blockers.indexOf(b),years:[]});
    if(b.year&&!groups.get(key).years.includes(b.year))groups.get(key).years.push(b.year);
  });
  return [...groups.values()];
}
function checkCards(blockers=S.calc.blockers){
  return groupedChecks(blockers).map(b=>`<article class="check-card" data-check-code="${esc(b.code)}" data-check-target="${esc(b.target||'')}">
    <div class="check-card-heading">${icon('alert')}<div><h3>${esc(b.title||b.message)}</h3><small>${b.years.join(' · ')||'Teljes vizsgálat'}${b.target&&actorName(b.target)!==b.target?' · '+esc(actorName(b.target)):''}</small></div>${pill('Teendő','amber')}</div>
    <p class="check-fact">${esc(b.message.replace(/^\d{4}:\s*/,''))}</p>
    <p><strong>Miért szükséges?</strong> ${esc(b.why||'A véglegesítéshez rendezett forrásadat szükséges.')}</p>
    <div class="check-next"><strong>Mit kell megadnod?</strong><p>${esc(b.action||'Ellenőrizd az érintett adatot és a forrását.')}</p></div>
    <div class="button-row">${(b.years.length?b.years:[null]).map(y=>button((y?y+' · ':'')+'Rendezés','resolve-check','small',`data-index="${b.index}" ${y?`data-year="${y}"`:''}`,'edit')).join('')}</div>
  </article>`).join('');
}
function checkSummary(){
  const open=groupedChecks(reviewChecks()).length;
  return `<div class="review-summary"><strong>${open?open+' rendezendő kérdés':'Minden adatellenőrzés rendezett'}</strong><p>A számláló az itt megjelenített teendőket számolja. Az adott évre ellenőrzött döntés ebből az évből eltűnik; másik évben külön igazolás szükséges. A Rendezés gomb közvetlenül a szükséges adathoz visz. Mentéskor újraellenőrizzük a tényeket; a mentés nem jelent automatikus szakértői megerősítést.</p></div>`;
}
function caseFeedback(){
  const last=S.lastSave;
  if(!last)return '';
  return `<section class="save-feedback" role="status"><div>${icon('check')}<strong>${esc(last.text)}</strong></div>${last.changes.length?`<details><summary>Mi változott a számításban? (${last.changes.length})</summary><ul>${last.changes.map(t=>`<li>${esc(t)}</li>`).join('')}</ul></details>`:''}${S.calc.blockers.length?button('Fennmaradó teendők','tab','small','data-tab="review"'):''}</section>`;
}
function saveFeedback(before,after){
  const old=groupedChecks(reviewChecks(before.blockers)),now=groupedChecks(reviewChecks(after.blockers));
  const keys=now.map(b=>[b.code,b.target].join('|'));
  const resolved=old.filter(b=>!keys.includes([b.code,b.target].join('|'))).length;
  const changes=[];
  after.years.forEach(y=>{
    const prev=before.years.find(a=>a.year===y.year);
    y.rows.forEach(row=>{
      const previous=prev?.rows.find(r=>r.company===row.company);
      if(previous&&(previous.percent!==row.percent||previous.relation!==row.relation))changes.push(`${y.year} · ${row.name}: ${relationLabels[previous.relation]} (${fmt(previous.percent)}%) → ${relationLabels[row.relation]} (${fmt(row.percent)}%).`);
    });
    if(prev&&Object.keys(y.totals).some(k=>y.totals[k]!==prev.totals[k]))changes.push(`${y.year} · Összesen: ${fmt(y.totals.employees)} fő, ${fmt(scale(y.totals.turnover,-3))} ezer Ft árbevétel, ${fmt(scale(y.totals.balance,-3))} ezer Ft mérlegfőösszeg.`);
  });
  return {text:`Mentve és újraszámítva. ${S.reviewScope==='all'?'Minden vizsgált év:':S.year+'. év:'} ${resolved?resolved+' kérdés rendeződött. ':''}${now.length?now.length+' kérdéshez még adat vagy döntés szükséges.':'Minden adatellenőrzés rendezett.'}`,changes};
}
function openCheck(index,year){
  const b=S.calc.blockers[index];if(!b)return;
  if(year||b.year)S.year=Number(year||b.year);
  const dest=b.destination;
  if(dest==='settings'){openSettings();return;}
  if(dest==='company'){entityModal('company',b.target);return;}
  if(dest==='ownership'){ownershipModal(b.target);return;}
  if(dest==='decision'){decisionModal(b.target);return;}
  if(dest==='new_decision'){decisionModal(null,{second:b.target});return;}
  if(dest==='override'){overrideModal(b.target,S.year);return;}
  if(dest==='event'){eventModal(b.target);return;}
  if(dest==='public'){publicModal();return;}
  if(dest==='financial'){financialModal(b.target);return;}
  S.tab=['rate','financials'].includes(dest)?'financials':dest==='graph'?'graph':'decisions';
  history.replaceState(null,'',`#case/${S.cid}/${S.tab}`);renderCase();
  const focus=dest==='rate'?document.querySelector('[data-rate="value"]'):[...document.querySelectorAll('[data-fin="employees"]')].find(el=>el.dataset.id===b.target);
  if(focus){focus.scrollIntoView({block:'center',behavior:'smooth'});focus.focus();}
}
function companyState(cid){
  const row=S.calc.years.find(y=>y.year===S.year)?.rows.find(r=>r.company===cid);
  if(!row)return 'Nem szerepel az adott hálóidőpontban';
  return `${S.year} · ${relationLabels[row.relation]} · ${fmt(row.percent)}% beszámítás${S.calc.blockers.some(b=>b.year===S.year&&(b.target===cid||S.data.decisions.some(d=>d.id===b.target&&(d.first===cid||d.second===cid))))?' · előzetes':''}`;
}
function decisionConfirmed(d,year){return !!d.confirmed&&(d.confirmed_years==null||d.confirmed_years.includes(Number(year)));}
function decisionNeeds(d){
  return [d.relation==='unresolved'?'kapcsolati minősítés':null,!d.reason?'indoklás':null,!d.source?'igazoló forrás':null,!decisionConfirmed(d,S.year)?S.year+'. évi ellenőrzés megerősítése':null,d.basis==='persons'&&!d.acting_together?'közös fellépés ténye':null,d.basis==='persons'&&!d.market?'piaci kapcsolat indoka':null].filter(Boolean);
}
function relationshipEvidence(first,second){
  const day=structureDay();
  const direct=S.data.ownerships.filter(o=>inPeriod(o,day)&&((o.owner===first&&o.company===second)||(o.owner===second&&o.company===first)));
  const evidence=direct.map(o=>`${actorName(o.owner)} → ${actorName(o.company)}: ${fmt(o.capital)}% tőke, ${fmt(o.votes)}% szavazat${o.control?', meghatározó irányítási jog':''}. ${o.votes>50||o.control?'Ez kapcsolódást (100%) alapoz meg.':Math.max(Number(o.capital),Number(o.votes))>=25?'Ez partnerkapcsolatot alapozhat meg, ha nincs kapcsolódás vagy igazolt kivétel.':'A közvetlen arány önmagában nem éri el a 25%-os partnerküszöböt.'}`);
  const pids=new Set(S.data.ownerships.filter(o=>inPeriod(o,day)&&[first,second].includes(o.company)&&person(o.owner)).map(o=>o.owner));
  const families=S.data.families.filter(f=>pids.has(f.first)&&pids.has(f.second));
  families.forEach(f=>evidence.push(`${actorName(f.first)} és ${actorName(f.second)}: ${f.relationship}. A rokonság mellett a közös fellépést és a piaci kapcsolatot külön igazolni kell.`));
  if(!direct.length)evidence.unshift('Nincs közvetlen vállalkozási tulajdoni/szavazati kapcsolat rögzítve e két cég között. A teljes kapcsolódási láncot és a személyi kapcsolatokat is ellenőrizd.');
  return `<ul>${evidence.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`;
}
function familyImpact(f,allowActions=true){
  const day=structureDay();
  const owned=pid=>[...new Set(S.data.ownerships.filter(o=>o.owner===pid&&inPeriod(o,day)).map(o=>o.company))];
  const first=owned(f.first),second=owned(f.second),pairs=[];
  for(const a of first)for(const b of second)if(a!==b&&!pairs.some(p=>p.includes(a)&&p.includes(b)))pairs.push([a,b]);
  return `<div class="family-impact"><strong>Mit jelent ez a számításban?</strong><p>Kapcsolat: ${esc(f.relationship||'még nincs megadva')}. Ettől az összeszámítási arány még nem változik: a rokonság mellett a közös fellépést és a piaci kapcsolatot is értékelni kell. A rögzített döntés és a teljes háló határozza meg a beszámítást.</p>${pairs.map(([a,b])=>{
    const ds=S.data.decisions.filter(d=>inPeriod(d,day)&&((d.first===a&&d.second===b)||(d.first===b&&d.second===a)));
    return `<div class="family-pair"><strong>${esc(actorName(a))} ↔ ${esc(actorName(b))}</strong><small>${ds.length?ds.map(d=>`${relationLabels[d.relation]}${d.relation==='partner'?' · '+fmt(d.percent)+'%':''}${decisionNeeds(d).length?' · hiányzik: '+decisionNeeds(d).join(', '):' · ellenőrzött döntés'}`).map(esc).join('; '):'Nincs kapcsolati döntés. Indokold, hogy a két személy közösen irányítja-e a cégeket, és azonos vagy szomszédos piacon működnek-e.'}</small>${allowActions?button(ds.length?'Döntés megnyitása':'Kapcsolat értékelése','family-decision','small',`data-first="${esc(a)}" data-second="${esc(b)}" ${ds[0]?`data-id="${esc(ds[0].id)}"`:''}`,'edit'):'<small>Mentés után itt megnyithatod a kapcsolati döntést.</small>'}</div>`;
  }).join('')||'<p>Előbb rendeld a személyeket a cégeikhez tulajdoni/szavazati kapcsolattal, hogy az érintett cégpárok megjelenjenek.</p>'}</div>`;
}
function updateModalGuidance(){
  const form=document.querySelector('#modal-form'),panel=document.querySelector('#relationship-guidance');
  if(!form||!panel||!S.modal)return;
  const p=Object.fromEntries(new FormData(form));
  if(S.modal.kind==='family'){panel.innerHTML=familyImpact(p,false);return;}
  const isDecision=S.modal.kind==='decision';
  if(!isDecision){
    const owner=company(p.owner),votes=Number(decimal(p.votes)||0),capital=Number(decimal(p.capital)||0),control=form.elements.control.checked;
    panel.innerHTML=`<strong>Várható kapcsolati hatás</strong><p>${!owner?'Természetes személy tulajdona önmagában nem hoz létre két cég közötti partnerkapcsolatot. Az érintett cégek közös fellépését külön döntésben kell értékelni.':owner.kind==='public'?'A közjogi részesedést a külön közjogi összesítésben is értékelni kell.':votes>50||control?'A megadott vállalkozási irányítás kapcsolódást alapoz meg: az érintett kapcsolódó blokk 100%-kal számítható be, ha a vizsgált céghez kapcsolódik.':Math.max(capital,votes)>=25?'A magasabb tőke/szavazati arány '+fmt(Math.max(capital,votes))+'%. Partnerkapcsolat lehet, ha nincs kapcsolódás vagy igazolt befektetői kivétel. A teljes háló dönti el a végső beszámítást.':'A közvetlen arány nem éri el a 25%-os partnerküszöböt. Más irányítási jog vagy kapcsolódási lánc még változtathat a minősítésen.'}</p><small>A mentés újraszámítja a teljes céghálót és megmutatja a tényleges változásokat. Igazoló forrást is adj meg.</small>`;
    return;
  }
  const effect={linked:'Kapcsolódó: a kapcsolódó blokk teljes adata 100%-kal szerepel, ha a vizsgált céghez kapcsolódik.',partner:'Partner: a megadott százalék súlyozza a partner és kapcsolódó blokkja adatait. Más útvonalak külön összeszámítási döntést igényelhetnek.',independent:'Önálló: ez a döntés nem alapoz meg beszámítást. A már igazolt kapcsolódási láncot vagy partnerarányt nem írja felül.',unresolved:'Még nincs minősítés: ez a döntés nyitva hagyja az ellenőrzési pontot. A mentéstől nem válik ellenőrzötté.'};
  panel.innerHTML=`<strong>Rögzített tények · ${esc(structureDay())}</strong>${relationshipEvidence(p.first,p.second)}<p><strong>Választásod hatása:</strong> ${effect[p.relation]}</p><small>A forrást, az indoklást és az ellenőrzést is meg kell adnod.${p.basis==='persons'?' Közös fellépés és azonos/szomszédos piac indoka is kötelező.':''}</small>`;
  const percent=form.elements.percent;percent.disabled=p.relation!=='partner';percent.required=p.relation==='partner';
  for(const name of ['acting_together','market']){
    const el=form.elements[name];el.required=p.basis==='persons';el.closest('.field').hidden=p.basis!=='persons';
  }
}
document.addEventListener('input',e=>{if(e.target.closest('#modal-form')){try{updateModalGuidance();}catch{/* Numeric validation is displayed by the form on submit. */}}});
document.addEventListener('change',e=>{if(e.target.closest('#modal-form')){try{updateModalGuidance();}catch{}}});
