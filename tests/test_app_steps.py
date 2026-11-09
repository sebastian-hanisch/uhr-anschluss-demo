"""AppTest über die Smoke-Prüfungen hinaus: jede Auswahl, jeder ▶️-Knopf einzeln (der Smoke-Test lässt ▶️ aus), Permalink, PDF, Auswahl nach Netzwechsel."""

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import uan_constants as C
import uan_evaluation as E
from uan_pdf_export import generate_report_pdf

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT = int(os.environ.get("APPTEST_TIMEOUT", "300"))


def _app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _ok(at):
    assert not at.exception, [str(e) for e in at.exception]


@pytest.mark.parametrize("lines", C.LINES_OPTIONS)
def test_every_line_count(lines):
    at = _app()
    at.sidebar.select_slider(key="lines").set_value(lines).run(timeout=TIMEOUT)
    _ok(at)


@pytest.mark.parametrize("seed", [C.SEED_MIN, C.SEED_MAX])
def test_seed_extremes(seed):
    at = _app()
    at.sidebar.number_input(key="seed").set_value(seed).run(timeout=TIMEOUT)
    _ok(at)


def test_forest_toggle_shows_the_construction():
    at = _app()
    assert not [s for s in at.success if "Konstruktion statt Suche" in s.value]
    at.sidebar.toggle(key="forest").set_value(True).run(timeout=TIMEOUT)
    _ok(at)
    assert [s for s in at.success if "Konstruktion statt Suche" in s.value]
    assert [m for m in at.metric if m.label == "Kreisrang"][0].value == "0"


def test_every_line_pair_and_every_connection_can_be_selected():
    at = _app()
    pair_options = list(at.selectbox(key="pair_sel").options)
    assert len(pair_options) >= 2
    for option in pair_options:
        at.selectbox(key="pair_sel").set_value(option).run(timeout=TIMEOUT)
        _ok(at)
        for sub in list(at.selectbox(key="pair_idx").options):
            at.selectbox(key="pair_idx").set_value(sub).run(timeout=TIMEOUT)
            _ok(at)


def test_changing_the_net_after_a_selection_does_not_leave_a_stale_selection():
    at = _app()
    last = list(at.selectbox(key="pair_sel").options)[-1]
    at.selectbox(key="pair_sel").set_value(last).run(timeout=TIMEOUT)
    _ok(at)
    at.sidebar.select_slider(key="lines").set_value(10).run(timeout=TIMEOUT)
    _ok(at)
    at.sidebar.number_input(key="seed").set_value(1234).run(timeout=TIMEOUT)
    _ok(at)
    assert at.selectbox(key="pair_sel").value in at.selectbox(key="pair_sel").options


def test_exact_button_proves_or_reports_not_proven():
    at = _app()
    at.button(key="exact_button").click().run(timeout=TIMEOUT)
    _ok(at)
    texts = [x.value for x in list(at.success) + list(at.info) + list(at.warning)]
    assert any(("beweist das Optimum" in t) or ("Nicht bewiesen" in t) for t in texts), texts


def test_exact_button_on_a_forest_agrees_with_the_construction():
    at = _app()
    at.sidebar.toggle(key="forest").set_value(True).run(timeout=TIMEOUT)
    at.button(key="exact_button").click().run(timeout=TIMEOUT)
    _ok(at)
    assert any("beweist das Optimum" in s.value and "gefunden" in s.value for s in at.success)


def test_exact_result_is_dropped_when_the_settings_change():
    at = _app()
    at.button(key="exact_button").click().run(timeout=TIMEOUT)
    assert any("Optimum" in x.value for x in list(at.success) + list(at.info) + list(at.warning) if "CP-SAT" in x.value)
    at.sidebar.slider(key="dwell").set_value(4).run(timeout=TIMEOUT)
    _ok(at)
    assert not any("CP-SAT" in x.value and ("beweist" in x.value or "Nicht bewiesen" in x.value) for x in list(at.success) + list(at.info) + list(at.warning))


def test_permalink_is_clamped_and_snapped():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.query_params["lines"] = "4"
    at.query_params["dwell"] = "99"
    at.query_params["arr"] = "-5"
    at.query_params["forest"] = "1"
    at.run()
    _ok(at)
    assert at.sidebar.select_slider(key="lines").value == 3 and at.sidebar.slider(key="dwell").value == C.DWELL_MAX
    assert at.slider(key="arr").value == C.ARR_MIN and at.sidebar.toggle(key="forest").value is True


def test_the_five_experiments_the_limits_and_the_formulas_are_on_the_page():
    at = _app()
    subs = [s.value for s in at.subheader]
    assert [s for s in subs if s.startswith("🔬 Experiment")] == [
        "🔬 Experiment 1: Die Kopplung an 600 Netzen, gegen die Fahrplantafel geprüft", "🔬 Experiment 2: Drei Untergrenzen nach Linienzahl",
        "🔬 Experiment 3: Wald gegen Kreise", "🔬 Experiment 4: Haltezeit als Regler", "🔬 Experiment 5: Brücke zur Wende-Standzeit"]
    assert "🚧 Wo die Annahmen enden" in subs
    labels = [e.label for e in at.expander]
    assert "📐 Mathematische Formulierung" in labels and "So funktioniert der Takt-Anschluss" in labels and "💬 In einfachen Worten" in labels
    body = "\n".join(m.value for m in next(e for e in at.expander if e.label == "📐 Mathematische Formulierung").markdown)
    assert body.count("**Lesehilfe.**") == 1 and body.count("| Symbol | Bedeutung |") == 1
    assert body.count("$$") % 2 == 0 and body.count("$$") >= 14


def test_pdf_report_is_a_pdf():
    a = E.analyse(E.Settings())
    data = generate_report_pdf(a, a.opt_offsets)
    assert data[:5] == b"%PDF-" and len(data) > 1500
