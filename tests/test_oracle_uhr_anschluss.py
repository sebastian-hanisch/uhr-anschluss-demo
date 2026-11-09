"""Orakel-Tests (ORACLE-PLAYBOOK §2, DEMO-PLAYBOOK §12): jede Kernroutine gegen einen ANDEREN Rechenweg.

Rechenweg der Demo: Modulo-Formeln und Schleifenzeit-Formel (uan_clock, uan_pair). Orakel hier: ein Fahrplansimulator (tests/conftest.py), der ein Fahrzeug einen Zyklus
fahren lässt und die Wartezeit über die Fahrplantafel (Abfahrten zu t + k·T, erste mit Abstand >= Mindestzeit) bestimmt, ohne Modulo auf der Zeit; dazu Vollaufzählung aller 60 Versätze,
Aufzählung der Gut-Mengen und CP-SAT (OR-Tools). Das Orakel wurde vorher an der Handrechnung der Mini-Instanz geprüft (test_oracle_simulator_matches_the_hand_calculation).
Der große Lauf (600 Netze, 25 568 Paare) steht in data/uan_results.json; hier die schnelle Fassung."""

import dataclasses

import pytest

import uan_clock as K
import uan_pair as P
import uan_search as S
from conftest import sim_events, sim_time, sim_wait
from uan_network import build_valid_instance
from uan_rng import SplitMix64

SEEDS = [(3, 10000), (3, 10100), (5, 11500), (5, 11600), (6, 13000), (6, 13100)]


def test_oracle_simulator_matches_the_hand_calculation(mini):
    ev_a = sim_events(mini.lines[0], 60, 2, 4, 0)
    ev_b = sim_events(mini.lines[1], 60, 2, 4, 0)
    assert [sim_time(ev_a, "arr", "f", 1), sim_time(ev_a, "dep", "b", 1), sim_time(ev_b, "arr", "b", 1), sim_time(ev_b, "dep", "b", 1)] == [10, 42, 42, 44]
    key = (0, "f", 1, 1, "f", 1)
    assert sim_wait(ev_a, key, sim_events(mini.lines[1], 60, 2, 4, 3), 60, 3) == 3          # Versatz 3: gerade erreicht
    assert sim_wait(ev_a, key, sim_events(mini.lines[1], 60, 2, 4, 2), 60, 3) == 62         # Versatz 2: eine Minute zu spät


def test_wait_time_formula_matches_an_independent_scan_of_absolute_minutes():
    for mt in range(1, 7):
        for arr in range(0, 60, 7):
            for dep in range(60):
                scan = next(g for g in range(mt, mt + 61) if (arr + g - dep) % 60 == 0)      # kleinste Wartezeit >= mt, bei der die Uhr auf die Abfahrt zeigt
                assert K.wait_time(arr, dep, mt, 60) == scan == K.board_wait(arr, dep, mt, 60), (arr, dep, mt)


@pytest.mark.parametrize("lines,seed", SEEDS)
def test_pair_cost_vector_matches_the_simulated_timetable_for_every_offset(lines, seed):
    inst, _, _, _ = build_valid_instance(lines, seed)
    pairs = P.hin_rueck_params(inst)
    assert pairs
    for k1, k2, pp in pairs:
        vec = P.pair_cost_vector(pp.d1, pp.c, 60, 3)
        for u in range(60):
            ev_a = sim_events(inst.lines[pp.la], 60, inst.dwell, inst.tmin, 0)
            ev_b = sim_events(inst.lines[pp.lb], 60, inst.dwell, inst.tmin, u)
            total = sim_wait(ev_a, k1, ev_b, 60, 3) + sim_wait(ev_b, k2, ev_a, 60, 3)
            assert total == vec[u], (k1, u)
        assert min(vec) == 6 + pp.c and int((vec == min(vec)).sum()) == pp.c + 1 and set(vec) <= {min(vec), min(vec) + 60}


@pytest.mark.parametrize("lines,seed", SEEDS[::2])
def test_pair_constant_from_loop_times_matches_the_simulated_loops(lines, seed):
    inst, _, _, _ = build_valid_instance(lines, seed)
    for k1, k2, pp in P.hin_rueck_params(inst):
        la, da, ka, lb, db, kb = k1
        ev_a = sim_events(inst.lines[la], 60, inst.dwell, inst.tmin, 0)
        ev_b = sim_events(inst.lines[lb], 60, inst.dwell, inst.tmin, 0)
        opp = lambda d: "b" if d == "f" else "f"                                          # noqa: E731
        # Schleife = Abfahrt in der Gegenrichtung minus Ankunft am selben Halt; liegt die Abfahrt im Zyklus davor, fehlt ein ganzer Zyklus (ein Vielfaches von T)
        raw_a = sim_time(ev_a, "dep", opp(da), ka) - sim_time(ev_a, "arr", da, ka)
        raw_b = sim_time(ev_b, "dep", db, kb) - sim_time(ev_b, "arr", opp(db), kb)
        got_a, got_b = K.pair_loops(inst, k1)
        assert (got_a - raw_a) % 60 == 0 and (got_b - raw_b) % 60 == 0, k1
        assert K.pair_constant(inst, k1) == pp.c == (got_a + got_b - 6) % 60


@pytest.mark.parametrize("dwell,mt", [(1, 3), (2, 3), (2, 5), (1, 6), (3, 3), (4, 3), (5, 2)])
def test_mirror_pairs_against_enumeration_of_the_good_sets(dwell, mt):
    """c + c' = 4(h - m) mod T für jedes Spiegelpaar; die Gut-Mengen sind für h < m genau dann disjunkt, wenn c + c' = T - 4(m - h) ist (aus der Aufzählung aller 60 Versätze)."""
    checked = disjoint = 0
    for lines, seed in SEEDS:
        inst0, _, _, _ = build_valid_instance(lines, seed)
        inst = dataclasses.replace(inst0, dwell=dwell, transfer_min=mt)
        ev0 = P.event_times_zero(inst)
        for k1, k2, pp in P.hin_rueck_params(inst):
            m1, m2 = P.mirror_key(k1), P.mirror_key(k2)
            if m1 not in inst.transfers or m2 not in inst.transfers:
                continue
            mpp = P.pair_params(inst, m1, m2, ev0)
            assert (pp.c + mpp.c - 4 * (dwell - mt)) % 60 == 0
            # Aufzählung über die Simulation: Menge der Versätze, bei denen die Summe auf dem kleineren Wert liegt
            def good(k_a, k_b, pr):
                ev_a = sim_events(inst.lines[pr.la], 60, dwell, inst.tmin, 0)
                sums = []
                for u in range(60):
                    ev_b = sim_events(inst.lines[pr.lb], 60, dwell, inst.tmin, u)
                    sums.append(sim_wait(ev_a, k_a, ev_b, 60, mt) + sim_wait(ev_b, k_b, ev_a, 60, mt))
                return {u for u in range(60) if sums[u] == min(sums)}
            g1, g2 = good(k1, k2, pp), good(m1, m2, mpp)
            assert g1 == set(P.good_set(pp.d1, pp.c, 60)) and g2 == set(P.good_set(mpp.d1, mpp.c, 60))
            pred = P.mirror_disjoint_predicted(pp.c, mpp.c, dwell, mt, 60)
            if pred is not None:
                assert pred == (not (g1 & g2)), (k1, pp.c, mpp.c)
            checked += 1
            disjoint += not (g1 & g2)
            if dwell >= mt:
                assert g1 & g2        # gemessen (kein Satz): auch hier überlappen die Gut-Mengen
    assert checked > 0


@pytest.mark.parametrize("dwell", range(1, 7))
def test_same_direction_minimum_against_simulation_and_formula(dwell):
    seen = 0
    for lines, seed in SEEDS[:4]:
        inst0, _, _, _ = build_valid_instance(lines, seed)
        inst = dataclasses.replace(inst0, dwell=dwell)
        for key, rev, pp in P.same_direction_params(inst)[:3]:
            ev_a = sim_events(inst.lines[pp.la], 60, dwell, inst.tmin, 0)
            sums = []
            for u in range(60):
                ev_b = sim_events(inst.lines[pp.lb], 60, dwell, inst.tmin, u)
                sums.append(sim_wait(ev_a, key, ev_b, 60, 3) + sim_wait(ev_b, rev, ev_a, 60, 3))
            assert min(sums) == 2 * 3 + (2 * dwell - 2 * 3) % 60 == P.pair_min(K.same_direction_constant(dwell, 3, 60), 3), (key, dwell)
            seen += 1
    assert seen > 0


def test_random_mean_wait_is_exact_for_every_minimum_transfer_time():
    for mt in range(1, 7):
        for lines, seed in SEEDS[:3]:
            inst0, _, _, _ = build_valid_instance(lines, seed)
            arrs = S.base_arrays(dataclasses.replace(inst0, transfer_min=mt))
            assert S.random_mean_exact(arrs) == pytest.approx(mt + 29.5) == pytest.approx(K.random_mean_wait(mt, 60))
            # Gegenprobe durch Ziehen: Mittel aus 300 Versatzvektoren liegt nahe am exakten Wert (Streuung des Mittels < 2 min)
            assert abs(S.random_mean_draws(arrs, 300, SplitMix64(11 * mt + lines)) - (mt + 29.5)) < 2.0


def test_line_pair_curve_equals_the_sum_of_simulated_waits():
    for lines, seed in SEEDS[:3]:
        inst, _, _, _ = build_valid_instance(lines, seed)
        costs = P.line_pair_costs(inst)
        (a, b), vec = max(costs.items(), key=lambda kv: kv[1].max())
        for u in (0, 7, 29, 59):
            ev_a = sim_events(inst.lines[a], 60, inst.dwell, inst.tmin, 0)
            ev_b = sim_events(inst.lines[b], 60, inst.dwell, inst.tmin, u)
            total = 0.0
            for key, w in inst.transfers.items():
                if {key[0], key[3]} == {a, b}:
                    arr_ev, dep_ev = (ev_a, ev_b) if key[0] == a else (ev_b, ev_a)
                    total += w * sim_wait(arr_ev, key, dep_ev, 60, 3)
            assert total == pytest.approx(vec[u]), (a, b, u)


def test_bounds_are_ordered_and_search_agrees_with_cpsat_on_small_nets():
    pytest.importorskip("ortools")
    from uan_exact import solve_phases
    for lines, seed in SEEDS[:4]:
        inst, _, _, used = build_valid_instance(lines, seed)
        arrs = S.base_arrays(inst)
        tw = float(arrs.w.sum())
        o, c = S.multistart(arrs, S.SearchSettings(restarts=40), SplitMix64(1_000_003 * used + lines))
        lb = P.pairs_bound(inst) / tw
        lb2 = P.line_pair_bound(inst) / tw
        assert 3 <= lb <= lb2 + 1e-9 <= c / tw + 2e-9
        ex = solve_phases(arrs, time_limit=20, workers=2, hint=o)
        assert ex.proven, (lines, seed)
        assert ex.mean_wait <= c / tw + 1e-6                 # das Optimum ist nie schlechter als der Fund der Lokalsuche
        assert c / tw - ex.mean_wait <= 0.2                  # Toleranz des Plans: Lokalsuche höchstens 0,2 min über dem Optimum
        assert lb2 <= ex.mean_wait + 1e-6
