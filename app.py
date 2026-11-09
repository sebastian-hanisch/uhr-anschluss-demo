"""Uhr und Anschluss – wie lange wartet ein Umsteiger im Takt - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Diese Demo gehört zur Linie „Takt und Periodizität“ der Konzepte-Reihe: ein Anschluss auf dem Zifferblatt, ein Linienpaar mit Hin/Rück-Kopplung, ein kleines Netz mit
Wald-Satz. Netze und Fahrpläne sind Annahmen (Generator der Fall-Demo taktfahrplan-demo), keine Echtdaten.

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import uan_clock as K
import uan_constants as C
import uan_evaluation as E
import uan_forest as F
import uan_results as R
import uan_search as S
import uan_visualization as V
from uan_exact import solve_phases
from uan_layout import dunkles_design, kopf_css
from uan_pdf_export import generate_report_pdf
from uan_presets import (
    SETTING_SPECS,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)

st.set_page_config(page_title="Uhr und Anschluss – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner=False)
def _results():
    return R.load_results()


@st.cache_data(show_spinner=False)
def _analysis(settings):
    return E.analyse(settings)


def _dir_word(d):
    return "hin" if d == "f" else "rück"


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in uan_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("🕒 Uhr und Anschluss – wie lange wartet ein Umsteiger im Takt")
st.markdown(
    """
Diese Demo gehört zur Linie **Takt und Periodizität** der Konzepte-Reihe. Im Takt fährt jede Linie jede Stunde zur selben Minute; wer umsteigt, wartet auf den **Rest einer Uhr**. Die Demo erklärt in drei Schritten,
wie viel dieser Wartezeit im Fahrplan **festliegt** und wie viel an den **Versätzen der Linien** hängt: ein **Anschluss** auf dem Zifferblatt, ein **Linienpaar** mit Hin- und Rückweg,
ein **kleines Netz**. Die Fall-Demo [taktfahrplan-demo](https://sebastianhanisch-taktfahrplan-demo.streamlit.app/) sucht und misst Fahrpläne am Netz (dort steht auch der Versatz-Regler am echten Netz); hier wird erklärt.
Netze und Fahrpläne sind **Annahmen** (synthetisches Modell), keine Echtdaten.

Darunter erklärt der Expander **💬 In einfachen Worten** die Aussage ohne Formeln; weiter unten: die **🔬 Experimente** an 600 Netzen, **🚧 Wo die Annahmen enden** und der Expander **📐 Mathematische Formulierung**.
"""
)

# erklaerseite:einfach:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/uhr-anschluss-erklaert.json, nicht von Hand ändern)
with st.expander("💬 In einfachen Worten"):
    st.markdown(
        """
Im Takt fährt jede Linie jede Stunde zur selben Minute. Wer umsteigt, wartet auf den **Rest einer Uhr**: die Zeit von der Ankunft bis zur nächsten Abfahrt der anderen Linie. Fährt der Anschluss eine Minute zu früh ab, wartet der Fahrgast fast eine ganze Stunde länger.

Hin- und Rückweg zwischen zwei Linien hängen zusammen: Was der eine Weg gewinnt, verliert der andere. Die Summe beider Wartezeiten nimmt höchstens zwei Werte an, einen kleinsten und diesen plus eine Stunde. Der kleinste Wert steht im Fahrplan fest, er folgt aus den **Schleifenzeiten** der beiden Linien. Der **Versatz** entscheidet nur, ob er gilt. Alle Umstiege zweier Linien teilen sich einen Versatz. Hängen die Linien eines Netzes wie ein Baum ohne Ringe zusammen, erreicht jedes Linienpaar seinen besten Wert.

[Ausführlich und verständlich erklärt, mit Fachteil](https://sebastianhanisch.net/uhr-anschluss-erklaert.html)
        """
    )
# erklaerseite:einfach:end

with st.expander("So funktioniert der Takt-Anschluss", expanded=True):
    st.markdown(
        f"""
1. **Die Uhr:** Fährt der Zug der Linie B jede Stunde zur Minute *d* und kommt Linie A zur Minute *a* an, wartet der Umsteiger ((*d* − *a* − *m*) mod {C.T}) + *m* Minuten, mit der Mindest-Umsteigezeit *m*.
   Ein Zug, der eine Minute zu früh abfährt, kostet fast eine Stunde.
2. **Hin und zurück:** Der Rückweg desselben Anschlusses hat dieselben Fahrzeiten rückwärts. Die **Summe** beider Wartezeiten nimmt nur zwei Werte an, 2·*m* + *c* oder 2·*m* + *c* + {C.T};
   *c* steht im Fahrplan fest (aus den **Schleifenzeiten** der beiden Linien), der Versatz entscheidet nur, welcher der beiden Werte gilt.
3. **Das Netz:** Alle Anschlüsse zweier Linien teilen **einen** Versatz. Die Untergrenze je Linienpaar liegt deshalb nicht niedriger als die je Hin/Rück-Paar; ist der Liniengraph ein **Wald**, ist sie auch erreichbar.
        """
    )

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("⚙️ Einstellungen")
    st.markdown("**Netz**")
    lines = st.select_slider("Linien", options=C.LINES_OPTIONS, key="lines", help="Zahl der Linien des synthetischen Netzes (der Generator lässt Linien mit weniger als zwei Halten weg).")
    seed = st.number_input("Zufalls-Seed des Netzes", *bounds("seed"), key="seed", step=1, help="Gültig ist der erste Seed ab diesem Wert mit mindestens drei Umsteigeverbindungen.")
    st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed)
    st.markdown("**Fahrplan-Annahmen**")
    dwell = st.slider("Haltezeit an Zwischenhalten (min)", *bounds("dwell"), key="dwell",
                      help="Wirkt hier nur auf die Umsteigezeit. Die längere Haltezeit verlängert die Fahrzeit der Durchfahrenden; das ist nicht eingerechnet.")
    mt = st.slider("Mindest-Umsteigezeit (min)", *bounds("mt"), key="mt", help="Kürzeste Zeit, die ein Umsteiger zwischen Ankunft und Abfahrt braucht.")
    st.markdown("**Liniengraph**")
    forest = st.toggle("Nur den aufspannenden Wald der Linienpaare behalten", key="forest",
                       help="Streicht alle Umstiege bis auf die eines aufspannenden Waldes (Kruskal nach Gewicht): dann gilt der Wald-Satz.")

settings = E.Settings(lines=int(lines), seed=int(seed), dwell=int(dwell), mt=int(mt), forest=bool(forest))
res = _results()
oc = R.oracle_counts(res)

# ===================================================================================================================================
# Schritt 1: ein Anschluss auf dem Zifferblatt
# ===================================================================================================================================

st.markdown("## 🕒 Schritt 1: Ein Anschluss auf dem Zifferblatt")
st.markdown(
    f"Linie A kommt zur Minute *a* an, Linie B fährt (ohne Versatz) zur Minute {C.B_BASE_DEP} ab; der **Versatz** verschiebt die ganze Linie B. "
    f"Die Mindest-Umsteigezeit ({settings.mt} min) steht in der Seitenleiste. Gerechnet wird auf zwei Wegen, die nichts voneinander wissen: als **Rest modulo {C.T}** und über die **Fahrplantafel** der Linie B."
)
c1, c2 = st.columns(2)
arr = c1.slider("Ankunft der Linie A (Minute)", *bounds("arr"), key="arr")
shift = c2.slider("Versatz der Linie B (min)", *bounds("shift"), key="shift", help=f"Linie B fährt zur Minute {C.B_BASE_DEP} + Versatz (mod {C.T}) ab.")
conn = E.connection(int(arr), int(shift), settings.mt)
m1, m2, m3 = st.columns(3)
m1.metric("Wartezeit (Rest modulo T)", f"{conn.wait_mod} min")
m2.metric("Wartezeit (Fahrplantafel)", f"{conn.wait_board} min", delta="gleich" if conn.wait_board == conn.wait_mod else "weicht ab", delta_color="off" if conn.wait_board == conn.wait_mod else "inverse")
m3.metric(f"Mittel über alle {C.T} Versätze", E.fmt(conn.mean_random) + " min", delta=f"= {settings.mt} + ({C.T} − 1) / 2", delta_color="off")
left, right = st.columns([1, 1])
with left:
    st.plotly_chart(V.build_clock(conn.arr, conn.dep, settings.mt, conn.wait_mod), width="stretch", key="clock_chart")
with right:
    rows = K.board_rows(conn.arr, conn.dep, settings.mt, C.T)
    board = ({
        "Abfahrt Linie B (Uhrzeit)": [f"{(720 + r['dep']) // 60}:{(720 + r['dep']) % 60:02d}" for r in rows],
        "Abstand zur Ankunft (min)": [r["gap"] for r in rows],
        "erreichbar": ["ja" if r["ok"] else "nein" for r in rows],
    })
    st.markdown(f"**Fahrplantafel der Linie B** (Ankunft der Linie A um 12:{conn.arr:02d})")
    st.dataframe(board, hide_index=True, width="stretch")
    st.caption("Der erste erreichbare Zug bestimmt die Wartezeit; die Tafel kommt ohne Modulo-Rechnung aus.")
st.plotly_chart(V.build_sawtooth(conn.curve, int(shift), settings.mt, conn.mean_random), width="stretch", key="saw_chart")
st.caption(f"Sägezahn: jede Minute Versatz (der Zug fährt eine Minute später ab) kostet eine Minute Warten, bis der nächste Zug erreichbar wird; dann fällt die Wartezeit um {C.T - 1} min auf die Mindestzeit. "
           f"Bei gleichverteiltem Versatz ist die mittlere Wartezeit {settings.mt} + ({C.T} − 1) / 2 = {E.fmt(K.random_mean_wait(settings.mt, C.T))} min, unabhängig von *a*.")
kind, text = E.verdict_connection(conn.wait_mod, settings.mt)
getattr(st, kind)(text)

st.markdown("---")

# ===================================================================================================================================
# Schritt 2: ein Linienpaar
# ===================================================================================================================================

with st.spinner("Netz wird gerechnet …"):
    a = _analysis(settings)

st.markdown("## 🔁 Schritt 2: Ein Linienpaar mit allen seinen Anschlüssen")
st.markdown(
    f"In diesem Modell hat jeder Umstieg einen Rückweg (in {oc['all_paired']} von {oc['nets']} Netzen der Messreihe ist das gesamte Umsteigegewicht in Hin/Rück-Paaren erfasst). Beide Wege hängen am **selben** Versatz *u* der Linie B gegen A: was die eine Wartezeit spart, kostet die andere. "
    f"Gezeigt wird ein Linienpaar des Netzes mit {a.n_lines} Linien (Seed {a.used_seed})."
)
st.info("**Haltezeit gilt hier nur als Umsteigezeit.** Eine längere Haltezeit verlängert auch die Fahrzeit der Durchfahrenden; das ist in dieser Demo nicht eingerechnet "
        "(Regler *Haltezeit* in der Seitenleiste). Der Versatz-Regler am echten Netz steht in der Fall-Demo taktfahrplan-demo; hier zeigt die Kurve alle Versätze auf einmal.")

pair_list = E.line_pair_list(a)
pair_labels = {f"Linie {p['pair'][0] + 1} ↔ Linie {p['pair'][1] + 1} · {p['activities']} Umstiege, Gewicht {E.fmt(p['weight'])}": p["pair"] for p in pair_list}
if st.session_state.get("pair_sel") not in pair_labels:
    st.session_state.pop("pair_sel", None)
pair_label = st.selectbox("Linienpaar", list(pair_labels), key="pair_sel", help="Die Linienpaare sind nach dem Gewicht ihrer Umstiege sortiert (schwerstes zuerst).")
line_pair = pair_labels[pair_label]
hr = E.hin_rueck_of(a, line_pair)
hr_labels = {}
for i, (k1, k2, pp) in enumerate(hr):
    la_, da_, ka_, lb_, db_, kb_ = k1
    hr_labels[f"Halt {a.inst.lines[la_].stops[ka_]}: Linie {la_ + 1} ({_dir_word(da_)}) → Linie {lb_ + 1} ({_dir_word(db_)}) und zurück"] = i
if st.session_state.get("pair_idx") not in hr_labels:
    st.session_state.pop("pair_idx", None)
hr_label = st.selectbox("Anschluss (Hin/Rück-Paar)", list(hr_labels), key="pair_idx")
pv = E.pair_view(a, line_pair, hr_labels[hr_label])
mtv = a.inst.transfer_min
p1, p2, p3, p4 = st.columns(4)
p1.metric("Konstante c", f"{pv.params.c} min")
p2.metric("kleinste Summe", f"{2 * mtv + pv.params.c} min", delta=f"= 2·{mtv} + c", delta_color="off")
p3.metric("Versätze auf dem kleineren Wert", f"{pv.params.c + 1} von {C.T}")
p4.metric("Schleifen A / B", f"{pv.loops[0]} / {pv.loops[1]} min")
lcol, rcol = st.columns([3, 2])
with lcol:
    st.plotly_chart(V.build_pair_chart(pv, mtv), width="stretch", key="pair_chart")
with rcol:
    st.plotly_chart(V.build_loops(pv, mtv), width="stretch", key="loop_chart")
st.caption("**Schleifenzeit:** die Zeit von der Ankunft an diesem Halt bis zur Abfahrt am selben Halt in der Gegenrichtung (über den Endpunkt und zurück). "
           f"c ist die Summe der beiden Schleifen minus 2·{mtv}, modulo {C.T}; sie entsteht allein aus Fahrzeiten, Halten und der Wende. Rechts steht diese Rechnung.")
kind, text = E.verdict_pair(pv, mtv)
getattr(st, kind)(text)

st.markdown("### Spiegelpaar: dieselben Halte, beide Richtungen vertauscht")
if pv.mirror is None:
    st.info("Für diesen Anschluss gibt es kein gespiegeltes Paar am selben Halt im Netz (Endhalt oder nicht nachgefragt).")
else:
    mi = pv.mirror
    st.markdown(
        f"Das gespiegelte Paar hat **c′ = {mi.params.c}**. Zwischen beiden gilt c + c′ ≡ 4·(Haltezeit − Mindestzeit) = {4 * (a.inst.dwell - mtv)}, also {(4 * (a.inst.dwell - mtv)) % C.T} (mod {C.T}); "
        f"hier ist c + c′ = {pv.params.c + mi.params.c}. Gut-Mengen disjunkt: **{'ja' if mi.disjoint else 'nein'}**."
    )
    st.plotly_chart(V.build_mirror_chart(pv, mtv), width="stretch", key="mirror_chart")
    st.caption(f"Beide Paare auf einem Versatz: kleinste gewichtete Summe {E.fmt(pv.joint_min)} statt {E.fmt(pv.separate_min)} (Summe der Einzel-Untergrenzen); Zuschlag {E.fmt(pv.surcharge)} (gewichtete Minuten; Gewicht = Nachfrage).")
    kind, text = E.verdict_mirror(pv, a.inst.dwell, mtv)
    getattr(st, kind)(text)

st.markdown("### Gleichgerichtetes Paar und die Haltezeit")
same_here = E.same_direction_of(a, line_pair) or E.same_direction_of(a)
if not same_here:
    st.info("In diesem Netz gibt es kein gleichgerichtetes Umsteigepaar (A → B und B → A in derselben Fahrtrichtung am selben Halt).")
else:
    key, rev, spp = max(same_here, key=lambda t: (t[2].w1 + t[2].w2, t[0]))
    rows_d = E.dwell_table(a.inst, key, rev)
    st.markdown(
        f"Umsteigen **von A nach B und von B nach A in derselben Fahrtrichtung** am selben Halt (hier Halt {a.inst.lines[key[0]].stops[key[2]]}, Linie {key[0] + 1} ↔ Linie {key[3] + 1}) "
        f"hat die Konstante c = (2·Haltezeit − 2·Mindestzeit) mod {C.T}: unter der Mindestzeit ist sie groß, bei Haltezeit = Mindestzeit ist sie 0 (ein Taktknoten). "
        "Die Tabelle rechnet den Fahrplan für jede Haltezeit neu aus den Ereigniszeiten."
    )
    tcol, ccol = st.columns([2, 3])
    with tcol:
        st.dataframe(({"Haltezeit (min)": [r["dwell"] for r in rows_d], "c (min)": [r["c"] for r in rows_d],
                                   "kleinste Summe beider Wartezeiten (min)": [r["min_sum"] for r in rows_d]}), hide_index=True, width="stretch")
    with ccol:
        st.plotly_chart(V.build_dwell_chart(rows_d, a.inst.dwell, mtv), width="stretch", key="dwell_chart")
    kind, text = E.verdict_dwell(rows_d, a.inst.dwell, mtv)
    getattr(st, kind)(text)

st.markdown("---")

# ===================================================================================================================================
# Schritt 3: das Netz
# ===================================================================================================================================

st.markdown("## 🕸️ Schritt 3: Ein kleines Netz")
st.markdown(
    "Im **Liniengraphen** sind die Linien Knoten und Linienpaare mit Umstiegen Kanten. Alle Anschlüsse eines Linienpaars teilen einen Versatz: die Untergrenze **je Linienpaar** (LB2) "
    "liegt deshalb nicht unter der **je Hin/Rück-Paar** (LB). Bildet der Graph einen **Wald**, sind die Versätze der Linienpaare unabhängig wählbar und das Optimum ist genau LB2; Kreise erzeugen den Rest."
)
k1_, k2_, k3_, k4_, k5_ = st.columns(5)
k1_.metric("Zufälliger Versatz", f"{E.fmt(a.rand_exact, 2)} min", delta=f"= {mtv} + ({C.T} − 1) / 2", delta_color="off")
k2_.metric("LB je Hin/Rück-Paar", f"{E.fmt(a.lb, 2)} min")
k3_.metric("LB2 je Linienpaar", f"{E.fmt(a.lb2, 2)} min")
k4_.metric("Phasen-Optimum", f"{E.fmt(a.opt, 2)} min", delta="Lokalsuche", delta_color="off")
k5_.metric("Kreisrang", f"{a.rank}", delta="Wald" if a.is_forest else "mit Kreisen", delta_color="off")
gcol, wcol = st.columns([2, 3])
with gcol:
    st.plotly_chart(V.build_line_graph(a), width="stretch", key="graph_chart")
    st.caption("Grün: Kanten des aufspannenden Waldes; orange gepunktet: Kanten, die einen Kreis schließen. Kantenbreite nach dem Gewicht der Umstiege.")
with wcol:
    st.plotly_chart(V.build_waterfall(a), width="stretch", key="waterfall_chart")
    st.caption("Zerlegung der mittleren Wartezeit bei zufälligem Versatz in Mindestzeit, Hin/Rück-Kopplung je Paar, mehrere Anschlüsse einer Linienpaarung und Kreise (einschließlich des Restabstands der Lokalsuche); "
               "der Rest bis zum Zufall ist der Gewinn der Optimierung.")
st.markdown("## ❓ Kernfrage: Welcher Teil der Wartezeit steht im Fahrplan fest?")
kind, text = E.verdict_net(a)
getattr(st, kind)(text)

arrs = S.base_arrays(a.inst)
if a.is_forest:
    fo = F.forest_offsets(a.inst)
    cost_fo = S.mean_wait(arrs, fo)
    st.success(f"**Konstruktion statt Suche:** Versätze {list(fo)} setzen jedes Linienpaar auf sein Minimum; die mittlere Wartezeit ist {E.fmt(cost_fo, 2)} min und gleich LB2 ({E.fmt(a.lb2, 2)} min). "
               "Da LB2 eine Untergrenze ist, ist das das Optimum.")

key_now = (settings, C.EXACT_TIME_LIMIT)
if st.button(f"▶️ Exakt prüfen (CP-SAT, höchstens {int(C.EXACT_TIME_LIMIT)} s, {C.EXACT_WORKERS} Arbeiter)", key="exact_button"):
    with st.spinner(f"CP-SAT rechnet (Zeitlimit {int(C.EXACT_TIME_LIMIT)} s) …"):
        st.session_state["exact"] = (key_now, solve_phases(arrs, C.EXACT_TIME_LIMIT, C.EXACT_WORKERS, hint=a.opt_offsets))
exact = st.session_state.get("exact")
if exact and exact[0] == key_now:
    ex = exact[1]
    if ex.status in ("OPTIMAL", "FEASIBLE"):
        kind, text = E.verdict_exact(a.opt, ex.mean_wait, ex.bound_wait, ex.proven)
        getattr(st, kind)(text)
    else:
        st.warning("CP-SAT fand im Zeitlimit keine Lösung.")
else:
    st.caption("Die Lokalsuche (40 Neustarts) ist ein Verfahren ohne Beweis; der Knopf lässt CP-SAT dasselbe Netz exakt lösen, mit Zeitlimit und der Anzeige „nicht bewiesen“.")
st.download_button("📄 Bericht als PDF (Versätze des Phasen-Optimums)", data=generate_report_pdf(a, a.opt_offsets), file_name="uhr-anschluss-bericht.pdf", mime="application/pdf")

st.markdown("---")

# ===================================================================================================================================
# Experimente
# ===================================================================================================================================

dist = R.c_distribution(res)
table = R.bounds_table(res)
fs = R.forest_summary(res)
cps = R.cp_summary(res)
mir = R.mirror_summary(res)
same = R.same_summary(res)
drows = R.dwell_rows(res)
spl = R.split_summary(res)

st.subheader("🔬 Experiment 1: Die Kopplung an 600 Netzen, gegen die Fahrplantafel geprüft")
st.caption(f"{oc['nets']} Netze (3, 5, 6, 8, 10 Linien; je vier Blöcke zu 30 Netzen), Seeds ab {C.SWEEP_SEED_BASE}; Haltezeit {C.DEFAULT_DWELL} min, Mindestzeit {C.DEFAULT_TRANSFER_MIN} min. "
           "„a ± s“ heißt Mittel der vier Block-Mittel ± Standardabweichung über die Blöcke.")
st.plotly_chart(V.build_c_histogram(dist), width="stretch", key="c_hist")
kind, text = E.verdict_e1(oc, dist, R.lb_share(res), R.bound_reached(res))
getattr(st, kind)(text)

st.subheader("🔬 Experiment 2: Drei Untergrenzen nach Linienzahl")
st.plotly_chart(V.build_bounds_chart(table), width="stretch", key="bounds_chart")
st.dataframe(({
    "Linien": [str(k) for k in C.SWEEP_LINES] + ["alle"],
    "Zufall": [R.pm(table[k]["rand"]) for k in list(C.SWEEP_LINES) + ["alle"]],
    "Phasen-Optimum": [R.pm(table[k]["opt"]) for k in list(C.SWEEP_LINES) + ["alle"]],
    "LB2 je Linienpaar": [R.pm(table[k]["lb2"]) for k in list(C.SWEEP_LINES) + ["alle"]],
    "LB je Hin/Rück-Paar": [R.pm(table[k]["lb"]) for k in list(C.SWEEP_LINES) + ["alle"]],
    "erklärter Anteil LB": [R.pm((100 * table[k]["share1"][0], 100 * table[k]["share1"][1]), 1) + " %" for k in list(C.SWEEP_LINES) + ["alle"]],
    "erklärter Anteil LB2": [R.pm((100 * table[k]["share2"][0], 100 * table[k]["share2"][1]), 1) + " %" for k in list(C.SWEEP_LINES) + ["alle"]],
}), hide_index=True, width="stretch")
kind, text = E.verdict_e2(table)
getattr(st, kind)(text)

st.subheader("🔬 Experiment 3: Wald gegen Kreise")
st.plotly_chart(V.build_rank_chart(fs["classes"]), width="stretch", key="rank_chart")
kind, text = E.verdict_e3(fs, cps)
getattr(st, kind)(text)
st.caption(f"Gegenprobe der Lokalsuche an {cps['a_n']} Netzen gegen CP-SAT ({C.EXACT_TIME_LIMIT:.0f} s, {C.EXACT_WORKERS} Arbeiter): {cps['a_proven']} von {cps['a_n']} bewiesen, "
           f"die Lokalsuche lag in {cps['a_ls_worse']} über dem CP-SAT-Fund (größte Abweichung {E.fmt(cps['a_max_dev'], 2)} min in der gespeicherten Messung; die Größe der Abweichung hängt vom Zeitlimit-Lauf ab).")

st.subheader("🔬 Experiment 4: Haltezeit als Regler")
st.plotly_chart(V.build_dwell_series(drows), width="stretch", key="dwell_series")
kind, text = E.verdict_e4(drows)
getattr(st, kind)(text)
st.caption(f"Gleichgerichtete Paare ({E.thousands(same['pairs'])} bei Haltezeit {C.DEFAULT_DWELL}, in {same['nets_with']} von {same['nets']} Netzen): {E.thousands(same['act_in'])} von {E.thousands(same['act_total'])} Umstiegen gehören zu einem.")

st.subheader("🔬 Experiment 5: Brücke zur Wende-Standzeit")
st.plotly_chart(V.build_split_chart(spl), width="stretch", key="split_chart")
kind, text = E.verdict_e5(spl)
getattr(st, kind)(text)

st.markdown("---")

# ===================================================================================================================================
# Grenzen
# ===================================================================================================================================

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    f"""
| Annahme | Was passiert, wenn sie verletzt ist | Wer setzt an |
|---|---|---|
| **Synthetische Netze** des Generators der Fall-Demo (20 Haltestellen, bis zu 6 Halte je Linie), ein Regelsatz: Takt {C.T}, Mindestzeit {C.DEFAULT_TRANSFER_MIN}, Halt {C.DEFAULT_DWELL} | Die Zahlen sind Messungen an diesen Netzen, keine Aussagen über reale Netze; andere Regelsätze liegen nur in den Reglern *Haltezeit* und *Mindestzeit* vor. | – |
| **Haltezeit nur als Umsteigezeit** | Eine längere Haltezeit verlängert die Fahrzeit der Durchfahrenden; die Demo rechnet das nicht ein. Der Netz-Effekt von 3 statt 2 min Haltezeit (Experiment 4) betrifft die Umsteigezeit allein; was die längere Haltezeit den Durchfahrenden kostet, ist nicht gemessen. | eine spätere Demo dieser Linie |
| **Standard-Aufteilung der Wende-Standzeit** | Bei freier Aufteilung liegt die kleinste gefundene Untergrenze je Hin/Rück-Paar bei {E.fmt(spl['lb_free'][0], 2)} statt {E.fmt(spl['lb_std'][0], 2)} min (Experiment 5, obere Schranke des wahren Minimums); ob LB2 dann die nächste Schranke ist, ist nicht gemessen. | eine spätere Demo dieser Linie (Takt suchen) |
| **Phasen-Optimum aus einer Lokalsuche** | Die Lokalsuche ist kein Beweis; im Vergleich mit CP-SAT lag sie in {cps['a_ls_worse']} von {cps['a_n']} Netzen über dem Fund (Experiment 3). Der Knopf in Schritt 3 prüft ein Netz exakt. | – |
| **Kreise über drei und mehr Linien** | Der Kreis-Rest (Optimum minus LB2) wird hier gemessen, aber nicht über eine Kreisbasis erklärt. | eine spätere Demo dieser Linie (Kreise und Spannung) |
| **Anschlüsse ohne Zugfolge und Zusatzzug** | Mindest-Zugfolge, Zusatzzüge und Fahrzeugumlauf fehlen. | Fall-Demo taktfahrplan-demo |
"""
)

st.markdown("---")

# ===================================================================================================================================
# Mathematik
# ===================================================================================================================================

with st.expander("📐 Mathematische Formulierung"):
    # erklaerseite:lesehilfe:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/uhr-anschluss-erklaert.json, nicht von Hand ändern)
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind ein Takt $T$, Linien mit festen Fahrzeiten, Haltezeiten und Wenden sowie gewichtete Umstiege (Ankunft einer Linie, Abfahrt einer anderen). Gesucht ist der **Versatz** $o_A \in \{0, \dots, T-1\}$ jeder Linie, der die gewichtete mittlere Wartezeit der Umsteiger klein macht. Es zählen nur Umsteigezeiten.

| Symbol | Bedeutung |
|---|---|
| $T$ | Takt in Minuten |
| $m$ | Mindest-Umsteigezeit |
| $h$ | Haltezeit an Zwischenhalten |
| $a$, $d$ | Ankunftsminute der einen, Abfahrtsminute der anderen Linie |
| $x$ | Wartezeit eines Umstiegs |
| $u = o_B - o_A$ | Versatz der Linie $B$ gegen $A$ |
| $D_1, D_2$ | Abfahrt minus Ankunft minus $m$ bei Versatz $0$ (Hin- und Rückweg) |
| $c$ | Konstante eines Hin/Rück-Paars, $c = (D_1 + D_2) \bmod T$ |
| $L_A$, $L_B$ | Schleifenzeiten der beiden Linien |
| $f_{AB}(u)$ | gewichtete Summe aller Wartezeiten zwischen $A$ und $B$ |
| $\mathrm{LB}_2$, $\mathrm{OPT}$ | Untergrenze je Linienpaar und bestes erreichbares Netz-Ergebnis |

[Schritt für Schritt erklärt, mit Herleitung und Literatur](https://sebastianhanisch.net/uhr-anschluss-erklaert.html#fachleute)
        """
    )
    # erklaerseite:lesehilfe:end
    st.markdown(
        r"""
Es zählen nur Umsteigezeiten, Zufall kommt nur in der Auswahl der Netze und der Startversätze der Lokalsuche vor.

**Wartezeit (Zifferblatt).** Für Ankunft $a$ und Abfahrt $d$:

$$x = \big((d - a - m) \bmod T\big) + m$$

**Hin/Rück-Paar.** Mit $x_1 = ((u + D_1) \bmod T) + m$ und $x_2 = ((-u + D_2) \bmod T) + m$ gilt

$$x_1 + x_2 = 2m + c + T \cdot \mathbf{1}\big[(u + D_1) \bmod T > c\big], \qquad c = (D_1 + D_2) \bmod T$$

Der kleinere Wert $2m + c$ gilt bei genau $c + 1$ von $T$ Versätzen (die **Gut-Menge**), unabhängig von allen anderen Linien.

**Schleifenzeit.** Die Schleife einer Linie an einem Halt ist die Zeit von der Ankunft bis zur Abfahrt am selben Halt in der Gegenrichtung. Mit den Schleifen $L_A$ und $L_B$ der beiden Linien:

$$c \equiv L_A + L_B - 2m \pmod T$$

**Spiegelpaar.** Vertauscht man beide Richtungen (Zwischenhalte beider Linien), gilt für die Konstante $c'$ des gespiegelten Paars

$$c + c' \equiv 4\,(h - m) \pmod T$$

*Satz (disjunkte Gut-Mengen).* Sei $h < m$ und $e = 2(m - h)$. Die Gut-Menge des Paars ist das Intervall $[s,\, s + c]$ modulo $T$, die des Spiegelpaars $[s',\, s' + c']$; es gilt $s' - s \equiv c + e \pmod T$,
und $c + c' \in \{T - 2e,\; 2T - 2e\}$. Bei $c + c' = T - 2e$ liegt das zweite Intervall bei $c + e, \dots, T - e$ relativ zu $s$, also hinter dem ersten und vor seinem nächsten Anfang: **disjunkt**.
Bei $c + c' = 2T - 2e$ haben die Gut-Mengen zusammen mehr als $T$ Elemente und überschneiden sich daher (Schubfachprinzip): **Überschneidung**. Bei $h \ge m$ gilt der Satz nicht (Messung: Experiment 4). Sind die Gut-Mengen disjunkt, kostet das Paar zusammen mindestens

$$\min_u \big(w_1 x(u) + w_2 x'(u)\big) = w_1 (2m + c) + w_2 (2m + c') + T \cdot \min(w_1, w_2)$$

**Gleichrichtungs-Paar** ($A \to B$ und $B \to A$ in derselben Fahrtrichtung am selben Zwischenhalt):

$$c_{=} = (2h - 2m) \bmod T$$

**Linienpaarung und Wald.** Alle Umstiege zweier Linien teilen den Versatz $u$; die Untergrenze des Netzes ist

$$\mathrm{LB}_2 = \sum_{\{A,B\}} \min_{u} f_{AB}(u) \;\le\; \mathrm{OPT}$$

*Satz (Wald).* Ist der Liniengraph (Kanten = Linienpaare mit Umstiegen) ein Wald, ist $\mathrm{OPT} = \mathrm{LB}_2$: Man wählt je Komponente eine Wurzel mit Versatz $0$ und setzt jedes Kind auf Elternversatz plus $\arg\min_u f_{AB}(u)$;
jede Kante liegt dann auf ihrem Minimum, die Kosten sind $\mathrm{LB}_2$. Bei Kreisen kann ein Kind nicht jede seiner Kanten auf das Minimum setzen; der Rest $\mathrm{OPT} - \mathrm{LB}_2$ ist das, was die Kreise kosten.

**Zufall.** Bei gleichverteiltem Versatz ist $(d - a - m) \bmod T$ gleichverteilt auf $0, \dots, T-1$, also $\mathbb{E}[x] = m + (T-1)/2$.

**Verfahren und Literatur.** Das Modell ist das *Periodic Event Scheduling Problem* (PESP); Quellen und die Suche nach Fahrplänen am Netz stehen in der Fall-Demo taktfahrplan-demo.
Die Aussagen oben sind Messungen und Beweise für das hier definierte Modell.
        """
    )

sync_query_params({key: st.session_state[key] for key in SETTING_SPECS})

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zur Reihe: [Takt und Periodizität: Fahrplan im Stundentakt](https://sebastianhanisch.net/konzepte-takt-periodizitaet.html)."
)
