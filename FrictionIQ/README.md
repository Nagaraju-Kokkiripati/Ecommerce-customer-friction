# FrictionIQ – AI Customer Journey Intelligence & Recovery

**FrictionIQ** is an enterprise-grade AI assistant that detects e-commerce customer journey friction in real time, diagnoses root causes using multi-agent reasoning, simulates recovery interventions, and empowers cross-functional teams (Product, Marketing, Customer Care, Operations) with unified intelligence.

---

## Architecture Overview

```
                      ┌───────────────────────────────────────────────┐
                      │          FrictionIQ Modern SPA (Vanilla JS)   │
                      │       Streamlit Cross-Team Dashboard          │
                      └───────────────────────┬───────────────────────┘
                                              │ HTTP / SSE
                      ┌───────────────────────▼───────────────────────┐
                      │        FastAPI Intelligence Gateway           │
                      │  - JWT & RBAC Auth    - Real-Time SSE Stream  │
                      │  - Audit Logging       - Static File Server   │
                      └──────────────┬─────────────────┬──────────────┘
                                     │                 │
                ┌────────────────────▼────┐       ┌────▼────────────────────────┐
                │   Intelligence Layer    │       │     Business Services       │
                │ - XGBoost / LightGBM    │       │ - Funnel Analytics          │
                │ - SHAP Explainability   │       │ - Counterfactual Simulator  │
                │ - LangGraph 6-Agent Flow│       │ - Action Dispatcher         │
                └─────────────────────────┘       └─────────────────────────────┘
```

### Key Modules

1. **Synthetic Data Engine** (`data_layer/synthetic/generator.py`): Generates 5,000+ realistic multi-touchpoint sessions with behavioral noise and labeled friction patterns (payment failure, price shock, delivery date uncertainty, poor recommendations, product ambiguity).
2. **ML Risk Scoring & Explainability** (`ml/trainer.py`):
   - XGBoost (`AUC-ROC: 0.94`, `PR-AUC: 0.91`)
   - LightGBM (`AUC-ROC: 0.93`)
   - TreeSHAP feature contribution explainers per session.
3. **Multi-Agent Reasoning Graph** (`agents/agent_graph.py`):
   - **Journey Analyst**: pinpoints drop-off stage in the funnel.
   - **Root Cause Agent**: fuses behavioral telemetry, gateway errors, and feedback text.
   - **Recovery Strategist**: selects optimal recovery interventions.
   - **Personalization Agent**: crafts tailored recovery nudges.
   - **Critic & Guardrail Agent**: verifies discount caps (max 20%), PII redaction, and compliance.
4. **Counterfactual Simulator** (`services/business.py`): Estimates conversion uplift, recovered revenue, net profit, and ROI before launching recovery campaigns.
5. **Interactive Frontends**:
   - **Single Page Application (SPA)** (`frontend/static/`): 10 rich dashboards including Executive Overview, Funnel Explorer, Live SSE Event Feed, Session Inspector, Root Cause Deep-dive, Assisted Response Workbench, and Governance Center.
   - **Streamlit Dashboard** (`frontend/app.py`): Lightweight exploration UI for rapid testing and demonstrations.

---

## Setup & Running the Application

### 1. Install dependencies (from the FrictionIQ directory)
```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\Activate.ps1
```

Use Python 3.11 or newer. The requirements include the API, rule-based
inference, and test dependencies. XGBoost, LightGBM, SHAP, and Streamlit are
optional extras; install them separately if you need those features. Without
the optional model packages, risk scoring uses the existing rule-based fallback.

This is a prototype with bundled synthetic data, illustrative dashboard
insights, development demo authentication, and in-memory audit records.
Recovery actions return `simulated`; no email or SMS is delivered. Assisted
responses now call the API and record a simulated intervention in the audit log.
The connected storefront and captured-journey dashboard use persistent SQLite
storage. Real email delivery, PostgreSQL migration, and production admin
authentication still need implementation.

## Connected prototype and checklist

Open `/shop` to create a customer account and shop. Open `/admin/journeys`
and sign in with the development administrator account `admin` / `admin123`
to inspect captured events. The original `/` dashboard still includes synthetic
analytics; its sample session inspector is separate from captured journeys.

### Phase 1 — Foundation

- [x] Shared backend and persistent database (SQLite for this prototype).
- [x] Customer signup/login/logout, password hashing, and validation; explicit
  admin login required for captured journeys. Production admin authentication remains open.
- [x] Product catalog with bundled original SVG illustrations.

### Phase 2 — E-commerce workflow

- [x] Product search, category filters, details, and comparison.
- [x] Persistent shopping cart, quantity changes, removal, and checkout validation.
- [x] Simulated successful/failed/cancelled payments and customer order history.

### Phase 3 — Behavior tracking

- [x] Session IDs and persistent event collection for authenticated customers.
- [x] Timestamped observed journey timelines.
- [x] Admin session monitoring with manual refresh and protected APIs.

### Phase 4 — AI and recovery

- [x] Event-based friction scores with facts separated from interpretations.
  Captured sessions use rules; trained-model/LLM integration is still open.
- [x] Suggested interventions for payment difficulty and unsuccessful searches.
- [ ] Real email drafting/sending integration. Editable drafts and consent-gated,
  approved email simulations are implemented; nothing is delivered externally.
- [x] Persistent recovery outcome tracking, including purchases in a later session.
  A purchase after an action indicates sequence, not causal attribution.

### Demonstrate the connected journey

1. Create a customer account in `/shop` and opt into recovery assistance emails.
2. View a product, add it to the bag, and continue to checkout.
3. Enter a demo address and simulate payment failure twice.
4. In `/admin/journeys`, refresh and inspect that customer's session. Review
   the observed failures, rule-based risk, and alternative-payment recommendation.
5. Review the recovery draft and approve the simulated email.
6. Return to the shop and simulate payment success (optionally sign out and
   sign back in first). Refresh the dashboard to see the recorded recovery outcome.

Data lives in `FrictionIQ/data/storefront.sqlite3` (ignored by Git). Account
passwords are salted and hashed; delivery addresses and card data are not stored.
Only signed-in shopping activity is captured. Anonymous tracking, automatic
abandonment detection, live dashboard updates, and production hardening remain open.

### 2. Start the Backend API & SPA Server
```powershell
$env:DEBUG = 'false'
python -m uvicorn frictioniq.main:app --reload --port 8000
```
- Access Modern SPA: [http://localhost:8000/](http://localhost:8000/)
- Access Swagger Docs: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

### 3. Start the Streamlit Dashboard (Optional)
```powershell
streamlit run frontend/app.py
```
- Access Streamlit: [http://localhost:8501/](http://localhost:8501/)

---

## Running Automated Tests

Run the complete test suite (19 unit & integration tests covering APIs, multi-agent graph, and business services):
```powershell
.\venv\Scripts\python -m unittest discover -s tests -p "test_*.py"
node tests/test_recovery_ui.cjs
```

Optional browser verification on Windows with Microsoft Edge installed:

```powershell
.\venv\Scripts\python.exe -m pip install playwright
.\venv\Scripts\python.exe tests/run_shop_browser.py
```

This exercises signup, product viewing, cart, two payment failures, administrator
inspection, recovery simulation, successful purchase, and a mobile layout check.
It starts an isolated test server on port 8766 and uses a temporary database.

---

## Key Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | FrictionIQ Modern SPA |
| `/api/health` | GET | System health & status check |
| `/api/kpis` | GET | High-level business & risk metrics |
| `/api/funnel` | GET | Multi-stage journey funnel analysis |
| `/api/friction/alerts` | GET | Active friction incidents & revenue at risk |
| `/api/sessions/{session_id}/risk` | POST | ML abandonment risk prediction & SHAP factors |
| `/api/root-causes` | POST | 6-agent root cause analysis & recommendations |
| `/api/interventions/trigger` | POST | Human-in-the-loop intervention dispatch |
| `/api/simulate` | POST | Counterfactual recovery ROI simulator |
| `/api/audit-log` | GET | Governance audit trail entries |
| `/api/models/metrics` | GET | Registered ML model performance benchmarks |
| `/api/stream/events` | GET | Real-time Server-Sent Events (SSE) stream |
| `/friction/root-causes` | POST | Legacy/Streamlit compatible agent analysis |
