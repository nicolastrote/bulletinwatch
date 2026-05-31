"""Tests unitaires pour analyser.py"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from analyser import get_trend, subject_status, THRESHOLD_PASS, THRESHOLD_SAFE


def test_trend_up():
    trend, delta = get_trend([65.0, 70.0])
    assert trend == "up"
    assert delta > 0


def test_trend_down():
    trend, delta = get_trend([75.0, 68.0])
    assert trend == "down"
    assert delta < 0


def test_trend_stable():
    trend, delta = get_trend([72.0, 73.0])
    assert trend == "stable"


def test_trend_insufficient():
    trend, _ = get_trend([72.0])
    assert trend == "insufficient_data"


def test_trend_empty():
    trend, _ = get_trend([])
    assert trend == "insufficient_data"


def test_status_on_track():
    assert subject_status(75.0) == "on_track"
    assert subject_status(70.0) == "on_track"


def test_status_at_risk():
    assert subject_status(65.0) == "at_risk"
    assert subject_status(60.0) == "at_risk"


def test_status_failing():
    assert subject_status(59.9) == "failing"
    assert subject_status(0.0) == "failing"


def test_thresholds():
    assert THRESHOLD_PASS == 60.0
    assert THRESHOLD_SAFE == 70.0
