"""Die drei kopierten Module (uan_rng, uan_network, uan_timetable) sind bis auf die Modulnamen und die Herkunftszeile wörtliche Kopien aus taktfahrplan-demo.

Zwei Prüfungen: (1) gegen den Hash der Quelle (läuft immer, auch in der CI ohne den Nachbarordner), (2) gegen die Quelle selbst, wenn der Ordner taktfahrplan-demo
neben diesem Repo liegt (sonst übersprungen). Eine Textkorrektur in einer Kopie bricht diesen Test; sie gehört in die Quelle und in alle Kopien (DEMO-PLAYBOOK §11a, Punkt 11)."""

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT.parent / "taktfahrplan-demo"
# SHA-256 der Quelldateien (taktfahrplan-demo/tkt_*.py, Zeilenenden LF) zum Zeitpunkt des Kopierens, 2026-11-09
SOURCE_HASH = {
    "rng": "6056cda35d26cb17b6a4afc2a2a308e965ceece1766be5627c680c50858f2c10",
    "network": "59e67fd6d3d0c547e3b7fbcb188af89f70a5237e5291311fccdf7edfa5673915",
    "timetable": "7b2b5bea9c749dc338ebdab827fc6b2df60cef7b5fb2a4e9667dd0ada258bcf1",
}


def _back_to_source(name: str) -> str:
    """Kopie -> Quelltext: Herkunftszeile entfernen, Modulnamen uan_ -> tkt_ zurücksetzen."""
    text = (ROOT / f"uan_{name}.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
    head, _, body = text.partition("\n")
    assert head.startswith(f"# aus taktfahrplan-demo (tkt_{name}.py)")
    return body.replace("uan_", "tkt_")


@pytest.mark.parametrize("name", list(SOURCE_HASH))
def test_copy_is_the_source_with_renamed_modules(name):
    assert hashlib.sha256(_back_to_source(name).encode("utf-8")).hexdigest() == SOURCE_HASH[name]


@pytest.mark.parametrize("name", list(SOURCE_HASH))
def test_copy_equals_the_original_if_it_is_next_to_this_repo(name):
    original = SOURCE / f"tkt_{name}.py"
    if not original.exists():
        pytest.skip("taktfahrplan-demo liegt nicht neben diesem Repo")
    assert original.read_bytes().decode("utf-8").replace("\r\n", "\n") == _back_to_source(name)


def test_the_copied_generator_is_deterministic():
    """Gleiche Eingabe (6 Linien, Seed 601), gleiches Netz: dieselben Linien und Umstiege bei jedem Aufruf (ganzzahliger SplitMix64, kein Python-hash())."""
    from uan_network import build_valid_instance
    inst, _, _, used = build_valid_instance(6, 601)
    assert len(inst.lines) == 6 and used >= 601 and len(inst.transfers) > 0
    again, _, _, used2 = build_valid_instance(6, 601)
    assert used2 == used and again.transfers == inst.transfers and [l.stops for l in again.lines] == [l.stops for l in inst.lines]
