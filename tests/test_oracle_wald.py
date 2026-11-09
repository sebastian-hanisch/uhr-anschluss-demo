"""Orakel für den Wald-Satz (Optimum = Linienpaar-Untergrenze LB2 bei Kreisrang 0): Vollaufzählung und CP-SAT (OR-Tools) als anderer Rechenweg als die Konstruktion `forest_offsets`.

Drei Wege: (1) Vollaufzählung aller 60² Versatzpaare bei drei Linien, (2) CP-SAT beweist das Optimum an konstruierten Wäldern (alle Umstiege bis auf einen aufspannenden Wald gestrichen),
(3) die Konstruktion erreicht LB2 an 40 solchen Wäldern. Das Orakel wurde vorher an der Mini-Instanz geprüft (CP-SAT und Aufzählung geben dort 30 min)."""

import itertools

import pytest

import uan_forest as F
import uan_pair as P
import uan_search as S
from uan_network import build_valid_instance


def _enumerate_optimum(arrs, n_lines, period=60):
    """Vollaufzählung: Linie 0 fest auf 0, die anderen laufen über alle Versätze."""
    best = float("inf")
    for rest in itertools.product(range(period), repeat=n_lines - 1):
        best = min(best, S.total_cost(arrs, [0, *rest]))
    return best / float(arrs.w.sum())


def test_mini_instance_enumeration_and_cpsat_agree(mini):
    pytest.importorskip("ortools")
    from uan_exact import solve_phases
    arrs = S.base_arrays(mini)
    assert _enumerate_optimum(arrs, 2) == 30.0
    ex = solve_phases(arrs, time_limit=10, workers=2)
    assert ex.proven and ex.mean_wait == pytest.approx(30.0)


def test_three_line_forests_by_full_enumeration():
    """Netze mit drei Linien und Kreisrang 0 (die ersten acht ab Seed 10000): Optimum aus der Aufzählung = LB2 = Konstruktion."""
    checked = 0
    for seed in range(10000, 14000, 25):
        if checked == 8:
            break
        inst, _, _, used = build_valid_instance(3, seed)
        edges = F.line_edges(inst)
        if len(inst.lines) != 3 or F.cycle_rank(3, edges) != 0:
            continue
        arrs = S.base_arrays(inst)
        tw = float(arrs.w.sum())
        lb2 = P.line_pair_bound(inst) / tw
        assert _enumerate_optimum(arrs, 3) == pytest.approx(lb2)
        assert S.mean_wait(arrs, F.forest_offsets(inst)) == pytest.approx(lb2)
        checked += 1
    assert checked == 8


@pytest.mark.parametrize("lines,seed", [(5, 21500), (6, 23000), (8, 24500), (10, 26000)])
def test_constructed_forest_is_proven_optimal_by_cpsat(lines, seed):
    pytest.importorskip("ortools")
    from uan_exact import solve_phases
    inst, _, _, _ = build_valid_instance(lines, seed)
    red, keep = F.forest_instance(inst)
    assert F.cycle_rank(len(red.lines), F.line_edges(red)) == 0 and len(keep) <= len(red.lines) - 1
    assert len(red.transfers) < len(inst.transfers)
    arrs = S.base_arrays(red)
    tw = float(arrs.w.sum())
    lb2 = P.line_pair_bound(red) / tw
    ex = solve_phases(arrs, time_limit=30, workers=2)
    assert ex.proven
    assert ex.mean_wait == pytest.approx(lb2, abs=1e-6)
    assert S.mean_wait(arrs, F.forest_offsets(red)) == pytest.approx(lb2)


def test_construction_reaches_lb2_on_forty_constructed_forests():
    done = 0
    for lines in (4, 5, 6, 8, 10):
        for i in range(8):
            inst, _, _, _ = build_valid_instance(lines, 30000 + 1500 * lines + 50 * i)
            red, _ = F.forest_instance(inst)
            arrs = S.base_arrays(red)
            tw = float(arrs.w.sum())
            lb2 = P.line_pair_bound(red) / tw
            assert S.mean_wait(arrs, F.forest_offsets(red)) == pytest.approx(lb2)
            done += 1
    assert done == 40


def test_forest_offsets_refuse_a_net_with_a_cycle():
    for seed in range(10000, 10600, 50):
        inst, _, _, _ = build_valid_instance(6, seed)
        if F.cycle_rank(len(inst.lines), F.line_edges(inst)) > 0:
            with pytest.raises(ValueError):
                F.forest_offsets(inst)
            return
    pytest.fail("kein Netz mit Kreis gefunden")
