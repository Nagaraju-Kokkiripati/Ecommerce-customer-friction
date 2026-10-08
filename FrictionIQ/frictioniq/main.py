"""
FrictionIQ – Main entrypoint bridging both legacy and comprehensive APIs.
Serves full SPA frontend, REST endpoints, SSE stream, and legacy demo routes.
"""
from __future__ import annotations

import uvicorn
from api.main import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("frictioniq.main:app", host="0.0.0.0", port=8000, reload=True)
