"""
BulletinWatch — Reporter
Lit data/analysis.json et génère docs/index.html pour GitHub Pages
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = Path(__file__).parent.parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)

TREND_ICON = {"up": "↑", "down": "↓", "stable": "→", "insufficient_data": "—"}
STATUS_ICON = {"on_track": "✅", "at_risk": "⚠️", "failing": "❌"}


def grade_color(grade: float) -> str:
    if grade >= 70:
        return "color-green"
    if grade >= 60:
        return "color-orange"
    return "color-red"


def render_etapes_section(subjects_raw: list) -> str:
    if not subjects_raw:
        return ""
    all_seqs = sorted({e["seq"] for s in subjects_raw for e in s.get("etapes_detail", [])})
    if len(all_seqs) <= 1:
        return ""

    header_cells = "".join(f"<th>Étape {seq}</th>" for seq in all_seqs)
    rows = ""
    for s in subjects_raw:
        by_seq = {e["seq"]: e["grade"] for e in s.get("etapes_detail", [])}
        cells = ""
        for seq in all_seqs:
            if seq in by_seq:
                g = by_seq[seq]
                cells += f'<td class="{grade_color(g)}">{g:.1f}%</td>'
            else:
                cells += '<td class="color-muted">—</td>'
        rows += f"<tr><td>{s['name']}</td>{cells}</tr>"

    return f"""
  <div class="card">
    <h2>Progression par étape</h2>
    <table>
      <thead><tr><th>Matière</th>{header_cells}</tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""


def render_recent_grades_section(changes: list) -> str:
    if not changes:
        return ""

    rows = ""
    for c in changes:
        grade = c.get("grade", 0)
        grade_prev = c.get("grade_prev", grade)
        color = grade_color(grade)
        delta = round(grade - grade_prev, 1)
        delta_str = f"({delta:+.1f})" if delta != 0 else ""
        delta_color = "color-green" if delta > 0 else "color-red"
        rows += f"""<tr>
          <td>{c.get("matiere", "")}</td>
          <td class="{color}"><strong>{grade:.1f}%</strong> <span class="{delta_color}" style="font-size:0.8rem">{delta_str}</span></td>
          <td class="color-muted">{c.get("date", "—")}</td>
        </tr>"""

    return f"""
  <div class="card">
    <h2>Dernières notes</h2>
    <table>
      <thead><tr><th>Matière</th><th>Note</th><th>Date</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>"""


def render_html(analysis: dict, subjects_raw: list | None = None) -> str:
    alert_level = analysis.get("alert_level", "ok")
    subjects = analysis.get("subjects", [])
    global_avg = analysis.get("global_average", 0)
    insight = analysis.get("insight", "")
    session_status = analysis.get("session_status", "unknown")
    analysed_at = analysis.get("analysed_at", "")

    try:
        dt = datetime.fromisoformat(analysed_at.replace("Z", "+00:00"))
        updated = dt.strftime("%H:%M le %Y-%m-%d (UTC)")
    except Exception:
        updated = analysed_at

    if alert_level == "scrape_error":
        banner = f'<div class="banner error">🔴 Données indisponibles — {insight}</div>'
        badge_class = "badge-red"
        badge_text = "Erreur"
    elif alert_level == "critical":
        banner = '<div class="banner critical pulse">❌ SESSION EN DANGER — Action requise</div>'
        badge_class = "badge-red"
        badge_text = "Critique"
    elif alert_level == "warning":
        banner = '<div class="banner warning">⚠️ Matière(s) à surveiller</div>'
        badge_class = "badge-orange"
        badge_text = "À surveiller"
    else:
        banner = ""
        badge_class = "badge-green"
        badge_text = "OK"

    rows = ""
    for s in subjects:
        trend = TREND_ICON.get(s.get("trend", ""), "—")
        trend_delta = s.get("trend_delta", 0)
        trend_color = (
            "color-green" if s.get("trend") == "up"
            else "color-red" if s.get("trend") == "down"
            else "color-muted"
        )
        status_icon = STATUS_ICON.get(s.get("status", ""), "")
        grade = s.get("grade", 0)
        grade_color = (
            "color-green" if grade >= 70
            else "color-orange" if grade >= 60
            else "color-red"
        )
        rows += f"""
        <tr>
          <td>{s.get("name", "")}</td>
          <td class="{grade_color}"><strong>{grade:.1f}%</strong></td>
          <td class="{trend_color}">{trend} {f"({trend_delta:+.1f})" if s.get("trend") not in ("insufficient_data",) else ""}</td>
          <td>{status_icon}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="refresh" content="3600">
  <title>BulletinWatch</title>
  <style>
    :root {{
      --bg: #0D1117; --surface: #161B22; --border: #30363D;
      --text: #E6EDF3; --muted: #8B949E;
      --green: #1D9E75; --orange: #E3A03A; --red: #CF222E;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; padding: 1rem; max-width: 800px; margin: 0 auto; }}
    h1 {{ font-size: 1.4rem; margin-bottom: 1rem; }}
    h2 {{ font-size: 1rem; color: var(--muted); margin-bottom: 0.75rem; }}
    .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }}
    .banner {{ border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-weight: 600; }}
    .banner.critical {{ background: #3d0c0e; border: 1px solid var(--red); color: #ff7b7b; }}
    .banner.warning {{ background: #2d1f07; border: 1px solid var(--orange); color: #f5c97a; }}
    .banner.error {{ background: #3d0c0e; border: 1px solid var(--red); color: #ff7b7b; }}
    @keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:.6 }} }}
    .pulse {{ animation: pulse 2s infinite; }}
    .badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }}
    .badge-green {{ background: #0f3d2e; color: var(--green); }}
    .badge-orange {{ background: #2d1f07; color: var(--orange); }}
    .badge-red {{ background: #3d0c0e; color: var(--red); }}
    .summary {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 0.5rem; }}
    .stat {{ font-size: 2rem; font-weight: 700; }}
    .stat-label {{ font-size: 0.8rem; color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; padding: 0.5rem 0.75rem; color: var(--muted); font-size: 0.8rem; border-bottom: 1px solid var(--border); }}
    td {{ padding: 0.6rem 0.75rem; border-bottom: 1px solid var(--border); }}
    tr:last-child td {{ border-bottom: none; }}
    .color-green {{ color: var(--green); }}
    .color-orange {{ color: var(--orange); }}
    .color-red {{ color: var(--red); }}
    .color-muted {{ color: var(--muted); }}
    footer {{ color: var(--muted); font-size: 0.75rem; text-align: center; margin-top: 1.5rem; }}
    @media (max-width: 480px) {{ .stat {{ font-size: 1.5rem; }} }}
  </style>
</head>
<body>
  <h1>📊 BulletinWatch</h1>
  {banner}
  <div class="card">
    <div class="summary">
      <div>
        <div class="stat">{global_avg:.1f}%</div>
        <div class="stat-label">Moyenne globale</div>
      </div>
      <div>
        <div style="margin-top:0.4rem"><span class="badge {badge_class}">{badge_text}</span></div>
        <div class="stat-label" style="margin-top:0.4rem">Session</div>
      </div>
    </div>
    <p style="color:var(--muted); font-size:0.9rem; margin-top:0.75rem">{insight}</p>
  </div>
  <div class="card">
    <h2>Notes par matière</h2>
    <table>
      <thead><tr><th>Matière</th><th>Note</th><th>Tendance</th><th>Statut</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  {render_etapes_section(subjects_raw or [])}
  {render_recent_grades_section(analysis.get("recent_grade_changes", []))}
  <footer>Dernière mise à jour : {updated} &nbsp;·&nbsp; Rafraîchissement auto toutes les heures</footer>
</body>
</html>"""


def main():
    analysis_path = DATA_DIR / "analysis.json"
    if not analysis_path.exists():
        print("[reporter] ERREUR : data/analysis.json introuvable", file=sys.stderr)
        sys.exit(1)

    analysis = json.loads(analysis_path.read_text())

    subjects_raw = []
    latest_path = DATA_DIR / "latest.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text())
        if latest.get("status") == "success":
            subjects_raw = latest.get("subjects", [])

    html = render_html(analysis, subjects_raw)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[reporter] OK — docs/index.html généré ({len(html)} chars)")


if __name__ == "__main__":
    main()
