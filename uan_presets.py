"""Permalink (Begrenzen, Einrasten), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import random
from dataclasses import dataclass

import streamlit as st

import uan_constants as C


def _to_bool(text) -> bool:
    return str(text).strip().lower() in ("1", "true", "ja", "yes")


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: object
    default: object
    lo: float | None = None
    hi: float | None = None
    choices: tuple | None = None      # erlaubte Werte (Auswahlregler): ein Permalink rastet auf den nächsten erlaubten Wert ein


SETTING_SPECS = {
    "lines": SettingSpec("lines", int, C.DEFAULT_LINES, min(C.LINES_OPTIONS), max(C.LINES_OPTIONS), C.LINES_OPTIONS),
    "seed": SettingSpec("seed", int, C.DEFAULT_SEED, C.SEED_MIN, C.SEED_MAX),
    "dwell": SettingSpec("dwell", int, C.DEFAULT_DWELL, C.DWELL_MIN, C.DWELL_MAX),
    "mt": SettingSpec("mt", int, C.DEFAULT_TRANSFER_MIN, C.MT_MIN, C.MT_MAX),
    "forest": SettingSpec("forest", _to_bool, False),
    "arr": SettingSpec("arr", int, C.DEFAULT_ARR, C.ARR_MIN, C.ARR_MAX),
    "shift": SettingSpec("shift", int, C.DEFAULT_SHIFT, C.SHIFT_MIN, C.SHIFT_MAX),
}
PRESET_KEYS = {key: key for key in SETTING_SPECS}


def clamp(spec: SettingSpec, value):
    """Wert auf die Reglergrenzen begrenzen bzw. auf den nächsten erlaubten Wert einrasten."""
    if spec.choices is not None:
        return min(spec.choices, key=lambda c: (abs(c - value), c))
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    return value


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
            except (ValueError, TypeError):
                continue
            st.session_state[state_key] = clamp(spec, value) if not isinstance(value, bool) else value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(int(value)) if isinstance(value, bool) else str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        if key in C.PRESETS[name]:
            st.session_state[state_key] = C.PRESETS[name][key]


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen
    Standardwert) mit dem Session State. Ein später ergänzter Regler braucht nur seinen Eintrag in SETTING_SPECS,
    dann hebt auch seine Änderung die Markierung auf (tests/test_layout.py prüft das für jeden Regler)."""
    preset_key_of = {state_key: key for key, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_seed():
    st.session_state["seed"] = random.randint(C.SEED_MIN, C.SEED_MAX)
