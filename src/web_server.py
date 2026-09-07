"""
BulletinWatch — Web Server
Expose latest grades via FastAPI
"""

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="BulletinWatch")
DATA_DIR = Path(__file__).parent.parent / "data"


@app.get("/api/latest")
async def get_latest():
    """Retourne les dernières notes"""
    latest_file = DATA_DIR / "latest.json"
    if not latest_file.exists():
        raise HTTPException(status_code=404, detail="Pas de données disponibles")

    data = json.loads(latest_file.read_text())
    return data


@app.get("/")
async def root():
    """Page d'accueil"""
    return {
        "status": "ok",
        "message": "BulletinWatch — Suivi des notes scolaires",
        "endpoints": {
            "latest_grades": "/api/latest",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check pour Uptime Kuma"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7000)
