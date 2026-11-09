"""Feste Annahmen, Regler-Grenzen, Presets und Farben der Demo „Uhr und Anschluss“ (eine Wahrheitsquelle)."""

# ------------------------------------------------------------------ Fahrplanmodell (feste Annahmen, wie in der Fall-Demo taktfahrplan-demo)
T = 60                      # Takt in Minuten
N_STOPS = 20                # Haltestellen im synthetischen Netz
MAX_LINE_LENGTH = 6         # höchstens so viele Halte je Linie
TURN_MIN = 4                # kürzeste Standzeit an einem Endpunkt (min); dort ändert die Demo nichts (Aufteilung: eine spätere Demo dieser Linie)
DEFAULT_DWELL = 2           # Haltezeit an Zwischenhalten (min)
DEFAULT_TRANSFER_MIN = 3    # Mindest-Umsteigezeit (min)
MIN_TRANSFERS = 3           # ein Seed gilt erst mit mindestens so vielen Umsteigeverbindungen als gültig (build_valid_instance)

# ------------------------------------------------------------------ Regler
LINES_OPTIONS = (3, 5, 6, 8, 10)
DEFAULT_LINES = 6
DWELL_MIN, DWELL_MAX = 1, 6
MT_MIN, MT_MAX = 1, 6
SEED_MIN, SEED_MAX = 0, 9999
DEFAULT_SEED = 601
ARR_MIN, ARR_MAX, DEFAULT_ARR = 0, 59, 40          # Schritt (a): Ankunftsminute der Linie A
SHIFT_MIN, SHIFT_MAX, DEFAULT_SHIFT = 0, 59, 0     # Schritt (a): Versatz der Linie B
B_BASE_DEP = 20                                     # Schritt (a): Abfahrtsminute der Linie B ohne Versatz
EXACT_TIME_LIMIT = 20.0                             # CP-SAT-Knopf: Zeitlimit in Sekunden (2 Arbeiter)
EXACT_WORKERS = 2

# ------------------------------------------------------------------ Suche
SEARCH_RESTARTS = 40        # Neustarts der Lokalsuche (wie in der Fall-Demo)
RANDOM_SAMPLES = 300        # Ziehungen zufälliger Versätze (Gegenprobe zur exakten Zufalls-Wartezeit)

# ------------------------------------------------------------------ Ergebnisdatei und Messreihe
RESULTS_FILE = "data/uan_results.json"
SWEEP_LINES = (3, 5, 6, 8, 10)
SWEEP_BLOCKS = 4
SWEEP_NETS = 30                                     # Netze je Linienzahl und Block
SWEEP_SEED_BASE = 10000                             # Seed = 10000*(Block+1) + 1500*Index(Linienzahl) + 50*i (alle >= 10000, Regler endet bei 9999)
FORCED_FOREST_PER_LINES = 5                         # konstruierte Wälder je Linienzahl 5/6/8/10 für den CP-SAT-Beweis
CP_ORACLE_PER_LINES = 6                             # Netze je Linienzahl für Lokalsuche gegen CP-SAT

# ------------------------------------------------------------------ Darstellung
COLOR_A = "#2a6fb0"
COLOR_B = "#2e7d4f"
COLOR_SUM = "#c0392b"
COLOR_GOOD = "rgba(46,125,79,0.20)"
COLOR_MIRROR = "#8e44ad"
COLOR_SAME = "#c77700"
COLOR_GREY = "#7d8898"
LINE_COLORS = ["#2a6fb0", "#2e7d4f", "#c77700", "#8e44ad", "#c0392b", "#16a085", "#7f8c8d", "#d35400", "#2c3e50", "#b03a6f"]

# ------------------------------------------------------------------ Presets
PRESET_ORDER = ["Standard", "Knapp verpasst", "Taktknoten", "Nur Wald", "Dichtes Netz"]
PRESETS = {
    "Standard": {"lines": DEFAULT_LINES, "seed": DEFAULT_SEED, "dwell": DEFAULT_DWELL, "mt": DEFAULT_TRANSFER_MIN, "forest": False,
                 "arr": DEFAULT_ARR, "shift": DEFAULT_SHIFT},
    "Knapp verpasst": {"lines": DEFAULT_LINES, "seed": DEFAULT_SEED, "dwell": DEFAULT_DWELL, "mt": DEFAULT_TRANSFER_MIN, "forest": False,
                       "arr": 40, "shift": 22},
    "Taktknoten": {"lines": DEFAULT_LINES, "seed": DEFAULT_SEED, "dwell": 3, "mt": DEFAULT_TRANSFER_MIN, "forest": False,
                   "arr": DEFAULT_ARR, "shift": DEFAULT_SHIFT},
    "Nur Wald": {"lines": 8, "seed": DEFAULT_SEED, "dwell": DEFAULT_DWELL, "mt": DEFAULT_TRANSFER_MIN, "forest": True,
                 "arr": DEFAULT_ARR, "shift": DEFAULT_SHIFT},
    "Dichtes Netz": {"lines": 10, "seed": 650, "dwell": DEFAULT_DWELL, "mt": DEFAULT_TRANSFER_MIN, "forest": False,
                     "arr": DEFAULT_ARR, "shift": DEFAULT_SHIFT},
}
PRESET_HELP = {
    "Standard": "6 Linien, Haltezeit 2 min, Mindest-Umsteigezeit 3 min: der Grundfall. Der Anschluss auf dem Zifferblatt kommt mit 40 min Wartezeit.",
    "Knapp verpasst": "Der Zug der Linie B fährt eine Minute vor der frühesten möglichen Abfahrt: die Wartezeit springt auf fast eine volle Stunde.",
    "Taktknoten": "Haltezeit 3 min, so lang wie die Mindest-Umsteigezeit: gleichgerichtete Umstiege am selben Halt kosten dann 6 statt 64 min Summe.",
    "Nur Wald": "8 Linien, aber nur ein aufspannender Wald der Linienpaare bleibt: hier ist das Optimum genau die Linienpaar-Untergrenze.",
    "Dichtes Netz": "10 Linien: mehr Linienpaare und Kreise im Liniengraphen; der Rest über der Linienpaar-Untergrenze wächst.",
}


def fmt_min(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",") + " min"


def fmt_num(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def fmt_pct(x, digits=0):
    return f"{100 * x:.{digits}f}".replace(".", ",") + " %"
