"""Vorgerechnete Messreihe (data/uan_results.json, erzeugt mit tools/sweep.py): Laden und Auswerten.

Die App rechnet die Messreihe nie live. „a ± s“ heißt: Mittel der vier Block-Mittel ± Standardabweichung über die vier Blöcke (ein Block = 30 Netze je Linienzahl).
Alle Zählungen stehen als „k von m“; die Zahlen in README und App kommen aus diesen Funktionen und werden in tests/test_claims.py nachgerechnet.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

import uan_constants as C

ROOT = Path(__file__).resolve().parent


def load_results(path=None) -> dict:
    return json.loads(Path(path or ROOT / C.RESULTS_FILE).read_text(encoding="utf-8"))


def generator_hash() -> str:
    """Hash der Dateien, die die Netze festlegen; steht er nicht mehr so in der Datei, ist die Messreihe veraltet (tests/test_results.py)."""
    h = hashlib.sha256()
    for name in ("uan_rng.py", "uan_network.py", "uan_timetable.py"):
        h.update((ROOT / name).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def nets(res: dict, lines: int | None = None) -> list[dict]:
    if lines is None:
        return [r for k in res["nets"] for r in res["nets"][k]]
    return res["nets"][str(lines)]


def block_ms(rows: list[dict], f) -> tuple[float, float]:
    """Mittel der Block-Mittel und Standardabweichung (ddof 1) über die Blöcke."""
    by: dict = defaultdict(list)
    for r in rows:
        by[r["block"]].append(f(r))
    means = [float(np.mean(v)) for _, v in sorted(by.items())]
    return float(np.mean(means)), (float(np.std(means, ddof=1)) if len(means) > 1 else float("nan"))


def pm(t: tuple[float, float], digits: int = 2) -> str:
    return f"{t[0]:.{digits}f} ± {t[1]:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------- E1: Kopplung und Orakel
def oracle_counts(res: dict) -> dict:
    """Zählungen der Fahrplantafel-Prüfung über alle Netze: Paare, Abweichungen von Untergrenze 2*mt + c, Zahl c + 1, Zwei-Werte-Regel, Schleifenzeit, Kurve."""
    rows = nets(res)
    return {"nets": len(rows), "pairs": sum(r["n_pairs"] for r in rows), "viol_min": sum(r["viol_min"] for r in rows), "viol_cnt": sum(r["viol_cnt"] for r in rows),
            "viol_two": sum(r["viol_two"] for r in rows), "viol_loop": sum(r["viol_loop"] for r in rows), "viol_vec": sum(r["viol_vec"] for r in rows),
            "lb_ok": sum(1 for r in rows if r["lb_ok"]), "all_paired": sum(1 for r in rows if r["all_paired"]),
            "rand_exact_ok": sum(1 for r in rows if abs(r["rand_exact"] - (C.DEFAULT_TRANSFER_MIN + (C.T - 1) / 2)) < 1e-9),
            "rand_300_min": min(r["rand_300"] for r in rows), "rand_300_max": max(r["rand_300"] for r in rows)}


def c_distribution(res: dict) -> dict:
    """Verteilung der Paar-Konstante c: Zehnerklassen, Mittel, Anteil c = 0, Anteil der zufälligen Versätze auf dem kleineren Wert ((c + 1) / T)."""
    c = np.array([x for r in nets(res) for x in r["c"]])
    classes = [float(np.mean((c >= a) & (c < a + 10))) for a in range(0, C.T, 10)]
    return {"n": int(len(c)), "mean": float(c.mean()), "share_zero": float(np.mean(c == 0)), "classes": classes, "random_low_share": float(np.mean((c + 1) / C.T)),
            "values": c}


def lb_share(res: dict, lines: int | None = None) -> tuple[float, float]:
    """Anteil des Aufschlags über die Mindestzeit, den die Untergrenze je Hin/Rück-Paar erklärt (Mittel der Netz-Anteile, Definition der Fall-Demo)."""
    mt = C.DEFAULT_TRANSFER_MIN
    return block_ms(nets(res, lines), lambda r: (r["lb"] - mt) / (r["opt"] - mt))


def lb2_share(res: dict, lines: int | None = None) -> tuple[float, float]:
    mt = C.DEFAULT_TRANSFER_MIN
    return block_ms(nets(res, lines), lambda r: (r["lb2"] - mt) / (r["opt"] - mt))


def bound_reached(res: dict) -> tuple[int, int]:
    """In wie vielen Netzen erreicht das Phasen-Optimum die Paar-Untergrenze (Opt - LB < 1e-9)?"""
    rows = nets(res)
    return sum(1 for r in rows if r["opt"] - r["lb"] < 1e-9), len(rows)


# ---------------------------------------------------------------- E2: drei Untergrenzen nach Linienzahl, Zerlegung
def bounds_row(res: dict, lines: int | None) -> dict:
    rows = nets(res, lines)
    mt = C.DEFAULT_TRANSFER_MIN
    out = {"n": len(rows), "rand": block_ms(rows, lambda r: r["rand_exact"]), "opt": block_ms(rows, lambda r: r["opt"]), "lb": block_ms(rows, lambda r: r["lb"]),
           "lb2": block_ms(rows, lambda r: r["lb2"]), "share1": lb_share(res, lines), "share2": lb2_share(res, lines),
           "pair": block_ms(rows, lambda r: r["lb"] - mt), "line_pair": block_ms(rows, lambda r: r["lb2"] - r["lb"]),
           "cycles": block_ms(rows, lambda r: r["opt"] - r["lb2"]), "gain": block_ms(rows, lambda r: r["rand_exact"] - r["opt"]),
           "gain_share": block_ms(rows, lambda r: (r["rand_exact"] - r["opt"]) / (r["rand_exact"] - r["lb2"]))}
    return out


def bounds_table(res: dict) -> dict:
    """{Linienzahl oder 'alle': Zeile}."""
    return {**{L: bounds_row(res, L) for L in C.SWEEP_LINES}, "alle": bounds_row(res, None)}


# ---------------------------------------------------------------- E3: Wald gegen Kreise
RANK_CLASSES = ((0, 0), (1, 2), (3, 5), (6, 10), (11, 20), (21, 999))


def forest_summary(res: dict) -> dict:
    rows = nets(res)
    forest = [r for r in rows if r["rank"] == 0]
    nonf = [r for r in rows if r["rank"] > 0]
    gaps = [r["opt"] - r["lb2"] for r in forest]
    classes = []
    for a, b in RANK_CLASSES:
        rs = [r for r in rows if a <= r["rank"] <= b]
        if rs:
            classes.append({"lo": a, "hi": b, "n": len(rs), "equal": sum(1 for r in rs if r["opt"] - r["lb2"] < 1e-6),
                            "gap": float(np.mean([r["opt"] - r["lb2"] for r in rs]))})

    def corr(x, y):
        return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and np.std(x) > 0 and np.std(y) > 0 else float("nan")

    within = {L: corr([r["rank"] for r in nets(res, L)], [r["opt"] - r["lb2"] for r in nets(res, L)]) for L in C.SWEEP_LINES}
    return {"n_forest": len(forest), "n_nets": len(rows), "forest_by_lines": {L: sum(1 for r in forest if r["L"] == L) for L in C.SWEEP_LINES},
            "forest_gap_max": max(gaps) if gaps else float("nan"), "forest_gap_positive": sum(1 for g in gaps if g > 1e-6),
            "nonforest_equal": sum(1 for r in nonf if r["opt"] - r["lb2"] < 1e-6), "n_nonforest": len(nonf), "classes": classes, "corr_within": within,
            "corr_all": corr([r["rank"] for r in rows], [r["opt"] - r["lb2"] for r in rows]),
            "corr_rank_opt": corr([r["rank"] for r in rows], [r["opt"] for r in rows]), "corr_rank_opt_lb": corr([r["rank"] for r in rows], [r["opt"] - r["lb"] for r in rows])}


def cp_summary(res: dict) -> dict:
    a = [r for r in res["cp"] if r["teil"] == "A"]
    b = [r for r in res["cp"] if r["teil"] == "B"]
    worse = [r["ls"] - r["cp"] for r in a if r["ls"] > r["cp"] + 1e-6]
    return {"a_n": len(a), "a_proven": sum(1 for r in a if r["proven"]), "a_ls_worse": len(worse), "a_ls_better": sum(1 for r in a if r["ls"] < r["cp"] - 1e-6),
            "a_max_dev": max([r["ls"] - r["cp"] for r in a]), "b_n": len(b), "b_proven": sum(1 for r in b if r["proven"]),
            "b_equal_lb2": sum(1 for r in b if abs(r["cp"] - r["lb2"]) < 1e-6), "b_forest_offsets_equal_lb2": sum(1 for r in b if abs(r["forest_offsets_cost"] - r["lb2"]) < 1e-9),
            "b_ls_equal_lb2": sum(1 for r in b if abs(r["ls"] - r["lb2"]) < 1e-6), "b_max_dev": max(abs(r["cp"] - r["lb2"]) for r in b)}


# ---------------------------------------------------------------- Spiegel- und Gleichrichtungs-Paare (Haltezeit 2, Mindestzeit 3)
def mirror_summary(res: dict) -> dict:
    rows = nets(res)
    keys = ("n", "sum_ok", "n_low", "disjoint_low", "n_high", "overlap_high", "ov_high_total", "other")
    m = {k: sum(r["mirror"][k] for r in rows) for k in keys}
    m["overlap_mean_high"] = m["ov_high_total"] / m["n_high"] if m["n_high"] else float("nan")
    return m


def same_summary(res: dict) -> dict:
    rows = nets(res)
    mins: dict = defaultdict(int)
    for r in rows:
        for k, v in r["same"]["mins"].items():
            mins[int(k)] += v
    return {"pairs": sum(r["same"]["n"] for r in rows), "act_in": sum(r["same"]["act_in"] for r in rows), "act_total": sum(r["n_act"] for r in rows),
            "nets_with": sum(1 for r in rows if r["same"]["n"] > 0), "nets": len(rows), "mins": dict(mins)}


# ---------------------------------------------------------------- E4: Haltezeit-Reihe
def dwell_rows(res: dict) -> list[dict]:
    """Je Haltezeit d: kleinste Summe der Gleichrichtungs-Paare (Mittel über Netze mit Paar), LB, LB2, Phasen-Optimum (a ± s), Spiegel-Zählung."""
    out = []
    for d in range(C.DWELL_MIN, C.DWELL_MAX + 1):
        rs = [r for r in res["dwell"] if r["dwell"] == d]
        sets = sorted({v for r in rs for v in r["same_min_set"]})
        with_pair = [r for r in rs if r["same_min_mean"] is not None]
        out.append({"dwell": d, "n": len(rs), "opt": block_ms(rs, lambda r: r["opt"]), "lb": block_ms(rs, lambda r: r["lb"]), "lb2": block_ms(rs, lambda r: r["lb2"]),
                    "lb2_minus_lb": block_ms(rs, lambda r: r["lb2"] - r["lb"]), "same_min_set": sets,
                    "same_min_mean": float(np.mean([r["same_min_mean"] for r in with_pair])) if with_pair else float("nan"),
                    "share2": block_ms(rs, lambda r: (r["lb2"] - C.DEFAULT_TRANSFER_MIN) / (r["opt"] - C.DEFAULT_TRANSFER_MIN)),
                    "mirror_n": sum(r["mirror_n"] for r in rs), "mirror_disjoint": sum(r["mirror_disjoint"] for r in rs),
                    "mirror_pred_disjoint": sum(r["mirror_pred_disjoint"] for r in rs), "mirror_mismatch": sum(r["mirror_mismatch"] for r in rs),
                    "check": [r["check"] for r in rs if "check" in r]})
    return out


# ---------------------------------------------------------------- E5: Brücke zur freien Aufteilung der Wende-Standzeit
def split_summary(res: dict) -> dict:
    rows = res["split"]
    return {"n": len(rows), "lb_std": block_ms(rows, lambda r: r["lb_std"]), "lb_free": block_ms(rows, lambda r: r["lb_free"]),
            "lower": sum(1 for r in rows if r["lb_free"] < r["lb_std"] - 1e-9), "share_cmin0": block_ms(rows, lambda r: r["share_cmin0"]),
            "c_std": block_ms(rows, lambda r: r["c_std_mean"]), "c_min": block_ms(rows, lambda r: r["c_min_mean"]),
            "slack": block_ms(rows, lambda r: r["mean_slack"])}
