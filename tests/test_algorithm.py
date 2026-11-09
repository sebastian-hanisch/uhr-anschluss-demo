"""Einheiten gegen Handrechnung an der Mini-Instanz (tests/conftest.py), jede Zahl als Rechnung, nicht als abgeschriebener Wert (DEMO-PLAYBOOK §1b und §5)."""

import numpy as np
import pytest

import uan_clock as K
import uan_forest as F
import uan_pair as P
import uan_search as S
from uan_rng import SplitMix64
from uan_timetable import fixed_line_times


# ---------------------------------------------------------------- Ereigniszeiten und Zifferblatt
def test_event_times_of_the_mini_lines(mini):
    ev_a, cyc_a = fixed_line_times(mini.lines[0], 60, 2, 4, 0)
    ev_b, cyc_b = fixed_line_times(mini.lines[1], 60, 2, 4, 0)
    assert cyc_a == cyc_b == 60
    assert (ev_a[("arr", "f", 1)], ev_a[("dep", "f", 1)], ev_a[("arr", "b", 1)], ev_a[("dep", "b", 1)]) == (10, 12, 40, 42)
    assert (ev_b[("arr", "f", 1)], ev_b[("dep", "f", 1)], ev_b[("arr", "b", 1)], ev_b[("dep", "b", 1)]) == (8, 10, 42, 44)


def test_wait_time_by_hand():
    # Ankunft :40, Mindestzeit 3: der Zug um :43 wird gerade erreicht (3), der um :42 nicht mehr (nächste Stunde: 62), der um :20 kommt 40 min später.
    assert K.wait_time(40, 43, 3, 60) == 3
    assert K.wait_time(40, 42, 3, 60) == 62 == 60 + 3 - 1
    assert K.wait_time(40, 20, 3, 60) == 40
    assert K.wait_time(10, 10, 3, 60) == 57 + 3        # gleiche Minute: (10 - 10 - 3) mod 60 = 57, plus die Mindestzeit
    assert K.board_wait(40, 43, 3, 60) == 3 and K.board_wait(40, 42, 3, 60) == 62 and K.board_wait(40, 20, 3, 60) == 40


def test_board_departures_window():
    assert K.board_departures(20, 60, 0, 130) == [20, 80]
    assert K.board_departures(20, 60, 21, 79) == []
    assert K.board_departures(20, 60, -40, 20) == [-40, 20]


def test_random_mean_wait_is_mt_plus_half_of_t_minus_one():
    assert K.random_mean_wait(3, 60) == 3 + 29.5 == 32.5


# ---------------------------------------------------------------- Schleifenzeiten, Hin/Rück-Paar
def test_loop_times_by_hand(mini):
    la, lb = mini.lines
    # A vorwärts an Halt 1: 2·2·(2-1) + 2·10 + 4 + 4 = 32;  B rückwärts an Halt 1: 2·2·1 + 2·8 + 4 + (8 - 4) = 28
    assert K.loop_time(la, "f", 1, 4, 60, 2, 4) == 4 + 20 + 4 + 4 == 32
    assert K.loop_time(lb, "b", 1, 4, 60, 2, 4) == 4 + 16 + 4 + 4 == 28
    assert K.default_end_wait(la, 60, 2, 4) == 4
    assert K.pair_loops(mini, (0, "f", 1, 1, "f", 1)) == (32, 28)


def test_hin_rueck_pair_constant_and_vector(mini):
    ((k1, k2, pp),) = P.hin_rueck_params(mini)
    assert (pp.d1, pp.c) == (57, 54)                       # D1 = 10 - 10 - 3 = -3 -> 57;  D2 = 42 - 42 - 3 = -3;  c = -6 mod 60 = 54
    assert K.pair_constant(mini, k1) == (32 + 28 - 2 * 3) % 60 == 54
    vec = P.pair_cost_vector(pp.d1, pp.c, 60, 3)
    assert vec.min() == 2 * 3 + 54 == 60 and sorted(set(vec)) == [60, 120]
    assert int((vec == 60).sum()) == 55 == pp.c + 1
    good = P.good_set(pp.d1, pp.c, 60)
    assert good == list(range(3, 58))                      # (u + 57) mod 60 <= 54  <=>  u in 3..57
    assert u_value(vec, 0) == 120 and u_value(vec, 3) == 60 and u_value(vec, 57) == 60 and u_value(vec, 58) == 120


def u_value(vec, u):
    return int(vec[u])


def test_single_waits_of_the_pair(mini):
    ((k1, k2, pp),) = P.hin_rueck_params(mini)
    hin, rueck = P.pair_wait_vectors(pp.d1, P.activity_d(mini, k2), 60, 3)
    assert hin[0] == 57 + 3 and rueck[0] == 57 + 3          # u = 0: beide 60 min
    assert hin[3] == 0 + 3 and rueck[3] == 54 + 3           # u = 3: Hinweg gerade erreicht (3), Rückweg 57
    assert list(hin + rueck) == list(P.pair_cost_vector(pp.d1, pp.c, 60, 3))


def test_mirror_pair_by_hand(mini_both):
    (p1, p2) = P.hin_rueck_params(mini_both)
    assert {p1[2].c, p2[2].c} == {54, 2}
    mirror = next(t for t in (p1, p2) if t[2].c == 2)
    assert mirror[2].d1 == 1                                # D1' = 44 - 40 - 3 = 1;  D2' = 12 - 8 - 3 = 1;  c' = 2
    assert K.mirror_constant(54, 2, 3, 60) == (4 * (2 - 3) - 54) % 60 == 2
    assert K.pair_constant(mini_both, mirror[0]) == (32 + 36 - 6) % 60 == 2
    assert P.good_set(1, 2, 60) == [0, 1, 59]               # (u + 1) mod 60 <= 2
    assert P.good_sets_disjoint(P.good_set(57, 54, 60), P.good_set(1, 2, 60))
    assert P.mirror_disjoint_predicted(54, 2, 2, 3, 60) is True          # c + c' = 56 = 60 - 4·(3 - 2)
    assert P.mirror_disjoint_predicted(58, 58, 2, 3, 60) is False        # 116 = 120 - 4: Überschneidung
    assert P.mirror_disjoint_predicted(54, 2, 3, 3, 60) is None          # Haltezeit = Mindestzeit: kein Satz


def test_joint_cost_of_pair_and_mirror_pair(mini_both):
    costs = P.line_pair_costs(mini_both)
    f = costs[(0, 1)]
    assert f.min() == 128 and P.line_pair_bound(mini_both) == 128      # nicht 60 + 8: die Gut-Mengen sind disjunkt
    assert P.pairs_bound(mini_both) == 60 + 8
    assert P.mirror_surcharge(1.0, 1.0, 60) == 60 == 128 - (60 + 8)
    assert P.mirror_surcharge(1.0, 2.5, 60) == 60.0 and P.mirror_surcharge(3.0, 2.5, 60) == 150.0


def test_same_direction_pair_by_hand(mini_same):
    ((k1, k2, pp),) = P.same_direction_params(mini_same)
    assert (pp.d1, pp.c) == (57, 58)                        # D1 = -3 -> 57;  D4 = 12 - 8 - 3 = 1;  c = 58
    assert P.pair_min(pp.c, 3) == 2 * 3 + 58 == 64
    assert K.same_direction_constant(2, 3, 60) == 58 and K.same_direction_constant(3, 3, 60) == 0
    # Handrechnung: Ankünfte alpha = 10 (A), beta = 8 (B): (beta - alpha - 1) mod 60 + (alpha - beta - 1) mod 60 + 6 = 57 + 1 + 6
    assert (8 - 10 - 1) % 60 + (10 - 8 - 1) % 60 + 6 == 57 + 1 + 6 == 64


# ---------------------------------------------------------------- Wald
def test_forest_offsets_from_synthetic_costs():
    f01 = np.full(60, 9.0)
    f01[7] = 1.0
    f12 = np.full(60, 9.0)
    f12[40] = 1.0
    assert F.forest_offsets_from_costs(3, {(0, 1): f01, (1, 2): f12}, 60) == [0, 7, 47]
    with pytest.raises(ValueError):
        F.forest_offsets_from_costs(3, {(0, 1): f01, (1, 2): f12, (0, 2): f01}, 60)    # Kreis


def test_cycle_rank_and_components():
    assert F.cycle_rank(4, [(0, 1), (1, 2), (2, 3)]) == 0
    assert F.cycle_rank(4, [(0, 1), (1, 2), (0, 2), (2, 3)]) == 1
    assert F.cycle_rank(4, [(0, 1), (2, 3)]) == 0 and F.components(4, [(0, 1), (2, 3)]) == 2
    assert F.cycle_rank(3, []) == 0 and F.components(3, []) == 3


def test_spanning_forest_takes_heavy_edges_first():
    weights = {(0, 1): 5.0, (1, 2): 4.0, (0, 2): 9.0, (2, 3): 1.0}
    assert F.spanning_forest(4, weights) == [(0, 2), (0, 1), (2, 3)]        # (1, 2) würde mit (0, 1) und (0, 2) einen Kreis schließen


# ---------------------------------------------------------------- Suche
def test_search_on_the_mini_instance(mini):
    arrs = S.base_arrays(mini)
    assert S.mean_wait(arrs, [0, 3]) == 60 / 2             # u = 3: beide Summen 60, zwei Aktivitäten mit Gewicht 1: Mittel 30
    assert S.mean_wait(arrs, [0, 0]) == 120 / 2
    o, c = S.multistart(arrs, S.SearchSettings(restarts=5), SplitMix64(7))
    assert c / 2 == 30.0 and (o[1] - o[0]) % 60 in range(3, 58)
    assert S.random_mean_exact(arrs) == 3 + 29.5


def test_coordinate_descent_never_increases_the_cost(mini_both):
    arrs = S.base_arrays(mini_both)
    for start in ([0, 0], [10, 30], [0, 59]):
        o, c = S.coordinate_descent(arrs, start)
        assert c <= S.total_cost(arrs, start) + 1e-9
        assert c == pytest.approx(S.total_cost(arrs, o))
