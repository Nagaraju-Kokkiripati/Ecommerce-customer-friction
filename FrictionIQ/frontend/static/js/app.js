/**
 * FrictionIQ – Main Application JS (ES Modules)
 * Vanilla JS SPA with hash router, Chart.js charts, SSE stream,
 * and full API integration.
 */

const API = '/api';
let authToken = null;
let currentRole = 'admin';

// ── Chart.js Defaults ─────────────────────────────────────────────────────────
function setupChartDefaults() {
  const getVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  Chart.defaults.color = getVar('--text-muted') || '#64748b';
  Chart.defaults.borderColor = getVar('--border-subtle') || 'rgba(255,255,255,0.06)';
  Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
}

// ── API Helper ────────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
  try {
    const res = await fetch(API + path, { ...options, headers });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return await res.json();
  } catch (err) {
    console.warn(`API call failed: ${err.message}`);
    return null;
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 300ms'; setTimeout(() => toast.remove(), 300); }, duration);
}

// ── Router ────────────────────────────────────────────────────────────────────
const PAGE_TITLES = {
  overview: 'Executive Overview',
  funnel: 'Journey Funnel Explorer',
  alerts: 'Friction Detection Center',
  session: 'Session Inspector',
  rootcause: 'Root Cause & Recommendations',
  responses: 'Assisted Responses',
  simulator: 'Recovery Simulator',
  feedback: 'Feedback Intelligence',
  workspace: 'Team Workspaces',
  governance: 'Governance Center',
};

function navigate(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const page = document.getElementById(`page-${pageId}`);
  if (page) page.classList.add('active');

  const navItem = document.querySelector(`[data-page="${pageId}"]`);
  if (navItem) navItem.classList.add('active');

  document.getElementById('topbar-title').textContent = PAGE_TITLES[pageId] || pageId;
  window.location.hash = `#${pageId}`;

  // Lazy load page data
  pageLoaders[pageId]?.();
}

// ── Page Loaders ─────────────────────────────────────────────────────────────
const pageLoaders = {
  overview: loadOverview,
  funnel: loadFunnel,
  alerts: initAlertStream,
  session: () => {},
  rootcause: loadRootCause,
  feedback: loadFeedback,
  governance: () => { loadModelMetrics(); loadAuditLog(); },
  simulator: initSimulatorChart,
};

// ── Overview Page ─────────────────────────────────────────────────────────────
let overviewLoaded = false;
async function loadOverview() {
  if (overviewLoaded) return;
  overviewLoaded = true;

  const kpis = await apiFetch('/kpis') || {
    total_sessions: 10247, conversion_rate: 28.4, abandonment_rate: 71.6,
    revenue_at_risk: 2456800, revenue_recovered: 312400,
    support_ticket_volume: 1842, avg_risk_score: 62.3, friction_spike_count: 4,
  };

  renderKPIs(kpis);
  renderTrendChart();
  renderHeatmapChart();
  renderAISummary(kpis);
}

function renderKPIs(kpis) {
  const grid = document.getElementById('kpi-grid');
  const cards = [
    { label: 'Total Sessions', value: kpis.total_sessions?.toLocaleString(), delta: '+12%', deltaPos: true, accent: '#6366f1', icon: '👥' },
    { label: 'Conversion Rate', value: `${kpis.conversion_rate}%`, delta: '+2.1%', deltaPos: true, accent: '#10b981', icon: '🛒' },
    { label: 'Abandonment Rate', value: `${kpis.abandonment_rate}%`, delta: '-3.2%', deltaPos: false, accent: '#ef4444', icon: '⚡' },
    { label: 'Revenue at Risk', value: `₹${(kpis.revenue_at_risk / 100000).toFixed(1)}L`, delta: '-8%', deltaPos: false, accent: '#f97316', icon: '⚠️' },
    { label: 'Revenue Recovered', value: `₹${(kpis.revenue_recovered / 1000).toFixed(0)}K`, delta: '+41%', deltaPos: true, accent: '#10b981', icon: '💰' },
    { label: 'Friction Spikes', value: kpis.friction_spike_count, delta: '+2 today', deltaPos: false, accent: '#f59e0b', icon: '🔥' },
  ];

  grid.innerHTML = cards.map(c => `
    <div class="kpi-card" style="--kpi-accent:${c.accent};">
      <div class="kpi-icon">${c.icon}</div>
      <div class="kpi-label">${c.label}</div>
      <div class="kpi-value">${c.value}</div>
      <div class="kpi-delta ${c.deltaPos ? '' : 'negative'}">
        ${c.deltaPos ? '▲' : '▼'} ${c.delta}
      </div>
    </div>
  `).join('');
}

function renderTrendChart() {
  const ctx = document.getElementById('chart-trend');
  if (!ctx) return;
  const labels = Array.from({length: 30}, (_, i) => {
    const d = new Date(2024, 8, 1 + i);
    return `${d.getDate()}/${d.getMonth()+1}`;
  });
  const data = labels.map(() => Math.random() * 20 + 60);

  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Abandonment %',
        data,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.08)',
        tension: 0.4,
        fill: true,
        pointRadius: 0,
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { maxTicksLimit: 8 } },
        y: { min: 50, max: 90, ticks: { callback: v => `${v}%` } },
      },
    },
  });
}

function renderHeatmapChart() {
  const ctx = document.getElementById('chart-friction-heatmap');
  if (!ctx) return;
  const frictionTypes = ['Payment', 'Delivery', 'Product Info', 'Price Shock', 'Technical'];
  const stages = ['Browse', 'Cart', 'Checkout', 'Payment', 'Post-Purchase'];

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: stages,
      datasets: frictionTypes.map((ft, i) => ({
        label: ft,
        data: stages.map(() => Math.round(Math.random() * 400 + 50)),
        backgroundColor: ['#ef4444','#f97316','#f59e0b','#6366f1','#0ea5e9'][i] + 'cc',
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top' } },
      scales: { x: { stacked: true }, y: { stacked: true } },
    },
  });
}

function renderAISummary(kpis) {
  document.getElementById('ai-summary').innerHTML = `
    <p>⚡ <strong>Current Status:</strong> FrictionIQ detected <strong>${kpis.friction_spike_count} friction spikes</strong> in the last 4 hours.
    The most critical is a <strong>payment failure spike on Razorpay</strong> (error: 3DS_TIMEOUT) affecting 342 sessions — 
    estimated ₹${(342 * 2200 * 0.4 / 1000).toFixed(0)}K in revenue at risk.</p>
    <br/>
    <p>💡 <strong>Root Cause:</strong> The Journey Analyst and Root Cause agents identified that 89% of failures are concentrated in
    Razorpay's 3DS gateway between 10:00–14:00 IST on mobile devices using the Chrome browser.</p>
    <br/>
    <p>✅ <strong>Recommended Action:</strong> The Recovery Strategist recommends deploying an <em>alternate payment method prompt</em>
    (UPI/wallet) with an expected 22% conversion lift. The Critic agent has approved this action — <strong>awaiting your approval to trigger.</strong></p>
  `;
}

// ── Funnel Page ───────────────────────────────────────────────────────────────
let funnelLoaded = false;
async function loadFunnel() {
  if (funnelLoaded) return;
  funnelLoaded = true;

  const data = await apiFetch('/funnel') || { stages: [] };
  const stages = data.stages?.length ? data.stages : [
    {stage: 'Browse/Discovery', sessions: 10247, drop_off: 0, drop_off_rate: 0, revenue_at_risk: 0},
    {stage: 'Product View', sessions: 7821, drop_off: 2426, drop_off_rate: 23.7, revenue_at_risk: 436680},
    {stage: 'Add to Cart', sessions: 4312, drop_off: 3509, drop_off_rate: 44.9, revenue_at_risk: 631620},
    {stage: 'Checkout Start', sessions: 3105, drop_off: 1207, drop_off_rate: 28.0, revenue_at_risk: 217260},
    {stage: 'Payment Attempted', sessions: 2234, drop_off: 871, drop_off_rate: 28.0, revenue_at_risk: 156780},
    {stage: 'Order Placed', sessions: 1842, drop_off: 392, drop_off_rate: 17.5, revenue_at_risk: 70560},
  ];

  const maxSessions = stages[0].sessions;
  const funnelViz = document.getElementById('funnel-viz');
  funnelViz.innerHTML = stages.map(s => `
    <div class="funnel-stage">
      <div class="funnel-label">${s.stage}</div>
      <div class="funnel-bar-track">
        <div class="funnel-bar-fill" style="width:${s.sessions/maxSessions*100}%"></div>
      </div>
      <div class="funnel-count">${s.sessions.toLocaleString()}</div>
    </div>
    ${s.drop_off > 0 ? `<div style="font-size:11px;color:var(--sev-high);padding:2px 0 4px 164px;">↓ ${s.drop_off.toLocaleString()} dropped (${s.drop_off_rate}%)</div>` : ''}
  `).join('');

  // Revenue risk chart
  const riskCtx = document.getElementById('chart-revenue-risk');
  if (riskCtx) {
    new Chart(riskCtx, {
      type: 'bar',
      data: {
        labels: stages.slice(1).map(s => s.stage),
        datasets: [{
          label: 'Revenue at Risk (₹)',
          data: stages.slice(1).map(s => s.revenue_at_risk),
          backgroundColor: 'rgba(239,68,68,0.7)',
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { ticks: { callback: v => `₹${(v/1000).toFixed(0)}K` } } },
      },
    });
  }

  // Device chart
  const devCtx = document.getElementById('chart-device-funnel');
  if (devCtx) {
    new Chart(devCtx, {
      type: 'bar',
      data: {
        labels: ['Browse', 'Cart', 'Checkout', 'Placed'],
        datasets: [
          { label: 'Mobile', data: [6200, 2800, 1800, 980], backgroundColor: '#6366f1cc' },
          { label: 'Desktop', data: [3200, 1200, 1100, 720], backgroundColor: '#0ea5e9cc' },
          { label: 'Tablet', data: [847, 312, 205, 142], backgroundColor: '#f59e0bcc' },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }
}

// ── Alert Stream (SSE) ────────────────────────────────────────────────────────
let alertEventSource = null;
let alertCount = 0;
const MAX_ALERTS = 30;

function initAlertStream() {
  const feed = document.getElementById('alert-feed');
  const status = document.getElementById('sse-status');

  if (alertEventSource) return;

  try {
    alertEventSource = new EventSource(`${API}/stream/events`);
    alertEventSource.addEventListener('friction_alert', (e) => {
      const alert = JSON.parse(e.data);
      addAlertToFeed(alert);
      alertCount++;
      document.getElementById('alert-badge').textContent = alertCount;
      updateSpikeTimeline(alert);
    });
    alertEventSource.onerror = () => {
      status.textContent = '● Reconnecting...';
      status.className = 'badge badge-medium';
    };
    alertEventSource.onopen = () => {
      status.textContent = '● Connected';
      status.className = 'badge badge-low';
    };
  } catch(e) {
    status.textContent = '● Offline';
    status.className = 'badge badge-critical';
    // Show demo alerts
    renderDemoAlerts();
  }
}

function addAlertToFeed(alert) {
  const feed = document.getElementById('alert-feed');
  const item = document.createElement('div');
  item.className = 'alert-item';
  item.style.animation = 'slideInRight 200ms ease';
  item.innerHTML = `
    <div class="alert-severity ${alert.severity}"></div>
    <div class="alert-body">
      <div class="alert-type">${formatFrictionType(alert.friction_type)}</div>
      <div class="alert-desc">Session: <code style="font-family:var(--font-mono);font-size:11px;">${alert.session_id}</code> — Risk: ${alert.risk_score}</div>
      <div class="alert-meta">${new Date(alert.timestamp).toLocaleTimeString()}</div>
    </div>
    <div>
      <div class="alert-revenue">₹${alert.revenue_at_risk?.toLocaleString()}</div>
      <span class="badge badge-${alert.severity}">${alert.severity}</span>
    </div>
  `;
  item.onclick = () => { navigate('session'); document.getElementById('session-id-input').value = alert.session_id; };
  feed.insertBefore(item, feed.firstChild);

  // Cap feed size
  while (feed.children.length > MAX_ALERTS) feed.removeChild(feed.lastChild);
}

function renderDemoAlerts() {
  const demos = [
    { friction_type: 'payment_failure', severity: 'critical', session_id: 'demo_001', risk_score: 94, revenue_at_risk: 8400, timestamp: new Date().toISOString() },
    { friction_type: 'delivery_uncertainty', severity: 'high', session_id: 'demo_002', risk_score: 78, revenue_at_risk: 3200, timestamp: new Date().toISOString() },
    { friction_type: 'price_shock', severity: 'medium', session_id: 'demo_003', risk_score: 65, revenue_at_risk: 1800, timestamp: new Date().toISOString() },
  ];
  demos.forEach(a => addAlertToFeed(a));
}

function clearAlerts() {
  document.getElementById('alert-feed').innerHTML = '';
  alertCount = 0;
  document.getElementById('alert-badge').textContent = '0';
}

let spikeChart = null;
const spikeData = { labels: [], datasets: [{ label: 'Alerts/min', data: [], borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', tension: 0.4, fill: true }] };

function updateSpikeTimeline(alert) {
  const ctx = document.getElementById('chart-spike-timeline');
  if (!ctx) return;
  const now = new Date().toLocaleTimeString();
  spikeData.labels.push(now);
  spikeData.datasets[0].data.push(Math.round(Math.random() * 5 + 1));
  if (spikeData.labels.length > 20) { spikeData.labels.shift(); spikeData.datasets[0].data.shift(); }
  if (!spikeChart) {
    spikeChart = new Chart(ctx, { type: 'line', data: spikeData, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, animation: false } });
  } else {
    spikeChart.update('none');
  }
}

// ── Session Inspector ─────────────────────────────────────────────────────────
async function analyzeSession() {
  const sessionId = document.getElementById('session-id-input').value || 'demo_payment_fail_001';
  const btn = document.getElementById('analyze-btn');
  btn.disabled = true;
  btn.textContent = 'Analyzing...';

  // Build demo features for payment failure scenario
  const demoFeatures = {
    session_id: sessionId,
    num_events: 12,
    duration_sec: 420,
    num_product_views: 3,
    num_compares: 1,
    num_cart_adds: 1,
    num_cart_removes: 0,
    num_searches: 1,
    num_payment_attempts: 3,
    num_payment_fails: 3,
    num_rage_clicks: 0,
    num_dead_clicks: 0,
    reached_checkout: 1,
    reached_payment: 1,
    placed_order: 0,
    exited_at_checkout: 1,
    payment_fail_rate: 1.0,
    pages_visited: 6,
    has_delivery_check: 1,
    device_mobile: 1,
    device_desktop: 0,
    channel_organic: 0,
    channel_paid: 1,
    is_new_customer: 1,
    search_reformulation_count: 0,
  };

  // Get risk score
  const risk = await apiFetch(`/sessions/${sessionId}/risk`, {
    method: 'POST',
    body: JSON.stringify(demoFeatures),
  }) || { risk_score: 94.2, risk_label: 'critical', model: 'xgboost', shap_factors: [
    {feature: 'num_payment_fails', impact: 0.42},
    {feature: 'payment_fail_rate', impact: 0.35},
    {feature: 'exited_at_checkout', impact: 0.28},
    {feature: 'is_new_customer', impact: 0.12},
    {feature: 'num_payment_attempts', impact: 0.09},
  ]};

  // Get agent analysis
  const analysis = await apiFetch('/root-causes', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      risk_score: risk.risk_score,
      features: demoFeatures,
      payment_context: { gateway: 'Razorpay', error_code: '3DS_TIMEOUT' },
      product_context: { description_quality_score: 0.82 },
      feedback_text: '',
      customer_segment: 'new',
    }),
  });

  document.getElementById('session-results').classList.remove('hidden');

  // Risk score
  const riskEl = document.getElementById('risk-score-value');
  riskEl.textContent = risk.risk_score?.toFixed(0) || '--';
  riskEl.style.color = risk.risk_score > 80 ? 'var(--sev-critical)' : risk.risk_score > 60 ? 'var(--sev-high)' : 'var(--sev-medium)';
  const labelEl = document.getElementById('risk-label');
  labelEl.textContent = (risk.risk_label || 'unknown').toUpperCase();
  labelEl.className = `badge badge-${risk.risk_label === 'critical' ? 'critical' : risk.risk_label === 'high' ? 'high' : 'medium'}`;
  labelEl.style.margin = 'var(--space-3) auto; width:fit-content;';

  // SHAP chart
  const shap = risk.shap_factors || [];
  const maxImpact = Math.max(...shap.map(s => Math.abs(s.impact)), 0.01);
  document.getElementById('shap-chart').innerHTML = shap.map(s => `
    <div class="shap-bar">
      <div class="shap-feature">${s.feature.replace(/_/g, ' ')}</div>
      <div class="shap-track">
        <div class="${s.impact > 0 ? 'shap-fill-pos' : 'shap-fill-neg'}" style="width:${Math.abs(s.impact)/maxImpact*100}%"></div>
      </div>
      <div class="shap-value ${s.impact > 0 ? 'text-danger' : 'text-success'}">${s.impact > 0 ? '+' : ''}${s.impact.toFixed(3)}</div>
    </div>
  `).join('') || '<p class="text-muted text-sm">No SHAP data available</p>';

  // Event timeline
  const mockEvents = [
    {ts:'10:23:01', type:'page_view', page:'home'},
    {ts:'10:23:24', type:'search', page:'search'},
    {ts:'10:24:10', type:'product_view', page:'product_detail'},
    {ts:'10:25:44', type:'add_to_cart', page:'cart'},
    {ts:'10:26:12', type:'checkout_start', page:'checkout'},
    {ts:'10:27:15', type:'address_entry', page:'checkout'},
    {ts:'10:27:44', type:'payment_attempt', page:'checkout', danger:true},
    {ts:'10:27:52', type:'payment_fail', page:'checkout', danger:true},
    {ts:'10:28:30', type:'payment_attempt', page:'checkout', danger:true},
    {ts:'10:28:38', type:'payment_fail', page:'checkout', danger:true},
    {ts:'10:29:20', type:'payment_attempt', page:'checkout', danger:true},
    {ts:'10:29:29', type:'payment_fail', page:'checkout', danger:true},
    {ts:'10:30:05', type:'exit', page:'checkout'},
  ];
  document.getElementById('event-timeline').innerHTML = `
    <div style="display:flex;gap:0;overflow-x:auto;padding-bottom:8px;">
      ${mockEvents.map(e => `
        <div style="display:flex;flex-direction:column;align-items:center;min-width:80px;padding:0 4px;">
          <div style="width:10px;height:10px;border-radius:50%;background:${e.danger ? 'var(--sev-critical)' : 'var(--brand-primary)'};box-shadow:${e.danger ? '0 0 8px var(--sev-critical)' : 'none'};"></div>
          <div style="width:1px;height:24px;background:var(--border-subtle);"></div>
          <div style="font-size:10px;color:${e.danger ? 'var(--sev-critical)' : 'var(--text-muted)'};text-align:center;">${e.type.replace(/_/g,' ')}</div>
          <div style="font-size:10px;color:var(--text-muted);font-family:var(--font-mono);">${e.ts}</div>
        </div>
      `).join('')}
    </div>
  `;

  // Agent trace
  const trace = analysis?.reasoning_trace || [
    {agent:'journey_analyst', output_summary:{friction_location:'payment_stage'}},
    {agent:'root_cause', output_summary:{top_cause:'payment_failure', confidence:0.95, evidence:'3 payment failures — 3DS_TIMEOUT on Razorpay'}},
    {agent:'recovery_strategist', output_summary:{interventions:['alternate_payment_method','smart_payment_retry']}},
    {agent:'critic_guardrail', output_summary:{approved:true, decision:'APPROVED'}},
  ];
  document.getElementById('agent-trace').innerHTML = trace.map(step => `
    <div class="trace-step">
      <div class="trace-dot"></div>
      <div>
        <div class="trace-agent">${step.agent?.replace(/_/g,' ').toUpperCase()}</div>
        <div class="trace-content">
          <pre>${JSON.stringify(step.output_summary, null, 2)}</pre>
        </div>
      </div>
    </div>
  `).join('');

  // Also populate root cause page
  if (analysis) populateRootCause(analysis);

  btn.disabled = false;
  btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg> Analyze Session';
  showToast(`Session analyzed — Risk: ${risk.risk_score?.toFixed(0)}/100 (${risk.risk_label})`, risk.risk_score > 70 ? 'error' : 'info');
}

// ── Root Cause Page ───────────────────────────────────────────────────────────
let lastAnalysis = null;

function loadRootCause() {
  if (lastAnalysis) return;
  // Load demo analysis
  populateRootCause({
    friction_location: 'payment_stage',
    root_causes: [
      {cause: 'payment_failure', confidence: 0.95, evidence: '3 failed attempts — 3DS_TIMEOUT on Razorpay', severity: 'high'},
      {cause: 'unclear_product_info', confidence: 0.65, evidence: 'High compare rate; description quality 0.82', severity: 'medium'},
    ],
    recommended_interventions: [
      {type: 'alternate_payment_method', uplift: 0.22, cost: 0, channel: 'in_app', for_cause: 'payment_failure'},
      {type: 'smart_payment_retry', uplift: 0.18, cost: 0, channel: 'in_app', for_cause: 'payment_failure'},
      {type: 'targeted_incentive_10pct', uplift: 0.14, cost: 0.10, channel: 'email', for_cause: 'unclear_product_info'},
    ],
    personalized_message: "We noticed a hiccup during your payment. Try UPI or net banking — it only takes 30 seconds!",
    compliance_approved: true,
    compliance_issues: [],
    final_decision: 'PENDING_HUMAN_APPROVAL',
  });
}

function populateRootCause(analysis) {
  lastAnalysis = analysis;

  // Root causes
  const causeList = document.getElementById('root-causes-list');
  if (causeList) {
    causeList.innerHTML = (analysis.root_causes || []).map((rc, i) => `
      <div style="padding:var(--space-4);border:1px solid var(--border-subtle);border-radius:var(--radius-md);margin-bottom:var(--space-3);">
        <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-2);">
          <span style="font-size:20px;font-weight:800;color:var(--text-muted);">${i+1}</span>
          <div>
            <div style="font-weight:700;font-size:14px;">${formatFrictionType(rc.cause)}</div>
            <div style="font-size:12px;color:var(--text-muted);">Confidence: ${(rc.confidence*100).toFixed(0)}%</div>
          </div>
          <span class="badge badge-${rc.severity}" style="margin-left:auto;">${rc.severity}</span>
        </div>
        <div style="font-size:12px;color:var(--text-secondary);padding-left:var(--space-8);">${rc.evidence}</div>
        <div style="padding-left:var(--space-8);margin-top:var(--space-2);">
          <div style="background:var(--bg-elevated);border-radius:var(--radius-full);height:6px;overflow:hidden;">
            <div style="width:${rc.confidence*100}%;height:100%;background:${rc.confidence > 0.8 ? 'var(--sev-high)' : 'var(--sev-medium)'};border-radius:var(--radius-full);"></div>
          </div>
        </div>
      </div>
    `).join('') || '<p class="text-muted text-sm">Run session analysis first</p>';
  }

  // Interventions
  const ivList = document.getElementById('interventions-list');
  if (ivList) {
    ivList.innerHTML = (analysis.recommended_interventions || []).map(iv => `
      <div style="padding:var(--space-4);border:1px solid var(--border-subtle);border-radius:var(--radius-md);margin-bottom:var(--space-3);">
        <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3);">
          <div style="flex:1;">
            <div style="font-weight:700;font-size:14px;">${formatInterventionType(iv.type)}</div>
            <div style="font-size:12px;color:var(--text-muted);">Channel: ${iv.channel} · Expected uplift: +${(iv.uplift*100).toFixed(0)}%</div>
          </div>
        </div>
        <div style="display:flex;gap:var(--space-2);">
          <button class="btn btn-success btn-sm" onclick="approveIntervention('${iv.type}','${iv.channel}')">✓ Approve</button>
          <button class="btn btn-outline btn-sm" onclick="editIntervention('${iv.type}')">✏ Edit</button>
          <button class="btn btn-danger btn-sm" onclick="rejectIntervention('${iv.type}')">✗ Reject</button>
        </div>
      </div>
    `).join('') || '<p class="text-muted text-sm">Run session analysis first</p>';
  }

  // Compliance
  const compliance = document.getElementById('compliance-content');
  if (compliance) {
    compliance.innerHTML = `
      <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4);">
        <span style="font-size:24px;">${analysis.compliance_approved ? '✅' : '⚠️'}</span>
        <div>
          <div style="font-weight:700;">${analysis.final_decision || 'PENDING'}</div>
          <div style="font-size:12px;color:var(--text-muted);">
            ${analysis.compliance_issues?.length ? analysis.compliance_issues.join(', ') : 'No compliance issues detected'}
          </div>
        </div>
        <span class="badge badge-${analysis.compliance_approved ? 'low' : 'medium'}" style="margin-left:auto;">
          ${analysis.compliance_approved ? 'COMPLIANT' : 'REVIEW NEEDED'}
        </span>
      </div>
      <div style="font-size:13px;color:var(--text-secondary);">
        <strong>Personalized Message Preview:</strong><br/>
        <div style="background:var(--bg-elevated);padding:var(--space-4);border-radius:var(--radius-sm);margin-top:var(--space-2);font-style:italic;">
          "${analysis.personalized_message || 'No message generated'}"
        </div>
      </div>
    `;
  }
}

async function approveIntervention(type, channel) {
  showToast(`Triggering intervention: ${formatInterventionType(type)}...`, 'info');
  const result = await apiFetch('/interventions/trigger', {
    method: 'POST',
    body: JSON.stringify({
      session_id: document.getElementById('session-id-input').value || 'demo_001',
      intervention_type: type,
      channel,
      message: lastAnalysis?.personalized_message || 'Recovery message',
      approved_by: currentRole,
    }),
  });
  if (result) {
    showToast(`${result.message}. Trigger ID: ${result.trigger_id}`, 'info', 5000);
  } else {
    showToast('Intervention failed. Check the API connection and permissions, then retry.', 'error');
  }
}

function editIntervention(type) {
  navigate('responses');
  document.getElementById('response-context').value = document.getElementById('response-context').options[0].value;
  showToast('Edit the message before sending', 'info');
}

function rejectIntervention(type) {
  showToast(`Intervention '${formatInterventionType(type)}' rejected`, 'error');
}

// ── Feedback Page ─────────────────────────────────────────────────────────────
let feedbackLoaded = false;
async function loadFeedback() {
  if (feedbackLoaded) return;
  feedbackLoaded = true;

  const data = await apiFetch('/feedback/themes') || { themes: [] };
  const themes = data.themes?.length ? data.themes : [
    {theme:'Delivery & Shipping', count:892, avg_sentiment:-0.45, sample_texts:['Order took forever', 'Tracking useless']},
    {theme:'Payment Issues', count:634, avg_sentiment:-0.68, sample_texts:['Payment kept failing']},
    {theme:'Product Information', count:521, avg_sentiment:-0.31, sample_texts:['Size guide was wrong']},
    {theme:'Post Purchase', count:387, avg_sentiment:-0.55, sample_texts:['WISMO frustration']},
    {theme:'Pricing', count:298, avg_sentiment:-0.42, sample_texts:['High shipping cost']},
  ];

  const themesCtx = document.getElementById('chart-themes');
  if (themesCtx) {
    new Chart(themesCtx, {
      type: 'doughnut',
      data: {
        labels: themes.map(t => t.theme),
        datasets: [{
          data: themes.map(t => t.count),
          backgroundColor: ['#ef4444','#f97316','#f59e0b','#6366f1','#0ea5e9'].map(c => c + 'cc'),
          borderWidth: 0,
        }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } },
    });
  }

  const sentCtx = document.getElementById('chart-sentiment');
  if (sentCtx) {
    const labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep'];
    new Chart(sentCtx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Negative', data: labels.map(() => -(Math.random()*30+40)), borderColor:'#ef4444', backgroundColor:'rgba(239,68,68,0.1)', fill:true, tension:0.4 },
          { label: 'Positive', data: labels.map(() => Math.random()*20+15), borderColor:'#10b981', backgroundColor:'rgba(16,185,129,0.1)', fill:true, tension:0.4 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { stacked: false } } },
    });
  }

  document.getElementById('theme-details').innerHTML = themes.map(t => `
    <div style="padding:var(--space-4);border:1px solid var(--border-subtle);border-radius:var(--radius-md);margin-bottom:var(--space-3);">
      <div style="display:flex;align-items:center;gap:var(--space-3);">
        <div style="flex:1;">
          <div style="font-weight:700;font-size:14px;">${t.theme}</div>
          <div style="font-size:12px;color:var(--text-muted);">${t.count} mentions · Avg sentiment: ${(t.avg_sentiment*100).toFixed(0)}%</div>
        </div>
        <span class="badge ${t.avg_sentiment < -0.5 ? 'badge-critical' : t.avg_sentiment < -0.3 ? 'badge-high' : 'badge-medium'}">
          ${t.avg_sentiment < -0.5 ? 'Highly Negative' : t.avg_sentiment < -0.3 ? 'Negative' : 'Mixed'}
        </span>
      </div>
      <div style="margin-top:var(--space-2);">${t.sample_texts?.map(s => `<span style="font-size:12px;background:var(--bg-elevated);padding:2px 8px;border-radius:var(--radius-sm);margin-right:4px;display:inline-block;margin-top:4px;">"${s}"</span>`).join('')}</div>
    </div>
  `).join('');
}

// ── Simulator ─────────────────────────────────────────────────────────────────
let simChart = null;
function initSimulatorChart() {
  const ctx = document.getElementById('chart-sim-comparison');
  if (!ctx || simChart) return;
  simChart = new Chart(ctx, {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Revenue Recovered (₹)', data: [], backgroundColor: '#6366f1cc', borderRadius: 4 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => `₹${(v/1000).toFixed(0)}K` } } } },
  });
}

async function runSimulation() {
  const intervention = document.getElementById('sim-intervention').value;
  const audience = parseInt(document.getElementById('sim-audience').value);
  const aov = parseFloat(document.getElementById('sim-aov').value);
  const incentive = parseFloat(document.getElementById('sim-incentive').value);

  const result = await apiFetch('/simulate', {
    method: 'POST',
    body: JSON.stringify({
      intervention_type: intervention,
      audience_size: audience,
      avg_order_value: aov,
      incentive_pct: incentive,
      baseline_conversion: 0.05,
      channel: 'email',
    }),
  }) || {
    intervention_type: intervention,
    expected_conversions: Math.round(audience * 0.065),
    conversion_lift: 12.3,
    revenue_recovered: Math.round(audience * 0.065 * aov),
    incentive_cost: Math.round(audience * 0.065 * aov * incentive / 100),
    net_revenue: Math.round(audience * 0.065 * aov * (1 - incentive/100)),
    roi: incentive > 0 ? 340 : 0,
    confidence_interval_low: 8.5,
    confidence_interval_high: 16.1,
  };

  document.getElementById('sim-results').innerHTML = `
    <div class="kpi-grid" style="grid-template-columns:repeat(2,1fr);">
      <div class="kpi-card" style="--kpi-accent:#10b981;">
        <div class="kpi-label">Expected Conversions</div>
        <div class="kpi-value">${result.expected_conversions?.toLocaleString()}</div>
        <div class="kpi-delta">+${result.conversion_lift?.toFixed(1)}% lift</div>
      </div>
      <div class="kpi-card" style="--kpi-accent:#6366f1;">
        <div class="kpi-label">Revenue Recovered</div>
        <div class="kpi-value">₹${(result.revenue_recovered/1000).toFixed(0)}K</div>
        <div class="kpi-delta">CI: ${result.confidence_interval_low?.toFixed(1)}-${result.confidence_interval_high?.toFixed(1)}%</div>
      </div>
      <div class="kpi-card" style="--kpi-accent:#f97316;">
        <div class="kpi-label">Incentive Cost</div>
        <div class="kpi-value">₹${(result.incentive_cost/1000).toFixed(0)}K</div>
        <div class="kpi-delta negative">−${incentive}% margin</div>
      </div>
      <div class="kpi-card" style="--kpi-accent:#0ea5e9;">
        <div class="kpi-label">Net Revenue</div>
        <div class="kpi-value">₹${(result.net_revenue/1000).toFixed(0)}K</div>
        <div class="kpi-delta">ROI: ${result.roi}%</div>
      </div>
    </div>
  `;

  // Update comparison chart
  if (simChart) {
    const label = formatInterventionType(intervention);
    const idx = simChart.data.labels.indexOf(label);
    if (idx >= 0) {
      simChart.data.datasets[0].data[idx] = result.revenue_recovered;
    } else {
      simChart.data.labels.push(label);
      simChart.data.datasets[0].data.push(result.revenue_recovered);
    }
    simChart.update();
  }

  showToast(`Simulation complete: ${result.conversion_lift?.toFixed(1)}% expected lift`, 'success');
}

// ── Governance Page ───────────────────────────────────────────────────────────
async function loadModelMetrics() {
  const metrics = await apiFetch('/models/metrics') || {
    xgboost: {auc_roc:0.94, pr_auc:0.91, f1:0.88, brier_score:0.08},
    lightgbm: {auc_roc:0.93, pr_auc:0.90, f1:0.87, brier_score:0.09},
    logistic_regression: {auc_roc:0.81, pr_auc:0.76, f1:0.74, brier_score:0.16},
  };

  const el = document.getElementById('model-metrics-table');
  if (!el) return;
  el.innerHTML = `
    <table class="data-table">
      <thead><tr><th>Model</th><th>AUC-ROC</th><th>PR-AUC</th><th>F1</th><th>Brier</th><th>Status</th></tr></thead>
      <tbody>
        ${Object.entries(metrics).map(([name, m], i) => `
          <tr>
            <td style="font-weight:600;">${name}</td>
            <td>${m.auc_roc?.toFixed(3)}</td>
            <td>${m.pr_auc?.toFixed(3)}</td>
            <td>${m.f1?.toFixed(3)}</td>
            <td>${m.brier_score?.toFixed(3)}</td>
            <td>${i===0 ? '<span class="badge badge-low">Champion</span>' : '<span class="badge badge-info">Challenger</span>'}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

async function loadAuditLog() {
  const data = await apiFetch('/audit-log?limit=20') || { entries: [] };
  const el = document.getElementById('audit-log-content');
  if (!el) return;

  const entries = data.entries?.length ? data.entries : [
    {entry_id:'a1b2',timestamp:new Date().toISOString(),actor:'admin',action:'login',resource:'auth',outcome:'success'},
    {entry_id:'c3d4',timestamp:new Date().toISOString(),actor:'admin',action:'root_cause_analysis',resource:'session:demo_001',details:{risk_score:94.2},outcome:'success'},
  ];

  if (!entries.length) { el.innerHTML = '<p class="text-muted text-sm" style="padding:var(--space-4);">No audit entries yet</p>'; return; }

  el.innerHTML = `
    <table class="data-table">
      <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Outcome</th></tr></thead>
      <tbody>
        ${entries.map(e => `
          <tr>
            <td class="font-mono text-xs">${new Date(e.timestamp).toLocaleTimeString()}</td>
            <td>${e.actor}</td>
            <td>${e.action?.replace(/_/g,' ')}</td>
            <td class="text-xs font-mono">${e.resource}</td>
            <td><span class="badge badge-${e.outcome==='success'?'low':'critical'}">${e.outcome}</span></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

// ── Assisted Responses ────────────────────────────────────────────────────────
const RESPONSE_TEMPLATES = {
  'Payment failure – 3DS_TIMEOUT': `Hi there! 👋 We noticed your recent payment hit a small snag — this can happen with 3D Secure authentication. The good news: your cart is saved! Try paying with UPI (it's instant and always works) or net banking. Click below and we'll take you straight to checkout. No need to re-enter your details. 🛒`,
  'Delivery uncertainty – ETA > 10 days': `Great news about your order! 📦 We've confirmed your delivery — guaranteed by [DATE]. Our logistics partner has prioritized your shipment. You'll receive real-time SMS updates. If it doesn't arrive on time, we'll refund your shipping fee, no questions asked.`,
  'Cart abandonment – price shock': `Hey! We noticed you left something behind. 🛍️ We want to make this easier — here's a special 10% discount code for your cart: SAVE10. This offer is valid for 24 hours. Complete your purchase now and enjoy free shipping on orders above ₹999.`,
  'WISMO – delayed order': `We're sorry for the wait! 🙏 Your order [ORDER_ID] is currently with our delivery partner and is expected to arrive by [DATE]. We know this isn't ideal — as a gesture of goodwill, we've added ₹100 in store credit to your account. Track your order in real time here: [LINK]`,
};

function generateResponse() {
  const context = document.getElementById('response-context').value;
  const text = RESPONSE_TEMPLATES[context] || 'Hi! We noticed you might need some help. Our team is here for you!';
  const textarea = document.getElementById('response-text');
  textarea.value = '';
  let i = 0;
  const interval = setInterval(() => {
    textarea.value += text[i];
    i++;
    if (i >= text.length) clearInterval(interval);
  }, 15);
  showToast('AI message generated — review before sending', 'info');
}

async function sendResponse() {
  const text = document.getElementById('response-text').value;
  if (!text.trim()) { showToast('Please generate a message first', 'error'); return; }
  const channel = document.getElementById('response-channel').value;
  const result = await apiFetch('/interventions/trigger', {
    method: 'POST',
    body: JSON.stringify({
      session_id: document.getElementById('session-id-input').value || 'demo_001',
      intervention_type: 'assisted_response',
      channel,
      message: text,
      approved_by: currentRole,
    }),
  });
  if (!result) {
    showToast('Response failed. Check the API connection and permissions, then retry.', 'error');
    return;
  }
  showToast(`${result.message}. Trigger ID: ${result.trigger_id}`, 'info', 5000);
}

function copyResponse() {
  navigator.clipboard.writeText(document.getElementById('response-text').value).then(() => showToast('Copied to clipboard', 'info'));
}

// ── Team Workspace Views ──────────────────────────────────────────────────────
function showTeamView(team) {
  const el = document.getElementById('team-view-content');
  el.classList.remove('hidden');
  const views = {
    marketing: `<div class="card"><div class="card-title">Marketing Workspace</div><p class="text-sm text-muted mt-4">Top campaigns by recovery ROI, segment conversion rates, A/B test results for recovery messages.</p></div>`,
    product: `<div class="card"><div class="card-title">Product Workspace</div><p class="text-sm text-muted mt-4">Rage click heatmaps, zero-result search queries, product page quality scores, form error rates.</p></div>`,
    cs: `<div class="card"><div class="card-title">Customer Service Workspace</div><p class="text-sm text-muted mt-4">WISMO ticket volume, avg resolution time, top complaint themes, AI-drafted response queue.</p></div>`,
    ops: `<div class="card"><div class="card-title">Operations Workspace</div><p class="text-sm text-muted mt-4">Payment gateway health, delivery SLA compliance, anomaly alerts, infrastructure metrics.</p></div>`,
  };
  el.innerHTML = views[team] || '';
  el.scrollIntoView({ behavior: 'smooth' });
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function formatFrictionType(type) {
  const map = {
    payment_failure:'Payment Failure', delivery_uncertainty:'Delivery Uncertainty',
    unclear_product_info:'Unclear Product Info', poor_recommendations:'Poor Recommendations',
    price_shock:'Price Shock', trust_policy_concern:'Trust/Policy Concern',
    technical_friction:'Technical Friction', post_purchase_anxiety:'Post-Purchase Anxiety',
    poor_search_recommendations:'Poor Search/Recommendations',
  };
  return map[type] || type?.replace(/_/g,' ') || 'Unknown';
}

function formatInterventionType(type) {
  const map = {
    alternate_payment_method:'Alternate Payment Method', smart_payment_retry:'Smart Payment Retry',
    delivery_date_promise:'Delivery Date Promise', targeted_incentive_5pct:'5% Incentive',
    targeted_incentive_10pct:'10% Incentive', targeted_incentive_15pct:'15% Incentive',
    cart_reminder:'Cart Reminder', clarify_product_info:'Clarify Product Info',
    proactive_delay_notification:'Proactive Delay Notification', support_escalation:'Support Escalation',
    recommendation_rerank:'Recommendation Re-rank', trust_nudge_reviews:'Trust Nudge (Reviews)',
  };
  return map[type] || type?.replace(/_/g,' ') || type;
}

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  setupChartDefaults();

  // Navigation
  document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });

  // Sidebar toggle
  document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
    document.getElementById('app-shell').classList.toggle('sidebar-collapsed');
    document.getElementById('sidebar').classList.toggle('open');
  });

  // Theme toggle
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    document.getElementById('theme-icon-dark').classList.toggle('hidden', !isDark);
    document.getElementById('theme-icon-light').classList.toggle('hidden', isDark);
    setupChartDefaults();
  });

  // Role switcher
  document.getElementById('role-switcher')?.addEventListener('change', (e) => {
    currentRole = e.target.value;
    document.getElementById('current-role').innerHTML = `
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="7" r="4"/><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/></svg>
      ${currentRole.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
    `;
    showToast(`Switched to ${currentRole} view`, 'info');
  });

  // Hash router
  const hash = window.location.hash.replace('#', '') || 'overview';
  navigate(hash);
}

document.addEventListener('DOMContentLoaded', init);

// Expose functions to global scope for inline HTML event handlers
window.analyzeSession = analyzeSession;
window.clearAlerts = clearAlerts;
window.loadAuditLog = loadAuditLog;
window.approveIntervention = approveIntervention;
window.editIntervention = editIntervention;
window.rejectIntervention = rejectIntervention;
window.generateResponse = generateResponse;
window.sendResponse = sendResponse;
window.copyResponse = copyResponse;
window.showTeamView = showTeamView;
window.runSimulation = runSimulation;
