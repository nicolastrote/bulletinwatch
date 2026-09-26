"""Tests unitaires : notes individuelles par matière (scraper.parse_notes_by_code / parse_subjects)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from scraper import parse_notes_by_code, parse_subjects


def travail(code, label, valeur, maximum, date, etape="1", matiere="Science/technologie"):
    return {
        "codeMatiere": code,
        "codeEtape": etape,
        "descriptionMatiere": matiere,
        "descriptionTravail": label,
        "dateTravail": date,
        "resultat": {"valeur": valeur, "noteMaximale": maximum},
    }


def test_notes_grouped_by_code_and_sorted_newest_first():
    travaux = [
        travail("055306", "Labo", "27", 40, "2026-09-11"),
        travail("085304", "Examen histoire", "6", 25, "2026-09-08"),
        travail("055306", "Examen chapitre 1", "37", 60, "2026-09-15"),
    ]
    notes = parse_notes_by_code(travaux)
    assert set(notes) == {"055306", "085304"}
    assert [n["label"] for n in notes["055306"]] == ["Examen chapitre 1", "Labo"]
    assert notes["055306"][0] == {
        "label": "Examen chapitre 1",
        "points": 37.0,
        "max": 60.0,
        "grade": 61.7,
        "date": "2026-09-15",
    }
    assert notes["085304"][0]["grade"] == 24.0


def test_note_without_value_is_skipped():
    travaux = [
        travail("055306", "Pas encore corrigé", None, 60, "2026-09-20"),
        travail("055306", "Corrigé", "30", 50, "2026-09-10"),
    ]
    notes = parse_notes_by_code(travaux)
    assert [n["label"] for n in notes["055306"]] == ["Corrigé"]


def test_non_numeric_value_is_skipped():
    travaux = [travail("055306", "Cote", "A+", 60, "2026-09-20")]
    assert parse_notes_by_code(travaux) == {}


def test_comma_decimal_is_accepted():
    notes = parse_notes_by_code([travail("055306", "Quiz", "7,5", 10, "2026-09-12")])
    assert notes["055306"][0]["points"] == 7.5
    assert notes["055306"][0]["grade"] == 75.0


def test_missing_maximum_defaults_to_100():
    notes = parse_notes_by_code([travail("055306", "Quiz", "82", None, "2026-09-12")])
    assert notes["055306"][0]["max"] == 100.0
    assert notes["055306"][0]["grade"] == 82.0


def test_travail_without_code_or_result_is_ignored():
    travaux = [
        {"descriptionTravail": "Sans code", "resultat": {"valeur": "5", "noteMaximale": 10}},
        {"codeMatiere": "055306", "descriptionTravail": "Sans résultat"},
        {"codeMatiere": "055306", "descriptionTravail": "Résultat nul", "resultat": None},
    ]
    assert parse_notes_by_code(travaux) == {}


def test_empty_input():
    assert parse_notes_by_code([]) == {}


def test_parse_subjects_attaches_notes_to_the_right_subject():
    travaux = [
        travail("055306", "Examen chapitre 1", "37", 60, "2026-09-15"),
        travail("055306", "Labo", "27", 40, "2026-09-11"),
        travail("085304", "Examen histoire", "6", 25, "2026-09-08", matiere="Histoire"),
    ]
    matieres_meta = [
        {"codeMatiere": "055306", "descriptionMatiere": "Science et technologie", "nombreUnites": 6},
        {"codeMatiere": "085304", "descriptionMatiere": "Histoire du Québec et du Canada", "nombreUnites": 4},
        {"codeMatiere": "132308", "descriptionMatiere": "Mathématique", "nombreUnites": 8},
    ]
    units = {m["codeMatiere"]: m["nombreUnites"] for m in matieres_meta}

    subjects = parse_subjects([], units, travaux, matieres_meta)
    by_name = {s["name"]: s for s in subjects}

    assert set(by_name) == {"Science et technologie", "Histoire du Québec et du Canada"}
    science = by_name["Science et technologie"]
    assert science["grade"] == 64.0
    assert [n["label"] for n in science["notes"]] == ["Examen chapitre 1", "Labo"]
    assert [n["points"] for n in by_name["Histoire du Québec et du Canada"]["notes"]] == [6.0]
