/* Evidence-linked, offline-only playback. The three JSON files are exported
 * from fixed MuJoCo episodes; this page does not simulate RF or robot motion. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const video = $('replayVideo');
  const app = $('replayApp');
  const status = $('traceStatus');
  const runButtons = Array.from(document.querySelectorAll('[data-run]'));
  const scenarios = {
    'ideal': { label: 'IDEAL MESSAGE · scheduled delivery', video: './assets/video/industrial-ideal.mp4', data: './assets/data/ideal.json', signal: 'Ideal / no PHY' },
    'noiseless': { label: 'NOISELESS QPSK · full wire and PHY', video: './assets/video/industrial-noiseless.mp4', data: './assets/data/noiseless.json', signal: 'QPSK / noiseless' },
    'awgn-8db': { label: 'AWGN 8 dB · fixed seed 303', video: './assets/video/industrial-awgn-8db.mp4', data: './assets/data/awgn-8db.json', signal: '8 dB AWGN' }
  };
  let selected = 'awgn-8db', currentData = null, token = 0, raf = 0, headingTrace = [], selectedEventKey = null;
  const cache = new Map();
  const clamp = (n,min,max) => Math.max(min,Math.min(max,n));
  const num = (x) => typeof x === 'number' && Number.isFinite(x);
  const format = (x,dec=2,unit='') => num(x) ? x.toFixed(dec)+unit : '—';
  const pickTime = (e) => num(e.rx_time_s) ? e.rx_time_s : (num(e.tx_time_s) ? e.tx_time_s : 0);
  const updateStatus = (message, cls='') => { status.textContent=message; status.className='trace-loading '+cls; };
  const readableStatus = (s) => !s ? '—' : String(s).replace(/_/g,' ').toUpperCase();
  function setFrameStatus(id, state){
    const el=$(id);
    const ok=state==='accepted';
    el.className=ok?'accepted':state?'rejected':'';
    el.textContent=state?readableStatus(state):'No frame yet';
  }
  function runSummary(run){
    const data=currentData;
    if(!data) return;
    const videoDuration=num(data.video_clock?.duration_s)?data.video_clock.duration_s:video.duration;
    const expected=run==='awgn-8db'?11:0;
    const rejects=(data.events||[]).filter(e=>e.status!=='accepted').length;
    if(run==='awgn-8db' && rejects!==expected){
      updateStatus('Data validation warning: 8 dB trace should contain exactly 11 rejected frames; found '+rejects+'.','error');
    } else {
      updateStatus('Trace loaded · '+(data.events||[]).length+' link events · '+(data.ticks||[]).length+' policy ticks · '+format(videoDuration,2,' s'),'ok');
    }
    $('eventsTotal').textContent=rejects+' REJECT'+(rejects===1?'':'S');
    const list=$('eventButtons'); list.replaceChildren();
    $('eventsDescription').textContent=rejects?'Click an error to seek the video and inspect the corresponding communication state.':'This run has no rejected frames; all delivered packets passed their receiver checks.';
    if(!rejects){
      const p=document.createElement('p');p.className='event-placeholder';p.textContent='All '+data.events.length+' frames accepted in this run.';list.appendChild(p);return;
    }
    data.events.forEach((e,index)=>{
      if(e.status==='accepted') return;
      const b=document.createElement('button');
      b.type='button';b.className='event-chip';
      const t=pickTime(e);
      b.dataset.eventKey=String(index);
      const time=document.createElement('span');time.className='chip-time';time.textContent='T+'+format(t,2,'s');
      const direction=document.createElement('span');direction.className='chip-type';direction.textContent=e.message_type||e.direction||'FRAME';
      const stat=document.createElement('span');stat.className='chip-status';stat.textContent=readableStatus(e.status);
      b.append(time,direction,stat);
      b.setAttribute('aria-label','Seek to '+readableStatus(e.status)+' at '+format(t,2,' seconds'));
      b.addEventListener('click',()=>{
        if(!currentData)return;
        selectedEventKey=String(index);
        const vtime=simulationToVideoTime(t);
        if(num(vtime)){video.currentTime=clamp(vtime,0,Math.max(0,(video.duration||26.32)-.05));updateAtTime(video.currentTime);}
        video.pause(); highlightEventButtons();
      });
      list.appendChild(b);
    });
  }
  function highlightEventButtons(){
    $('eventButtons').querySelectorAll('button').forEach(button=>{
      const isActive=button.dataset.eventKey===selectedEventKey;
      button.classList.toggle('active',isActive);
      button.setAttribute('aria-pressed',String(isActive));
    });
  }
  function simulationToVideoTime(t){
    const map=currentData?.video_clock?.frame_map;
    if(!Array.isArray(map)||!map.length)return t;
    let lo=0,hi=map.length;
    while(lo<hi){const m=(lo+hi)>>>1;if(map[m].sim_time_s<t)lo=m+1;else hi=m}
    const i=clamp(lo,0,map.length-1),v=map[i].video_time_s;
    return num(v)?v:t;
  }
  function frameForVideoTime(seconds){
    const frames=currentData?.video_clock?.frame_map;
    if(!Array.isArray(frames)||!frames.length)return null;
    const fps=currentData.video_clock.fps||25;
    const i=clamp(Math.floor(Math.max(0,seconds)*fps+1e-8),0,frames.length-1);
    return frames[i];
  }
  function latestEvents(events,simTime){
    let lo=0,hi=events.length;
    while(lo<hi){const mid=(lo+hi)>>>1;if(pickTime(events[mid])<=simTime+1e-9)lo=mid+1;else hi=mid}
    return lo;
  }
  function obsRange(tick){
    const o=tick?.controller_input||tick?.raw_observation;
    return o && o.valid===true && num(o.range_m)?o.range_m:null;
  }
  function obsBearing(tick){
    const o=tick?.controller_input||tick?.raw_observation;
    return o && o.valid===true && num(o.bearing_rad)?o.bearing_rad:null;
  }
  function cmdVx(cmd){
    if(cmd && typeof cmd==='object'){
      if(num(cmd.vx)) return cmd.vx;
      if(num(cmd.vx_m_s))return cmd.vx_m_s;
    }
    return null;
  }
  function currentYaw(tick){return num(tick?.yaw_rad)?tick.yaw_rad:null}
  function drawHeading(){
    const ticks=currentData?.ticks||[];
    headingTrace=ticks.filter(t=>num(currentYaw(t))&&num(t.time_s));
    if(headingTrace.length<2){$('headingPath').setAttribute('d','');return}
    // Unwrap yaw to show the real search turn rather than wrapped discontinuities.
    const expanded=[];let prior=headingTrace[0].yaw_rad,heading=prior;
    for(const t of headingTrace){let d=t.yaw_rad-prior;while(d>Math.PI)d-=2*Math.PI;while(d< -Math.PI)d+=2*Math.PI;heading+=d;expanded.push({time:t.time_s,value:heading});prior=t.yaw_rad}
    const low=Math.min(...expanded.map(x=>x.value)),high=Math.max(...expanded.map(x=>x.value)),spread=Math.max(.01,high-low);
    const duration=currentData.video_clock?.duration_s||26.32;
    const path=expanded.filter((_,i)=>i%4===0||i===expanded.length-1).map((p,i)=>(i?'L':'M')+(34+clamp(p.time/duration,0,1)*690).toFixed(1)+','+(116-(p.value-low)/spread*98).toFixed(1)).join(' ');
    $('headingPath').setAttribute('d',path);
    const end=$('headingChart').querySelectorAll('text');if(end.length)end[end.length-1].textContent=Math.round(duration)+'s';
  }
  function updateAtTime(seconds){
    $('stampTime').textContent='T+'+format(Math.max(0,seconds),2,'s');
    if(!currentData)return;
    const mapped=frameForVideoTime(seconds);
    if(!mapped)return;
    const idx=clamp(mapped.trace_index||0,0,currentData.ticks.length-1);
    const tick=currentData.ticks[idx]||{};
    const t=num(mapped.sim_time_s)?mapped.sim_time_s:Math.max(0,seconds);
    $('controllerState').textContent=readableStatus(tick.controller_state);
    $('targetRange').textContent=format(obsRange(tick),2,' m');
    const bearing=obsBearing(tick);$('targetBearing').textContent=num(bearing)?format(bearing*180/Math.PI,1,'°'):'—';
    $('cmdAge').textContent=format(tick.command_age_ms,0,' ms');
    $('appliedVx').textContent=format(cmdVx(tick.applied_cmd),3,' m/s');
    const yaw=currentYaw(tick);$('headingNow').textContent=num(yaw)?format(yaw*180/Math.PI,1,'° (wrapped)'):'—';
    const dur=currentData.video_clock?.duration_s||26.32;
    const x=34+clamp(seconds/dur,0,1)*690;
    $('headingCursor').setAttribute('x1',String(x));$('headingCursor').setAttribute('x2',String(x));
    const events=currentData.events||[];const end=latestEvents(events,t);const recent=events.slice(0,end);
    const accepted=recent.reduce((n,e)=>n+(e.status==='accepted'?1:0),0);
    const rejected=end-accepted;
    $('acceptedCount').textContent=accepted+' / '+end;
    $('rejectCount').textContent=String(rejected);
    let obs=null,cmd=null;
    for(let i=end-1;i>=0 && (obs===null||cmd===null);i--){
      const event=events[i],kind=(event.message_type||event.direction||'').toUpperCase();
      if(kind.includes('OBS')||kind.includes('UP')){if(obs===null)obs=event}
      if(kind.includes('CMD')||kind.includes('DOWN')){if(cmd===null)cmd=event}
    }
    setFrameStatus('obsStatus',obs?.status);setFrameStatus('cmdStatus',cmd?.status);
    const latest=recent.length?recent[recent.length-1]:null;
    $('lastRxClock').textContent=latest?'T+'+format(pickTime(latest),2,'s'):'—';
  }
  function scheduleFrame(){if(!raf)raf=requestAnimationFrame(()=>{raf=0;updateAtTime(video.currentTime);if(!video.paused&&!video.ended)scheduleFrame()})}
  async function loadRun(id){
    if(!scenarios[id])return;
    const current=++token; selected=id; currentData=null;selectedEventKey=null;
    runButtons.forEach(b=>{const on=b.dataset.run===id;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on))});
    const s=scenarios[id],wasPlaying=!video.paused;
    video.pause();video.src=s.video;video.load();
    $('linkCondition').textContent=s.signal;
    $('replayRunLabel').textContent=s.label;
    $('eventsTotal').textContent='— EVENTS';
    $('eventButtons').replaceChildren();
    $('controllerState').textContent='—';
    ['targetRange','targetBearing','cmdAge','appliedVx','headingNow','acceptedCount','rejectCount','lastRxClock'].forEach(k=>$(k).textContent='—');
    setFrameStatus('obsStatus',null);setFrameStatus('cmdStatus',null);
    $('headingPath').setAttribute('d','');
    $('viewSplit').disabled=id!=='awgn-8db';
    $('viewSplit').setAttribute('aria-pressed','false');
    $('viewSplit').textContent=id==='awgn-8db'?'Show robot camera ↗':'Robot camera · 8 dB only';
    updateStatus('Loading verified '+id+' trace…');
    try{
      let promise=cache.get(id);
      if(!promise){
        promise=fetch(s.data).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status+' for '+s.data);return r.json()});
        cache.set(id,promise);
      }
      const loaded=await promise;
      if(current!==token)return;
      if(loaded.run_id!==id || !Array.isArray(loaded.events) || !Array.isArray(loaded.ticks) || !Array.isArray(loaded.video_clock?.frame_map))throw Error('Trace schema or run ID mismatch');
      // Enforce source identity. No mixed-run telemetry is ever displayed.
      const frames=loaded.video_clock.frame_map;
      if(frames.length!==loaded.video_clock.frame_count)throw Error('Frame map is inconsistent');
      currentData=loaded;
      runSummary(id);drawHeading();updateAtTime(0);
      if(wasPlaying){try{await video.play()}catch(_){/* browser gesture/autoplay restriction */}}
    }catch(err){
      if(current!==token)return;
      cache.delete(id);currentData=null;
      updateStatus('Unable to load this run: '+err.message+'. Serve website/ using a local HTTP server (not file://).','error');
      const p=document.createElement('p');p.className='event-placeholder';p.textContent='No telemetry available for this run.';$('eventButtons').replaceChildren(p);
    }
  }
  runButtons.forEach(b=>b.addEventListener('click',()=>loadRun(b.dataset.run)));
  video.addEventListener('timeupdate',()=>updateAtTime(video.currentTime));
  video.addEventListener('seeked',()=>updateAtTime(video.currentTime));
  video.addEventListener('play',scheduleFrame);
  video.addEventListener('pause',()=>{if(raf){cancelAnimationFrame(raf);raf=0}});
  $('viewSplit').addEventListener('click',()=>{
    if(selected!=='awgn-8db')return;
    const current=video.currentTime,play=!video.paused;
    const isSplit=$('viewSplit').getAttribute('aria-pressed')==='true';
    const next=!isSplit;
    video.pause();
    video.src=next?'./assets/video/industrial-awgn-8db-split.mp4':scenarios[selected].video;
    video.load();
    video.addEventListener('loadedmetadata',()=>{video.currentTime=clamp(current,0,Math.max(0,(video.duration||26.24)-.05));if(play)video.play().catch(()=>{})},{once:true});
    $('viewSplit').setAttribute('aria-pressed',String(next));
    $('viewSplit').textContent=next?'Use third-person ↙':'Show robot camera ↗';
  });
  // The hero is muted decorative footage; respect reduced-motion preferences.
  if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){const hero=$('heroVideo');hero.pause();hero.removeAttribute('autoplay')}
  const progress=$('readingProgress');let ticking=false;
  window.addEventListener('scroll',()=>{if(ticking)return;ticking=true;requestAnimationFrame(()=>{const available=document.documentElement.scrollHeight-window.innerHeight;progress.style.width=(available>0?clamp(window.scrollY/available*100,0,100):0).toFixed(1)+'%';ticking=false})},{passive:true});
  loadRun('awgn-8db');
})();