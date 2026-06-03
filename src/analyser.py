"""
BulletinWatch — Analyste
Lit data/latest.json, calcule moyennes et tendances, écrit data/analysis.json
"""

import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"

THRESHOLD_SAFE = 70.0
THRESHOLD_PASS = 60.0


def recent_grade_changes(limit: int = 10) -> list[dict]:
    files = sorted(glob.glob(str(DATA_DIR / "grades_*.json")))
    timeline = []
    for f in files:
        data = json.loads(Path(f).read_text())
        if data.get("status") != "success":
            continue
        date = Path(f).stem.replace("grades_", "")
        grades = {s["name"]: s["grade"] for s in data.get("subjects", [])}
        timeline.append((date, grades))

    changes = []
    for i in range(1, len(timeline)):
        date, curr = timeline[i]
        _, prev = timeline[i - 1]
        for subject, grade in curr.items():
            prev_grade = prev.get(subject)
            if prev_grade is not None and grade != prev_grade:
                changes.append({
                    "matiere": subject,
                    "grade": grade,
                    "grade_prev": prev_grade,
                    "date": date,
                })

    changes.sort(key=lambda c: c["date"], reverse=True)
    return changes[:limit]


def load_history(subject_name: str) -> list[float]:
    files = sorted(glob.glob(str(DATA_DIR / "grades_*.json")))
    grades = []
    for f in files:
        data = json.loads(Path(f).read_text())
        if data.get("status") != "success":
            continue
        for s in data.get("subjects", []):
            if s["name"] == subject_name:
                grades.append(s["grade"])
    return grades


def get_trend(grades: list[float]) -> tuple[str, float]:
    if len(grades) < 2:
        return "insufficient_data", 0.0
    delta = grades[-1] - grades[-2]
    if delta > 2:
        return "up", round(delta, 1)
    if delta < -2:
        return "down", round(delta, 1)
    return "stable", round(delta, 1)


def subject_status(grade: float) -> str:
    if grade >= THRESHOLD_SAFE:
        return "on_track"
    if grade >= THRESHOLD_PASS:
        return "at_risk"
    return "failing"


def main():
    latest_path = DATA_DIR / "latest.json"
    if not latest_path.exists():
        print("[analyste] ERREUR : data/latest.json introuvable", file=sys.stderr)
        sys.exit(1)

    latest = json.loads(latest_path.read_text())

    if latest.get("status") != "success":
        analysis = {
            "analysed_at": datetime.now(timezone.utc).isoformat(),
            "global_average": 0,
            "session_status": "unknown",
            "alert_level": "scrape_error",
            "subjects": [],
            "subjects_at_risk": [],
            "subjects_failing": [],
            "insight": f"Données indisponibles : {latest.get('error', 'erreur inconnue')}",
            "data_points": 0,
        }
        (DATA_DIR / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
        print("[analyste] Scrape error propagée dans analysis.json")
        return

    subjects_raw = latest.get("subjects", [])
    total_weight = sum(s["weight"] for s in subjects_raw)
    global_avg = (
        sum(s["grade"] * s["weight"] for s in subjects_raw) / total_weight
        if total_weight > 0
        else 0.0
    )

    subjects_out = []
    for s in subjects_raw:
        history = load_history(s["name"])
        trend, delta = get_trend(history)
        status = subject_status(s["grade"])
        subjects_out.append({
            "name": s["name"],
            "grade": s["grade"],
            "status": status,
            "trend": trend,
            "trend_delta": delta,
            "at_risk": s["grade"] < THRESHOLD_SAFE,
            "data_points": len(history),
        })

    at_risk = [s["name"] for s in subjects_out if s["status"] == "at_risk"]
    failing = [s["name"] for s in subjects_out if s["status"] == "failing"]

    if failing:
        alert_level = "critical"
        session_status = "failing"
    elif at_risk:
        alert_level = "warning"
        session_status = "at_risk"
    else:
        alert_level = "ok"
        session_status = "on_track"

    if failing:
        insight = f"{len(failing)} matière(s) en échec : {', '.join(failing)}. Action requise."
    elif at_risk:
        insight = f"{len(at_risk)} matière(s) à surveiller : {', '.join(at_risk)}. Moyenne globale : {global_avg:.1f}%."
    else:
        insight = f"Toutes les matières sont au-dessus du seuil. Moyenne globale : {global_avg:.1f}%."

    analysis = {
        "analysed_at": datetime.now(timezone.utc).isoformat(),
        "global_average": round(global_avg, 1),
        "session_status": session_status,
        "alert_level": alert_level,
        "subjects": subjects_out,
        "subjects_at_risk": at_risk,
        "subjects_failing": failing,
        "insight": insight,
        "data_points": max((s["data_points"] for s in subjects_out), default=0),
        "recent_grade_changes": recent_grade_changes(),
    }

    (DATA_DIR / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    print(f"[analyste] OK — {alert_level.upper()} | moyenne {global_avg:.1f}%")


if __name__ == "__main__":
    main()
