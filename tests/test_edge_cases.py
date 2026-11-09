"""Randfälle, an denen Kernroutinen erfahrungsgemäß brechen (DEMO-PLAYBOOK §12): zwei Linien, eine Linie, keine Umstiege, Extremwerte der Regler, Gleichstände."""

import dataclasses

import numpy as np
import pytest

import uan_clock as K
import uan_constants as C
import uan_evaluation as E
import uan_forest as F
import uan_pair as P
import uan_search as S
from uan_rng import SplitMix64
from uan_timetable import Instance, Line


def test_exactly_two_lines_form_a_forest_and_the_optimum_is_the_line_pair_bound(mini):
    """n = 2: der kleinste Fall mit einem Linienpaar (der Zweig `n < 2` darf nicht greifen)."""
    edges = F.line_edges(mini)
    assert edges == {(0, 1): 2.0} and F.cycle_rank(2, edges) == 0
    assert F.forest_offsets(mini) == [0, 3]                                  # erstes Minimum der Kurve: u = 3
    assert S.mean_wait(S.base_arrays(mini), F.forest_offsets(mini)) == 30.0 == P.line_pair_bound(mini) / 2


def test_single_line_and_no_transfers_do_not_divide_by_zero():
    inst = Instance(60, [Line([0, 1, 2], [10, 10])], {})
    arrs = S.base_arrays(inst)
    assert S.random_mean_exact(arrs) == 0.0 and S.mean_wait(arrs, [0]) == 0.0
    o, c = S.multistart(arrs, S.SearchSettings(restarts=3), SplitMix64(1))
    assert c == 0.0 and len(o) == 1 and 0 <= o[0] < 60        # ohne Umstiege ist jeder Versatz gleich gut: der Startversatz bleibt
    assert F.cycle_rank(1, []) == 0 and F.spanning_forest(1, {}) == [] and F.forest_offsets(inst) == [0]
    assert P.line_pair_costs(inst) == {} and P.line_pair_bound(inst) == 0.0 and P.pairs_bound(inst) == 0.0


def test_wait_time_over_the_whole_clock_for_the_extreme_minimum_transfer_times():
    for mt in (1, 6):
        for arr in (0, 59):
            for dep in range(60):
                w = K.wait_time(arr, dep, mt, 60)
                assert mt <= w <= mt + 59 and w == K.board_wait(arr, dep, mt, 60)
                assert (arr + w - dep) % 60 == 0


def test_connection_at_all_corners():
    for arr in (C.ARR_MIN, C.ARR_MAX):
        for shift in (C.SHIFT_MIN, C.SHIFT_MAX):
            conn = E.connection(arr, shift, 3)
            assert conn.wait_mod == conn.wait_board and len(conn.curve) == 60 and conn.mean_random == 32.5
            assert conn.curve[shift] == conn.wait_mod


@pytest.mark.parametrize("lines", [3, 10])
@pytest.mark.parametrize("dwell,mt", [(1, 1), (6, 6), (1, 6), (6, 1)])
def test_analysis_at_the_slider_corners(lines, dwell, mt):
    for seed in (C.SEED_MIN, C.SEED_MAX):
        a = E.analyse(E.Settings(lines=lines, seed=seed, dwell=dwell, mt=mt))
        assert mt <= a.lb <= a.lb2 + 1e-9 <= a.opt + 2e-9 and a.opt <= a.rand_exact + 1e-9
        assert a.rand_exact == pytest.approx(mt + 29.5)
        assert sum(a.parts.values()) == pytest.approx(a.rand_exact - mt)
        assert E.verdict_net(a)[0] in ("info", "success")


def test_forest_switch_gives_rank_zero_for_every_line_count():
    for lines in C.LINES_OPTIONS:
        a = E.analyse(E.Settings(lines=lines, seed=C.DEFAULT_SEED, forest=True))
        assert a.is_forest and a.comps >= 1 and a.opt == pytest.approx(a.lb2)


def test_equal_weights_tie_in_the_spanning_forest_is_resolved_by_the_smaller_edge():
    assert F.spanning_forest(3, {(0, 1): 2.0, (0, 2): 2.0, (1, 2): 2.0}) == [(0, 1), (0, 2)]


def test_ties_in_the_cost_curve_take_the_smallest_offset():
    vec = np.full(60, 5.0)
    assert F.forest_offsets_from_costs(2, {(0, 1): vec}, 60) == [0, 0]


def test_dwell_and_minimum_transfer_time_change_the_net_without_changing_its_lines():
    base, _ = E.build_net(E.Settings())
    other, _ = E.build_net(E.Settings(dwell=5, mt=1))
    assert [l.stops for l in base.lines] == [l.stops for l in other.lines] and base.transfers == other.transfers
    assert dataclasses.replace(base, dwell=5, transfer_min=1) == other


def test_loop_time_rejects_an_arrival_that_does_not_exist():
    line = Line([0, 1, 2], [10, 10])
    with pytest.raises(ValueError):
        K.loop_time(line, "f", 0, 0, 60, 2, 4)            # vorwärts kommt man an Halt 0 nie an
    with pytest.raises(ValueError):
        K.loop_time(line, "b", 2, 0, 60, 2, 4)            # rückwärts kommt man am letzten Halt nie an


def test_pair_params_rejects_two_activities_that_are_not_opposite(mini):
    with pytest.raises(ValueError):
        P.pair_params(mini, (0, "f", 1, 1, "f", 1), (0, "f", 1, 1, "f", 1))
