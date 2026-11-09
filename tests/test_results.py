"""Die vorgerechnete Messreihe (data/uan_results.json): Aufbau, Erzeuger-Hash, Stichprobe gegen eine frische Rechnung."""

import dataclasses
import json
from pathlib import Path

import pytest

import uan_constants as C
import uan_pair as P
import uan_results as R
import uan_search as S
from uan_network import build_valid_instance
from uan_rng import SplitMix64

RES = R.load_results()


def test_meta_matches_the_current_generator_and_the_constants():
    meta = RES["meta"]
    assert meta["generator_hash"] == R.generator_hash(), "uan_rng/uan_network/uan_timetable haben sich geändert: Messreihe mit tools/sweep.py neu erzeugen"
    assert (meta["T"], meta["mt"], meta["dwell"], meta["restarts"], meta["blocks"], meta["nets_per_block"]) == (
        C.T, C.DEFAULT_TRANSFER_MIN, C.DEFAULT_DWELL, C.SEARCH_RESTARTS, C.SWEEP_BLOCKS, C.SWEEP_NETS)
    assert meta["lines"] == list(C.SWEEP_LINES)


def test_every_line_count_has_four_blocks_of_thirty_nets():
    for L in C.SWEEP_LINES:
        rows = R.nets(RES, L)
        assert len(rows) == C.SWEEP_BLOCKS * C.SWEEP_NETS
        assert {(r["block"], r["i"]) for r in rows} == {(b, i) for b in range(C.SWEEP_BLOCKS) for i in range(C.SWEEP_NETS)}
        assert all(r["L"] == L and r["seed"] >= r["seed0"] >= C.SWEEP_SEED_BASE for r in rows)


def test_seeds_follow_the_rule_and_do_not_overlap():
    seen = set()
    for L in C.SWEEP_LINES:
        for r in R.nets(RES, L):
            assert r["seed0"] == C.SWEEP_SEED_BASE * (r["block"] + 1) + 1500 * C.SWEEP_LINES.index(L) + 50 * r["i"]
            span = set(range(r["seed0"], r["seed"] + 1))
            assert not (span & seen)
            seen |= span


def test_dwell_series_has_every_net_at_every_dwell_time():
    assert len(RES["dwell"]) == 600 * 6
    assert {(r["L"], r["block"], r["i"], r["dwell"]) for r in RES["dwell"]} == {(r["L"], r["block"], r["i"], d) for r in R.nets(RES) for d in range(1, 7)}


@pytest.mark.parametrize("lines,block,i", [(3, 0, 0), (5, 1, 7), (6, 2, 13), (8, 3, 29), (10, 0, 5), (10, 3, 17)])
def test_a_stored_net_equals_a_fresh_computation(lines, block, i):
    rec = next(r for r in R.nets(RES, lines) if r["block"] == block and r["i"] == i)
    inst, _, _, used = build_valid_instance(lines, rec["seed0"])
    assert used == rec["seed"] and len(inst.lines) == rec["n_lines"] and len(inst.transfers) == rec["n_act"]
    arrs = S.base_arrays(inst)
    tw = float(arrs.w.sum())
    assert P.pairs_bound(inst) / tw == pytest.approx(rec["lb"]) and P.line_pair_bound(inst) / tw == pytest.approx(rec["lb2"])
    o, c = S.multistart(arrs, S.SearchSettings(restarts=C.SEARCH_RESTARTS), SplitMix64(1_000_003 * used + lines))
    assert c / tw == pytest.approx(rec["opt"])
    assert sorted(pp.c for _, _, pp in P.hin_rueck_params(inst)) == sorted(rec["c"])


def test_a_stored_dwell_record_equals_a_fresh_computation():
    rec = next(r for r in RES["dwell"] if (r["L"], r["block"], r["i"], r["dwell"]) == (6, 1, 3, 3))
    net = next(r for r in R.nets(RES, 6) if (r["block"], r["i"]) == (1, 3))
    inst0, _, _, used = build_valid_instance(6, net["seed0"])
    inst = dataclasses.replace(inst0, dwell=3)
    arrs = S.base_arrays(inst)
    tw = float(arrs.w.sum())
    assert used == rec["seed"]
    assert P.pairs_bound(inst) / tw == pytest.approx(rec["lb"]) and P.line_pair_bound(inst) / tw == pytest.approx(rec["lb2"])
    o, c = S.multistart(arrs, S.SearchSettings(restarts=C.SEARCH_RESTARTS), SplitMix64(1_000_003 * used + 6 + 1000 * 3))
    assert c / tw == pytest.approx(rec["opt"])


def test_the_file_is_valid_json_and_not_huge():
    path = Path(R.ROOT / C.RESULTS_FILE)
    json.loads(path.read_text(encoding="utf-8"))
    assert path.stat().st_size < 3_000_000
