"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen, Permalink begrenzt und rastet ein."""


import uan_constants as C
import uan_evaluation as E
import uan_presets as P


def test_every_preset_has_help_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP) == set(C.PRESET_ORDER)
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name]


def test_preset_values_are_inside_the_slider_bounds():
    for name, p in C.PRESETS.items():
        assert p["lines"] in C.LINES_OPTIONS and C.DWELL_MIN <= p["dwell"] <= C.DWELL_MAX and C.MT_MIN <= p["mt"] <= C.MT_MAX, name
        assert C.SEED_MIN <= p["seed"] <= C.SEED_MAX and C.ARR_MIN <= p["arr"] <= C.ARR_MAX and C.SHIFT_MIN <= p["shift"] <= C.SHIFT_MAX, name
        assert isinstance(p["forest"], bool)


def test_default_preset_equals_the_default_settings():
    d = C.PRESETS["Standard"]
    assert E.Settings(lines=d["lines"], seed=d["seed"], dwell=d["dwell"], mt=d["mt"], forest=d["forest"]) == E.Settings()
    assert (d["arr"], d["shift"]) == (C.DEFAULT_ARR, C.DEFAULT_SHIFT)
    assert {k: v.default for k, v in P.SETTING_SPECS.items()} == d


def test_every_preset_differs_from_the_default_in_exactly_what_its_help_names():
    d = C.PRESETS["Standard"]
    diff = {name: {k for k in d if C.PRESETS[name][k] != d[k]} for name in C.PRESETS if name != "Standard"}
    assert diff["Knapp verpasst"] == {"shift"}
    assert diff["Taktknoten"] == {"dwell"}
    assert diff["Nur Wald"] == {"lines", "forest"}
    assert diff["Dichtes Netz"] == {"lines", "seed"}


def test_setting_specs_cover_every_preset_key():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)


def test_preset_seeds_stay_clear_of_the_measurement_series_seeds():
    """Die Messreihe nutzt Seeds ab 10000; build_valid_instance zählt höchstens 50 hoch, die Presets liegen weit darunter."""
    assert C.SEED_MAX < C.SWEEP_SEED_BASE
    assert all(p["seed"] + 50 < C.SWEEP_SEED_BASE for p in C.PRESETS.values())


def test_permalink_values_are_clamped_and_snapped():
    spec = P.SETTING_SPECS
    assert P.clamp(spec["dwell"], 99) == C.DWELL_MAX and P.clamp(spec["dwell"], -5) == C.DWELL_MIN
    assert P.clamp(spec["lines"], 4) == 3 and P.clamp(spec["lines"], 7) == 6 and P.clamp(spec["lines"], 100) == 10      # Gleichstand: der kleinere erlaubte Wert
    assert P.clamp(spec["seed"], 10 ** 7) == C.SEED_MAX and P.clamp(spec["arr"], 61) == C.ARR_MAX
    assert P._to_bool("1") and P._to_bool("true") and not P._to_bool("0") and not P._to_bool("")
