"""Erzeugt die vorgerechnete Messreihe (data/uan_results.json) in Teilen; die App rechnet sie nie live.

Aufruf (Python des Test-venv, höchstens zwei Prozesse zugleich, CP-SAT höchstens 2 Arbeiter):

    python tools/sweep.py main   <Rohdatei.jsonl> [Linienzahlen kommagetrennt]     600 Netze: Kopplung, drei Untergrenzen, Spiegel, Gleichrichtung, Orakel (Fahrplantafel)
    python tools/sweep.py dwell  <Rohdatei.jsonl> [Linienzahlen kommagetrennt]     dieselben 600 Netze, Haltezeit d = 1..6
    python tools/sweep.py split  <Rohdatei.jsonl> [Linienzahlen kommagetrennt]     Brücke: freie Aufteilung der Wende-Standzeit
    python tools/sweep.py cp     <Rohdatei.jsonl> [Zeitlimit s]                     Lokalsuche gegen CP-SAT und konstruierte Wälder (CP-SAT, 2 Arbeiter)
    python tools/sweep.py merge  <Ordner mit den Rohdateien> [Ausgabe]              fügt alles zu data/uan_results.json zusammen

Seeds der Messreihe: 10000*(Block+1) + 1500*Index(Linienzahl) + 50*i (alle >= 10000, die Regler der App enden bei 9999; build_valid_instance zählt höchstens
50 Seeds hoch). Zufall nur über SplitMix64.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import uan_clock as K  # noqa: E402
import uan_constants as C  # noqa: E402
import uan_forest as F  # noqa: E402
import uan_pair as P  # noqa: E402
import uan_search as S  # noqa: E402
from uan_exact import solve_phases  # noqa: E402
from uan_network import build_valid_instance  # noqa: E402
from uan_rng import SplitMix64  # noqa: E402
from uan_timetable import fixed_line_times, symmetric_lower_bound, turn_slack  # noqa: E402

LIDX = {L: i for i, L in enumerate(C.SWEEP_LINES)}
T, MT = C.T, C.DEFAULT_TRANSFER_MIN


def seed0(L: int, block: int, i: int) -> int:
    return C.SWEEP_SEED_BASE * (block + 1) + 1500 * LIDX[L] + 50 * i


def lines_arg(argv, pos):
    return [int(x) for x in argv[pos].split(",")] if len(argv) > pos else list(C.SWEEP_LINES)


def board_sums(inst, key1, key2, ev_a, ev0_b_fn):
    """Fahrplantafel-Vollaufzählung des Versatzes u der zweiten Linie: Summe der Wartezeiten der Aktivitäten key1 (la -> lb) und key2 (lb -> la)."""
    la, da, ka, lb, db, kb = key1
    _, da2, ka2, _, db2, kb2 = key2
    out = []
    for u in range(inst.T):
        ev_b = ev0_b_fn(u)
        x1 = K.board_wait(ev_a[("arr", da, ka)], ev_b[("dep", db, kb)], inst.transfer_min, inst.T)
        x2 = K.board_wait(ev_b[("arr", da2, ka2)], ev_a[("dep", db2, kb2)], inst.transfer_min, inst.T)
        out.append(x1 + x2)
    return out


def measure_main(L: int, block: int, i: int) -> dict:
    s0 = seed0(L, block, i)
    inst, _, _, used = build_valid_instance(L, s0)
    n = len(inst.lines)
    arrs = S.base_arrays(inst)
    tw = float(arrs.w.sum())
    ev0 = P.event_times_zero(inst)
    rec = {"L": L, "block": block, "i": i, "seed0": s0, "seed": used, "n_lines": n, "n_act": len(inst.transfers)}
    # ---- Hin/Rück-Paare: Fahrplantafel gegen Formel, Zwei-Werte-Regel, Zahl der Versätze auf dem kleineren Wert, Schleifenzeit
    hr = P.hin_rueck_params(inst)
    cs, viol_min, viol_cnt, viol_two, viol_loop, viol_vec = [], 0, 0, 0, 0, 0
    vec_of = {}                                           # Schlüssel -> (Summenkurve der Tafel in Orientierung des Schlüssels, la, lb)
    for k1, k2, pp in hr:
        ev_a = ev0[pp.la]
        sums = board_sums(inst, k1, k2, ev_a, lambda u, lb=pp.lb: fixed_line_times(inst.lines[lb], inst.T, inst.dwell, inst.tmin, u)[0])
        lo = min(sums)
        cs.append(pp.c)
        viol_min += lo != 2 * MT + pp.c
        viol_cnt += sums.count(lo) != pp.c + 1
        viol_two += not set(sums) <= {lo, lo + T}
        viol_loop += K.pair_constant(inst, k1) != pp.c
        viol_vec += sums != [int(x) for x in P.pair_cost_vector(pp.d1, pp.c, T, MT)]
        vec_of[k1] = (sums, pp.la, pp.lb)
        flipped = [sums[(-u) % T] for u in range(T)]      # u' = o_la - o_lb = -u für die Gegenorientierung (Schlüssel k2: lb -> la)
        vec_of[k2] = (flipped, pp.lb, pp.la)
    paired_w = sum(2 * pp.w1 for _, _, pp in hr)
    rec.update({"n_pairs": len(hr), "c": cs, "viol_min": viol_min, "viol_cnt": viol_cnt, "viol_two": viol_two, "viol_loop": viol_loop,
                "viol_vec": viol_vec, "lb_ok": abs(P.pairs_bound(inst) - symmetric_lower_bound(inst)) < 1e-9, "all_paired": abs(paired_w - tw) < 1e-9})
    # ---- Spiegel-Paare (beide Richtungen vertauscht, gleicher Halt), Gut-Mengen aus der Tafel
    seen = set()
    mir = {"n": 0, "sum_ok": 0, "n_low": 0, "disjoint_low": 0, "n_high": 0, "overlap_high": 0, "ov_high_total": 0, "other": 0}
    for k1, k2, pp in hr:
        m1 = P.mirror_key(k1)
        if m1 not in vec_of or k1 in seen:
            continue
        sums_m, la_m, lb_m = vec_of[m1]
        sums_1, _, _ = vec_of[k1]
        # beide Orientierungen sind la -> lb (m1 hat dieselben Linien in derselben Reihenfolge)
        seen.update({k1, k2, m1, P.mirror_key(k2)})
        g1 = {u for u in range(T) if sums_1[u] == min(sums_1)}
        g2 = {u for u in range(T) if sums_m[u] == min(sums_m)}
        c1, c2 = min(sums_1) - 2 * MT, min(sums_m) - 2 * MT
        mir["n"] += 1
        mir["sum_ok"] += (c1 + c2 - 4 * (inst.dwell - MT)) % T == 0
        total = c1 + c2
        if total == T - 4 * (MT - inst.dwell):
            mir["n_low"] += 1
            mir["disjoint_low"] += not (g1 & g2)
        elif total == 2 * T - 4 * (MT - inst.dwell):
            mir["n_high"] += 1
            mir["overlap_high"] += bool(g1 & g2)
            mir["ov_high_total"] += len(g1 & g2)
        else:
            mir["other"] += 1
    rec["mirror"] = mir
    # ---- Gleichrichtungs-Paare, kleinste Summe aus der Tafel
    mins: dict = {}
    n_same = n_in = 0
    for key, rev, pp in P.same_direction_params(inst):
        sums = board_sums(inst, key, rev, ev0[pp.la], lambda u, lb=pp.lb: fixed_line_times(inst.lines[lb], inst.T, inst.dwell, inst.tmin, u)[0])
        lo = min(sums)
        mins[str(lo)] = mins.get(str(lo), 0) + 1
        n_same += 1
        n_in += 2
        assert lo == P.pair_min(pp.c, MT)
    rec["same"] = {"n": n_same, "act_in": n_in, "mins": mins}
    # ---- drei Untergrenzen, Zufall, Optimum
    edges = F.line_edges(inst)
    costs = P.line_pair_costs(inst)
    rec.update({"n_line_pairs": len(edges), "rank": F.cycle_rank(n, edges), "comps": F.components(n, edges),
                "lb": P.pairs_bound(inst) / tw, "lb2": sum(float(v.min()) for v in costs.values()) / tw, "rand_exact": S.random_mean_exact(arrs),
                "rand_300": S.random_mean_draws(arrs, C.RANDOM_SAMPLES, SplitMix64(1_000_003 * used + L + 77))})
    o, c_opt = S.multistart(arrs, S.SearchSettings(restarts=C.SEARCH_RESTARTS), SplitMix64(1_000_003 * used + L))
    rec["opt"] = c_opt / tw
    return rec


def run_main(out: str, Ls) -> None:
    with open(out, "a", encoding="utf-8") as f:
        for L in Ls:
            for block in range(C.SWEEP_BLOCKS):
                for i in range(C.SWEEP_NETS):
                    f.write(json.dumps(measure_main(L, block, i)) + "\n")
                    f.flush()
            print("fertig L =", L, flush=True)


def measure_dwell(L: int, block: int, i: int) -> list[dict]:
    inst0, _, _, used = build_valid_instance(L, seed0(L, block, i))
    out = []
    for d in range(C.DWELL_MIN, C.DWELL_MAX + 1):
        inst = replace(inst0, dwell=d)
        arrs = S.base_arrays(inst)
        tw = float(arrs.w.sum())
        costs = P.line_pair_costs(inst)
        o, c = S.multistart(arrs, S.SearchSettings(restarts=C.SEARCH_RESTARTS), SplitMix64(1_000_003 * used + L + 1000 * d))
        same = P.same_direction_params(inst)
        ev0 = P.event_times_zero(inst)
        mins = [P.pair_min(pp.c, MT) for _, _, pp in same]
        # Spiegel-Paare nach Satz: disjunkt genau dann, wenn c + c' = T - 4*(mt - d) (nur für d < mt); gezählt aus den Gut-Mengen
        mir_n = mir_dis = mir_pred_dis = mir_mismatch = 0
        seen = set()
        for k1, k2, pp in P.hin_rueck_params(inst):
            m1, m2 = P.mirror_key(k1), P.mirror_key(k2)
            if k1 in seen or m1 not in inst.transfers or m2 not in inst.transfers:
                continue
            mpp = P.pair_params(inst, m1, m2, ev0)
            seen.update({k1, k2, m1, m2})
            dis = P.good_sets_disjoint(P.good_set(pp.d1, pp.c, T), P.good_set(mpp.d1, mpp.c, T))
            pred = P.mirror_disjoint_predicted(pp.c, mpp.c, d, MT, T)
            mir_n += 1
            mir_dis += dis
            if pred is not None:
                mir_pred_dis += pred
                mir_mismatch += pred != dis
        rec = {"L": L, "block": block, "i": i, "seed": used, "dwell": d, "n_lines": len(inst.lines), "lb": P.pairs_bound(inst) / tw,
               "lb2": sum(float(v.min()) for v in costs.values()) / tw, "opt": c / tw, "n_same": len(same),
               "same_min_mean": float(np.mean(mins)) if mins else None, "same_min_set": sorted(set(mins)),
               "mirror_n": mir_n, "mirror_disjoint": mir_dis, "mirror_pred_disjoint": mir_pred_dis, "mirror_mismatch": mir_mismatch}
        if block == 0 and i < 3 and same:                   # Formel gegen Fahrplantafel
            key, rev, pp = same[0]
            sums = board_sums(inst, key, rev, ev0[pp.la], lambda u, lb=pp.lb: fixed_line_times(inst.lines[lb], inst.T, inst.dwell, inst.tmin, u)[0])
            rec["check"] = [P.pair_min(K.same_direction_constant(d, MT, T), MT), min(sums)]
        out.append(rec)
    return out


def run_dwell(out: str, Ls) -> None:
    with open(out, "a", encoding="utf-8") as f:
        for L in Ls:
            for block in range(C.SWEEP_BLOCKS):
                for i in range(C.SWEEP_NETS):
                    for rec in measure_dwell(L, block, i):
                        f.write(json.dumps(rec) + "\n")
                    f.flush()
            print("fertig L =", L, flush=True)


def measure_split(L: int, block: int, i: int) -> dict:
    """Brücke zur Wende-Standzeit: c eines Paars hängt von den Standzeiten (Wartezeit am f-Ende) nur linear (mod T) ab. Je Paar der kleinste erreichbare c-Wert bei
    freier Aufteilung (Paar einzeln); je Netz die kleinste gefundene Summe der Paar-Untergrenzen (Koordinatenabstieg, 1 + 20 Neustarts): eine OBERE Schranke
    des wahren Minimums, kein Beweis."""
    inst, _, _, used = build_valid_instance(L, seed0(L, block, i))
    n = len(inst.lines)
    slack = [turn_slack(l, inst.T, inst.dwell, inst.tmin) for l in inst.lines]
    sstd = [s // 2 for s in slack]
    hr = P.hin_rueck_params(inst)
    PA, PB, SA, SB, C0, W = [], [], [], [], [], []
    cmin = []
    for k1, k2, pp in hr:
        sa_sig = 1 if k1[1] == "f" else -1
        sb_sig = 1 if (K.opposite(k1[4]) == "f") else -1
        for sa in (0, slack[pp.la]):                         # Linearität an den Ecken gegen die Schleifenzeit prüfen
            for sb in (0, slack[pp.lb]):
                assert (pp.c + sa_sig * (sa - sstd[pp.la]) + sb_sig * (sb - sstd[pp.lb])) % T == K.pair_constant(inst, k1, sa, sb)
        sa_r = np.arange(slack[pp.la] + 1)[:, None]
        sb_r = np.arange(slack[pp.lb] + 1)[None, :]
        cmin.append(int(((pp.c + sa_sig * (sa_r - sstd[pp.la]) + sb_sig * (sb_r - sstd[pp.lb])) % T).min()))
        PA.append(pp.la), PB.append(pp.lb), SA.append(sa_sig), SB.append(sb_sig), C0.append(pp.c), W.append(pp.w1)
    PA, PB, SA, SB, C0, W = map(np.array, (PA, PB, SA, SB, C0, W))
    sstd_a, slack_a = np.array(sstd), np.array(slack)
    tw = sum(inst.transfers.values())

    def lbsum(s):
        c = (C0 + SA * (s[PA] - sstd_a[PA]) + SB * (s[PB] - sstd_a[PB])) % T
        return float((W * (2 * MT + c)).sum())

    lb_std = lbsum(sstd_a.copy())
    best = lb_std
    rng = SplitMix64(1_000_003 * used + L + 5)
    starts = [sstd_a.copy()] + [np.array([rng.randrange(int(slack_a[x]) + 1) for x in range(n)]) for _ in range(20)]
    for s0 in starts:
        s = s0.copy()
        cur = lbsum(s)
        improved = True
        while improved:
            improved = False
            for line in range(n):
                keep = s[line]
                for cand in range(int(slack_a[line]) + 1):
                    s[line] = cand
                    v = lbsum(s)
                    if v < cur - 1e-9:
                        cur, keep, improved = v, cand, True
                s[line] = keep
        best = min(best, cur)
    return {"L": L, "block": block, "i": i, "seed": used, "n_pairs": len(hr), "lb_std": lb_std / tw, "lb_free": best / tw,
            "c_std_mean": float(np.mean(C0)), "c_min_mean": float(np.mean(cmin)), "share_cmin0": float(np.mean(np.array(cmin) == 0)),
            "mean_slack": float(np.mean(slack)), "share_slack0": float(np.mean(np.array(slack) == 0))}


def run_split(out: str, Ls) -> None:
    with open(out, "a", encoding="utf-8") as f:
        for L in Ls:
            for block in range(C.SWEEP_BLOCKS):
                for i in range(C.SWEEP_NETS):
                    f.write(json.dumps(measure_split(L, block, i)) + "\n")
                    f.flush()
            print("fertig L =", L, flush=True)


def run_cp(out: str, limit: float) -> None:
    """Teil A: Lokalsuche (40 Neustarts) gegen CP-SAT auf den ersten Netzen von Block 0 je Linienzahl; Teil B: konstruierte Wälder (alle Umstiege außer einem
    aufspannenden Wald gestrichen): Optimum = LB2?"""
    with open(out, "a", encoding="utf-8") as f:
        for L in C.SWEEP_LINES:
            for i in range(C.CP_ORACLE_PER_LINES):
                inst, _, _, used = build_valid_instance(L, seed0(L, 0, i))
                arrs = S.base_arrays(inst)
                tw = float(arrs.w.sum())
                o, c = S.multistart(arrs, S.SearchSettings(restarts=C.SEARCH_RESTARTS), SplitMix64(1_000_003 * used + L))
                r = solve_phases(arrs, limit, C.EXACT_WORKERS, hint=o)
                f.write(json.dumps({"teil": "A", "L": L, "seed": used, "ls": c / tw, "cp": r.mean_wait, "bound": r.bound_wait, "status": r.status,
                                    "proven": r.proven}) + "\n")
                f.flush()
        for L in (5, 6, 8, 10):
            for i in range(C.FORCED_FOREST_PER_LINES):
                inst, _, _, used = build_valid_instance(L, 20000 + 1500 * LIDX[L] + 50 * i)
                red, keep = F.forest_instance(inst)
                arrs = S.base_arrays(red)
                tw = float(arrs.w.sum())
                lb2 = sum(float(v.min()) for v in P.line_pair_costs(red).values()) / tw
                o, c = S.multistart(arrs, S.SearchSettings(restarts=C.SEARCH_RESTARTS), SplitMix64(1_000_003 * used + L))
                fo = F.forest_offsets(red)
                c_forest = S.mean_wait(arrs, fo)
                r = solve_phases(arrs, limit, C.EXACT_WORKERS, hint=o)
                f.write(json.dumps({"teil": "B", "L": L, "seed": used, "n_lines": len(inst.lines), "kept_edges": len(keep), "act_orig": len(inst.transfers),
                                    "act_red": len(red.transfers), "lb2": lb2, "ls": c / tw, "forest_offsets_cost": c_forest, "cp": r.mean_wait,
                                    "bound": r.bound_wait, "status": r.status, "proven": r.proven}) + "\n")
                f.flush()
    print("fertig")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def generator_hash() -> str:
    """Hash der Dateien, die die Netze festlegen (siehe uan_results.generator_hash)."""
    import uan_results
    return uan_results.generator_hash()


def merge(raw_dir: str, out: str) -> None:
    raw = Path(raw_dir)
    main_rows = [r for p in sorted(raw.glob("main_*.jsonl")) for r in read_jsonl(p)]
    dwell_rows = [r for p in sorted(raw.glob("dwell_*.jsonl")) for r in read_jsonl(p)]
    split_rows = [r for p in sorted(raw.glob("split_*.jsonl")) for r in read_jsonl(p)]
    cp_rows = [r for p in sorted(raw.glob("cp_*.jsonl")) for r in read_jsonl(p)]
    nets = {str(L): sorted([r for r in main_rows if r["L"] == L], key=lambda r: (r["block"], r["i"])) for L in C.SWEEP_LINES}
    res = {
        "meta": {"generator_hash": generator_hash(), "T": T, "mt": MT, "dwell": C.DEFAULT_DWELL, "restarts": C.SEARCH_RESTARTS, "blocks": C.SWEEP_BLOCKS,
                 "nets_per_block": C.SWEEP_NETS, "lines": list(C.SWEEP_LINES), "seed_rule": "10000*(Block+1) + 1500*Index(Linienzahl) + 50*i",
                 "note": "Netze und Fahrpläne sind Annahmen (Generator der Fall-Demo taktfahrplan-demo), keine Echtdaten."},
        "nets": nets,
        "dwell": sorted(dwell_rows, key=lambda r: (r["L"], r["block"], r["i"], r["dwell"])),
        "split": sorted(split_rows, key=lambda r: (r["L"], r["block"], r["i"])),
        "cp": cp_rows,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    print("geschrieben:", out, {k: (len(v) if isinstance(v, list) else {kk: len(vv) for kk, vv in v.items()} if k == "nets" else "-") for k, v in res.items()})


def main():
    cmd = sys.argv[1]
    if cmd == "main":
        run_main(sys.argv[2], lines_arg(sys.argv, 3))
    elif cmd == "dwell":
        run_dwell(sys.argv[2], lines_arg(sys.argv, 3))
    elif cmd == "split":
        run_split(sys.argv[2], lines_arg(sys.argv, 3))
    elif cmd == "cp":
        run_cp(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else C.EXACT_TIME_LIMIT)
    elif cmd == "merge":
        merge(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else str(ROOT / C.RESULTS_FILE))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
