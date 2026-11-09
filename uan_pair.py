"""Schritt (b): das Linienpaar. Kostenkurve eines Hin/Rück-Paars über den Versatz, Gut-Menge, Spiegel- und Gleichrichtungs-Paare, Kurve einer Linienpaarung.

Eine Aktivität (Umstieg) A -> B hat bei dem Versatz u = o_B - o_A der beiden Linien die Wartezeit (u + D) mod T + mt, mit D = Abfahrt(B) - Ankunft(A) - mt bei
Versatz 0. Zwei Aktivitäten desselben Linienpaars, deren Wartezeiten sich bei u gegenläufig ändern (Hin und zurück, oder gleichgerichtet am selben Halt), haben die
Summe 2*mt + c (wenn (u + D1) mod T <= c) oder 2*mt + c + T, mit c = (D1 + D2) mod T. Kein Zufall, kein Zustand.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from uan_timetable import Instance, fixed_line_times, opposite, reciprocal_pairs


@dataclass(frozen=True)
class PairParams:
    """Zwei gegenläufige Aktivitäten zwischen den Linien la und lb: d1 = D der ersten (la -> lb), c = (D1 + D2) mod T, w1/w2 = Gewichte."""
    la: int
    lb: int
    d1: int
    c: int
    w1: float
    w2: float


def event_times_zero(inst: Instance) -> list[dict]:
    """Ereigniszeiten aller Linien bei Versatz 0 und Standard-Aufteilung."""
    return [fixed_line_times(line, inst.T, inst.dwell, inst.tmin, 0)[0] for line in inst.lines]


def activity_d(inst: Instance, key: tuple, ev0: list[dict] | None = None) -> int:
    """D der Aktivität key = (la, da, ka, lb, db, kb) bei Versatz 0: Abfahrt(lb) - Ankunft(la) - Mindestzeit (nicht auf 0..T-1 reduziert)."""
    ev0 = event_times_zero(inst) if ev0 is None else ev0
    la, da, ka, lb, db, kb = key
    return ev0[lb][("dep", db, kb)] - ev0[la][("arr", da, ka)] - inst.transfer_min


def pair_params(inst: Instance, key1: tuple, key2: tuple, ev0: list[dict] | None = None) -> PairParams:
    """Parameter eines Paars gegenläufiger Aktivitäten key1 = (la -> lb) und key2 = (lb -> la)."""
    ev0 = event_times_zero(inst) if ev0 is None else ev0
    if (key2[0], key2[3]) != (key1[3], key1[0]):
        raise ValueError("key2 muss von der Linie lb zur Linie la führen")
    d1 = activity_d(inst, key1, ev0)
    d2 = activity_d(inst, key2, ev0)
    return PairParams(key1[0], key1[3], d1 % inst.T, (d1 + d2) % inst.T, inst.transfers[key1], inst.transfers[key2])


def hin_rueck_params(inst: Instance) -> list[tuple[tuple, tuple, PairParams]]:
    """Alle Hin/Rück-Paare (zweite Aktivität = Gegenrichtung des Anschlusses) mit ihren Parametern."""
    ev0 = event_times_zero(inst)
    return [(k1, k2, pair_params(inst, k1, k2, ev0)) for k1, k2, _, _ in reciprocal_pairs(inst)]


def same_direction_params(inst: Instance) -> list[tuple[tuple, tuple, PairParams]]:
    """Alle Gleichrichtungs-Paare: A(d) -> B(d') und B(d') -> A(d) am selben Halt, beide in der Richtung, in der die Linien den Halt befahren."""
    ev0 = event_times_zero(inst)
    out, seen = [], set()
    for key in inst.transfers:
        la, da, ka, lb, db, kb = key
        rev = (lb, db, kb, la, da, ka)
        if rev in inst.transfers and rev != key and (rev, key) not in seen:
            seen.add((key, rev))
            out.append((key, rev, pair_params(inst, key, rev, ev0)))
    return out


def mirror_key(key: tuple) -> tuple:
    """Schlüssel der gespiegelten Aktivität: beide Richtungen vertauscht, gleiche Halte."""
    la, da, ka, lb, db, kb = key
    return (la, opposite(da), ka, lb, opposite(db), kb)


def pair_cost_vector(d1: int, c: int, period: int, mt: int) -> np.ndarray:
    """Summe beider Wartezeiten über den Versatz u = o_lb - o_la = 0..T-1: 2*mt + c, falls (u + D1) mod T <= c, sonst 2*mt + c + T."""
    u = np.arange(period)
    return (2 * mt + c + np.where((u + d1) % period <= c, 0, period)).astype(float)


def pair_wait_vectors(d1: int, d2: int, period: int, mt: int) -> tuple[np.ndarray, np.ndarray]:
    """Einzelne Wartezeiten beider Richtungen über u: (u + D1) mod T + mt und (-u + D2) mod T + mt."""
    u = np.arange(period)
    return ((u + d1) % period + mt).astype(float), ((-u + d2) % period + mt).astype(float)


def good_set(d1: int, c: int, period: int) -> list[int]:
    """Versätze u, bei denen das Paar auf dem kleineren Wert liegt: {u : (u + D1) mod T <= c}; es sind genau c + 1."""
    return [u for u in range(period) if (u + d1) % period <= c]


def oriented(vec: np.ndarray, flipped: bool) -> np.ndarray:
    """Kurve über u = o_lb - o_la in die Gegenorientierung u' = o_la - o_lb = -u bringen (flipped = True)."""
    if not flipped:
        return vec
    n = len(vec)
    return np.array([vec[(-u) % n] for u in range(n)])


def pair_min(c: int, mt: int) -> int:
    """Kleinste Summe eines solchen Paars: 2*mt + c, unabhängig von allen Versätzen."""
    return 2 * mt + c


def mirror_surcharge(w1: float, w2: float, period: int) -> float:
    """Zuschlag, wenn zwei Paare mit disjunkten Gut-Mengen (gespiegelte Paare, Haltezeit < Mindestzeit) einen Versatz teilen: period * min(w1, w2).
    Bei jedem Versatz liegt höchstens eines der beiden Paare auf dem kleineren Wert; das andere zahlt einen vollen Takt."""
    return period * min(w1, w2)


def good_sets_disjoint(g1: list[int], g2: list[int]) -> bool:
    return not (set(g1) & set(g2))


def mirror_disjoint_predicted(c: int, c_mirror: int, dwell: int, mt: int, period: int) -> bool | None:
    """Vorhersage des Satzes (Zwischenhalte, Haltezeit < Mindestzeit): disjunkt genau dann, wenn c + c' = T - 4*(mt - dwell). None, wenn der Satz nicht gilt
    (Haltezeit >= Mindestzeit oder 4*(mt - dwell) > T)."""
    shift = 4 * (mt - dwell)
    if dwell >= mt or shift > period:
        return None
    return c + c_mirror == period - shift


def activity_cost_vector(d: int, la_is_first: bool, period: int, mt: int) -> np.ndarray:
    """Wartezeit EINER Aktivität über u = o_b - o_a für das Linienpaar (a < b): la == a: (u + D) mod T + mt, sonst (-u + D) mod T + mt."""
    u = np.arange(period)
    return (((u if la_is_first else -u) + d) % period + mt).astype(float)


def line_pair_costs(inst: Instance) -> dict[tuple[int, int], np.ndarray]:
    """Je Linienpaar (a < b): gewichtete Summe der Wartezeiten ALLER Umstiege zwischen den beiden Linien als Funktion von u = o_b - o_a (T Werte)."""
    ev0 = event_times_zero(inst)
    out: dict[tuple[int, int], np.ndarray] = {}
    for key, w in inst.transfers.items():
        la, lb = key[0], key[3]
        a, b = (la, lb) if la < lb else (lb, la)
        out[(a, b)] = out.get((a, b), np.zeros(inst.T)) + w * activity_cost_vector(activity_d(inst, key, ev0), la == a, inst.T, inst.transfer_min)
    return out


def line_pair_bound(inst: Instance) -> float:
    """LB2: Summe über die Linienpaare des Minimums der Kostenkurve (gewichtete Wartezeit, nicht durch das Gesamtgewicht geteilt)."""
    return float(sum(v.min() for v in line_pair_costs(inst).values()))


def pairs_bound(inst: Instance) -> float:
    """LB: Summe der Hin/Rück-Paar-Untergrenzen w*(2*mt + c) (nicht durch das Gesamtgewicht geteilt); gleich `symmetric_lower_bound` der Fall-Demo."""
    return float(sum(pp.w1 * pair_min(pp.c, inst.transfer_min) for _, _, pp in hin_rueck_params(inst)))
