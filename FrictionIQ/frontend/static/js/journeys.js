'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = value => new Intl.NumberFormat('en-IN', {style:'currency',currency:'INR',maximumFractionDigits:0}).format(value);
let token = sessionStorage.getItem('journey_admin_token'), selected = null, emailMode = 'simulated', refreshing = false;

function signedOut() {
  token = null; selected = null; sessionStorage.removeItem('journey_admin_token');
  $('admin-login').hidden = false;
  ['journey-list','journey-detail','live-overview','admin-logout'].forEach(id => $(id).hidden = true);
}
async function request(path, options={}) {
  const response = await fetch('/api'+path, {...options, headers:{'Content-Type':'application/json', ...(token?{Authorization:'Bearer '+token}:{}), ...options.headers}});
  const data = await response.json();
  if (!response.ok) {
    if (response.status===401 || response.status===403) signedOut();
    throw new Error(typeof data.detail==='string'?data.detail:'Please check the form.');
  }
  return data;
}
function status(text) { $('admin-status').textContent=text; }
function safe(handler) { return async event=>{try{await handler(event);}catch(error){status(error.message);}}; }
async function refresh() {
  if (!token || refreshing) return;
  refreshing=true;
  try {
    const [sessions,kpis,model] = await Promise.all([request('/journeys'),request('/kpis'),request('/models/metrics')]);
    if (!token) return;
    emailMode=model.email_mode;
    $('admin-login').hidden=true;
    ['journey-list','live-overview','admin-logout'].forEach(id=>$(id).hidden=false);
    $('session-count').textContent=`${sessions.length} recent sessions`;
    $('kpis').innerHTML=[['Sessions',kpis.total_sessions],['Conversion',kpis.conversion_rate+'%'],['Possible abandonment',kpis.possibly_abandoned_sessions],['Payment failures',kpis.payment_failures],['Demo order revenue',money(kpis.order_revenue)],['Revenue after recovery',money(kpis.revenue_recovered)]].map(([label,value])=>`<div class="panel metric"><p>${label}</p><strong>${value}</strong></div>`).join('');
    const max=Math.max(kpis.total_sessions,1);
    $('funnel').innerHTML=kpis.funnel.map(s=>`<div class="funnel-step"><p>${esc(s.stage)} <strong>${s.sessions}</strong></p><div class="funnel-track"><div style="width:${s.sessions/max*100}%"></div></div></div>`).join('');
    $('model-status').textContent=model.available?`${model.model} is active. Training source: ${model.training_source}. Live accuracy has not been validated. No LLM is active.`:'XGBoost is unavailable. Observed-event rules remain active.';
    $('email-status').textContent=emailMode==='smtp'?'SMTP email submission enabled. Administrator approval and customer consent are required.':'Email simulation enabled. Configure SMTP to send real emails.';
    $('journey-rows').innerHTML=sessions.map(s=>`<tr><td><strong>${esc(s.name)}</strong><br><small class="session-id">${esc(s.session_id)}</small></td><td><span class="badge">${s.risk_score}/100</span></td><td>${esc(s.status.replaceAll('_',' '))}</td><td>${esc(s.recovery_outcome.replaceAll('_',' '))}</td><td><button data-session="${esc(s.session_id)}">Inspect</button></td></tr>`).join('')||'<tr><td colspan="5">No recorded sessions yet. Open the storefront to begin.</td></tr>';
    status('Updated '+new Date().toLocaleTimeString());
    if (selected) await inspect(selected);
  } finally {refreshing=false;}
}
async function inspect(id) {
  const s=await request('/journeys/'+encodeURIComponent(id));
  const newSelection=selected!==id; selected=id;
  $('journey-detail').hidden=false;
  $('detail-title').textContent=s.name+' · '+s.risk_score+'/100 observed-event risk';
  $('detail-id').textContent=s.session_id;
  $('facts').innerHTML=s.facts.map(f=>`<p>${esc(f)}</p>`).join('');
  $('timeline').innerHTML=s.events.map(e=>`<p><small>${new Date(e.timestamp).toLocaleString()}</small><br><strong>${esc(e.type.replaceAll('_',' '))}</strong> <small>${esc(JSON.stringify(e.details))}</small></p>`).join('');
  $('prediction').textContent=s.prediction.risk_score===null?s.prediction.limitation:`Predicted abandonment probability: ${s.prediction.risk_score}% (${s.prediction.model}). ${s.prediction.limitation}`;
  $('model-drivers').innerHTML=s.prediction.drivers.map(d=>`<p>${esc(d.feature.replaceAll('_',' '))}: ${d.impact>0?'+':''}${d.impact} log-odds contribution</p>`).join('');
  $('inference').textContent=s.inference;
  $('recommendation').textContent=s.recommendation;
  $('consent').textContent=s.consent?'Customer opted into recovery emails.':'Customer has not opted into recovery emails; approval is disabled.';
  $('record-recovery').disabled=!s.consent||s.completed||s.recovery_outcome==='purchase_after_action';
  $('record-recovery').textContent=emailMode==='smtp'?'Approve and send email':'Approve simulated email';
  // Polling must never overwrite an administrator's edited draft.
  if(newSelection) $('recovery-draft').value=s.recommendation.includes('payment')?'Hi! Your recent payment did not complete. Your bag is saved. Please try an alternative payment method or retry checkout. Our team can help if you need assistance.':'Hi! Your bag is saved. If you need help choosing a product or completing checkout, our team is here to assist.';
  $('recovery-history').textContent=`${s.recoveries.length} recovery actions · ${s.recovery_outcome.replaceAll('_',' ')}`;
  $('recovery-records').innerHTML=s.recoveries.map(r=>`<p><strong>${esc(r.status)}</strong> · ${new Date(r.created).toLocaleString()}<br>${esc(r.message)}${r.error?'<br>'+esc(r.error):''}</p>`).join('');
}
$('admin-login').addEventListener('submit',safe(async event=>{
  event.preventDefault();const form=event.currentTarget,button=form.querySelector('button');button.disabled=true;
  try {const result=await request('/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});token=result.access_token;sessionStorage.setItem('journey_admin_token',token);form.reset();await refresh();}finally{button.disabled=false;}
}));
$('refresh').onclick=safe(refresh);
$('admin-logout').onclick=()=>{signedOut();status('Signed out.');};
$('journey-rows').addEventListener('click',safe(async event=>{const button=event.target.closest('[data-session]');if(button){await inspect(button.dataset.session);$('journey-detail').scrollIntoView({behavior:'smooth'});}}));
$('recovery-form').addEventListener('submit',safe(async event=>{
  event.preventDefault();const button=$('record-recovery');button.disabled=true;
  try {const result=await request('/journeys/'+encodeURIComponent(selected)+'/recovery',{method:'POST',body:JSON.stringify({message:$('recovery-draft').value})});await refresh();status(result.message);}finally{if(selected)await inspect(selected);}
}));
setInterval(()=>{if(!document.hidden)safe(refresh)();},5000);
safe(refresh)();
