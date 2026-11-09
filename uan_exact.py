"""Exaktes Phasen-Optimum per CP-SAT (OR-Tools), nur auf Knopfdruck und mit Zeitlimit; „nicht bewiesen“, wenn das Limit zuerst kommt.

Modell: Versatz o_i in 0..T-1 je Linie (Linie 0 fest auf 0, denn eine gemeinsame Verschiebung ändert nichts), je Umstieg x = o_lb - o_la + D + T*p mit x in 0..T-1;
Ziel: gewichtete Summe der x (Gewichte mit 2 multipliziert, damit ganzzahlig: die Gewichte sind Vielfache von 0,5).
"""
from __future__ import annotations

from dataclasses import dataclass

from uan_search import Arrays
from uan_timetable import Instance


@dataclass(frozen=True)
class ExactResult:
    status: str            # "OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN" ...
    proven: bool
    mean_wait: float       # mittlere Wartezeit der besten gefundenen Lösung (inkl. Mindestzeit)
    bound_wait: float      # untere Schranke in derselben Einheit
    offsets: tuple[int, ...]
    seconds: float


def solve_phases(arrs: Arrays, time_limit: float = 20.0, workers: int = 2, hint=None, seed: int = 1) -> ExactResult:
    """Optimum der Versätze (Ganzzahlmodell). `hint`: Startlösung (z. B. aus der Lokalsuche)."""
    from ortools.sat.python import cp_model

    T = arrs.period
    n = arrs.n_lines
    two_w = [int(round(2 * float(w))) for w in arrs.w]
    if any(abs(2 * float(w) - tw) > 1e-9 for w, tw in zip(arrs.w, two_w)):
        raise ValueError("Gewichte müssen Vielfache von 0,5 sein")
    model = cp_model.CpModel()
    o = [model.NewIntVar(0, T - 1, f"o{i}") for i in range(n)]
    model.Add(o[0] == 0)
    xs = []
    for i in range(len(two_w)):
        x = model.NewIntVar(0, T - 1, f"x{i}")
        p = model.NewIntVar(-2, 2, f"p{i}")
        model.Add(o[int(arrs.lb[i])] - o[int(arrs.la[i])] + int(arrs.d[i]) + T * p == x)
        xs.append(x)
    model.Minimize(sum(two_w[i] * xs[i] for i in range(len(xs))))
    if hint is not None:
        for i in range(n):
            model.AddHint(o[i], (hint[i] - hint[0]) % T)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    solver.parameters.num_workers = int(workers)
    solver.parameters.random_seed = int(seed)
    status = solver.Solve(model)
    name = solver.StatusName(status)
    tw = float(arrs.w.sum())
    if name not in ("OPTIMAL", "FEASIBLE") or not tw:
        return ExactResult(name, False, float("nan"), float("nan"), (), solver.WallTime())
    return ExactResult(name, name == "OPTIMAL", solver.ObjectiveValue() / 2 / tw + arrs.mt, solver.BestObjectiveBound() / 2 / tw + arrs.mt,
                       tuple(int(solver.Value(v)) for v in o), solver.WallTime())


def solve_instance(inst: Instance, time_limit: float = 20.0, workers: int = 2, hint=None) -> ExactResult:
    from uan_search import base_arrays
    return solve_phases(base_arrays(inst), time_limit, workers, hint)
