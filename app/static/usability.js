'use strict';
function fieldValidity(el,message=''){
  el.setAttribute('aria-invalid',message?'true':'false');el.setCustomValidity(message);
  el.style.borderColor=message?'#b66c61':'';
  let hint=el.parentElement.querySelector('.field-error');
  if(message&&!hint){hint=document.createElement('small');hint.className='field-error';hint.id='field-error-'+id();hint.setAttribute('role','alert');el.parentElement.append(hint);el.setAttribute('aria-describedby',hint.id);}
  if(hint){hint.textContent=message;hint.hidden=!message;}
}
document.addEventListener('keydown',e=>{
  if(e.key!=='Tab'||!S.modal)return;
  const items=[...document.querySelectorAll('.modal button:not(:disabled),.modal input:not(:disabled),.modal select:not(:disabled),.modal textarea:not(:disabled)')].filter(el=>el.getClientRects().length);
  const first=items[0],last=items.at(-1);
  if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
  else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
});
function refreshApprovalAvailability(){
  const form=document.querySelector('#approval-form');if(!form)return;
  const checked=['financials','relationships','rules'].filter(n=>form.elements[n].checked).length;
  const reasons=[];
  if(!canApprove())reasons.push('Jóváhagyó szakértői jogosultság szükséges.');
  if(S.dirty)reasons.push('Mentsd a módosításokat az újraszámításhoz.');
  if(!S.calc.ready)reasons.push(`Rendezd a ${groupedChecks().length} nyitott ellenőrzési kérdést.`);
  if(S.pendingIntake===null)reasons.push('Az ügyfélválaszok ellenőrzése folyamatban.');
  else if(S.pendingIntake>0)reasons.push(`Dolgozd fel a ${S.pendingIntake} új ügyfélválaszt.`);
  if(checked<3)reasons.push(`Szakértői ellenőrzések: ${checked}/3 visszaigazolva.`);
  form.querySelector('[type=submit]').disabled=reasons.length>0;
  document.querySelector('#approval-progress').textContent=reasons.join(' ')||'Minden feltétel teljesült; a mentett verzió jóváhagyható.';
}
async function loadReviewIntake(){
  const cid=S.cid,panel=document.querySelector('#review-intake-panel');
  try{
    const replies=await api(`/cases/${cid}/intake`);if(cid!==S.cid||!panel?.isConnected)return;
    const pending=replies.filter(i=>!i.reviewed);S.pendingIntake=pending.length;
    panel.innerHTML=pending.map(i=>`<div class="list-row" style="display:block"><small>${esc(i.author)} · ${shortDate(i.created)}</small><div class="intake-message">${esc(i.message)}</div>${button('Feldolgozottként jelölés','review-intake','small',`data-id="${esc(i.id)}"`)}</div>`).join('')||'<p class="section-note">Nincs feldolgozatlan ügyfélválasz.</p>';
    refreshApprovalAvailability();
  }catch(error){if(panel?.isConnected)panel.innerHTML=`<p role="alert">${esc(error.message)}</p>${button('Újrapróbálás','reload-intake','small')}`;}
}
async function loadReportPreview(){
  const cid=S.cid,version=S.version,panel=document.querySelector('#report-preview-content');
  try{
    const r=await api(`/cases/${cid}/report-summary`);if(cid!==S.cid||version!==S.version||!panel?.isConnected)return;
    panel.innerHTML=`${S.dirty?'<p class="banner amber">Az előnézet a legutóbbi mentésből készül. Mentsd a módosításokat a frissítéshez.</p>':''}<h3>A vizsgálat tárgya</h3><p>${esc(r.opening)}</p><h3>Kapcsolatok és beszámítás</h3>${r.relationships.map(t=>`<p>${esc(t)}</p>`).join('')||'<p>Csak a vizsgált vállalkozás saját adatai szerepelnek.</p>'}<h3>Éves számítás és indokolás</h3>${r.annuals.map(y=>`<h4>${y.year} · ${esc(y.label)}</h4><p>${esc(y.reason)}</p>`).join('')}<h3>Kétéves szabály</h3>${r.history.map(t=>`<p>${esc(t)}</p>`).join('')}<h3>Összefoglaló megállapítás</h3><p><strong>${esc(r.conclusion)}</strong></p><p>${esc(r.transfer_pricing)}</p>${r.notes?`<h3>Szakértői kiegészítés</h3><p>${esc(r.notes)}</p>`:''}<p class="section-note">A teljes Word/PDF a forrásokat, árfolyamokat, részletes táblázatokat és az évenkénti céghálót is tartalmazza.</p>`;
  }catch(error){if(panel?.isConnected)panel.innerHTML=`<p role="alert">${esc(error.message)}</p>${button('Előnézet újratöltése','reload-preview','small')}`;}
}
document.addEventListener('click',e=>{
  const action=e.target.closest('[data-action]')?.dataset.action;
  if(action==='reload-intake')loadReviewIntake();
  if(action==='reload-preview')loadReportPreview();
});
