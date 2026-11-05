/* Synchronized playback of three recorded MuJoCo/QPSK experiments.
   No new communication or robot physics is calculated in the browser. */
(() => {
'use strict';
const el=id=>document.getElementById(id);
const video=el('replayVideo');
const sources={
  ideal:{video:'./assets/video/industrial-ideal.mp4',data:'./assets/data/ideal.json',label:'Ideal messages · no PHY',eb:'Ideal / no AWGN'},
  noiseless:{video:'./assets/video/industrial-noiseless.mp4',data:'./assets/data/noiseless.json',label:'Noiseless QPSK · full wire',eb:'Noiseless QPSK'},
  'awgn-8db':{video:'./assets/video/industrial-awgn-8db.mp4',data:'./assets/data/awgn-8db.json',label:'8 dB QPSK/AWGN · seed 303',eb:'8 dB AWGN'}
};
let active='awgn-8db',data=null,loadToken=0,videoLoop=0,selectedEvent=null,visibleEvent=null;
const cache=new Map();
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
const fixed=(n,d=2,s='')=>finite(n)?n.toFixed(d)+s:'—';
const eventTime=e=>finite(e.rx_time_s)?e.rx_time_s:(finite(e.tx_time_s)?e.tx_time_s:0);
const label=s=>s?String(s).replace(/_/g,' ').toUpperCase():'—';
const getType=e=>{
  const text=String(e.message_type||e.direction||'').toUpperCase();
  return text.includes('OBS')||text.includes('UP')?'OBS':text.includes('CMD')||text.includes('DOWN')?'CMD':null;
};
const getTxTime=e=>finite(e.tx_time_s)?e.tx_time_s:eventTime(e);
function setStatus(s,error=false){const e=el('traceStatus');e.textContent=s;e.className='status-note'+(error?' error':' ok');}
function getFrame(t){
  const frames=data?.video_clock?.frame_map;
  if(!frames?.length)return null;
  const fps=data.video_clock.fps||25;
  return frames[clamp(Math.floor(Math.max(0,t)*fps+1e-8),0,frames.length-1)];
}
function eventsThrough(t){
  const rows=data?.events||[];
  let lo=0,hi=rows.length;
  while(lo<hi){const mid=(lo+hi)>>>1;if(eventTime(rows[mid])<=t+1e-9)lo=mid+1;else hi=mid}
  return lo;
}
function simToVideo(t){
  const rows=data?.video_clock?.frame_map||[];
  if(!rows.length)return t;
  let lo=0,hi=rows.length;
  while(lo<hi){const m=(lo+hi)>>>1;if(rows[m].sim_time_s<t)lo=m+1;else hi=m}
  return rows[clamp(lo,0,rows.length-1)].video_time_s;
}
function observation(tick){
 const a=tick?.controller_input,b=tick?.raw_observation;
 return a?.valid?a:(b?.valid?b:a||b||null);
}
function commandVx(v){
 if(!v||typeof v!=='object')return null;
 if(finite(v.vx))return v.vx;
 if(finite(v.vx_m_s))return v.vx_m_s;
 return null;
}
function statusChip(lane,statusText){
 const node=el(lane+'Lane');
 node.classList.remove('accepted','rejected');
 if(statusText==='accepted')node.classList.add('accepted');
 else if(statusText)node.classList.add('rejected');
 el(lane+'Status').textContent=statusText?label(statusText):'—';
}
function bitOutput(id,bits,errorIndices=[]){
 const node=el(id);
 node.replaceChildren();
 if(typeof bits!=='string'||!/^[01]{96}$/.test(bits)){node.textContent='No 96-bit data recorded';return}
 const indices=new Set(errorIndices),fragment=document.createDocumentFragment();
 for(let i=0;i<bits.length;i++){
  const c=indices.has(i)?document.createElement('mark'):document.createElement('span');
  c.textContent=bits[i];
  fragment.appendChild(c);
  if(i===15||i===27||i===79){const spacer=document.createTextNode(' ');fragment.appendChild(spacer)}
 }
 node.appendChild(fragment);
}
function showPacket(e){
 if(!e){el('packetDirection').textContent='—';el('packetResult').textContent='—';el('packetResult').className='';el('packetTime').textContent='—';bitOutput('txBits',null);bitOutput('rxBits',null);el('bitErrorCount').textContent='—';el('packetInterpretation').textContent='Waiting for the first recorded frame.';return}
 const tx=e.tx_bits,rx=e.rx_bits,wrong=[];
 if(typeof tx==='string'&&typeof rx==='string'&&tx.length===rx.length){for(let i=0;i<tx.length;i++)if(tx[i]!==rx[i])wrong.push(i)}
 el('packetDirection').textContent=(getType(e)||'FRAME')+' · '+(e.direction||'LINK');
 el('packetResult').textContent=label(e.status);
 el('packetResult').className=e.status==='accepted'?'ok':'error';
 el('packetTime').textContent='RX '+fixed(eventTime(e),3,' s');
 bitOutput('txBits',tx);
 bitOutput('rxBits',rx,wrong);
 el('bitErrorCount').textContent=wrong.length+' bit difference'+(wrong.length===1?'':'s');
 let reason=e.status==='accepted'?'Receiver accepted frame; message is available to the downstream logic.':'Receiver rejected frame; its semantic payload is not applied.';
 if(wrong.length)reason+=' Red cells indicate differing TX/RX bits.';
 if(finite(e.tx_time_s)&&finite(e.rx_time_s))reason+=' Recorded TX→RX span: '+fixed((e.rx_time_s-e.tx_time_s)*1000,0,' ms')+'.';
 el('packetInterpretation').textContent=reason;
}
function movePacket(lane,e,simTime){
 const ball=el(lane+'Packet');
 if(!e){ball.style.opacity='.08';ball.style.left='0%';return}
 // The visual emphasis persists for 100 ms so frames can be inspected at 25 fps.
 // This is a highlight, NOT a claim about actual over-air packet duration.
 const age=simTime-eventTime(e),phase=clamp(1-age/.1,0,1);
 ball.style.opacity=age>=0&&age<=.1?'1':'.14';
 ball.style.left=(lane==='uplink'?(70+25*phase):(5+25*(1-phase)))+'%';
}
function update(t){
 el('frameClock').textContent='T + '+fixed(t,2,' s');
 if(!data)return;
 const mapped=getFrame(t);
 if(!mapped)return;
 const tick=data.ticks[clamp(mapped.trace_index||0,0,data.ticks.length-1)]||{};
 const sim=finite(mapped.sim_time_s)?mapped.sim_time_s:t;
 const obs=observation(tick);
 el('controllerState').textContent=label(tick.controller_state);
 el('targetRange').textContent=obs?.valid&&finite(obs.range_m)?fixed(obs.range_m,2,' m'):'—';
 el('robotHeading').textContent=finite(tick.yaw_rad)?fixed(tick.yaw_rad*180/Math.PI,1,'°'):'—';
 el('appliedVx').textContent=fixed(commandVx(tick.applied_cmd),3,' m/s');
 el('cmdAge').textContent=fixed(tick.command_age_ms,0,' ms');
 const events=data.events;
 const n=eventsThrough(sim);
 let obsEvent=null,cmdEvent=null,received=null,accepted=0;
 for(let i=0;i<n;i++){const e=events[i];if(e.status==='accepted')accepted++}
 for(let i=n-1;i>=0;i--){const e=events[i];if(!received)received=e;const kind=getType(e);if(kind==='OBS'&&!obsEvent)obsEvent=e;if(kind==='CMD'&&!cmdEvent)cmdEvent=e;if(received&&obsEvent&&cmdEvent)break}
 el('acceptedCount').textContent=accepted+' / '+n;
 el('rejectedCount').textContent=String(n-accepted);
 statusChip('uplink',obsEvent?.status);
 statusChip('downlink',cmdEvent?.status);
 movePacket('uplink',obsEvent,sim);movePacket('downlink',cmdEvent,sim);
 if(received!==visibleEvent){showPacket(received);visibleEvent=received}
}
function rebuildEvents(){
 const list=el('eventButtons');list.replaceChildren();
 const bad=data.events.map((e,i)=>({...e,_index:i})).filter(e=>e.status!=='accepted');
 el('eventsTotal').textContent=bad.length+' rejected frames';
 if(!bad.length){const note=document.createElement('span');note.className='empty';note.textContent='No rejected frames in this run ('+data.events.length+' accepted).';list.appendChild(note);return}
 bad.forEach(e=>{
  const b=document.createElement('button');b.type='button';b.className='event-chip';
  const t=document.createElement('span');t.textContent='T+'+fixed(eventTime(e),2,'s');
  const typ=document.createElement('span');typ.textContent=getType(e)||'LINK';
  const reason=document.createElement('span');reason.textContent=label(e.status);
  b.append(t,typ,reason);
  b.setAttribute('aria-label','Seek to '+(getType(e)||'frame')+' '+label(e.status)+' at '+fixed(eventTime(e),2)+' seconds');
  b.addEventListener('click',()=>{
    if(!data)return;
    video.pause();
    const target=simToVideo(eventTime(e));
    if(finite(target))video.currentTime=clamp(target,0,Math.max(0,(video.duration||27)-.04));
    update(video.currentTime);
    selectedEvent=e._index;
    for(const other of list.children)other.classList.remove('active');
    b.classList.add('active');
    // The inspector directly shows the selected reject, even if the frame
    // maps just before a 10/20 ms RX event boundary.
    showPacket(e);visibleEvent=null;
  });
  list.appendChild(b);
 });
}
function loop(){if(videoLoop)return;videoLoop=requestAnimationFrame(()=>{videoLoop=0;update(video.currentTime);if(!video.paused&&!video.ended)loop()})}
async function selectRun(id){
 if(!sources[id])return;
 const k=++loadToken,wasPlaying=!video.paused;
 active=id;data=null;visibleEvent=null;selectedEvent=null;
 document.querySelectorAll('[data-run]').forEach(b=>{const on=b.dataset.run===id;b.classList.toggle('active',on);b.setAttribute('aria-pressed',on?'true':'false')});
 const source=sources[id];
 el('linkCondition').textContent=source.eb;
 el('acceptedCount').textContent=el('rejectedCount').textContent=el('cmdAge').textContent='—';
 el('controllerState').textContent=el('targetRange').textContent=el('robotHeading').textContent=el('appliedVx').textContent='—';
 statusChip('uplink',null);statusChip('downlink',null);showPacket(null);
 el('eventButtons').textContent='Loading recorded events…';
 el('eventsTotal').textContent='—';
 el('toggleCamera').disabled=id!=='awgn-8db';
 el('toggleCamera').textContent=id==='awgn-8db'?'Robot camera split view ↗':'Split view: 8 dB only';
 el('toggleCamera').setAttribute('aria-pressed','false');
 video.pause();video.src=source.video;video.load();
 el('traceStatus').textContent='Loading matching trace…';
 try{
  if(!cache.has(id))cache.set(id,fetch(source.data).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}));
  const obj=await cache.get(id);
  if(k!==loadToken)return;
  if(obj.run_id!==id||!Array.isArray(obj.events)||!Array.isArray(obj.ticks)||!Array.isArray(obj.video_clock?.frame_map)||obj.video_clock.frame_map.length!==obj.video_clock.frame_count)throw Error('Trace/run mismatch');
  if(id==='awgn-8db' && obj.events.filter(e=>e.status!=='accepted').length!==11)throw Error('AWGN trace reject count mismatch');
  // Source exporter records events by link arrival order; sort only for
  // indexing the UI, without changing or dropping any recorded frame.
  obj.events.sort((a,b)=>eventTime(a)-eventTime(b));
  data=obj;rebuildEvents();update(0);
  setStatus('Loaded '+obj.ticks.length+' robot ticks and '+obj.events.length+' real link events. Replay is ready.');
  if(wasPlaying)video.play().catch(()=>{});
 }catch(err){
  if(k!==loadToken)return;
  cache.delete(id);setStatus('Trace load failed: '+err.message+'. Open this page over HTTP, not file://.',true);
 }
}
document.querySelectorAll('[data-run]').forEach(b=>b.addEventListener('click',()=>selectRun(b.dataset.run)));
video.addEventListener('timeupdate',()=>update(video.currentTime));
video.addEventListener('seeked',()=>update(video.currentTime));
video.addEventListener('play',loop);
video.addEventListener('pause',()=>{if(videoLoop){cancelAnimationFrame(videoLoop);videoLoop=0}});
el('toggleCamera').addEventListener('click',()=>{
 if(active!=='awgn-8db')return;
 const t=video.currentTime,play=!video.paused;
 const split=el('toggleCamera').getAttribute('aria-pressed')==='true',next=!split;
 video.pause();video.src=next?'./assets/video/industrial-awgn-8db-split.mp4':sources[active].video;video.load();
 video.addEventListener('loadedmetadata',()=>{video.currentTime=clamp(t,0,Math.max(0,(video.duration||26.24)-.04));if(play)video.play().catch(()=>{})},{once:true});
 el('toggleCamera').setAttribute('aria-pressed',String(next));
 el('toggleCamera').textContent=next?'Third-person view ↙':'Robot camera split view ↗';
});
selectRun('awgn-8db');
})();
