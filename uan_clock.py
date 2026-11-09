"""Schritt (a): ein Anschluss auf dem Zifferblatt. Wartezeit als Rest modulo T, die Fahrplantafel als zweiter Rechenweg, Schleifenzeit.

Kleine Einheiten mit expliziten Ein- und Ausgaben (DEMO-PLAYBOOK 1b); kein Zufall, kein Zustand. `wait_time` ist die Formel der Fall-Demo (kopiert
in uan_timetable.py); `board_wait` rechnet ohne Modulo-Operator über die Abfahrten der Zielline und dient als Gegenprobe (tests/test_oracle_uhr_anschluss.py).
"""
from __future__ import annotations

from uan_timetable import Instance, Line, opposite, turn_slack, wait_time  # noqa: F401  (wait_time: Re-Export, unverändert)


def board_departures(dep_minute: int, period: int, lo: int, hi: int) -> list[int]:
    """Fahrplantafel: alle absoluten Abfahrtszeiten dep_minute + k*period im Fenster lo..hi (Minuten seit einem frei gewählten Nullpunkt)."""
    first = dep_minute + ((lo - dep_minute + period - 1) // period) * period
    return list(range(first, hi + 1, period))


def board_wait(arr_minute: int, dep_minute: int, mt: int, period: int) -> int:
    """Wartezeit inkl. Mindestzeit über die Fahrplantafel: erste Abfahrt, die mindestens mt nach der Ankunft liegt (ohne Modulo-Operator auf der Zeit)."""
    candidates = board_departures(dep_minute, period, arr_minute + mt, arr_minute + mt + period)
    return candidates[0] - arr_minute


def board_rows(arr_minute: int, dep_minute: int, mt: int, period: int, hours: int = 2) -> list[dict]:
    """Zeilen der Fahrplantafel für die Anzeige: Abfahrten der Zielline ab einer Stunde vor der Ankunft; ok = Anschluss erreichbar."""
    rows = []
    for dep in board_departures(dep_minute, period, arr_minute - period, arr_minute + hours * period):
        rows.append({"dep": dep, "gap": dep - arr_minute, "ok": dep - arr_minute >= mt})
    return rows


def loop_time(line: Line, direction: str, k: int, s_end: int, period: int, dwell: int, tmin: int) -> int:
    """Schleifenzeit: Zeit von der Ankunft am Halt k in `direction` bis zur Abfahrt am selben Halt in der Gegenrichtung (über den Endpunkt und zurück).
    Vorwärts (f, k = 1..m): 2*dwell*(m-k) + 2*sum(run[k:]) + tmin + s_end.
    Rückwärts (b, k = 0..m-1): 2*dwell*k + 2*sum(run[:k]) + tmin + (Schlupf - s_end). s_end = Wartezeit am f-Ende (Standard: Schlupf // 2)."""
    m = len(line.stops) - 1
    slack = turn_slack(line, period, dwell, tmin)
    if direction == "f":
        if not 1 <= k <= m:
            raise ValueError("Vorwärts-Ankunft gibt es nur an den Halten 1..m")
        return 2 * dwell * (m - k) + 2 * sum(line.run[k:]) + tmin + s_end
    if not 0 <= k <= m - 1:
        raise ValueError("Rückwärts-Ankunft gibt es nur an den Halten 0..m-1")
    return 2 * dwell * k + 2 * sum(line.run[:k]) + tmin + (slack - s_end)


def default_end_wait(line: Line, period: int, dwell: int, tmin: int) -> int:
    """Standard-Aufteilung der Wende-Standzeit: der Schlupf halbiert (wie in der Fall-Demo)."""
    return turn_slack(line, period, dwell, tmin) // 2


def pair_constant(inst: Instance, key: tuple, s_a: int | None = None, s_b: int | None = None) -> int:
    """c = (Schleife der Linie A + Schleife der Linie B - 2*Mindestzeit) mod T für das Hin/Rück-Paar mit Schlüssel key = (la, da, ka, lb, db, kb),
    allein aus Fahrzeiten, Halten und Wende gerechnet (ohne die Ereigniszeiten)."""
    la, da, ka, lb, db, kb = key
    a_line, b_line = inst.lines[la], inst.lines[lb]
    sa = default_end_wait(a_line, inst.T, inst.dwell, inst.tmin) if s_a is None else s_a
    sb = default_end_wait(b_line, inst.T, inst.dwell, inst.tmin) if s_b is None else s_b
    loop_a = loop_time(a_line, da, ka, sa, inst.T, inst.dwell, inst.tmin)
    loop_b = loop_time(b_line, opposite(db), kb, sb, inst.T, inst.dwell, inst.tmin)
    return (loop_a + loop_b - 2 * inst.transfer_min) % inst.T


def pair_loops(inst: Instance, key: tuple) -> tuple[int, int]:
    """Die beiden Schleifenzeiten (Linie A in ihrer Richtung, Linie B in der Gegenrichtung ihres Umstiegs) für die Balkenanzeige."""
    la, da, ka, lb, db, kb = key
    a_line, b_line = inst.lines[la], inst.lines[lb]
    return (loop_time(a_line, da, ka, default_end_wait(a_line, inst.T, inst.dwell, inst.tmin), inst.T, inst.dwell, inst.tmin),
            loop_time(b_line, opposite(db), kb, default_end_wait(b_line, inst.T, inst.dwell, inst.tmin), inst.T, inst.dwell, inst.tmin))


def mirror_constant(c: int, dwell: int, mt: int, period: int) -> int:
    """c' des gespiegelten Paars (beide Richtungen vertauscht, gleicher Halt): c + c' = 4*(dwell - mt) (mod T). Gilt für Zwischenhalte beider Linien."""
    return (4 * (dwell - mt) - c) % period


def same_direction_constant(dwell: int, mt: int, period: int) -> int:
    """c des Gleichrichtungs-Paars (A -> B und B -> A in derselben Fahrtrichtung am selben Zwischenhalt): (2*dwell - 2*mt) mod T."""
    return (2 * (dwell - mt)) % period


def random_mean_wait(mt: int, period: int) -> float:
    """Mittlere Wartezeit bei zufälligem Versatz: der Rest (dep - arr - mt) mod T ist gleichverteilt auf 0..T-1, also mt + (T - 1) / 2."""
    return mt + (period - 1) / 2
