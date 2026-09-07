"""
BulletinWatch — Web Server
Expose latest grades via FastAPI + HTML frontend
"""

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

app = FastAPI(title="BulletinWatch")
DATA_DIR = Path(__file__).parent.parent / "data"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BulletinWatch — Notes</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 100%;
            padding: 40px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .grades {
            margin-top: 20px;
        }
        
        .grade-item {
            border-left: 4px solid #667eea;
            padding: 16px;
            margin-bottom: 12px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        
        .grade-subject {
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
        }
        
        .grade-value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        
        .status-pending {
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 16px;
        }
        
        .status-error {
            text-align: center;
            padding: 40px;
            color: #e74c3c;
            font-size: 16px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #667eea;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 BulletinWatch</h1>
        <div class="subtitle">Suivi des notes scolaires</div>
        <div id="content" class="loading">
            <div class="spinner"></div>
            Chargement des notes...
        </div>
    </div>
    
    <script>
        async function loadGrades() {
            try {
                const response = await fetch('/api/latest');
                const data = await response.json();
                
                const content = document.getElementById('content');
                
                if (data.status === 'pending') {
                    content.innerHTML = '<div class="status-pending">⏳ Notes pas encore disponibles (en attente de publication)</div>';
                    return;
                }
                
                if (data.status === 'error') {
                    content.innerHTML = '<div class="status-error">❌ ' + data.error + '</div>';
                    return;
                }
                
                if (!data.matieres || data.matieres.length === 0) {
                    content.innerHTML = '<div class="status-pending">Pas de données disponibles</div>';
                    return;
                }
                
                let html = '<div class="grades">';
                data.matieres.forEach(m => {
                    html += `
                        <div class="grade-item">
                            <div class="grade-subject">${m.nom}</div>
                            <div class="grade-value">${m.pourcentage}%</div>
                        </div>
                    `;
                });
                html += '</div>';
                
                content.innerHTML = html;
            } catch (error) {
                document.getElementById('content').innerHTML = '<div class="status-error">Erreur: ' + error.message + '</div>';
                console.error(error);
            }
        }
        
        loadGrades();
        setInterval(loadGrades, 5 * 60 * 1000);
    </script>
</body>
</html>
"""

@app.get("/")
async def root():
    """Page d'accueil avec interface"""
    return HTMLResponse(content=HTML_TEMPLATE)

@app.get("/api/latest")
async def get_latest():
    """Retourne les dernières notes"""
    latest_file = DATA_DIR / "latest.json"
    if not latest_file.exists():
        raise HTTPException(status_code=404, detail="Pas de données disponibles")

    data = json.loads(latest_file.read_text(encoding='utf-8'))
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(content=json_str, media_type="application/json")

@app.get("/health")
async def health():
    """Health check pour Uptime Kuma"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000)
