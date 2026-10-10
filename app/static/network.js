'use strict';

let graphDrag=null,graphClickSuppressedUntil=0;

function networkPositions(){
  const positions={};
  S.data.persons.forEach((p,i)=>{positions[p.id]={x:150,y:140+i*110};});
  S.data.companies.forEach((c,i)=>{positions[c.id]={x:490+(i%2)*340,y:140+Math.floor(i/2)*125};});
  for(const [key,value] of Object.entries(S.data.graph_positions||{}))if(positions[key])positions[key]={...value};
  return positions;
}
function networkBoundary(a,b){
  const dx=b.x-a.x,dy=b.y-a.y;
  const ratio=1/Math.max(Math.abs(dx)/105,Math.abs(dy)/36,1);
  return {x:a.x+dx*ratio,y:a.y+dy*ratio};
}
function networkSvg(){
  const positions=networkPositions(),values=Object.values(positions);
  const width=Math.max(1030,...values.map(p=>p.x+140)),height=Math.max(470,...values.map(p=>p.y+115));
  const year=S.calc.years.find(y=>y.year===S.year),rows=new Map((year?.rows||[]).map(r=>[r.company,r]));
  const colors={own:'#234b3f',linked:'#477a52',partner:'#a47a26',independent:'#859080',unresolved:'#ad6246',consolidated:'#477a52'};
  const nodes=[...S.data.persons.map(p=>({...p,person:true})),...S.data.companies];
  const edges=[];
  function edge(first,second,label,color,dashed=false,arrow=false){
    const a=positions[first],b=positions[second];if(!a||!b)return;
    const from=networkBoundary(a,b),to=networkBoundary(b,a);
    const mx=(from.x+to.x)/2,my=(from.y+to.y)/2;
    edges.push(`<g><path d="M${from.x} ${from.y} L${to.x} ${to.y}" fill="none" stroke="${color}" stroke-width="2" ${dashed?'stroke-dasharray="7 5"':''} ${arrow?'marker-end="url(#network-arrow)"':''}/><rect x="${mx-75}" y="${my-21}" width="150" height="22" rx="6" fill="#ffffff" opacity=".95"/><text x="${mx}" y="${my-6}" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="${color}">${esc(label)}</text></g>`);
  }
  S.data.ownerships.filter(o=>inPeriod(o,structureDay())).forEach(o=>edge(o.owner,o.company,`${fmt(o.capital)}% tőke · ${fmt(o.votes)}% szav.${o.control?' · irányítás':''}`,'#698477',false,true));
  S.data.decisions.filter(d=>inPeriod(d,structureDay())).forEach(d=>edge(d.first,d.second,`${relationLabels[d.relation]}${d.relation==='partner'?' '+fmt(d.percent)+'%':''}${decisionNeeds(d).length?' · ?':''}`,colors[d.relation]||'#ad6246',true));
  S.data.families.forEach(f=>edge(f.first,f.second,f.relationship,'#8d779d',true));
  function nameLines(name){
    if(name.length<=26)return [name];
    let at=name.lastIndexOf(' ',26);if(at<10)at=26;
    return [name.slice(0,at),name.slice(at).trim()];
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="A vállalkozások és személyek kapcsolati hálója"><title>${esc(company(S.data.root)?.name)} · Cégháló · ${S.year}</title><rect width="100%" height="100%" fill="#f8faf5"/><defs><marker id="network-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L8 4L0 8Z" fill="#698477"/></marker></defs><text x="24" y="32" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="#234b3f">${esc(company(S.data.root)?.name)} · Cégháló</text><text x="24" y="54" font-family="Arial, sans-serif" font-size="11" fill="#65765e">${S.year} · Hálóidőpont: ${esc(structureDay())} · ${S.dirty?'Nem mentett elrendezés / adatok':S.version+'. mentett verzió'}${S.calc.blockers.length?' · Előzetes minősítés':''}</text>${edges.join('')}${nodes.map(n=>{
    const p=positions[n.id],row=rows.get(n.id),root=n.id===S.data.root,color=colors[row?.relation]||'#859080';
    const lines=nameLines(n.name),state=n.person?'Természetes személy':n.kind==='public'?'Közjogi szereplő':row?`${relationLabels[row.relation]} · ${fmt(row.percent)}%`:'Az adott időpontban nem aktív';
    return `<g class="graph-node" data-graph-node="${esc(n.id)}" tabindex="0" role="button" data-action="${n.person?'edit-person':'edit-company'}" data-id="${esc(n.id)}" aria-label="${esc(n.name)}: ${esc(state)}. Kattintás: szerkesztés. Húzás vagy nyílbillentyűk: mozgatás."><title>${esc(n.name)}\n${esc(state)}${row?'\n'+esc(row.reason):''}</title><rect x="${p.x-105}" y="${p.y-36}" width="210" height="72" rx="12" fill="${root?'#234b3f':n.person?'#edf2e6':'#ffffff'}" stroke="${root?'#234b3f':color}" stroke-width="${root?2:1.5}"/><text x="${p.x}" y="${p.y-(lines.length>1?14:6)}" text-anchor="middle" fill="${root?'#ffffff':'#294e40'}" font-family="Arial, sans-serif" font-size="12" font-weight="bold">${lines.map((line,i)=>`<tspan x="${p.x}" dy="${i?15:0}" ${line.length>29?'textLength="184" lengthAdjust="spacingAndGlyphs"':''}>${esc(line)}</tspan>`).join('')}</text><text x="${p.x}" y="${p.y+23}" text-anchor="middle" fill="${root?'#deebbf':color}" font-family="Arial, sans-serif" font-size="10">${esc(state)}</text></g>`;
  }).join('')}<text x="24" y="${height-26}" font-family="Arial, sans-serif" font-size="10" fill="#65765e">Folytonos nyíl: tulajdon / szavazat · Szaggatott: szakértői döntés vagy rokonság · A rokonság önmagában nem összeszámítási döntés.</text></svg>`;
}
function networkPoint(event,svg){
  const point=new DOMPoint(event.clientX,event.clientY);
  return point.matrixTransform(svg.getScreenCTM().inverse());
}
function redrawNetwork(){const wrap=document.querySelector('.graph-wrap');if(wrap)wrap.innerHTML=networkSvg();}
function setNetworkPosition(key,x,y){
  S.data.graph_positions??={};
  S.data.graph_positions[key]={x:Math.round(Math.max(110,Math.min(5000,x))),y:Math.round(Math.max(100,Math.min(5000,y)))};
}
document.addEventListener('pointerdown',event=>{
  const node=event.target.closest('[data-graph-node]');if(!node||event.button!==0||graphDrag)return;
  const svg=node.closest('svg'),wrap=svg.parentElement,point=networkPoint(event,svg),key=node.dataset.graphNode;
  const start=networkPositions()[key];
  graphDrag={key,wrap,start,point,inverse:svg.getScreenCTM().inverse(),viewBox:svg.getAttribute('viewBox'),width:svg.getAttribute('width'),height:svg.getAttribute('height'),pointer:event.pointerId,moved:false,original:S.data.graph_positions?.[key]?{...S.data.graph_positions[key]}:null};
});
document.addEventListener('pointermove',event=>{
  const d=graphDrag;if(!d||event.pointerId!==d.pointer)return;
  // Freeze the initial transform: growing the canvas during a drag must not rescale motion.
  const point=new DOMPoint(event.clientX,event.clientY).matrixTransform(d.inverse),dx=point.x-d.point.x,dy=point.y-d.point.y;
  if(!d.moved&&Math.hypot(dx,dy)<5)return;
  if(!d.moved)d.wrap.setPointerCapture(event.pointerId);
  d.moved=true;event.preventDefault();
  setNetworkPosition(d.key,d.start.x+dx,d.start.y+dy);
  // Keep the drag coordinate system stable until pointerup.
  const next=networkSvg();d.wrap.innerHTML=next;
  const svg=d.wrap.querySelector('svg');svg.setAttribute('viewBox',d.viewBox);svg.setAttribute('width',d.width);svg.setAttribute('height',d.height);
});
function finishNetworkDrag(event,cancel=false){
  const d=graphDrag;if(!d||event.pointerId!==d.pointer)return;
  graphDrag=null;
  if(d.wrap.hasPointerCapture(d.pointer))d.wrap.releasePointerCapture(d.pointer);
  if(d.moved){
    graphClickSuppressedUntil=performance.now()+350;
    if(cancel){if(d.original)S.data.graph_positions[d.key]=d.original;else delete S.data.graph_positions[d.key];}
    else markDirty();
    redrawNetwork();
  }
}
document.addEventListener('pointerup',event=>finishNetworkDrag(event));
document.addEventListener('pointercancel',event=>finishNetworkDrag(event,true));
document.addEventListener('keydown',event=>{
  const node=event.target.closest('[data-graph-node]');if(!node)return;
  if(event.key==='Enter'||event.key===' '){event.preventDefault();node.click();return;}
  const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];if(!delta)return;
  event.preventDefault();const key=node.dataset.graphNode,p=networkPositions()[key],step=event.shiftKey?30:10;
  setNetworkPosition(key,p.x+delta[0]*step,p.y+delta[1]*step);markDirty();redrawNetwork();
  [...document.querySelectorAll('[data-graph-node]')].find(n=>n.dataset.graphNode===key)?.focus();
});
async function downloadNetwork(kind){
  const svg=networkSvg(),blob=new Blob([svg],{type:'image/svg+xml;charset=utf-8'});
  let output=blob;
  if(kind==='png'){
    const image=new Image(),url=URL.createObjectURL(blob);
    try{
      await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('A cégháló képpé alakítása nem sikerült.'));image.src=url;});
      const canvas=document.createElement('canvas'),scale=Math.min(2,8192/Math.max(image.naturalWidth,image.naturalHeight),Math.sqrt(16000000/(image.naturalWidth*image.naturalHeight)));
      canvas.width=Math.round(image.naturalWidth*scale);canvas.height=Math.round(image.naturalHeight*scale);
      canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
      output=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!output)throw Error('A PNG-export nem sikerült.');
    }finally{URL.revokeObjectURL(url);}
  }
  const url=URL.createObjectURL(output),a=document.createElement('a');a.href=url;a.download=`KKV_ceghalo_${S.year}.${kind==='png'?'png':'svg'}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast('A cégháló letöltése elkészült.');
}
