"""Kennzahlen, Ansichten und Verdikte der Demo „Uhr und Anschluss“.

Alle Verdikte sind reine Funktionen `verdict_*(...) -> (Art, Text)`; die App ruft `getattr(st, Art)(Text)`, tests/test_verdicts.py prüft Schwellen und jede Zahl im Text.
Eine Analyse bekommt ein `Settings`-Objekt (nur mit Schlüsselwörtern), nie Positionsargumente.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

import uan_clock as K
import uan_constants as C
import uan_forest as F
import uan_pair as P
import uan_search as S
from uan_network import build_valid_instance
from uan_rng import SplitMix64
from uan_timetable import Instance


def fmt(x: float, digits: int = 1) -> str:
    """Zahl mit Dezimalkomma (Anzeige)."""
    return f"{x:.{digits}f}".replace(".", ",")


@dataclass(frozen=True, kw_only=True)
class Settings:
    lines: int = C.DEFAULT_LINES
    seed: int = C.DEFAULT_SEED
    dwell: int = C.DEFAULT_DWELL
    mt: int = C.DEFAULT_TRANSFER_MIN
    forest: bool = False


@dataclass(frozen=True)
class NetAnalysis:
    settings: Settings
    inst: Instance                       # Netz mit Haltezeit und Mindestzeit der Einstellungen (bei Wald-Schalter: nur der Wald)
    used_seed: int
    n_lines: int
    n_act: int
    total_weight: float
    edges: dict                          # Liniengraph: (a, b) -> Gewicht
    rank: int                            # Kreisrang
    comps: int
    forest_edges: tuple                  # aufspannender Wald (Kanten)
    rand_exact: float                    # mittlere Wartezeit bei zufälligem Versatz (exakt)
    rand_draws: float                    # Mittel über C.RANDOM_SAMPLES Ziehungen
    lb: float                            # Stufe 1: Untergrenze je Hin/Rück-Paar
    lb2: float                           # Stufe 2: Untergrenze je Linienpaar
    opt: float                           # Phasen-Optimum der Lokalsuche
    opt_offsets: tuple
    line_costs: dict = field(repr=False, default_factory=dict)

    @property
    def parts(self) -> dict:
        """Zerlegung des Zufalls-Aufschlags (Zufall - Mindestzeit) in vier Anteile; die Summe ist der Aufschlag."""
        mt = self.inst.transfer_min
        return {"pair": self.lb - mt, "line_pair": self.lb2 - self.lb, "cycles": self.opt - self.lb2, "gain": self.rand_exact - self.opt}

    @property
    def is_forest(self) -> bool:
        return self.rank == 0


def build_net(settings: Settings) -> tuple[Instance, int]:
    """Netz der Fall-Demo-Erzeugung mit den Haltezeiten und der Mindestzeit der Einstellungen; Rückgabe (Instanz, tatsächlich verwendeter Seed)."""
    inst, _, _, used = build_valid_instance(settings.lines, settings.seed)
    return replace(inst, dwell=settings.dwell, transfer_min=settings.mt), used


def analyse_instance(inst: Instance, settings: Settings, used_seed: int) -> NetAnalysis:
    arrs = S.base_arrays(inst)
    tw = float(arrs.w.sum())
    edges = F.line_edges(inst)
    n = len(inst.lines)
    opt_o, opt_c = S.multistart(arrs, S.SearchSettings(restarts=C.SEARCH_RESTARTS), SplitMix64(1_000_003 * used_seed + settings.lines))
    costs = P.line_pair_costs(inst)
    rng = SplitMix64(1_000_003 * used_seed + settings.lines + 77)
    return NetAnalysis(
        settings=settings, inst=inst, used_seed=used_seed, n_lines=n, n_act=len(inst.transfers), total_weight=tw, edges=edges,
        rank=F.cycle_rank(n, edges), comps=F.components(n, edges), forest_edges=tuple(F.spanning_forest(n, edges)),
        rand_exact=S.random_mean_exact(arrs), rand_draws=S.random_mean_draws(arrs, C.RANDOM_SAMPLES, rng),
        lb=P.pairs_bound(inst) / tw, lb2=sum(float(v.min()) for v in costs.values()) / tw, opt=opt_c / tw, opt_offsets=tuple(opt_o),
        line_costs=costs)


def analyse(settings: Settings) -> NetAnalysis:
    inst, used = build_net(settings)
    if settings.forest:
        inst, _ = F.forest_instance(inst)
    return analyse_instance(inst, settings, used)


# ---------------------------------------------------------------- Schritt (a): ein Anschluss auf dem Zifferblatt
@dataclass(frozen=True)
class Connection:
    arr: int            # Ankunftsminute der Linie A
    dep: int            # Abfahrtsminute der Linie B (nach Versatz)
    mt: int
    wait_mod: int       # Rechenweg 1: Rest modulo T
    wait_board: int     # Rechenweg 2: Fahrplantafel
    earliest: int       # früheste Abfahrtsminute (Ankunft + Mindestzeit, modulo T)
    curve: tuple        # Wartezeit über alle T Versätze der Linie B (Sägezahn)
    mean_random: float  # Mittel der Kurve = mt + (T - 1) / 2


def connection(arr: int, shift: int, mt: int, period: int = C.T, base_dep: int = C.B_BASE_DEP) -> Connection:
    dep = (base_dep + shift) % period
    curve = tuple(K.wait_time(arr, (base_dep + u) % period, mt, period) for u in range(period))
    return Connection(arr % period, dep, mt, K.wait_time(arr, dep, mt, period), K.board_wait(arr, dep, mt, period), (arr + mt) % period, curve,
                      float(np.mean(curve)))


def verdict_connection(wait: int, mt: int, period: int = C.T) -> tuple[str, str]:
    """Verdikt des Anschlusses auf dem Zifferblatt."""
    if wait == mt:
        return "success", f"Der Zug fährt genau zur frühesten möglichen Minute ab: Wartezeit **{wait} min**, das ist die Mindest-Umsteigezeit und nicht zu unterbieten."
    if wait == period + mt - 1:
        return "warning", (f"Der Zug ist gerade weg: Wartezeit **{wait} min**. Eine Minute später abgefahren, wäre der Anschluss erreicht worden "
                           f"(Wartezeit {mt} min); so gilt der Zug der nächsten Stunde ({wait - mt} min über der Mindestzeit).")
    return "info", f"Wartezeit **{wait} min**, davon {mt} min Mindestzeit und {wait - mt} min Warten auf den nächsten Zug."


# ---------------------------------------------------------------- Schritt (b): Linienpaar
@dataclass(frozen=True)
class MirrorView:
    key: tuple
    params: P.PairParams
    good: tuple
    c_formula: int
    disjoint: bool
    predicted: bool | None


@dataclass(frozen=True)
class PairView:
    line_pair: tuple                 # (a, b)
    key1: tuple
    key2: tuple
    params: P.PairParams
    loops: tuple                     # (Schleife A, Schleife B)
    c_loops: int                     # c allein aus den Schleifenzeiten
    good: tuple
    curve: tuple                     # Summe beider Wartezeiten über u = o_lb - o_la
    wait_hin: tuple
    wait_rueck: tuple
    mirror: MirrorView | None
    joint_curve: tuple | None        # gewichtete Summe von Paar und Spiegelpaar über u (Orientierung la -> lb des Paars)
    joint_min: float | None
    separate_min: float | None       # Summe der beiden Einzel-Untergrenzen (gewichtet)
    surcharge: float | None          # joint_min - separate_min


def line_pair_list(a: NetAnalysis) -> list[dict]:
    """Linienpaare des Netzes, schwerste zuerst: Gewicht, Zahl der Umstiege, Minimum der Kurve."""
    counts: dict = {}
    for key in a.inst.transfers:
        e = (min(key[0], key[3]), max(key[0], key[3]))
        counts[e] = counts.get(e, 0) + 1
    out = [{"pair": e, "weight": a.edges[e], "activities": counts[e], "minimum": float(a.line_costs[e].min())} for e in a.edges]
    out.sort(key=lambda d: (-d["weight"], d["pair"]))
    return out


def hin_rueck_of(a: NetAnalysis, line_pair: tuple) -> list[tuple[tuple, tuple, P.PairParams]]:
    return [t for t in P.hin_rueck_params(a.inst) if (min(t[2].la, t[2].lb), max(t[2].la, t[2].lb)) == line_pair]


def pair_view(a: NetAnalysis, line_pair: tuple, index: int) -> PairView:
    inst = a.inst
    pairs = hin_rueck_of(a, line_pair)
    k1, k2, pp = pairs[index % len(pairs)]
    T, mt = inst.T, inst.transfer_min
    ev0 = P.event_times_zero(inst)
    d2 = P.activity_d(inst, k2, ev0)
    wh, wr = P.pair_wait_vectors(pp.d1, d2, T, mt)
    loops = K.pair_loops(inst, k1)
    mirror = None
    joint = joint_min = separate = surcharge = None
    m1, m2 = P.mirror_key(k1), P.mirror_key(k2)          # das gespiegelte Paar: beide Richtungen vertauscht, gleiche Halte
    if m1 in inst.transfers and m2 in inst.transfers:
        mpp = P.pair_params(inst, m1, m2, ev0)
        g1, g2 = P.good_set(pp.d1, pp.c, T), P.good_set(mpp.d1, mpp.c, T)
        mirror = MirrorView(m1, mpp, tuple(g2), K.mirror_constant(pp.c, inst.dwell, mt, T), P.good_sets_disjoint(g1, g2),
                            P.mirror_disjoint_predicted(pp.c, mpp.c, inst.dwell, mt, T))
        joint_v = pp.w1 * P.pair_cost_vector(pp.d1, pp.c, T, mt) + mpp.w1 * P.pair_cost_vector(mpp.d1, mpp.c, T, mt)
        joint = tuple(float(x) for x in joint_v)
        joint_min = float(joint_v.min())
        separate = float(pp.w1 * P.pair_min(pp.c, mt) + mpp.w1 * P.pair_min(mpp.c, mt))
        surcharge = joint_min - separate
    return PairView(line_pair, k1, k2, pp, loops, K.pair_constant(inst, k1), tuple(P.good_set(pp.d1, pp.c, T)),
                    tuple(float(x) for x in P.pair_cost_vector(pp.d1, pp.c, T, mt)), tuple(float(x) for x in wh), tuple(float(x) for x in wr),
                    mirror, joint, joint_min, separate, surcharge)


def same_direction_of(a: NetAnalysis, line_pair: tuple | None = None) -> list[tuple[tuple, tuple, P.PairParams]]:
    out = P.same_direction_params(a.inst)
    if line_pair is not None:
        out = [t for t in out if (min(t[2].la, t[2].lb), max(t[2].la, t[2].lb)) == line_pair]
    return out


def dwell_table(inst: Instance, key: tuple, rev: tuple, dwells=range(C.DWELL_MIN, C.DWELL_MAX + 1)) -> list[dict]:
    """Kleinste Summe eines Gleichrichtungs-Paars für jede Haltezeit (Fahrplan jeweils neu aus den Ereigniszeiten gerechnet, nicht aus der Formel).
    Gilt für Zwischenhalte beider Linien; die längere Haltezeit verlängert die Fahrzeit der Durchfahrenden, das ist NICHT eingerechnet."""
    rows = []
    for d in dwells:
        i2 = replace(inst, dwell=d)
        pp = P.pair_params(i2, key, rev)
        rows.append({"dwell": d, "c": pp.c, "min_sum": P.pair_min(pp.c, inst.transfer_min), "formula_c": K.same_direction_constant(d, inst.transfer_min, inst.T)})
    return rows


def verdict_dwell(rows: list[dict], current: int, mt: int) -> tuple[str, str]:
    """Verdikt der Haltezeit-Tabelle eines Gleichrichtungs-Paars."""
    cur = next(r for r in rows if r["dwell"] == current)
    best = min(rows, key=lambda r: (r["min_sum"], r["dwell"]))
    if cur["min_sum"] == best["min_sum"]:
        return "success", (f"Bei {current} min Haltezeit liegt die kleinste Summe des gleichgerichteten Umsteigepaars bei **{cur['min_sum']} min**: "
                           f"das ist der kleinste Wert der Tabelle. Voraussetzung: Haltezeit gleich Mindest-Umsteigezeit ({mt} min), die Fahrzeit der Durchfahrenden ist nicht eingerechnet.")
    return "warning", (f"Bei {current} min Haltezeit kostet das gleichgerichtete Umsteigepaar mindestens **{cur['min_sum']} min** (Summe beider Wartezeiten), "
                       f"bei {best['dwell']} min Haltezeit nur {best['min_sum']} min. Das gilt nur für die Umsteigezeit; die längere Haltezeit verlängert die Fahrzeit der Durchfahrenden, das ist nicht eingerechnet.")


def verdict_pair(pv: PairView, mt: int, period: int = C.T) -> tuple[str, str]:
    """Verdikt des Hin/Rück-Paars: die Summe hat nur zwei Werte, der kleinere liegt bei c + 1 von T Versätzen."""
    c = pv.params.c
    share = (c + 1) / period
    return "info", (f"Die Summe beider Wartezeiten ist mindestens **{2 * mt + c} min** (2·{mt} + c mit c = {c}), egal wie die Linien gegeneinander verschoben werden. "
                    f"Den kleineren Wert gibt es bei {c + 1} von {period} Versätzen ({fmt(100 * share)} %); bei allen anderen sind es {2 * mt + c + period} min.")


def verdict_mirror(pv: PairView, dwell: int, mt: int, period: int = C.T) -> tuple[str, str]:
    """Verdikt des gespiegelten Paars am selben Halt."""
    m = pv.mirror
    if m is None:
        return "info", "Für dieses Paar gibt es kein gespiegeltes Paar am selben Halt im Netz (Endhalt oder nicht nachgefragt)."
    if m.disjoint:
        return "warning", (f"Das gespiegelte Paar hat c' = {m.params.c} (c + c' = {pv.params.c + m.params.c}). Beide Paare liegen bei **keinem** Versatz zugleich auf dem kleineren Wert: "
                           f"zusammen kosten die beiden Paare mindestens {fmt(pv.surcharge)} gewichtete Minuten mehr als ihre Einzel-Untergrenzen "
                           f"({period} min mal dem kleineren der beiden Gewichte, {fmt(min(pv.params.w1, m.params.w1))}).")
    return "info", (f"Das gespiegelte Paar hat c' = {m.params.c} (c + c' = {pv.params.c + m.params.c}). Hier überlappen die Gut-Mengen, "
                    f"der Satz „nie zugleich auf dem kleineren Wert“ gilt nur für Haltezeit < Mindest-Umsteigezeit und den kleineren der beiden möglichen Werte von c + c'.")


# ---------------------------------------------------------------- Schritt (c): Netz
def explained_share(lower: float, opt: float, mt: int) -> float | None:
    """Anteil des Aufschlags über die Mindestzeit, den eine Untergrenze erklärt: (Untergrenze - Mindestzeit) / (Optimum - Mindestzeit); None ohne Aufschlag."""
    if opt - mt <= 1e-9:
        return None
    return (lower - mt) / (opt - mt)


def verdict_net(a: NetAnalysis) -> tuple[str, str]:
    mt = a.inst.transfer_min
    s1 = explained_share(a.lb, a.opt, mt)
    s2 = explained_share(a.lb2, a.opt, mt)
    if s1 is None or s2 is None:
        return "info", "In diesem Netz gibt es keinen Aufschlag über die Mindest-Umsteigezeit: Optimum und Mindestzeit sind gleich."
    gap = a.opt - a.lb2
    if a.is_forest:
        return "success", (f"Der Liniengraph ist ein Wald (Kreisrang 0): das Optimum ({fmt(a.opt, 2)} min) ist genau die Linienpaar-Untergrenze ({fmt(a.lb2, 2)} min). "
                           f"Die Untergrenze je Hin/Rück-Paar erklärt {fmt(100 * s1)} % des Aufschlags des Optimums über der Mindestzeit, die je Linienpaar {fmt(100 * s2)} %.")
    return "info", (f"Kreisrang {a.rank}: das Optimum ({fmt(a.opt, 2)} min) liegt {fmt(gap, 2)} min über der Linienpaar-Untergrenze ({fmt(a.lb2, 2)} min). "
                    f"Je Hin/Rück-Paar erklärt die Untergrenze {fmt(100 * s1)} % des Aufschlags des Optimums über der Mindestzeit, je Linienpaar {fmt(100 * s2)} %.")


def verdict_exact(heur: float, exact_mean: float, bound: float, proven: bool) -> tuple[str, str]:
    """Vergleich Lokalsuche und CP-SAT."""
    if proven:
        if heur <= exact_mean + 1e-6:
            return "success", f"CP-SAT beweist das Optimum {fmt(exact_mean, 2)} min; die Lokalsuche hat es gefunden ({fmt(heur, 2)} min)."
        return "warning", f"CP-SAT beweist das Optimum {fmt(exact_mean, 2)} min; die Lokalsuche liegt mit {fmt(heur, 2)} min {fmt(heur - exact_mean, 2)} min darüber."
    return "info", (f"Nicht bewiesen: CP-SAT fand {fmt(exact_mean, 2)} min, die Schranke liegt bei {fmt(bound, 2)} min; die Lokalsuche hat {fmt(heur, 2)} min.")


# ---------------------------------------------------------------- Verdikte der Experimente (aus den vorgerechneten Messreihen, uan_results.py)
def thousands(n: int) -> str:
    """Ganze Zahl mit geschütztem Leerzeichen als Tausendertrenner (deutsche Schreibweise)."""
    return f"{n:,}".replace(",", " ")


def pct(x: float, digits: int = 1) -> str:
    return fmt(100 * x, digits)


def verdict_e1(oc: dict, dist: dict, share: tuple, reached: tuple) -> tuple[str, str]:
    """E1: Kopplung. oc = oracle_counts, dist = c_distribution, share = (Mittel, Std) des von der Paar-Untergrenze erklärten Anteils, reached = (k, m)."""
    bad = oc["viol_min"] + oc["viol_cnt"] + oc["viol_two"] + oc["viol_loop"] + oc["viol_vec"]
    if bad:
        return "warning", f"Die Fahrplantafel weicht in {bad} Prüfungen von der Formel ab: Das Modell trägt hier nicht, die Aussagen unten gelten nicht."
    return "success", (f"An {oc['nets']} Netzen und {thousands(oc['pairs'])} Hin/Rück-Paaren (Vollaufzählung aller {C.T} Versätze über die Fahrplantafel) sind es 0 Abweichungen von "
                       f"„kleinste Summe = 2·{C.DEFAULT_TRANSFER_MIN} + c“, von der Zwei-Werte-Regel, von der Zahl c + 1 der Versätze auf dem kleineren Wert und von der Schleifenzeit-Formel. "
                       f"Ein zufälliger Versatz liegt im Mittel über die Paare bei {pct(dist['random_low_share'])} % der Versätze auf dem kleineren Wert; "
                       f"die Untergrenze erklärt {pct(share[0])} ± {pct(share[1])} % des Aufschlags, den das Phasen-Optimum über der Mindestzeit hat, und wird in {reached[0]} von {reached[1]} Netzen erreicht.")


def verdict_e2(table: dict) -> tuple[str, str]:
    """E2: drei Untergrenzen nach Linienzahl."""
    s1 = [table[L]["share1"][0] for L in C.SWEEP_LINES]
    s2 = [table[L]["share2"][0] for L in C.SWEEP_LINES]
    al = table["alle"]
    return "info", (f"Je Linienpaar erklärt die Untergrenze {pct(al['share2'][0])} ± {pct(al['share2'][1])} % des Aufschlags, den das Phasen-Optimum über der Mindestzeit hat, bei 3 Linien {pct(s2[0])} %, bei 10 Linien {pct(s2[-1])} %. "
                    f"Je Hin/Rück-Paar sind es {pct(al['share1'][0])} ± {pct(al['share1'][1])} %; über 3, 5, 6, 8, 10 Linien "
                    f"{' / '.join(pct(v) for v in s1)} %: {'nicht monoton' if not (s1 == sorted(s1) or s1 == sorted(s1, reverse=True)) else 'monoton'}, Spanne {fmt(100 * (max(s1) - min(s1)))} Prozentpunkte bei einer Block-Streuung bis {fmt(100 * max(table[L]['share1'][1] for L in C.SWEEP_LINES))} Prozentpunkten.")


def forest_where(fs: dict) -> str:
    """Wo die Wälder vorkommen: „alle mit 3 Linien“ oder die Zählung je Linienzahl."""
    by = {L: k for L, k in fs["forest_by_lines"].items() if k}
    if len(by) == 1:
        (L, k), = by.items()
        return f"alle mit {L} Linien"
    return ", ".join(f"{k} mit {L} Linien" for L, k in by.items())


def verdict_e3(fs: dict, cp: dict) -> tuple[str, str]:
    """E3: Wald gegen Kreise."""
    w = (f"Kreisrang 0 (Wald) kommt in {fs['n_forest']} von {fs['n_nets']} Netzen vor ({forest_where(fs)}): dort ist das Optimum in {fs['n_forest'] - fs['forest_gap_positive']} von {fs['n_forest']} Netzen "
         f"genau die Linienpaar-Untergrenze. In {cp['b_n']} konstruierten Wäldern (5 bis 10 Linien) bewies CP-SAT {cp['b_proven']} von {cp['b_n']} Optima, {cp['b_equal_lb2']} gleichen der Untergrenze. ")
    c = fs["corr_within"]
    return "info", w + (f"Mit Kreisen steigt die Lücke im Klassenmittel von {fmt(fs['classes'][1]['gap'], 2)} auf {fmt(fs['classes'][-1]['gap'], 2)} min; innerhalb einer Linienzahl ist der Zusammenhang "
                        f"von Kreisrang und Lücke schwach bis mäßig (Pearson {fmt(min(c.values()), 2)} bis {fmt(max(c.values()), 2)}).")


def verdict_e4(rows: list[dict]) -> tuple[str, str]:
    """E4: Haltezeit-Reihe."""
    r2 = next(r for r in rows if r["dwell"] == 2)
    r3 = next(r for r in rows if r["dwell"] == 3)
    return "info", (f"Bei Haltezeit 2 min liegt die kleinste Summe eines gleichgerichteten Paars bei {int(r2['same_min_mean'])} min, bei 3 min bei {int(r3['same_min_mean'])} min. "
                    f"Das Phasen-Optimum des Netzes sinkt nur von {fmt(r2['opt'][0], 2)} auf {fmt(r3['opt'][0], 2)} min ({fmt(r2['opt'][0] - r3['opt'][0], 2)} min), danach bleibt es bis 6 min "
                    f"zwischen {fmt(min(r['opt'][0] for r in rows if r['dwell'] >= 3), 2)} und {fmt(max(r['opt'][0] for r in rows if r['dwell'] >= 3), 2)} min. "
                    "Gerechnet ist nur die Umsteigezeit; die längere Haltezeit verlängert die Fahrzeit der Durchfahrenden, das ist nicht eingerechnet.")


def verdict_e5(s: dict) -> tuple[str, str]:
    """E5: Brücke zur freien Aufteilung der Wende-Standzeit."""
    return "info", (f"Bei freier Aufteilung der Wende-Standzeit kann c in {pct(s['share_cmin0'][0], 0)} % der Hin/Rück-Paare einzeln auf 0 sinken (Ø c {fmt(s['c_std'][0])} → {fmt(s['c_min'][0])} min). "
                    f"Die kleinste gefundene Netz-Untergrenze ist {fmt(s['lb_free'][0])} min gegen {fmt(s['lb_std'][0])} min bei Standard-Aufteilung, in {s['lower']} von {s['n']} Netzen niedriger. "
                    "Das ist eine obere Schranke des wahren Minimums der Untergrenze; ob die Untergrenze je Linienpaar mit freier Aufteilung die nächste Schranke ist, ist nicht gemessen.")
