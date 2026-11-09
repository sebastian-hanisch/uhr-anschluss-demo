"""Schritt (c): der Liniengraph. Linien als Knoten, Linienpaare mit mindestens einem Umstieg als Kanten; Kreisrang, aufspannender Wald, Wald-Fahrplan.

Satz (Wald): Ist der Liniengraph ein Wald, sind die Versätze der Linienpaare unabhängig wählbar; jede Kostenkurve erreicht ihr Minimum, also ist das Optimum
der Phasen gleich der Linienpaar-Untergrenze LB2. `forest_offsets` baut diese Versätze (Breitensuche, Wurzel 0): ein Beweis durch Konstruktion.
"""
from __future__ import annotations

from collections import deque
from dataclasses import replace

import numpy as np

from uan_pair import line_pair_costs
from uan_timetable import Instance


def line_edges(inst: Instance) -> dict[tuple[int, int], float]:
    """Kanten des Liniengraphen (a < b) mit dem Gesamtgewicht der Umstiege zwischen den beiden Linien (nur Gewicht > 0)."""
    out: dict[tuple[int, int], float] = {}
    for (la, _, _, lb, _, _), w in inst.transfers.items():
        if w > 0 and la != lb:
            e = (min(la, lb), max(la, lb))
            out[e] = out.get(e, 0.0) + w
    return out


def components(n_lines: int, edges) -> int:
    parent = list(range(n_lines))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    return len({find(x) for x in range(n_lines)})


def cycle_rank(n_lines: int, edges) -> int:
    """Kreisrang des Liniengraphen: Kanten - Knoten + Zusammenhangskomponenten (0 genau bei einem Wald)."""
    edges = list(edges)
    return len(edges) - n_lines + components(n_lines, edges)


def spanning_forest(n_lines: int, weights: dict[tuple[int, int], float]) -> list[tuple[int, int]]:
    """Aufspannender Wald nach Kruskal: Kanten nach Gewicht absteigend (Gleichstand: kleinere Kante zuerst), eine Kante nur, wenn sie keinen Kreis schließt."""
    parent = list(range(n_lines))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    keep = []
    for e in sorted(weights, key=lambda e: (-weights[e], e)):
        ra, rb = find(e[0]), find(e[1])
        if ra != rb:
            parent[ra] = rb
            keep.append(e)
    return keep


def forest_instance(inst: Instance) -> tuple[Instance, list[tuple[int, int]]]:
    """Netz, in dem nur die Umstiege der Linienpaare des aufspannenden Waldes bleiben (Wald-Schalter der App)."""
    keep = spanning_forest(len(inst.lines), line_edges(inst))
    kept = set(keep)
    transfers = {k: w for k, w in inst.transfers.items() if (min(k[0], k[3]), max(k[0], k[3])) in kept}
    return replace(inst, transfers=transfers), keep


def forest_offsets(inst: Instance) -> list[int]:
    """Versätze, die in einem Wald jedes Linienpaar auf sein Minimum setzen; Kostenkurven aus dem Netz, Rest siehe `forest_offsets_from_costs`."""
    return forest_offsets_from_costs(len(inst.lines), line_pair_costs(inst), inst.T)


def forest_offsets_from_costs(n: int, costs: dict, period: int) -> list[int]:
    """Versätze, die in einem Wald jedes Linienpaar auf sein Minimum setzen (Breitensuche je Komponente, Wurzel 0, Kind = Elternversatz + argmin u).
    `costs[(a, b)]` ist die Kostenkurve über u = o_b - o_a. Nur für einen Wald gültig (sonst ValueError); isolierte Linien bleiben bei 0."""
    if cycle_rank(n, costs) != 0:
        raise ValueError("kein Wald: der Liniengraph hat einen Kreis")
    adj = {i: [] for i in range(n)}
    for a, b in costs:
        adj[a].append(b)
        adj[b].append(a)
    offsets = [0] * n
    seen = [False] * n
    for root in range(n):
        if seen[root]:
            continue
        seen[root] = True
        queue = deque([root])
        while queue:
            x = queue.popleft()
            for y in adj[x]:
                if seen[y]:
                    continue
                seen[y] = True
                a, b = (x, y) if x < y else (y, x)
                u_best = int(np.argmin(costs[(a, b)]))          # u = o_b - o_a
                offsets[y] = (offsets[x] + (u_best if y == b else -u_best)) % period
                queue.append(y)
    return offsets
