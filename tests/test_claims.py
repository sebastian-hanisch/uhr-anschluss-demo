"""Jede Zahl aus der README wird hier nachgerechnet (DEMO-PLAYBOOK §11a): über dieselben Auswertungsfunktionen wie in der App (uan_results), als Zählung k von m, nie als „meist“.

Zwei Schritte je Aussage: (1) die Zahl aus der Messreihe rechnen und gegen den Wert prüfen, (2) prüfen, dass genau diese Schreibweise in der README steht."""

import subprocess
import sys
from pathlib import Path

import pytest

import uan_constants as C
import uan_results as R

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
RES = R.load_results()


def de(x, digits):
    return f"{x:.{digits}f}".replace(".", ",")


def has(text):
    assert text in README, text


def test_oracle_counts_25568_pairs_600_nets_zero_deviations():
    oc = R.oracle_counts(RES)
    assert (oc["nets"], oc["pairs"]) == (600, 25568)
    assert oc["viol_min"] == oc["viol_cnt"] == oc["viol_two"] == oc["viol_loop"] == oc["viol_vec"] == 0
    assert oc["lb_ok"] == oc["all_paired"] == oc["rand_exact_ok"] == 600
    has("600 Netzen und 25 568 Hin/Rück-Paaren")
    has("**0 Abweichungen**")


def test_random_mean_is_32_5_in_600_of_600_and_the_draws_stay_in_a_band():
    oc = R.oracle_counts(RES)
    assert oc["rand_exact_ok"] == 600 and C.DEFAULT_TRANSFER_MIN + (C.T - 1) / 2 == 32.5
    has("= **32,5 min**; die Mittelung über alle 60 Versätze trifft das per Konstruktion in 600 von 600 Netzen")
    has(f"zwischen {de(oc['rand_300_min'], 2)} und {de(oc['rand_300_max'], 2)} min")


def test_distribution_of_c():
    d = R.c_distribution(RES)
    has(" / ".join(de(100 * s, 1) for s in d["classes"]) + " %")
    has(f"Mittel {de(d['mean'], 1)} min")
    has(f"c = 0 in {de(100 * d['share_zero'], 1)} % der Paare")
    has(f"{de(100 * d['random_low_share'], 1)} % der Versätze auf dem kleineren Wert")


def test_pair_bound_explains_71_percent_without_a_monotone_trend():
    t = R.bounds_table(RES)
    has(f"**{R.pm((100 * t['alle']['share1'][0], 100 * t['alle']['share1'][1]), 1)} %**")
    shares = [100 * t[L]["share1"][0] for L in C.SWEEP_LINES]
    has(" / ".join(de(s, 1) for s in shares) + " %")
    assert shares != sorted(shares) and shares != sorted(shares, reverse=True)
    has(f"Spanne {de(max(shares) - min(shares), 1)} Prozentpunkte")
    has(f"bis {de(100 * max(t[L]['share1'][1] for L in C.SWEEP_LINES), 1)} Prozentpunkten")
    reached, n = R.bound_reached(RES)
    assert (reached, n) == (1, 600)
    has("in 1 von 600 Netzen")


def test_three_bounds_and_their_explained_shares():
    t = R.bounds_table(RES)["alle"]
    has(f"Phasen-Optimum **{R.pm(t['opt'])}**")
    has(f"LB {R.pm(t['lb'])}")
    has(f"LB2 **{R.pm(t['lb2'])}**")
    s2 = R.bounds_table(RES)
    has(f"**{R.pm((100 * t['share2'][0], 100 * t['share2'][1]), 1)} %**")
    has(f"bei 3 Linien {de(100 * s2[3]['share2'][0], 1)} %, bei 10 Linien {de(100 * s2[10]['share2'][0], 1)} %")
    shares = [s2[L]["share2"][0] for L in C.SWEEP_LINES]
    assert shares == sorted(shares, reverse=True)                      # fallend mit der Linienzahl (alle fünf Werte)
    has("Zufall 32,50")


def test_decomposition_of_the_random_surcharge():
    t = R.bounds_table(RES)["alle"]
    has(f"Paar-Kopplung {R.pm(t['pair'])}")
    has(f"Linienpaarung {R.pm(t['line_pair'])}")
    has(f"Kreise im Liniengraphen {R.pm(t['cycles'])}")
    has(f"Gewinn der Optimierung {R.pm(t['gain'])}")
    assert t["pair"][0] + t["line_pair"][0] + t["cycles"][0] + t["gain"][0] == pytest.approx(29.5)


def test_forest_theorem_counts():
    fs = R.forest_summary(RES)
    cp = R.cp_summary(RES)
    assert (fs["n_forest"], fs["n_nets"], fs["forest_by_lines"][3], fs["forest_gap_positive"]) == (24, 600, 24, 0) and fs["forest_gap_max"] == 0.0
    has("Kreisrang 0 kommt in 24 von 600 Netzen vor (alle mit 3 Linien): Optimum = LB2 in **24 von 24**")
    assert (cp["b_n"], cp["b_proven"], cp["b_equal_lb2"], cp["b_forest_offsets_equal_lb2"]) == (20, 20, 20, 20)
    has("bewies CP-SAT **20 von 20** Optima, alle gleich LB2; die Konstruktion `forest_offsets` erreicht LB2 in 20 von 20")


def test_cycles_cost_a_little_and_rank_explains_little():
    fs = R.forest_summary(RES)
    assert (fs["nonforest_equal"], fs["n_nonforest"]) == (101, 576)
    has("Optimum = LB2 in 101 von 576 Netzen mit Kreisen")
    has(" / ".join(de(c["gap"], 2) for c in fs["classes"][1:]) + " min")
    w = fs["corr_within"]
    has(f"Pearson +{de(min(w.values()), 2)} bis +{de(max(w.values()), 2)}")
    assert min(w.values()) > 0
    has(f"über alle Netze +{de(fs['corr_all'], 2)}")
    has(f"Kreisrang gegen Phasen-Optimum −{de(-fs['corr_rank_opt'], 2)}, gegen Optimum − LB −{de(-fs['corr_rank_opt_lb'], 2)}")
    has(f"Klassenmittel {de(fs['classes'][1]['gap'], 2)} → {de(fs['classes'][-1]['gap'], 2)} min")


def test_mirror_pairs():
    m = R.mirror_summary(RES)
    assert (m["n"], m["n_low"], m["disjoint_low"], m["n_high"], m["overlap_high"], m["other"], m["sum_ok"]) == (4090, 3877, 3877, 213, 213, 0, 4090)
    has("4090 Paare; c + c′ = 56 in 3877 (Gut-Mengen **disjunkt in 3877 von 3877**), c + c′ = 116 in 213 (überlappend in 213 von 213, Ø " + de(m["overlap_mean_high"], 1) + " Versätze)")


def test_same_direction_pairs():
    s = R.same_summary(RES)
    assert (s["pairs"], s["act_in"], s["act_total"], s["nets_with"], s["nets"], s["mins"]) == (8180, 16360, 51136, 592, 600, {64: 8180})
    has("8180 Paare, kleinste Summe **64 min in 8180 von 8180**")
    has("16 360 von 51 136 Umstiegen (32 %)")
    assert round(100 * s["act_in"] / s["act_total"]) == 32
    has("592 von 600 Netzen")


def test_dwell_series():
    rows = R.dwell_rows(RES)
    has(" / ".join(str(round(r["same_min_mean"])) for r in rows) + " min")
    has(" / ".join(de(r["opt"][0], 2) for r in rows) + " min")
    r2, r3 = rows[1], rows[2]
    has(f"nur **{de(r2['opt'][0] - r3['opt'][0], 2)} min**")
    later = [r["opt"][0] for r in rows[2:]]
    has(f"{de(min(later), 2)} bis {de(max(later), 2)}")
    has(f"LB2 − LB fällt von {de(r2['lb2_minus_lb'][0], 2)} (*h* = 2) auf {de(r3['lb2_minus_lb'][0], 2)} (*h* = 3)")
    assert [r["mirror_n"] for r in rows] == [4090] * 6
    has(" / ".join(str(r["mirror_disjoint"]) for r in rows) + " von je 4090")
    assert all(r["mirror_disjoint"] == 0 for r in rows[2:]) and rows[0]["mirror_mismatch"] == rows[1]["mirror_mismatch"] == 0
    has("von 2 auf 3 min nur")


def test_local_search_against_cpsat():
    cp = R.cp_summary(RES)
    assert (cp["a_n"], cp["a_proven"], cp["a_ls_worse"], cp["a_ls_better"]) == (30, 26, 2, 0)
    has("26 von 30 bewiesen, die Lokalsuche lag in 2 über dem CP-SAT-Fund, nie darunter (größte Abweichung " + de(cp["a_max_dev"], 2) + " min in der gespeicherten Messung;")
    has("bewiesen suboptimal ist die Lokalsuche nur in 1 Netz, um 0,05 min")
    has("in 2 von 30 Netzen über dem Fund")


def test_bridge_to_the_turn_slack():
    s = R.split_summary(RES)
    assert s["n"] == 600 and s["lower"] == 600
    has(f"in {round(100 * s['share_cmin0'][0])} % der Paare einzeln auf 0 sinken (Ø c {de(s['c_std'][0], 1)} → {de(s['c_min'][0], 1)} min)")
    has(f"{de(s['lb_free'][0], 2)} gegen {de(s['lb_std'][0], 2)} min bei Standard-Aufteilung, in 600 von 600 Netzen niedriger")


def test_hypothesis_table_uses_the_same_numbers():
    t = R.bounds_table(RES)
    has(f"(95,3 ± 0,2 %; {de(100 * t[3]['share2'][0], 1)} → {de(100 * t[10]['share2'][0], 1)} %)")
    shares = [100 * t[L]["share1"][0] for L in C.SWEEP_LINES]
    has(f"kein monotoner Verlauf ({de(min(shares), 1)} bis {de(max(shares), 1)} %)")
    has("H6 Kreis-Rest wächst mit dem Kreisrang")


def test_readme_test_count_matches_the_suite():
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True, timeout=300).stdout
    n = int(out.strip().splitlines()[-1].split()[0])
    has(f"**Testzahl:** {n} Tests")
