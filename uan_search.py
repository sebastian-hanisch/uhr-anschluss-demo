"""Lokalsuche über die Versätze der Linien (Phasen-Optimum) und die Zufalls-Referenz.

Gleiches Verfahren wie `local_search_multistart` der Fall-Demo (Koordinatenabstieg von zufälligen Startversätzen, erster bester Versatz je Linie), aber je Linie
für alle T Versätze auf einmal vektorisiert; die Ergebnisse stimmen bei gleichem Zufallsstrom überein. Zufall nur über einen übergebenen SplitMix64 (uan_rng).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from uan_pair import event_times_zero
from uan_timetable import Instance


@dataclass(frozen=True)
class SearchSettings:
    restarts: int = 40
    seed: int = 1


@dataclass(frozen=True)
class Arrays:
    """Vorrechnung: Wartezeit der Aktivität i ist ((o[lb[i]] - o[la[i]] + d[i]) mod T) + mt, Gewicht w[i]."""
    la: np.ndarray
    lb: np.ndarray
    d: np.ndarray
    w: np.ndarray
    period: int
    mt: int
    n_lines: int


def base_arrays(inst: Instance) -> Arrays:
    ev0 = event_times_zero(inst)
    la, lb, d, w = [], [], [], []
    for (a, da, ka, b, db, kb), weight in inst.transfers.items():
        la.append(a)
        lb.append(b)
        w.append(weight)
        d.append((ev0[b][("dep", db, kb)] - ev0[a][("arr", da, ka)] - inst.transfer_min) % inst.T)
    return Arrays(np.array(la, dtype=np.int64), np.array(lb, dtype=np.int64), np.array(d, dtype=np.int64), np.array(w, dtype=float),
                  inst.T, inst.transfer_min, len(inst.lines))


def total_cost(arrs: Arrays, offsets) -> float:
    """Gewichtete Summe der Wartezeiten bei den Versätzen `offsets`."""
    o = np.asarray(offsets, dtype=np.int64)
    return float((arrs.w * (((o[arrs.lb] - o[arrs.la] + arrs.d) % arrs.period) + arrs.mt)).sum())


def mean_wait(arrs: Arrays, offsets) -> float:
    tw = float(arrs.w.sum())
    return total_cost(arrs, offsets) / tw if tw else 0.0


def random_offsets(n_lines: int, period: int, rng) -> list[int]:
    return [rng.randrange(period) for _ in range(n_lines)]


def _line_costs(arrs: Arrays, o: np.ndarray, li: int) -> np.ndarray:
    """Kosten (nur die Aktivitäten an Linie li) für jeden Versatz 0..T-1 der Linie li bei festen anderen Linien."""
    T = arrs.period
    cand = np.arange(T)[:, None]
    cost = np.zeros(T)
    as_a = arrs.la == li
    if as_a.any():           # Linie li ist die Ausgangslinie: Wartezeit hängt von (o_lb - cand)
        cost += (((o[arrs.lb[as_a]][None, :] - cand + arrs.d[as_a][None, :]) % T) + arrs.mt) @ arrs.w[as_a]
    as_b = arrs.lb == li
    if as_b.any():
        cost += ((((cand - o[arrs.la[as_b]][None, :]) + arrs.d[as_b][None, :]) % T) + arrs.mt) @ arrs.w[as_b]
    return cost


def coordinate_descent(arrs: Arrays, start) -> tuple[list[int], float]:
    """Linie für Linie auf den besten Versatz setzen (bei Gleichstand der kleinste), bis sich nichts mehr verbessert."""
    o = np.array(start, dtype=np.int64)
    best = total_cost(arrs, o)
    improved = True
    while improved:
        improved = False
        for li in range(arrs.n_lines):
            costs = _line_costs(arrs, o, li)
            k = int(np.argmin(costs))
            new_total = best - costs[o[li]] + costs[k]
            if new_total < best - 1e-9:
                o[li] = k
                best = new_total
                improved = True
    return [int(x) for x in o], float(best)


def multistart(arrs: Arrays, settings: SearchSettings, rng) -> tuple[list[int], float]:
    """Mehrere Abstiege von zufälligen Startversätzen; der beste (strikt kleinere Kosten gewinnen, der frühere bleibt bei Gleichstand)."""
    best_o, best_c = None, float("inf")
    for _ in range(settings.restarts):
        o, c = coordinate_descent(arrs, random_offsets(arrs.n_lines, arrs.period, rng))
        if c < best_c:
            best_o, best_c = o, c
    return best_o, best_c


def random_mean_exact(arrs: Arrays) -> float:
    """Mittlere Wartezeit bei gleichverteiltem Versatz, exakt über alle T Versätze je Aktivität (ohne Zufall)."""
    tw = float(arrs.w.sum())
    if not tw:
        return 0.0
    T = arrs.period
    per = np.array([np.mean((np.arange(T) + dd) % T) + arrs.mt for dd in arrs.d])
    return float((arrs.w * per).sum() / tw)


def random_mean_draws(arrs: Arrays, n: int, rng) -> float:
    """Mittel über n zufällige Versatzvektoren (Gegenprobe zu `random_mean_exact`)."""
    tw = float(arrs.w.sum())
    return float(np.mean([total_cost(arrs, random_offsets(arrs.n_lines, arrs.period, rng)) / tw for _ in range(n)])) if tw else 0.0
