'use strict';
window.CaseAssistant=(()=>{
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={persons:'Személyek',ownerships:'Tulajdon és szavazat',families:'Rokonság',decisions:'Kapcsolati döntés tervezete',financials:'Éves beszámoló',rates:'Árfolyam',events:'Változási esemény',voting_facts:'Szavazati tény',family_facts:'Rokonsági tény',control_facts:'Irányítási jog',management_facts:'Ügyvezetés',establishment_facts:'Telephely',trust_facts:'Bizalmi vagyonkezelés',assumptions:'Feltételezések',market_analysis:'Piaci elemzés',conclusion_notes:'Következtetés',law_source:'Jogi forrás',law_applicability:'Történeti alkalmazhatóság'};
 const fieldNames={name:'Név',registration:'Cégazonosító',country:'Ország',kind:'Típus',owner:'Tulajdonos',company:'Vállalkozás',first:'Első szereplő',second:'Második szereplő',year:'Év',as_of:'Vizsgálati nap',capital:'Tulajdon (%)',votes:'Szavazat (%)',relationship:'Rokonság',relation:'Kapcsolat',result:'Minősítés',basis:'Jogalap',reason:'Indokolás',source:'Forrás',quote:'Forrásidézet',page:'Oldal',evidence:'Bizonyíték',confirmed:'Szakértőileg ellenőrzött',confirmed_years:'Ellenőrzött évek',percent:'Beszámítás (%)',start:'Kezdet',end:'Vége',valid_from:'Érvényesség kezdete',valid_to:'Érvényesség vége',employees:'Létszám',turnover:'Árbevétel (teljes pénzegység)',balance:'Mérleg (teljes pénzegység)',currency:'Deviza',accepted:'Elfogadás napja',date:'Dátum',quoted:'Jegyzés napja',value:'Árfolyam',market:'Piac',acting_together:'Közös fellépés',assumptions:'Feltételezések',missing:'Hiányok',vote_mode:'Szavazat kezelése',membership:'Tagi jogállás',condition:'Irányítási feltétel',reviewed_as_of:'Vizsgált időpont',relevant_grounds_reviewed:'Jogalapok ellenőrzése',attribution_reviewed:'Hozzárendelés ellenőrzése',control:'Irányítási jog',notes:'Megjegyzés',immediate:'Azonnali hatás',resolution:'Alátámasztás',description:'Leírás'};
 const valueNames={true:'Igen',false:'Nem',linked:'Kapcsolódó',partner:'Partner',independent:'Önálló',unresolved:'Tisztázandó',related:'Kapcsolt',not_related:'Nem kapcsolt',undetermined:'Nem eldönthető',sibling:'Testvér',spouse:'Házastárs',lineal:'Egyeneságbeli rokon',ownership_default:'Tulajdon = szavazat munkafeltételezés',explicit:'Dokumentált szavazat',expert:'Szakértői tervezet',unknown:'Tisztázandó'};
 function friendly(value,names){
  if(value==null)return 'Nincs megadva';
  if(Array.isArray(value))return value.length?value.map(v=>friendly(v,names)).join(', '):'Nincs';
  if(typeof value==='object')return Object.entries(value).filter(([k])=>k!=='id').map(([k,v])=>`${fieldNames[k]||k}: ${friendly(v,names)}`).join(' · ');
  return names[value]||valueNames[value]||String(value);
 }
 function compare(change,data){
  const names=Object.fromEntries([...(data?.companies||[]),...(data?.persons||[])].map(v=>[v.id,v.name]));
  if(typeof change.after!=='object'||change.after==null)return `<p><strong>Korábbi:</strong> ${esc(change.before||'Nincs megadva')}</p><p><strong>Javasolt:</strong> ${esc(change.after)}</p>`;
  return `<table><thead><tr><th>Adat</th><th>Korábbi</th><th>Javasolt</th></tr></thead><tbody>${Object.keys(change.after).filter(k=>k!=='id'&&JSON.stringify(change.before?.[k])!==JSON.stringify(change.after[k])).map(k=>`<tr><th>${esc(fieldNames[k]||k)}</th><td>${esc(friendly(change.before?.[k],names))}</td><td>${esc(friendly(change.after[k],names))}</td></tr>`).join('')}</tbody></table>`;
 }
 const sessions=new Map();let active;
 async function open(options){
  let settings={},settingsError;try{settings=await options.api('/assistant/settings');}catch(e){settingsError=e.message;}
  document.querySelector('#case-assistant')?.remove();
  const key=options.module+options.id;
  const session=sessions.get(key)||{messages:[],proposal:null};sessions.set(key,session);
  const dialog=document.createElement('dialog');dialog.id='case-assistant';dialog.className='assistant-dialog';document.body.append(dialog);
  active={...options,session,dialog,configured:false,busy:false,recognition:null,...settings};
  render();dialog.showModal();
  if(settingsError)showError(settingsError);
  dialog.addEventListener('close',()=>{active?.recognition?.stop();if(active?.dialog===dialog)active=null;dialog.remove();});
 }
 function showError(message){const e=active?.dialog.querySelector('.assistant-error');if(e){e.textContent=message;e.hidden=false;}}
 function render(){
  if(!active)return;const a=active,s=a.session,d=a.dialog;
  d.innerHTML=`<div class="assistant-heading"><h2>Beszélgetős segítség · ${a.module==='kkv'?'KKV':'Tao'}</h2><button type="button" class="assistant-close" aria-label="Beszélgetés bezárása">✕</button></div><p class="assistant-note">${a.configured?'AI-kapcsolat beállítva. A kérdéseddel az ügy mentett adatait és ezt a beszélgetést a(z) '+(a.provider==='gemini'?'Google Gemini':'OpenAI')+' szolgáltatónak küldöd.':'Helyi hiánymagyarázat érhető el. Szabad szöveges adatkitöltéshez állíts be AI-kapcsolatot.'} A kitöltési javaslatot külön jóváhagyod; a szakértői ellenőrzés külön lépés.</p>${a.user.role==='admin'?`<details class="assistant-settings"><summary>AI-kapcsolat beállítása</summary><form id="ai-settings"><p>A kulcs a géped data/ai-settings.json fájljába kerül, és nem jelenik meg a válaszokban. Az API használata a szolgáltatónál díjköteles lehet; a ChatGPT-előfizetés külön szolgáltatás.</p><label>AI-szolgáltató<select name="provider"><option value="gemini" ${a.provider==='gemini'?'selected':''}>Google Gemini</option><option value="openai" ${a.provider==='openai'?'selected':''}>OpenAI</option></select></label><label id="ai-key-label">${a.provider==='gemini'?'Gemini':'OpenAI'} API-kulcs<input name="api_key" type="password" autocomplete="new-password" placeholder="${a.configured?'Beállítva; üresen hagyva megmarad':'API-kulcs'}"></label><label>Modell<input name="model" value="${esc(a.model||(a.provider==='gemini'?'gemini-2.5-flash':'gpt-4.1-mini'))}" required></label><label><input type="checkbox" name="clear">A gépen mentett kulcs törlése</label><button type="submit">AI-beállítás mentése</button>${a.environment_key?'<p>A környezeti változóban beállított kulcs elsőbbséget élvez.</p>':''}</form></details>`:''}<div class="assistant-messages" aria-live="polite">${s.messages.length?s.messages.map(m=>`<article class="assistant-message ${m.role}"><strong>${m.role==='user'?'Te':'Segítség'}</strong><p>${esc(m.content)}</p></article>`).join(''):'<p>Kérdezheted például: „Miért nem dönthető el még az Alfa és a Beta kapcsolata?”, majd válaszolhatsz a tisztázó kérdésre a saját szavaiddal.</p>'}</div><div class="assistant-error" role="alert" hidden></div>${s.proposal?.changes.length?`<section class="assistant-proposal"><h3>Javasolt kitöltés · még nincs mentve</h3>${s.proposal.impact?`<p><strong>Várható számítási hatás:</strong> ${esc(s.proposal.impact)}</p>`:''}${s.proposal.changes.map(c=>`<article><h4>${esc(labels[c.field]||c.field)}</h4><p>${esc(c.explanation)}</p><details><summary>Korábbi és javasolt érték összehasonlítása</summary>${compare(c,s.proposal.proposed_data)}</details></article>`).join('')}<p>A tényadatok változása korábbi kapcsolati ellenőrzéseket nyithat újra. Az AI nem jelöl döntést szakértőileg ellenőrzöttnek.</p><button type="button" class="assistant-apply">Jóváhagyom a kitöltést · mentés és újraszámítás</button><button type="button" class="assistant-discard">Javaslat elvetése</button></section>`:''}<form id="assistant-message-form"><label for="assistant-question">Kérdésed vagy válaszod</label><textarea id="assistant-question" name="question" rows="3" maxlength="12000" required placeholder="Írd le a saját szavaiddal…"></textarea><div class="assistant-actions"><button type="submit">${a.configured?'Küldés az AI-nak':'Hiányok megmutatása'}</button>${(window.SpeechRecognition||window.webkitSpeechRecognition)?'<button type="button" class="assistant-dictate">Diktálás</button>':'<small>Diktáláshoz használhatod a Windows Win+H billentyűit.</small>'}</div><small>A beszélgetés ebben a böngészőlapban marad meg. A jóváhagyott adatok az ügy mentett verziójába kerülnek.</small></form>`;
  d.querySelector('.assistant-close').onclick=()=>d.close();
  d.querySelector('#ai-settings [name=provider]')?.addEventListener('change',e=>{
   const form=e.target.form,provider=e.target.value;
   form.elements.model.value=provider===a.provider?a.model:(provider==='gemini'?'gemini-2.5-flash':'gpt-4.1-mini');
   form.elements.api_key.value='';form.elements.api_key.placeholder=provider===a.provider&&a.configured?'Beállítva; üresen hagyva megmarad':'Az új szolgáltató API-kulcsa';
   d.querySelector('#ai-key-label').firstChild.textContent=(provider==='gemini'?'Gemini':'OpenAI')+' API-kulcs';
  });
  d.querySelector('#ai-settings')?.addEventListener('submit',async e=>{
   e.preventDefault();const form=e.target,fields=Object.fromEntries(new FormData(form));
   await run(async()=>{await a.api('/assistant/settings',{method:'POST',body:{provider:fields.provider,api_key:fields.api_key,model:fields.model,clear:!!fields.clear}});Object.assign(a,await a.api('/assistant/settings'));render();});
  });
  d.querySelector('#assistant-message-form').onsubmit=async e=>{
   e.preventDefault();const question=e.target.elements.question.value.trim();if(!question)return;
   if(s.messages.length>=28){showError('Ez a beszélgetés elérte a kérési méretkorlátot. Nyiss új beszélgetést az oldal újratöltésével; a mentett adatok megmaradnak.');return;}
   await run(async()=>{
    const messages=[...s.messages,{role:'user',content:question}];
    const response=await a.api(`/assistant/${a.module}/${a.id}`,{method:'POST',body:{messages,use_ai:a.configured}});
    s.messages=[...messages,{role:'assistant',content:response.answer}];s.proposal=response.changes.length?response:null;render();
   });
  };
  d.querySelector('.assistant-apply')?.addEventListener('click',()=>run(async()=>{
   const proposal=s.proposal;
   const current=await a.api(`${a.module==='tao'?'/tao':''}/cases/${a.id}`);
   if(current.version!==proposal.base_version)throw Error('Az ügy a javaslat óta módosult. A kitöltés nem menthető; kérj friss javaslatot a legújabb adatokból.');
   await a.apply(proposal.proposed_data);
   s.messages.push({role:'assistant',content:'A jóváhagyott kitöltést mentettem, és a vizsgálat újraszámolt. A fennmaradó kérdéseket az új adatok alapján tisztázhatjuk.'});s.proposal=null;render();
  }));
  d.querySelector('.assistant-discard')?.addEventListener('click',()=>{s.proposal=null;render();});
  d.querySelector('.assistant-dictate')?.addEventListener('click',()=>{
   const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;const recognition=new Recognition();a.recognition=recognition;recognition.lang='hu-HU';recognition.interimResults=false;
   showError('Diktálás: a böngésző beszédfelismerő szolgáltatása dolgozza fel a hangot. A szöveg szerkeszthető; a küldés külön gomb.');
   recognition.onresult=e=>{const input=d.querySelector('#assistant-question');input.value+=(input.value?' ':'')+e.results[0][0].transcript;};
   recognition.onerror=()=>showError('A diktálás nem indult el. Ellenőrizd a mikrofon engedélyét, vagy használd a Win+H billentyűket.');recognition.start();
  });
  d.querySelector('.assistant-messages').scrollTop=d.querySelector('.assistant-messages').scrollHeight;
 }
 async function run(action){
  const a=active;if(!a||a.busy)return;a.busy=true;
  a.dialog.querySelectorAll('button').forEach(b=>b.disabled=true);
  const error=a.dialog.querySelector('.assistant-error');error.hidden=false;error.textContent='Feldolgozás…';
  try{await action();}catch(e){showError(e.message);}finally{a.busy=false;a.dialog.querySelectorAll('button').forEach(b=>b.disabled=false);}
 }
 return {open};
})();
