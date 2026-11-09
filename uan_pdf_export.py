"""Bericht als PDF (fpdf2, Kernschrift Helvetica: Umlaute gehen; Gedankenstrich, Pfeile, Emoji und U+2212 nicht)."""
from __future__ import annotations

from fpdf import FPDF

from uan_timetable import fixed_line_times

_REPLACE = {"–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=", "→": "->", "↔": "<->", "…": "...", "€": "EUR", "·": "."}


def _clean(text: str) -> str:
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_report_pdf(a, offsets, title: str = "Uhr und Anschluss: Bericht zum Netz") -> bytes:
    """Kennzahlen des Netzes (Zufall, Untergrenzen, Phasen-Optimum) und die Abfahrtsminuten je Linie bei den Versätzen `offsets` (z. B. dem Phasen-Optimum)."""
    inst = a.inst
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    s = a.settings
    lines = [
        f"Netz: {a.n_lines} Linien, Zufalls-Seed {s.seed} (verwendet: {a.used_seed}), Haltezeit {s.dwell} min, Mindest-Umsteigezeit {s.mt} min, Takt {inst.T} min"
        + (", nur aufspannender Wald der Linienpaare" if s.forest else ""),
        f"Zufälliger Versatz: Ø {a.rand_exact:.2f} min Wartezeit (exakt: Mindestzeit + (T - 1) / 2).".replace(".", ","),
        f"Untergrenze je Hin/Rück-Paar: {a.lb:.2f} min; je Linienpaar: {a.lb2:.2f} min; Phasen-Optimum der Lokalsuche: {a.opt:.2f} min.".replace(".", ","),
        f"Liniengraph: {len(a.edges)} Linienpaare, Kreisrang {a.rank}" + (" (Wald: Optimum = Untergrenze je Linienpaar)." if a.rank == 0 else "."),
        "Modell mit synthetischen Netzen, keine Echtdaten; die Haltezeit wirkt hier nur auf die Umsteigezeit, nicht auf die Fahrzeit der Durchfahrenden.",
    ]
    for line in lines:
        pdf.multi_cell(0, 5, _clean(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _clean("Abfahrtsminuten je Linie (Versätze des Phasen-Optimums)"), new_x="LMARGIN", new_y="NEXT")
    for li, line in enumerate(inst.lines):
        ev, _ = fixed_line_times(line, inst.T, inst.dwell, inst.tmin, int(offsets[li]) % inst.T)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, _clean(f"Linie {li + 1}: Halte {' - '.join(str(x) for x in line.stops)}, Versatz {int(offsets[li]) % inst.T} min"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for k, stop in enumerate(line.stops):
            hin = ev.get(("dep", "f", k))
            rueck = ev.get(("dep", "b", k))
            pdf.cell(30, 5, f"Halt {stop}", border=1)
            pdf.cell(55, 5, "-" if hin is None else f"Hin: Minute {hin % inst.T:02d}", border=1)
            pdf.cell(55, 5, "-" if rueck is None else f"Rück: Minute {rueck % inst.T:02d}", border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
    return bytes(pdf.output())
