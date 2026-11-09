"""Gemeinsame Fixtures: die von Hand gerechnete Mini-Instanz (DEMO-PLAYBOOK §1b) und ein unabhängiger Fahrplansimulator als Orakel.

Mini-Instanz: Linie A mit den Halten 0-1-2 und den Fahrzeiten 10, 10; Linie B mit den Halten 3-1-4 und den Fahrzeiten 8, 12; Umsteigehalt ist Halt 1 (Index 1 in beiden Linien).
Haltezeit 2, kürzeste Wende 4, T = 60, Mindestzeit 3. A: c0 = 2·20 + 2·2·1 + 2·4 = 52, Schlupf 8, je 4 min Wartezeit an jedem Ende.
A vorwärts (Versatz 0): ab Halt 0 um 0, an Halt 1 um 10, ab 12, an Halt 2 um 22, ab (Rückrichtung) 22 + 4 + 4 = 30, an Halt 1 um 40, ab 42, an Halt 0 um 52.
B: ab 0, an Halt 1 um 8, ab 10, an Halt 2 um 22, ab 30, an Halt 1 um 42, ab 44, an Halt 0 um 52.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uan_timetable import Instance, Line  # noqa: E402

# Umstiege (Ankunft der einen, Abfahrt der anderen Linie): Schlüssel (la, da, ka, lb, db, kb) -> Gewicht
HIN_RUECK = {(0, "f", 1, 1, "f", 1): 1.0, (1, "b", 1, 0, "b", 1): 1.0}      # A vorwärts -> B vorwärts und B rückwärts -> A rückwärts
SPIEGEL = {(0, "b", 1, 1, "b", 1): 1.0, (1, "f", 1, 0, "f", 1): 1.0}        # beide Richtungen vertauscht
GLEICHRICHTUNG = {(0, "f", 1, 1, "f", 1): 1.0, (1, "f", 1, 0, "f", 1): 1.0}  # A -> B und B -> A, beide vorwärts


def _mini(transfers):
    return Instance(60, [Line([0, 1, 2], [10, 10]), Line([3, 1, 4], [8, 12])], dict(transfers))


@pytest.fixture
def mini():
    return _mini(HIN_RUECK)


@pytest.fixture
def mini_both():
    return _mini({**HIN_RUECK, **SPIEGEL})


@pytest.fixture
def mini_same():
    return _mini(GLEICHRICHTUNG)


# ------------------------------------------------------------------ unabhängiger Simulator (Orakel)
def sim_slack(line, period, dwell, tmin):
    """Kleinste Wartezeit an den Enden, bei der der Zyklus ein Vielfaches des Taktes wird (gesucht, nicht per Modulo gerechnet)."""
    m = len(line.stops) - 1
    base = 2 * sum(line.run) + 2 * dwell * (m - 1) + 2 * tmin
    s = 0
    while (base + s) % period:
        s += 1
    return s


def sim_events(line, period, dwell, tmin, offset, s_end=None):
    """Ein Fahrzeug fährt einen Zyklus: Liste (Art, Richtung, Halt, absolute Minute). Der Takt entsteht, indem alle Zeiten zusätzlich um k·T verschoben gelten."""
    m = len(line.stops) - 1
    slack = sim_slack(line, period, dwell, tmin)
    s_end = slack // 2 if s_end is None else s_end
    t = offset
    out = [("dep", "f", 0, t)]
    for k in range(1, m + 1):
        t += line.run[k - 1]
        out.append(("arr", "f", k, t))
        if k < m:
            t += dwell
            out.append(("dep", "f", k, t))
    t += tmin + s_end
    out.append(("dep", "b", m, t))
    for k in range(m - 1, -1, -1):
        t += line.run[k]
        out.append(("arr", "b", k, t))
        if k > 0:
            t += dwell
            out.append(("dep", "b", k, t))
    return out


def sim_time(events, kind, direction, k):
    return next(t for (a, d, s, t) in events if (a, d, s) == (kind, direction, k))


def sim_wait(arr_events, key, dep_events, period, mt):
    """Wartezeit eines Umstiegs über die Fahrplantafel: erste Abfahrt (Zeit + k·T), die mindestens mt nach der Ankunft liegt."""
    la, da, ka, lb, db, kb = key
    t_arr = sim_time(arr_events, "arr", da, ka)
    t_dep = sim_time(dep_events, "dep", db, kb)
    best = None
    for k in range(-12, 13):
        gap = t_dep + k * period - t_arr
        if gap >= mt and (best is None or gap < best):
            best = gap
    return best
