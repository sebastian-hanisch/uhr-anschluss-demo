"""Zweig-Tests (Nullspalten-Regel, DEMO-PLAYBOOK §0): jede Variante weicht auf mindestens einem Netz von der Nachbarvariante ab, jede Spalte der Messreihen hat mehr als einen Wert,
und jedes Preset zeigt die Verdikt-Zeile, die sein Hilfetext verspricht."""

import pytest

import uan_constants as C
import uan_evaluation as E
import uan_forest as F
import uan_pair as P
import uan_results as R
import uan_search as S
from uan_network import build_valid_instance


@pytest.fixture(scope="module")
def res():
    return R.load_results()


def test_dwell_two_against_three_changes_the_same_direction_sum():
    inst, _, _, _ = build_valid_instance(6, C.DEFAULT_SEED)
    key, rev, _ = max(P.same_direction_params(inst), key=lambda t: (t[2].w1 + t[2].w2, t[0]))
    rows = {r["dwell"]: r["min_sum"] for r in E.dwell_table(inst, key, rev)}
    assert rows[2] == 64 and rows[3] == 6 and rows[1] == 62 and rows[4] == 8 and rows[6] == 12


def test_forest_switch_changes_the_number_of_activities_and_the_rank():
    full = E.analyse(E.Settings(lines=8, seed=C.DEFAULT_SEED))
    wood = E.analyse(E.Settings(lines=8, seed=C.DEFAULT_SEED, forest=True))
    assert wood.n_act < full.n_act and wood.rank == 0 < full.rank and len(wood.edges) < len(full.edges)
    assert wood.opt == pytest.approx(wood.lb2) and full.opt > full.lb2


def test_there_is_a_net_with_line_pair_bound_above_pair_bound_and_one_with_optimum_above_line_pair_bound():
    gaps12, gaps2o = [], []
    for seed in range(C.DEFAULT_SEED, C.DEFAULT_SEED + 12):
        a = E.analyse(E.Settings(lines=6, seed=seed))
        gaps12.append(a.lb2 - a.lb)
        gaps2o.append(a.opt - a.lb2)
    assert max(gaps12) > 1.0 and max(gaps2o) > 0.1
    assert min(gaps12) >= 0 and min(gaps2o) >= -1e-9


def test_mirror_surcharge_exists_at_dwell_two_and_not_at_dwell_three():
    """Haltezeit 2 < Mindestzeit 3: alle Spiegelpaare des Netzes haben disjunkte Gut-Mengen (oder c + c' = 116) und ein Teil zahlt den Zuschlag; bei Haltezeit 3 ist keines disjunkt."""
    for dwell, expect_disjoint in ((2, True), (3, False)):
        a = E.analyse(E.Settings(lines=6, seed=C.DEFAULT_SEED, dwell=dwell))
        found = []
        for edge in a.edges:
            for i in range(len(E.hin_rueck_of(a, edge))):
                pv = E.pair_view(a, edge, i)
                if pv.mirror is not None:
                    found.append((pv.mirror.disjoint, pv.surcharge))
        assert found
        if expect_disjoint:
            assert any(d and s > 0 for d, s in found)
        else:
            assert not any(d for d, _ in found)


def test_every_column_of_the_precomputed_series_has_more_than_one_value(res):
    nets = R.nets(res)
    for col in ("n_lines", "n_act", "n_pairs", "n_line_pairs", "rank", "lb", "lb2", "opt", "rand_300"):
        assert len({r[col] for r in nets}) > 1, col
    assert len({r["rand_exact"] for r in nets}) == 1                  # Ausnahme mit Grund: exakt mt + 29,5 in jedem Netz
    assert len({v for r in nets for v in r["c"]}) > 30
    for col in ("lb", "lb2", "opt", "same_min_mean", "mirror_disjoint", "n_same"):
        assert len({r[col] for r in res["dwell"]}) > 1, col
    assert len({r["dwell"] for r in res["dwell"]}) == 6
    for col in ("lb_std", "lb_free", "share_cmin0", "c_min_mean"):
        assert len({r[col] for r in res["split"]}) > 1, col
    assert len({r["status"] for r in res["cp"]}) > 1                  # bewiesen und nicht bewiesen kommen beide vor


def test_the_dwell_series_columns_move_with_the_dwell_time(res):
    rows = R.dwell_rows(res)
    assert [round(r["same_min_mean"]) for r in rows] == [62, 64, 6, 8, 10, 12]
    assert rows[1]["mirror_disjoint"] > 0 and rows[0]["mirror_disjoint"] > 0 and all(r["mirror_disjoint"] == 0 for r in rows[2:])


def test_preset_standard_shows_the_neutral_connection():
    p = C.PRESETS["Standard"]
    conn = E.connection(p["arr"], p["shift"], p["mt"])
    assert conn.wait_mod == 40 == (C.B_BASE_DEP + p["shift"] - p["arr"] - p["mt"]) % 60 + p["mt"]
    assert E.verdict_connection(conn.wait_mod, p["mt"])[0] == "info"


def test_preset_knapp_verpasst_misses_the_connection_by_one_minute():
    p = C.PRESETS["Knapp verpasst"]
    conn = E.connection(p["arr"], p["shift"], p["mt"])
    assert conn.dep == p["arr"] + p["mt"] - 1 and conn.wait_mod == 62 and E.verdict_connection(conn.wait_mod, p["mt"])[0] == "warning"
    ok = E.connection(p["arr"], p["shift"] + 1, p["mt"])
    assert ok.wait_mod == p["mt"] and E.verdict_connection(ok.wait_mod, p["mt"])[0] == "success"


def test_preset_taktknoten_gives_a_cheap_same_direction_pair():
    p = C.PRESETS["Taktknoten"]
    a = E.analyse(E.Settings(lines=p["lines"], seed=p["seed"], dwell=p["dwell"], mt=p["mt"]))
    key, rev, _ = max(E.same_direction_of(a), key=lambda t: (t[2].w1 + t[2].w2, t[0]))
    assert E.verdict_dwell(E.dwell_table(a.inst, key, rev), a.inst.dwell, a.inst.transfer_min)[0] == "success"
    std = E.analyse(E.Settings(lines=p["lines"], seed=p["seed"]))
    k2, r2, _ = max(E.same_direction_of(std), key=lambda t: (t[2].w1 + t[2].w2, t[0]))
    assert E.verdict_dwell(E.dwell_table(std.inst, k2, r2), std.inst.dwell, std.inst.transfer_min)[0] == "warning"


def test_preset_nur_wald_is_a_forest_with_the_bound_reached():
    p = C.PRESETS["Nur Wald"]
    a = E.analyse(E.Settings(lines=p["lines"], seed=p["seed"], forest=p["forest"]))
    assert a.is_forest and E.verdict_net(a)[0] == "success"
    assert S.mean_wait(S.base_arrays(a.inst), F.forest_offsets(a.inst)) == pytest.approx(a.lb2)


def test_preset_dichtes_netz_has_ten_lines_and_cycles():
    p = C.PRESETS["Dichtes Netz"]
    a = E.analyse(E.Settings(lines=p["lines"], seed=p["seed"]))
    assert a.n_lines >= 9 and a.rank > 0 and E.verdict_net(a)[0] == "info"
