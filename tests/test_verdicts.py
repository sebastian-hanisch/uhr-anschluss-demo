"""Verdikte an von Hand gesetzten Werten (DEMO-PLAYBOOK §12): jede Schwelle und jede Zahl im Text steht hier.

Ein Verdikt ist eine reine Funktion (Art, Text) und bekommt Zahlen, nicht Seeds."""

import uan_evaluation as E
from uan_pair import PairParams


def test_connection_verdict_branches_and_numbers():
    kind, text = E.verdict_connection(3, 3)
    assert kind == "success" and "**3 min**" in text and "Mindest-Umsteigezeit" in text
    kind, text = E.verdict_connection(62, 3)                       # Mindestzeit + 59 = knapp verpasst
    assert kind == "warning" and "**62 min**" in text and "(Wartezeit 3 min)" in text and "59 min über der Mindestzeit" in text
    kind, text = E.verdict_connection(40, 3)
    assert kind == "info" and "**40 min**" in text and "davon 3 min Mindestzeit und 37 min Warten" in text
    assert E.verdict_connection(63, 4)[0] == "warning" and E.verdict_connection(62, 4)[0] == "info"       # Schwelle liegt bei mt + T - 1
    assert E.verdict_connection(1, 1)[0] == "success"


def _pair_view(c=54, w1=1.0, mirror=None, surcharge=None):
    pp = PairParams(0, 1, 57, c, w1, w1)
    return E.PairView((0, 1), (0, "f", 1, 1, "f", 1), (1, "b", 1, 0, "b", 1), pp, (32, 28), c, tuple(), tuple(), tuple(), tuple(), mirror, None, None, None, surcharge)


def test_pair_verdict_names_minimum_and_share():
    kind, text = E.verdict_pair(_pair_view(c=54), 3)
    assert kind == "info"
    assert "mindestens **60 min**" in text and "c = 54" in text and "55 von 60 Versätzen (91,7 %)" in text and "sind es 120 min" in text
    assert "mindestens **6 min**" in E.verdict_pair(_pair_view(c=0), 3)[1] and "1 von 60 Versätzen (1,7 %)" in E.verdict_pair(_pair_view(c=0), 3)[1]


def test_mirror_verdict_branches():
    kind, text = E.verdict_mirror(_pair_view(), 2, 3)
    assert kind == "info" and "kein gespiegeltes Paar" in text
    mp = PairParams(0, 1, 1, 2, 1.0, 1.0)
    dis = E.MirrorView((0, "b", 1, 1, "b", 1), mp, (59, 0, 1), 2, True, True)
    kind, text = E.verdict_mirror(_pair_view(mirror=dis, surcharge=60.0), 2, 3)
    assert kind == "warning" and "c' = 2" in text and "c + c' = 56" in text and "zusammen kosten die beiden Paare mindestens 60,0 gewichtete Minuten" in text and "60 min mal dem kleineren der beiden Gewichte, 1,0" in text
    over = E.MirrorView((0, "b", 1, 1, "b", 1), PairParams(0, 1, 1, 58, 1.0, 1.0), (1, 2), 58, False, False)
    kind, text = E.verdict_mirror(_pair_view(c=58, mirror=over), 2, 3)
    assert kind == "info" and "c' = 58" in text and "überlappen" in text and "Haltezeit < Mindest-Umsteigezeit" in text


def test_dwell_verdict_branches():
    rows = [{"dwell": d, "c": (2 * d - 6) % 60, "min_sum": 6 + (2 * d - 6) % 60, "formula_c": (2 * d - 6) % 60} for d in range(1, 7)]
    kind, text = E.verdict_dwell(rows, 3, 3)
    assert kind == "success" and "**6 min**" in text and "3 min Haltezeit" in text
    kind, text = E.verdict_dwell(rows, 2, 3)
    assert kind == "warning" and "**64 min**" in text and "bei 3 min Haltezeit nur 6 min" in text and "nicht eingerechnet" in text


def test_explained_share():
    assert E.explained_share(20.0, 25.0, 3) == (20 - 3) / (25 - 3)
    assert E.explained_share(3.0, 3.0, 3) is None and E.explained_share(3.0, 3.0 + 1e-12, 3) is None


def _net(rank, lb=18.0, lb2=23.0, opt=24.0, mt=3):
    from uan_timetable import Instance
    inst = Instance(60, [], {}, transfer_min=mt)
    return E.NetAnalysis(settings=E.Settings(), inst=inst, used_seed=1, n_lines=4, n_act=2, total_weight=2.0, edges={}, rank=rank, comps=1, forest_edges=(),
                         rand_exact=32.5, rand_draws=32.4, lb=lb, lb2=lb2, opt=opt, opt_offsets=(0,))


def test_net_verdict_forest_cycles_and_no_surcharge():
    a = _net(0, lb=18.0, lb2=24.0, opt=24.0)
    kind, text = E.verdict_net(a)
    assert kind == "success" and "Kreisrang 0" in text and "(24,00 min)" in text and "je Hin/Rück-Paar erklärt 71,4 %" in text and "je Linienpaar 100,0 %" in text
    a = _net(8)
    kind, text = E.verdict_net(a)
    assert kind == "info" and "Kreisrang 8" in text and "1,00 min über der Linienpaar-Untergrenze" in text and "erklärt die Untergrenze 71,4 %" in text and "je Linienpaar 95,2 %" in text
    assert "keinen Aufschlag" in E.verdict_net(_net(0, lb=3.0, lb2=3.0, opt=3.0))[1]
    assert a.parts == {"pair": 15.0, "line_pair": 5.0, "cycles": 1.0, "gain": 8.5} and sum(a.parts.values()) == 32.5 - 3


def test_exact_verdict_branches():
    assert E.verdict_exact(24.0, 24.0, 24.0, True)[0] == "success"
    kind, text = E.verdict_exact(24.2, 24.0, 24.0, True)
    assert kind == "warning" and "0,20 min darüber" in text and "24,00" in text
    kind, text = E.verdict_exact(24.0, 23.9, 22.5, False)
    assert kind == "info" and "Nicht bewiesen" in text and "22,50" in text and "23,90" in text


def test_experiment_verdicts_use_the_numbers_they_are_given():
    oc = {"nets": 600, "pairs": 25568, "viol_min": 0, "viol_cnt": 0, "viol_two": 0, "viol_loop": 0, "viol_vec": 0}
    dist = {"random_low_share": 0.515}
    kind, text = E.verdict_e1(oc, dist, (0.714, 0.008), (1, 600))
    assert kind == "success" and "600 Netzen" in text and "25 568" in text and "51,5 %" in text and "71,4 ± 0,8 %" in text and "1 von 600" in text
    assert "sind es 0 Abweichungen" in text
    kind, text = E.verdict_e1({**oc, "viol_cnt": 2}, dist, (0.7, 0.01), (0, 600))
    assert kind == "warning" and "2 Prüfungen" in text
    table = {L: {"share1": (0.70 + 0.01 * i, 0.02), "share2": (0.99 - 0.01 * i, 0.01)} for i, L in enumerate((3, 5, 6, 8, 10))}
    table["alle"] = {"share1": (0.714, 0.008), "share2": (0.953, 0.002)}
    kind, text = E.verdict_e2(table)
    assert "95,3 ± 0,2 %" in text and "bei 3 Linien 99,0 %" in text and "bei 10 Linien 95,0 %" in text and "70,0 / 71,0 / 72,0 / 73,0 / 74,0 %" in text and "Spanne 4,0 Prozentpunkte" in text
    table["alle"]["share1"] = (0.714, 0.008)
    mono = {L: {"share1": (0.70 + 0.01 * i, 0.02), "share2": (0.99 - 0.01 * i, 0.01)} for i, L in enumerate((3, 5, 6, 8, 10))}
    mono["alle"] = table["alle"]
    assert "monoton, Spanne" in E.verdict_e2(mono)[1] and "nicht monoton" not in E.verdict_e2(mono)[1]
    wavy = {**mono, 6: {"share1": (0.69, 0.02), "share2": (0.95, 0.01)}}
    assert "nicht monoton, Spanne" in E.verdict_e2(wavy)[1]
    two = {"n_forest": 5, "n_nets": 100, "forest_by_lines": {3: 3, 5: 2, 6: 0, 8: 0, 10: 0}, "forest_gap_positive": 0, "classes": [{"gap": 0.0}, {"gap": 0.1}, {"gap": 0.2}, {"gap": 0.3}, {"gap": 0.4}, {"gap": 0.5}],
           "corr_within": {3: 0.1, 5: 0.2, 6: 0.3, 8: 0.4, 10: 0.5}}
    assert "(3 mit 3 Linien, 2 mit 5 Linien)" in E.verdict_e3(two, {"b_n": 20, "b_proven": 20, "b_equal_lb2": 20})[1]
    fs = {"n_forest": 24, "n_nets": 600, "forest_by_lines": {3: 24, 5: 0, 6: 0, 8: 0, 10: 0}, "forest_gap_positive": 0, "classes": [{"gap": 0.0}, {"gap": 0.29}, {"gap": 0.4}, {"gap": 0.97}, {"gap": 1.3}, {"gap": 1.61}],
          "corr_within": {3: 0.18, 5: 0.2, 6: 0.22, 8: 0.04, 10: 0.42}}
    cp = {"b_n": 20, "b_proven": 20, "b_equal_lb2": 20}
    kind, text = E.verdict_e3(fs, cp)
    assert "24 von 600 Netzen vor (alle mit 3 Linien)" in text and "24 von 24" in text and "20 von 20 Optima" in text and "von 0,29 auf 1,61 min" in text and "0,04 bis 0,42" in text
    rows = [{"dwell": d, "same_min_mean": {1: 62, 2: 64}.get(d, 2 * d), "opt": (23.9 if d < 3 else 22.5 + 0.1 * (d - 3), 0.3)} for d in range(1, 7)]
    kind, text = E.verdict_e4(rows)
    assert "64 min, bei 3 min bei 6 min" in text and "von 23,90 auf 22,50 min (1,40 min)" in text and "zwischen 22,50 und 22,80 min" in text and "nicht eingerechnet" in text
    spl = {"share_cmin0": (0.82, 0.01), "c_std": (29.8, 0.3), "c_min": (2.6, 0.3), "lb_free": (11.9, 0.1), "lb_std": (17.8, 0.2), "lower": 600, "n": 600}
    kind, text = E.verdict_e5(spl)
    assert "82 %" in text and "29,8 → 2,6 min" in text and "11,9 min gegen 17,8 min" in text and "600 von 600" in text and "nicht gemessen" in text
