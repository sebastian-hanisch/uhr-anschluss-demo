"""Layout (DEMO-PLAYBOOK §2): fester Kopf, Schnellstart oben in der Seitenleiste, aktives Preset hervorgehoben.

Die Hervorhebung ist zustandslos (`aktives_preset` vergleicht jeden Regler aus SETTING_SPECS mit dem Preset). Die Netz-Regler stehen in der Seitenleiste, die zwei Regler des
Zifferblatts (Schritt 1) neben ihrem Diagramm im Hauptbereich; beide Gruppen stehen in SETTING_SPECS, jede Änderung hebt die Markierung auf."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import uan_constants as C
import uan_presets as P

APP = str(Path(__file__).resolve().parent.parent / "app.py")
REGLER_ARTEN = ("slider", "number_input", "select_slider", "selectbox", "radio", "toggle", "checkbox", "text_input")
SIDEBAR_KEYS = {"lines", "seed", "dwell", "mt", "forest"}
MAIN_KEYS = {"arr", "shift"}


def _app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _typen(at) -> dict:
    return {b.label: b.proto.type for b in at.sidebar.button if b.label in C.PRESETS}


def _regler(at, key):
    for bereich in (at.sidebar, at.main):
        for art in REGLER_ARTEN:
            try:
                return getattr(bereich, art)(key=key)
            except KeyError:
                continue
    raise AssertionError(f"Regler {key} nicht gefunden")


def test_presets_stehen_in_der_seitenleiste_und_nicht_im_hauptbereich():
    at = _app()
    assert [b.label for b in at.sidebar.button][: len(C.PRESETS)] == list(C.PRESETS)
    assert not [b for b in at.main.button if b.label in C.PRESETS]


def test_titel_steht_im_festen_kopf():
    at = _app()
    assert "st-key-kopf" in " ".join(h.proto.body for h in at.get("html"))
    assert at.title[0].value


def test_beim_start_ist_genau_das_standard_preset_hervorgehoben():
    typen = _typen(_app())
    assert [name for name, typ in typen.items() if typ == "primary"] == [next(iter(C.PRESETS))]


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_angeklicktes_preset_ist_hervorgehoben_und_bleibt_es_im_naechsten_lauf(name):
    at = _app()
    at.sidebar.button(key=f"preset_{name}").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    assert [n for n, typ in _typen(at).items() if typ == "primary"] == [name]
    at.run()
    assert [n for n, typ in _typen(at).items() if typ == "primary"] == [name]


def test_jeder_regler_steht_in_setting_specs_und_im_erwarteten_bereich():
    at = _app()
    seite = {w.key for art in REGLER_ARTEN for w in getattr(at.sidebar, art) if w.key}
    haupt = {w.key for art in REGLER_ARTEN for w in getattr(at.main, art) if w.key}
    assert seite == SIDEBAR_KEYS
    assert MAIN_KEYS <= haupt and haupt - MAIN_KEYS <= {"pair_sel", "pair_idx"}          # die zwei Auswahlfelder der Schritte 2 sind Ansicht, keine Szenario-Regler
    assert (seite | MAIN_KEYS) == set(P.SETTING_SPECS)


@pytest.mark.parametrize("state_key", list(P.SETTING_SPECS))
def test_jede_aenderung_eines_reglers_hebt_die_hervorhebung_auf(state_key):
    at = _app()
    spec = P.SETTING_SPECS[state_key]
    regler = _regler(at, state_key)
    if isinstance(spec.default, bool):
        regler.set_value(not regler.value)
    elif spec.choices is not None:
        regler.set_value(next(c for c in spec.choices if c != regler.value))
    else:
        regler.set_value(spec.hi if regler.value != spec.hi else spec.lo)
    regler.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert "primary" not in _typen(at).values()
    name = next(iter(C.PRESETS))
    at.sidebar.button(key=f"preset_{name}").click().run()
    assert _typen(at)[name] == "primary"
