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

### 1. Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### 2. Start the Backend API & SPA Server
```powershell
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
```

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
