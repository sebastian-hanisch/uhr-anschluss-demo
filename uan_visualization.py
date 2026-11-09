"""Plotly-Abbildungen der Demo „Uhr und Anschluss“. Alle Achsen fest (fixedrange), damit Touch-Scrollen nicht am Diagramm hängen bleibt;
Zifferblatt und Liniengraph mit scaleanchor nur mit autorange und Eckmarkern (Plotly friert sonst den Bereich beim ersten Zeichnen ein)."""
from __future__ import annotations

import math

import plotly.graph_objects as go

import uan_constants as C


def _lock(fig, height=340, **layout):
    fig.update_layout(height=height, margin=dict(l=50, r=20, t=30, b=55), font=dict(size=12),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0), **layout)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def runs(values: list[int], period: int) -> list[tuple[int, int]]:
    """Zusammenhängende Läufe einer Menge von Minuten auf dem Zifferblatt (zyklisch): [(Anfang, Ende)] mit Ende >= Anfang; ein Lauf über die 0 wird geteilt."""
    s = sorted(set(values))
    out: list[list[int]] = []
    for v in s:
        if out and v == out[-1][1] + 1:
            out[-1][1] = v
        else:
            out.append([v, v])
    return [(a, b) for a, b in out]


def _minute_xy(minute: float, radius: float) -> tuple[float, float]:
    angle = math.radians(6.0 * minute)          # 0 oben, im Uhrzeigersinn
    return radius * math.sin(angle), radius * math.cos(angle)


def build_clock(arr: int, dep: int, mt: int, wait: int, period: int = C.T) -> go.Figure:
    """Zifferblatt: Ankunft der Linie A, früheste mögliche Abfahrt (Ankunft + Mindestzeit), Abfahrt der Linie B; die Wartezeit als Spirale im Uhrzeigersinn."""
    fig = go.Figure()
    ring = [_minute_xy(m / 4, 1.0) for m in range(period * 4 + 1)]
    fig.add_trace(go.Scatter(x=[p[0] for p in ring], y=[p[1] for p in ring], mode="lines", line=dict(color="#95a0ae", width=1.5), hoverinfo="skip", showlegend=False))
    for m in range(0, period, 5):
        x0, y0 = _minute_xy(m, 0.96)
        x1, y1 = _minute_xy(m, 1.0)
        fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", line=dict(color="#95a0ae", width=2), hoverinfo="skip", showlegend=False))
        tx, ty = _minute_xy(m, 1.12)
        fig.add_annotation(x=tx, y=ty, text=str(m), showarrow=False, font=dict(size=12, color="#5b6b80"))
    steps = max(2, int(wait * 4))
    spiral = [_minute_xy(arr + wait * k / steps, 0.80 + 0.12 * (wait * k / steps) / period) for k in range(steps + 1)]
    fig.add_trace(go.Scatter(x=[p[0] for p in spiral], y=[p[1] for p in spiral], mode="lines", line=dict(color=C.COLOR_SUM, width=4), name=f"Wartezeit {wait} min",
                             hoverinfo="skip"))
    mt_steps = max(2, mt * 4)
    held = [_minute_xy(arr + mt * k / mt_steps, 0.80 + 0.12 * (mt * k / mt_steps) / period) for k in range(mt_steps + 1)]
    fig.add_trace(go.Scatter(x=[p[0] for p in held], y=[p[1] for p in held], mode="lines", line=dict(color=C.COLOR_GREY, width=7), name=f"Mindestzeit {mt} min",
                             hoverinfo="skip"))
    ax, ay = _minute_xy(arr, 0.80)
    fig.add_trace(go.Scatter(x=[ax], y=[ay], mode="markers+text", marker=dict(size=16, color=C.COLOR_A), text=["A"], textposition="top center",
                             name=f"Ankunft Linie A (Minute {arr})", hovertemplate=f"Ankunft Minute {arr}<extra></extra>"))
    ex, ey = _minute_xy(arr + mt, 0.80 + 0.12 * mt / period)
    fig.add_trace(go.Scatter(x=[ex], y=[ey], mode="markers", marker=dict(size=12, color="white", line=dict(color="#1c2430", width=2), symbol="diamond"),
                             name=f"früheste Abfahrt (Minute {(arr + mt) % period})", hovertemplate="früheste mögliche Abfahrt<extra></extra>"))
    dx, dy = _minute_xy(arr + wait, 0.80 + 0.12 * wait / period)
    fig.add_trace(go.Scatter(x=[dx], y=[dy], mode="markers+text", marker=dict(size=16, color=C.COLOR_B), text=["B"], textposition="bottom center",
                             name=f"Abfahrt Linie B (Minute {dep})", hovertemplate=f"Abfahrt Minute {dep}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[-1.35, 1.35], y=[-1.35, 1.35], mode="markers", marker=dict(opacity=0), showlegend=False, hoverinfo="skip"))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="left", x=0))
    fig.update_xaxes(visible=False, fixedrange=True, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False, fixedrange=True)
    return fig


def build_sawtooth(curve, current: int, mt: int, mean: float) -> go.Figure:
    """Wartezeit über alle Versätze der Linie B (Sägezahn): steigt um 1 min je Minute Versatz (die Abfahrt der Linie B liegt später), fällt dann um T − 1 min auf die Mindestzeit."""
    xs = list(range(len(curve)))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=list(curve), mode="lines+markers", line=dict(color=C.COLOR_SUM, width=2), marker=dict(size=4), name="Wartezeit",
                             hovertemplate="Versatz %{x}: %{y} min<extra></extra>"))
    fig.add_hline(y=mean, line_color=C.COLOR_GREY, line_dash="dash", annotation_text=f"Mittel über alle Versätze: {mean:.1f}".replace(".", ","),
                  annotation_position="top left")
    fig.add_hline(y=mt, line_color=C.COLOR_B, line_dash="dot", annotation_text=f"Mindestzeit {mt}", annotation_position="bottom right")
    fig.add_vline(x=current, line_color="#1c2430", line_width=1.5)
    fig.add_trace(go.Scatter(x=[current], y=[curve[current]], mode="markers", marker=dict(size=11, color="#1c2430"), showlegend=False, hoverinfo="skip"))
    fig.update_xaxes(title_text="Versatz der Linie B (Minuten im Takt)", range=[0, len(curve) - 1])
    fig.update_yaxes(title_text="Wartezeit (min)", range=[0, max(curve) * 1.12])
    return _lock(fig, 320)


def _good_rects(fig, good, period, color=C.COLOR_GOOD):
    for a, b in runs(list(good), period):
        fig.add_vrect(x0=a - 0.5, x1=b + 0.5, fillcolor=color, line_width=0, layer="below")


def build_pair_chart(pv, mt: int) -> go.Figure:
    """Hin/Rück-Paar: beide Wartezeiten und ihre Summe über den Versatz u = o_B - o_A; grün hinterlegt die Versätze, bei denen die Summe auf dem kleineren Wert liegt."""
    xs = list(range(len(pv.curve)))
    fig = go.Figure()
    _good_rects(fig, pv.good, len(xs))
    fig.add_trace(go.Scatter(x=xs, y=list(pv.wait_hin), mode="lines", name="Wartezeit Hinrichtung", line=dict(color=C.COLOR_A, width=2.5)))
    fig.add_trace(go.Scatter(x=xs, y=list(pv.wait_rueck), mode="lines", name="Wartezeit Rückrichtung", line=dict(color=C.COLOR_B, width=2.5)))
    fig.add_trace(go.Scatter(x=xs, y=list(pv.curve), mode="lines", name="Summe beider", line=dict(color=C.COLOR_SUM, width=3, dash="dash")))
    fig.add_hline(y=2 * mt + pv.params.c, line_color=C.COLOR_SUM, line_dash="dot",
                  annotation_text=f"kleinste Summe 2·{mt} + c = {2 * mt + pv.params.c}", annotation_position="top left")
    fig.update_xaxes(title_text="Versatz u der Linie B gegen A (Minuten im Takt); grün: Summe auf dem kleineren Wert", range=[0, len(xs) - 1])
    fig.update_yaxes(title_text="Wartezeit (min)", range=[0, max(pv.curve) * 1.12])
    return _lock(fig, 360)


def build_loops(pv, mt: int, period: int = C.T) -> go.Figure:
    """c aus den Schleifenzeiten: Schleife A + Schleife B - 2·Mindestzeit, vermindert um ganze Takte."""
    la, lb = pv.loops
    raw = la + lb - 2 * mt
    whole = (raw - pv.c_loops)
    fig = go.Figure(go.Waterfall(
        x=["Schleife Linie A", "+ Schleife Linie B", f"− 2 · Mindestzeit ({mt})", f"− ganze Takte ({whole // period} · {period})", "= c"],
        y=[la, lb, -2 * mt, -whole, pv.c_loops], measure=["absolute", "relative", "relative", "relative", "total"],
        text=[str(la), f"+{lb}", f"−{2 * mt}", f"−{whole}", str(pv.c_loops)], textposition="outside",
        connector=dict(line=dict(color="#95a0ae")), increasing=dict(marker=dict(color=C.COLOR_A)), decreasing=dict(marker=dict(color=C.COLOR_GREY)),
        totals=dict(marker=dict(color=C.COLOR_SUM))))
    fig.update_yaxes(title_text="Minuten", rangemode="tozero")
    return _lock(fig, 330, showlegend=False)


def build_mirror_chart(pv, mt: int) -> go.Figure:
    """Paar, gespiegeltes Paar und beide auf einem Versatz (gewichtete Summen über u); die Gut-Mengen sind farbig hinterlegt."""
    from uan_pair import pair_cost_vector
    m = pv.mirror
    xs = list(range(len(pv.curve)))
    fig = go.Figure()
    _good_rects(fig, pv.good, len(xs))
    _good_rects(fig, m.good, len(xs), "rgba(142,68,173,0.20)")
    fig.add_trace(go.Scatter(x=xs, y=[pv.params.w1 * v for v in pv.curve], mode="lines", name="Paar", line=dict(color=C.COLOR_A, width=2.5)))
    mv = [m.params.w1 * float(x) for x in pair_cost_vector(m.params.d1, m.params.c, len(xs), mt)]
    fig.add_trace(go.Scatter(x=xs, y=mv, mode="lines", name="gespiegeltes Paar", line=dict(color=C.COLOR_MIRROR, width=2.5)))
    fig.add_trace(go.Scatter(x=xs, y=list(pv.joint_curve), mode="lines", name="beide auf einem Versatz", line=dict(color=C.COLOR_SUM, width=3, dash="dash")))
    fig.update_xaxes(title_text="Versatz u der Linie B gegen A (Minuten im Takt); grün: Gut-Menge des Paars, violett: des gespiegelten Paars", range=[0, len(xs) - 1])
    fig.update_yaxes(title_text="gewichtete Summe der Wartezeiten", range=[0, max(pv.joint_curve) * 1.1])
    return _lock(fig, 360)


def build_dwell_chart(rows: list[dict], current: int, mt: int) -> go.Figure:
    colors = [C.COLOR_SUM if r["dwell"] == current else C.COLOR_GREY for r in rows]
    fig = go.Figure(go.Bar(x=[f"{r['dwell']} min" for r in rows], y=[r["min_sum"] for r in rows], marker_color=colors, text=[str(r["min_sum"]) for r in rows],
                           textposition="outside", hovertemplate="Haltezeit %{x}: kleinste Summe %{y} min<extra></extra>"))
    fig.update_xaxes(title_text="Haltezeit an den Zwischenhalten")
    fig.update_yaxes(title_text="kleinste Summe beider Wartezeiten (min)", rangemode="tozero")
    return _lock(fig, 320, showlegend=False)


def build_line_graph(a) -> go.Figure:
    """Liniengraph: Linien als Knoten auf einem Kreis, Linienpaare als Kanten (Breite nach Gewicht); grün: Kanten des aufspannenden Waldes, orange: Kanten, die einen Kreis schließen."""
    n = a.n_lines
    pos = [(math.sin(2 * math.pi * i / n), math.cos(2 * math.pi * i / n)) for i in range(n)]
    forest = set(a.forest_edges)
    fig = go.Figure()
    wmax = max(a.edges.values()) if a.edges else 1.0
    for (u, v), w in sorted(a.edges.items()):
        inside = (u, v) in forest
        fig.add_trace(go.Scatter(x=[pos[u][0], pos[v][0]], y=[pos[u][1], pos[v][1]], mode="lines", showlegend=False,
                                 line=dict(color=C.COLOR_B if inside else C.COLOR_SAME, width=1.5 + 6.5 * w / wmax, dash="solid" if inside else "dot"),
                                 hovertemplate=f"Linie {u + 1} – Linie {v + 1}: Gewicht {w:.1f}<extra></extra>".replace(".", ",")))
    fig.add_trace(go.Scatter(x=[p[0] for p in pos], y=[p[1] for p in pos], mode="markers+text", text=[str(i + 1) for i in range(n)], textposition="middle center",
                             marker=dict(size=30, color=[C.LINE_COLORS[i % len(C.LINE_COLORS)] for i in range(n)]), textfont=dict(color="white", size=13), showlegend=False,
                             hovertemplate="Linie %{text}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[-1.3, 1.3], y=[-1.3, 1.3], mode="markers", marker=dict(opacity=0), showlegend=False, hoverinfo="skip"))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
    fig.update_xaxes(visible=False, fixedrange=True, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False, fixedrange=True)
    return fig


def build_waterfall(a) -> go.Figure:
    """Zerlegung des Zufalls-Aufschlags: Mindestzeit, Paar-Kopplung, Linienpaarung, Kreise = Phasen-Optimum; der Rest bis zum Zufall ist der Gewinn der Optimierung."""
    p = a.parts
    mt = a.inst.transfer_min
    fig = go.Figure(go.Waterfall(
        x=["Mindestzeit", "Hin/Rück-Kopplung je Paar", "mehrere Anschlüsse einer Linienpaarung", "Kreise im Liniengraphen", "= Phasen-Optimum", "Gewinn der Optimierung", "= Zufall"],
        y=[mt, p["pair"], p["line_pair"], p["cycles"], a.opt, p["gain"], a.rand_exact],
        measure=["absolute", "relative", "relative", "relative", "total", "relative", "total"],
        text=[f"{v:.1f}".replace(".", ",") for v in (mt, p["pair"], p["line_pair"], p["cycles"], a.opt, p["gain"], a.rand_exact)], textposition="outside",
        connector=dict(line=dict(color="#95a0ae")), increasing=dict(marker=dict(color=C.COLOR_SUM)), totals=dict(marker=dict(color=C.COLOR_A))))
    fig.update_yaxes(title_text="mittlere Wartezeit (min)", rangemode="tozero")
    fig.update_xaxes(tickangle=-20)
    _lock(fig, 430, showlegend=False)
    fig.update_layout(margin=dict(l=50, r=20, t=30, b=130))
    return fig


# ---------------------------------------------------------------- Experimente
def build_c_histogram(dist: dict) -> go.Figure:
    labels = [f"{a}–{a + 9}" for a in range(0, C.T, 10)]
    fig = go.Figure(go.Bar(x=labels, y=[100 * s for s in dist["classes"]], marker_color=C.COLOR_A, text=[f"{100 * s:.1f}".replace(".", ",") for s in dist["classes"]],
                           textposition="outside", hovertemplate="c = %{x}: %{y:.1f} %<extra></extra>"))
    fig.update_xaxes(title_text="Konstante c des Hin/Rück-Paars (min)")
    fig.update_yaxes(title_text="Anteil der Paare (%)", rangemode="tozero")
    return _lock(fig, 300, showlegend=False)


def build_bounds_chart(table: dict) -> go.Figure:
    keys = list(C.SWEEP_LINES)
    xs = [f"{k} Linien" for k in keys]
    fig = go.Figure()
    for name, field, color, dash in (("Zufall", "rand", C.COLOR_GREY, "dash"), ("Phasen-Optimum", "opt", C.COLOR_A, "solid"),
                                     ("Untergrenze je Linienpaar (LB2)", "lb2", C.COLOR_B, "solid"), ("Untergrenze je Hin/Rück-Paar (LB)", "lb", C.COLOR_SUM, "solid")):
        fig.add_trace(go.Scatter(x=xs, y=[table[k][field][0] for k in keys], error_y=dict(type="data", array=[table[k][field][1] for k in keys], visible=True),
                                 mode="lines+markers", name=name, line=dict(color=color, width=2.5, dash=dash)))
    fig.update_yaxes(title_text="mittlere Wartezeit (min)", range=[0, 36])
    return _lock(fig, 360)


def build_rank_chart(classes: list[dict]) -> go.Figure:
    labels = [f"{c['lo']}" if c["lo"] == c["hi"] else (f"≥ {c['lo']}" if c["hi"] >= 999 else f"{c['lo']}–{c['hi']}") for c in classes]
    fig = go.Figure(go.Bar(x=labels, y=[c["gap"] for c in classes], marker_color=C.COLOR_SAME, text=[f"{c['gap']:.2f}".replace(".", ",") for c in classes],
                           textposition="outside", customdata=[[c["n"], c["equal"]] for c in classes],
                           hovertemplate="Kreisrang %{x}: Ø %{y:.2f} min über LB2; Optimum = LB2 in %{customdata[1]} von %{customdata[0]} Netzen<extra></extra>"))
    fig.update_xaxes(title_text="Kreisrang des Liniengraphen")
    fig.update_yaxes(title_text="Ø Optimum − LB2 (min)", rangemode="tozero")
    return _lock(fig, 320, showlegend=False)


def build_dwell_series(rows: list[dict]) -> go.Figure:
    xs = [f"{r['dwell']} min" for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=[r["opt"][0] for r in rows], error_y=dict(type="data", array=[r["opt"][1] for r in rows], visible=True), mode="lines+markers",
                             name="Phasen-Optimum", line=dict(color=C.COLOR_A, width=2.5)))
    fig.add_trace(go.Scatter(x=xs, y=[r["lb2"][0] for r in rows], mode="lines+markers", name="Untergrenze je Linienpaar", line=dict(color=C.COLOR_B, width=2.5)))
    fig.add_trace(go.Scatter(x=xs, y=[r["lb"][0] for r in rows], mode="lines+markers", name="Untergrenze je Hin/Rück-Paar", line=dict(color=C.COLOR_SUM, width=2.5)))
    fig.update_xaxes(title_text="Haltezeit aller Linien")
    fig.update_yaxes(title_text="mittlere Wartezeit (min)", range=[15, 26])
    return _lock(fig, 340)


def build_split_chart(s: dict) -> go.Figure:
    fig = go.Figure(go.Bar(x=["Standard-Aufteilung", "freie Aufteilung (obere Schranke)"], y=[s["lb_std"][0], s["lb_free"][0]], marker_color=[C.COLOR_GREY, C.COLOR_B],
                           error_y=dict(type="data", array=[s["lb_std"][1], s["lb_free"][1]], visible=True),
                           text=[f"{s['lb_std'][0]:.1f}".replace(".", ","), f"{s['lb_free'][0]:.1f}".replace(".", ",")], textposition="inside", textfont=dict(color="white", size=13)))
    fig.update_yaxes(title_text="Ø Untergrenze je Hin/Rück-Paar (min)", rangemode="tozero")
    return _lock(fig, 300, showlegend=False)
