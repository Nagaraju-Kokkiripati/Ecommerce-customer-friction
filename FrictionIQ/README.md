# FrictionIQ — Connected customer journey detection and recovery

A working research storefront and administrator dashboard sharing FastAPI and
persistent SQLite storage. Analytics use recorded shop activity exclusively.
The bundled synthetic session datasets, fabricated analytics, and random alerts
have been removed. Existing customer accounts and captured sessions are preserved.

## Run locally

From the repository's `FrictionIQ` directory:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DEBUG = 'false'
.\venv\Scripts\python.exe -m uvicorn frictioniq.main:app --reload --port 8000
```

Python 3.14 is verified locally. Use the virtual environment's Python directly;
activation is optional. On an existing installation, run the pip command again
to install the new XGBoost dependency.

| Page | Address |
|---|---|
| Unified dashboard | http://localhost:8000/ |
| Customer storefront | http://localhost:8000/shop |
| Dashboard alias | http://localhost:8000/admin/journeys |
| API documentation | http://localhost:8000/api/docs |

Development admin: `admin` / `admin123`. Create customer accounts in the shop.
The shop has six sample products with original bundled SVG illustrations.
Payments and orders are simulated; no card data is collected.

## Model

The active bundled model is **XGBoost v1**, loaded from
`models/registry/xgboost_v1.joblib`. It predicts from features extracted from
recorded events and shows native TreeSHAP feature contributions. It was trained
on synthetic sessions and is **not validated on real customers**. Synthetic
training files and unsupported accuracy claims were removed; the pretrained
artifact is retained and its provenance is displayed.

Observed-event rules separately explain payment failures, unsuccessful searches,
and possible abandonment. These facts are distinct from model predictions.
No LLM is active. Missing predictors use zero, and missing model dependencies
produce an explicit unavailable state, never a fabricated score.

## Checklist

### Foundation

- [x] Shared persistent backend/database (SQLite).
- [x] Customer signup/login/logout, email validation, salted password hashes,
  ownership checks, and revoked shopping sessions on logout.
- [x] Protected admin APIs, configurable admin password hash, login attempt
  throttling, security headers, and cross-origin action checks.
- [x] Product catalog and bundled illustrations.

### E-commerce workflow

- [x] Search, category filters, details, and comparison.
- [x] Guest and customer carts, quantities, removal, and validated checkout.
- [x] Simulated successful/failed/cancelled payments and order history.

### Tracking and intelligence

- [x] Anonymous and authenticated sessions with persistent event collection.
- [x] Guest cart/session adoption when a customer signs in or registers.
- [x] Timestamped timelines, recorded KPIs, observed funnel, automatic refresh.
- [x] Possible abandonment after configurable inactivity (default 30 minutes)
  with a nonempty recorded cart. Inactivity is an inference, not proof of intent.
- [x] XGBoost inference, feature contributions, and evidence-based recommendations.
- [x] Retraining workflow for collected outcomes with leakage checks and held-out
  customer groups. Training refuses to invent rows when data is insufficient.

### Recovery and deployment

- [x] Editable drafts, customer consent, admin approval, persistent action history.
- [x] SMTP submission with persisted failure/acceptance status.
- [x] Purchases after successful/simulated actions tracked across customer sessions.
- [x] Container packaging and environment configuration.
- [ ] Configure an email provider and verify real submission/inbox delivery.
- [ ] Choose a hosting target and deploy with HTTPS and persistent storage.
- [ ] Collect sufficient mature outcomes, train a candidate, and evaluate live accuracy.

SQLite is suitable for this single-instance prototype. Multi-instance hosting
needs a shared database and shared rate limiting. PostgreSQL migration is not
implemented. Password reset, unsubscribe management for production mail,
provider delivery webhooks, and broader production operations need further work.

## Demonstration

1. Browse anonymously, view a product, and add it to the bag.
2. Register at checkout; opt into recovery assistance email if desired.
3. Enter a demo address and simulate payment failure twice.
4. Sign in to the dashboard and inspect that session. Review observed facts,
   rule explanations, and the separate XGBoost prediction.
5. Edit and approve a recovery draft. Without SMTP configuration it is simulated.
6. Simulate successful checkout, then inspect the recorded purchase after action.

Dashboard updates every five seconds without overwriting edited drafts. Revenue
is from simulated orders; purchases after actions do not establish causation.
The dashboard is empty until shopping activity is recorded.

## Real email configuration

Copy `.env.example` to `.env`, then configure locally:

```dotenv
EMAIL_MODE=smtp
SMTP_HOST=your-provider-host
SMTP_PORT=587
SMTP_USERNAME=your-provider-username
SMTP_PASSWORD=your-provider-password
SMTP_FROM=your-verified-sender@example.com
```

Restart the API. Admin approval then submits real email to the opted-in customer's
registered address. STARTTLS is required. Status `accepted` means the SMTP server
accepted the message; it does not confirm inbox delivery. `failed` records a
submission failure. A crash during submission can leave `sending`; verify with
the provider before retrying. Tests mock SMTP and never send external mail.

## Retrain from collected outcomes

```powershell
$env:DEBUG = 'false'
.\venv\Scripts\python.exe -m ml.train_captured
# Review the candidate's held-out metrics before activating:
.\venv\Scripts\python.exe -m ml.train_captured --activate
```

Training requires at least 100 sessions older than a day and at least 20 of each
outcome. Conversion and mature cart inactivity are proxy labels, not confirmed
intentions. Terminal payment/order events and inactivity-derived exit flags are
excluded from predictors. Customer groups are disjoint between training and
holdout; newest first-seen groups are held out. Metrics are measured on the
holdout and not presented as live production accuracy.

The candidate is saved to `data/model_candidate.joblib`; activation saves
`data/model_live.joblib`. Restart the API to use it. Both are ignored by Git.
Back up activated models and the SQLite database along with deployment storage.

## Deployment preparation

Outside development, configure `ENV=production`, a random `SECRET_KEY` of at least
32 characters, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH`. The application refuses
to start without the key and hash. Generate values locally:

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
.\venv\Scripts\python.exe -c "from getpass import getpass; from api.shop import password_hash; print(password_hash(getpass('Admin password: ')))"
```

Generate the password hash while `ENV` is still `development`, then set production
configuration. Production shopping cookies require HTTPS. Configure
`ALLOWED_ORIGINS` to the actual HTTPS origin. Keep `.env` out of Git.

For a local **development** container:

```powershell
docker build -t frictioniq .
docker run --rm -p 8000:8000 --env-file .env -v frictioniq-data:/app/persist frictioniq
```

For production, use HTTPS termination, provider-managed secrets, a durable volume
at `/app/persist`, backups, and a single application instance. The Dockerfile is
provided; the local Docker daemon was unavailable, so its build is unverified.
No hosted deployment or real email submission has been performed.

## Verification

```powershell
$env:DEBUG = 'false'
.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node --check frontend/static/js/shop.js
node --check frontend/static/js/journeys.js
# Optional browser check with Microsoft Edge installed:
.\venv\Scripts\python.exe -m pip install playwright
.\venv\Scripts\python.exe tests/run_shop_browser.py
```

Tests use temporary SQLite databases. They cover empty analytics, actual event
totals, auth/ownership, guest linking, inactivity, XGBoost inference, SMTP failure
and acceptance, recovery outcomes, and exclusion of terminal outcomes from model
features. The browser check covers the complete shopping/recovery journey and a
mobile overflow check.
