# Uhr und Anschluss – wie lange wartet ein Umsteiger im Takt – Streamlit-Demo

<!-- TODO nach dem Deploy: direkt hierher den Live-Link setzen (Leerzeile davor und danach):
**[→ Demo live ausprobieren](https://sebastianhanisch-uhr-anschluss-demo.streamlit.app/)** -->

Diese Demo gehört zur Linie **Takt und Periodizität** der Konzepte-Reihe auf der Website „Sebastian Hanisch – Operations Research und Machine Learning“. Die Demo erklärt, wie viel der
Wartezeit eines Umsteigers im Taktfahrplan **im Fahrplan festliegt** und wie viel an den **Versätzen der Linien** hängt: in drei Schritten, **ein Anschluss auf dem Zifferblatt**, **ein Linienpaar** mit Hin- und Rückweg
und **ein kleines Netz** mit Wald-Satz. Vehikel sind die synthetischen Netze der Fall-Demo [taktfahrplan-demo](https://github.com/sebastian-hanisch/taktfahrplan-demo): Takt 60 min, Haltezeit 2 min, Mindest-Umsteigezeit 3 min,
ganzzahlige Minuten. Die Fall-Demo **sucht und misst** Fahrpläne am Netz (dort steht auch der Versatz-Regler am echten Netz, den diese Demo nicht wiederholt); diese Demo **erklärt** die Mechanik dahinter und ergänzt, was die Fall-Demo nicht hat:
die Schleifenzeit, Spiegel- und Gleichrichtungs-Paare, die Haltezeit als Regler, die Linienpaarung als Untergrenze und den Wald-Satz. Netze und Fahrpläne sind **Annahmen**, keine Echtdaten.

## Warum dieses Problem

Im Takt fährt jede Linie jede Stunde zur selben Minute; wer umsteigt, wartet auf den **Rest einer Uhr**. Die Kernfrage: *Wie lange muss ein Umsteiger im Takt mindestens warten, und welcher Teil davon steht im Fahrplan fest,
welcher hängt an der Wahl der Versätze?* Der Hook ist nicht „die Optimierung gewinnt“, sondern wie viel **jedes einzelne Paar** schon erzwingt: ein Hin/Rück-Paar kostet bei fester Haltezeit und Standard-Aufteilung der Wende-Standzeit mindestens 2·m + c Minuten, ganz gleich, wie die Linien gegeneinander verschoben sind.

## Modell

Linien fahren in beide Richtungen alle *T* = 60 min; ein Umstieg ist die Aktivität Ankunft einer Linie → Abfahrt einer anderen mit der Wartezeit ((*d* − *a* − *m*) mod *T*) + *m*. Gewählt wird der Versatz *o* jeder Linie (0 bis 59).
Alle Formeln, die Beweise der beiden Sätze und eine Symboltabelle stehen im Expander **📐 Mathematische Formulierung** der App (`uan_clock.py`, `uan_pair.py`, `uan_forest.py`). Kurz:

- **Hin/Rück-Paar:** Die Summe beider Wartezeiten nimmt nur die Werte 2·*m* + *c* und 2·*m* + *c* + *T* an, der kleinere gilt bei genau *c* + 1 von *T* Versätzen; *c* = (*L*_A + *L*_B − 2·*m*) mod *T* mit den **Schleifenzeiten** der beiden Linien.
- **Spiegelpaar** (beide Richtungen vertauscht, Zwischenhalte): *c* + *c′* ≡ 4·(*h* − *m*) mod *T*. **Satz:** Für Haltezeit *h* < Mindestzeit *m* sind die Gut-Mengen genau dann disjunkt, wenn *c* + *c′* = *T* − 4·(*m* − *h*) ist (Beweis in der App; geprüft in `tests/test_oracle_uhr_anschluss.py`). Teilen beide gespiegelten Paare einen Versatz und sind ihre Gut-Mengen disjunkt, kostet das mindestens den Zuschlag *T* · min(*w*₁, *w*₂).
- **Gleichrichtungs-Paar** (A → B und B → A in derselben Fahrtrichtung am selben Zwischenhalt): *c* = (2*h* − 2*m*) mod *T*, bei *h* = 2, *m* = 3 also 58 und die kleinste Summe 64 min, bei *h* = 3 die kleinste Summe 6 min.
- **Linienpaarung:** Alle Umstiege zweier Linien teilen **einen** Versatz; die Untergrenze LB2 summiert über die Linienpaare das Minimum der Kostenkurve und liegt nicht unter der Untergrenze LB je Hin/Rück-Paar (im Mittel 5,09 min darüber).
- **Wald-Satz:** Ist der Liniengraph (Kanten = Linienpaare mit Umstiegen) ein Wald, ist das Optimum genau LB2; `forest_offsets` baut die optimalen Versätze, ein Beweis durch Konstruktion.
- **Haltezeit nur als Umsteigezeit:** Eine längere Haltezeit verlängert die Fahrzeit der Durchfahrenden; das ist **nicht** eingerechnet (in der App ausdrücklich genannt).

## Methodik

- **Schritt 1 (Zifferblatt):** Wartezeit auf zwei Wegen, als Rest modulo 60 und über die Fahrplantafel der Zielline (erste Abfahrt mit Abstand ≥ Mindestzeit, ohne Modulo-Operator); Sägezahn über alle 60 Versätze; Mittel über alle Versätze exakt *m* + (*T* − 1)/2.
- **Schritt 2 (Linienpaar):** Auswahl aus dem Netz; Schleifenzeiten als Rechnung, Gut-Menge als Farbband, Spiegelpaar mit gemeinsamer Kurve, Gleichrichtungs-Paar mit einer Haltezeit-Tabelle, die den Fahrplan für jede Haltezeit neu aus den Ereigniszeiten rechnet.
- **Schritt 3 (Netz):** Liniengraph, Kreisrang, aufspannender Wald (Kruskal nach Gewicht, Wald-Schalter), Zerlegung des Zufalls-Aufschlags in vier Anteile, Phasen-Optimum per Lokalsuche (Koordinatenabstieg, 40 Neustarts, SplitMix64) und ein Knopf **▶️ Exakt prüfen** (CP-SAT, 2 Arbeiter, Zeitlimit, Anzeige „nicht bewiesen“).
- **Messreihen** (vorgerechnet, `data/uan_results.json`, erzeugt mit `tools/sweep.py`): 600 Netze (3, 5, 6, 8, 10 Linien, je vier Blöcke zu 30 Netze, Seeds ab 10000), dazu die Haltezeit-Reihe (dieselben Netze mit *h* = 1 bis 6), die Brücke zur Wende-Standzeit und die Gegenprobe gegen CP-SAT.
  „a ± s“ heißt Mittel der vier Block-Mittel ± Standardabweichung über die Blöcke. Zufall nur über einen ganzzahligen SplitMix64.
- **Kopien:** `uan_rng.py`, `uan_network.py`, `uan_timetable.py` sind wörtliche Kopien aus taktfahrplan-demo (nur die Modulnamen sind angepasst; `tests/test_copies.py` vergleicht gegen die Quelle).

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen stehen in `data/uan_results.json` (Messreihe, Haltezeit 2 min, Mindestzeit 3 min) und werden in `tests/test_claims.py` nachgerechnet.

| Frage | Befund |
|---|---|
| Trägt die Formel? | An 600 Netzen und 25 568 Hin/Rück-Paaren (Vollaufzählung aller 60 Versätze über die Fahrplantafel): **0 Abweichungen** von „kleinste Summe = 2·3 + c“, von der Zwei-Werte-Regel, von der Zahl c + 1 der Versätze auf dem kleineren Wert und von der Schleifenzeit-Formel. |
| Mittlere Wartezeit bei zufälligem Versatz? | Satz: *m* + (*T* − 1)/2 = 3 + 59/2 = **32,5 min**; die Mittelung über alle 60 Versätze trifft das per Konstruktion in 600 von 600 Netzen, die Gegenprobe mit 300 Ziehungen je Netz liegt zwischen 31,79 und 33,28 min. |
| Wie verteilt sich c? | Zehnerklassen 16,2 / 15,9 / 16,1 / 17,1 / 18,3 / 16,5 %; Mittel 29,9 min; c = 0 in 1,7 % der Paare. Ein zufälliger Versatz liegt im Mittel über die Paare bei 51,5 % der Versätze auf dem kleineren Wert. |
| Wie viel des Aufschlags erklärt die Paar-Untergrenze? | **71,4 ± 0,8 %** des Aufschlags, den das Phasen-Optimum über der Mindestzeit hat ((LB − 3) / (Optimum − 3); gegen den Zufalls-Aufschlag von 29,5 min wären es 50,3 %); je Linienzahl 70,9 / 71,4 / 69,5 / 71,4 / 73,9 % (3, 5, 6, 8, 10 Linien): nicht monoton, Spanne 4,4 Prozentpunkte bei einer Block-Streuung bis 2,8 Prozentpunkten. Das Phasen-Optimum erreicht die Paar-Untergrenze in 1 von 600 Netzen: sie ist ein Boden, kein Fahrplan. |
| Und die Untergrenze je Linienpaar? | Zufall 32,50 → Phasen-Optimum **23,92 ± 0,34**; LB 17,85 ± 0,19; LB2 **22,94 ± 0,33**. LB2 erklärt **95,3 ± 0,2 %** des Aufschlags des (per Lokalsuche gefundenen) Phasen-Optimums über der Mindestzeit (gegen den Zufalls-Aufschlag 67,6 %), bei 3 Linien 98,8 %, bei 10 Linien 92,5 % (fallend mit der Linienzahl). |
| Woraus besteht der Zufalls-Aufschlag (29,5 min)? | Paar-Kopplung 14,85 ± 0,19, mehrere Anschlüsse einer Linienpaarung 5,09 ± 0,22, Kreise im Liniengraphen 0,97 ± 0,05 (einschließlich des Restabstands der Lokalsuche), Gewinn der Optimierung 8,58 ± 0,34 (Mittel über alle Netze). |
| Gilt der Wald-Satz? | Kreisrang 0 kommt in 24 von 600 Netzen vor (alle mit 3 Linien): Optimum = LB2 in **24 von 24**. In 20 konstruierten Wäldern (5, 6, 8, 10 Linien) bewies CP-SAT **20 von 20** Optima, alle gleich LB2; die Konstruktion `forest_offsets` erreicht LB2 in 20 von 20. |
| Was bringen Kreise? | Optimum = LB2 in 101 von 576 Netzen mit Kreisen. Klassenmittel Optimum − LB2 nach Kreisrang 1–2 / 3–5 / 6–10 / 11–20 / ≥ 21: 0,29 / 0,41 / 0,97 / 1,30 / 1,61 min. Innerhalb einer Linienzahl nur schwacher bis mäßiger Zusammenhang (Pearson +0,04 bis +0,42); über alle Netze +0,51, aber durch die Linienzahl vermengt. Kreisrang gegen Phasen-Optimum −0,09, gegen Optimum − LB −0,13. |
| Spiegelpaare (Haltezeit 2)? | 4090 Paare; c + c′ = 56 in 3877 (Gut-Mengen **disjunkt in 3877 von 3877**), c + c′ = 116 in 213 (überlappend in 213 von 213, Ø 58,3 Versätze). Beweis siehe App. |
| Gleichrichtungs-Paare (Haltezeit 2)? | 8180 Paare, kleinste Summe **64 min in 8180 von 8180**; 16 360 von 51 136 Umstiegen (32 %) gehören zu einem, 592 von 600 Netzen haben eins. |
| Haltezeit als Regler? | Kleinste Summe eines Gleichrichtungs-Paars bei *h* = 1 / 2 / 3 / 4 / 5 / 6: 62 / 64 / 6 / 8 / 10 / 12 min. Phasen-Optimum im Netz: 23,87 / 23,92 / 22,80 / 22,59 / 22,47 / 22,59 min: von 2 auf 3 min nur **1,12 min**, danach bleibt es bei 22,47 bis 22,80. **Der Paar-Effekt (64 → 6) ist groß, der Netz-Effekt mit 1,12 min (4,7 %) deutlich kleiner, aber größer als die Block-Streuung (0,34 min).** LB2 − LB fällt von 5,09 (*h* = 2) auf 3,76 (*h* = 3). Spiegelpaare disjunkt in 3583 / 3877 / 0 / 0 / 0 / 0 von je 4090 (*h* = 1 bis 6; ab *h* = 3 nur gemessen, kein Satz). |
| Lokalsuche gegen CP-SAT? | An 30 Netzen (Zeitlimit, 2 Arbeiter): 26 von 30 bewiesen, die Lokalsuche lag in 2 über dem CP-SAT-Fund, nie darunter (größte Abweichung 0,06 min in der gespeicherten Messung; ein Neulauf lieferte 0,17 min, die Abweichung hängt vom Zeitlimit-Lauf ab; bewiesen suboptimal ist die Lokalsuche nur in 1 Netz, um 0,05 min). |
| Brücke zur Wende-Standzeit? | Bei freier Aufteilung kann c in 82 % der Paare einzeln auf 0 sinken (Ø c 29,8 → 2,6 min); die kleinste gefundene Netz-Untergrenze ist 11,94 gegen 17,85 min bei Standard-Aufteilung, in 600 von 600 Netzen niedriger. Das ist eine **obere Schranke** des wahren Minimums; ob LB2 mit freier Aufteilung die nächste Schranke ist, ist **nicht gemessen**. |

### Hypothesen

| Hypothese | Ergebnis |
|---|---|
| H1 Hin/Rück-Summe nimmt zwei Werte an, kleinerer bei c + 1 von 60 Versätzen | Ja (0 von 25 568 Abweichungen); Wiederholung der Fall-Demo |
| H2 Zufälliger Versatz: 3 + 59/2 = 32,5 min exakt | Ja (600 von 600) |
| H3 Paar-Untergrenze erklärt etwa 71 % des Aufschlags des Phasen-Optimums über der Mindestzeit | Ja (71,4 ± 0,8 %); Wiederholung der Fall-Demo |
| H4 Linienpaarung erklärt etwa 95 % des Aufschlags des Phasen-Optimums, sinkend mit der Linienzahl | Ja (95,3 ± 0,2 %; 98,8 → 92,5 %) |
| H5 Wald im Liniengraphen ⇒ Optimum = LB2 | Ja, bewiesen durch Konstruktion; 24 von 24 und 20 von 20 |
| H6 Kreis-Rest wächst mit dem Kreisrang | Nur schwach: Klassenmittel 0,29 → 1,61 min (Kreisrang 1–2 bis ≥ 21), innerhalb einer Linienzahl r = +0,04 bis +0,42; nicht als „der Rang erklärt den Rest“ lesen |
| H7 c = (Schleife A + Schleife B − 2·m) mod T | Ja (0 von 25 568 Abweichungen) |
| H8 Gespiegelte Paare liegen bei c + c′ = *T* − 4(*m* − *h*) = 56 nie zugleich auf dem kleineren Wert; bei c + c′ = 116 überlappen die Gut-Mengen | Ja, **bewiesen** für Zwischenhalte und h < m; gemessen 3877 von 3877 (von 4090 Paaren, 213 überlappen) |
| H9 Gleichrichtungs-Paar: kleinste Summe 64 min bei h = 2, 2h ab h = m | Ja (8180 von 8180) |
| H10 Haltezeit ≥ Mindestzeit senkt das Netz-Optimum deutlich | Nein, nur 1,12 min (4,7 %; 23,92 → 22,80) bei einem Paar-Effekt 64 → 6 min |
| H11 Freie Aufteilung öffnet die Paar-Untergrenze | Ja auf Paar-Ebene (82 % der Paare c = 0); Netz-Ebene offen |
| H12 Die Linienzahl bestimmt den Anteil der Paar-Kopplung | Kein Zusammenhang nachgewiesen: kein monotoner Verlauf (69,5 bis 73,9 %), die Unterschiede liegen in der Größe der Block-Streuung |

## Ehrliche Grenzen

- **Synthetische Netze eines Generators, ein Regelsatz** (Takt 60, Mindestzeit 3, Halt 2; Haltezeit und Mindestzeit sind in der App regelbar, die Messreihen gelten bei 2 und 3 min bzw. in der Haltezeit-Reihe für *h* = 1 bis 6 bei *m* = 3). Aussagen über reale Netze sind das nicht.
- **Haltezeit nur als Umsteigezeit.** Die längere Haltezeit verlängert die Fahrzeit der Durchfahrenden; der Netz-Effekt von 1,12 min ist deshalb nur ein Effekt auf die Umsteigezeit.
- **Das Phasen-Optimum ist der Wert einer Lokalsuche**, kein Beweis; gegen CP-SAT lag sie in 2 von 30 Netzen über dem Fund (die Größe der Abweichung ist laufabhängig). Bei 8 und 10 Linien bewies CP-SAT im Zeitlimit nicht jedes Netz.
- **Spiegel-Satz:** bewiesen nur für Zwischenhalte beider Linien und Haltezeit < Mindestzeit; für Haltezeit ≥ Mindestzeit sind die Gut-Mengen in allen gemessenen Fällen überlappend, das ist ein Messbefund.
- **Kreisrang erklärt den Kreis-Rest nur schwach** (H6); über alle Netze steckt in r = +0,51 der Größeneffekt der Linienzahl.
- Die Aussagen sind Messungen und Beweise für das hier definierte Modell, **keine Literaturaussagen**: Quellen zum Taktfahrplan (PESP) stehen in der Fall-Demo und sind hier nicht erneut an der Quelle geprüft.

## Verifikation

- **Kern:** Einheiten gegen die von Hand gerechnete Mini-Instanz (`tests/conftest.py`, `tests/test_algorithm.py`): Ereigniszeiten, D, c = 54, Schleifen 32 und 28, kleinste Summe 60 bei 55 von 60 Versätzen, Spiegelpaar c′ = 2 mit 128 statt 60 + 8, Gleichrichtung 64, Wald-Versätze (0, 7, 47); alle Umstiege der Mini-Instanz haben das Gewicht 1,0.
- **Orakel** (`tests/test_oracle_uhr_anschluss.py`, `tests/test_oracle_wald.py`): ein unabhängiger Fahrplansimulator (ein Fahrzeug fährt einen Zyklus, Fahrplantafel statt Modulo) gegen Formel, Schleifenzeit, Kurve des Paars, Spiegel-Gut-Mengen (sieben Kombinationen aus Haltezeit und Mindestzeit), Gleichrichtungs-Summe für Haltezeit 1 bis 6 und Linienpaar-Kurve; Zufall exakt *m* + 29,5; Lokalsuche gegen CP-SAT; Wald-Satz gegen Vollaufzählung (drei Linien) und gegen CP-SAT an konstruierten Wäldern.
- **Zweig-Tests** (`tests/test_branches.py`): Haltezeit 2 gegen 3 ändert die Gleichrichtungs-Summe (64 gegen 6), der Wald-Schalter ändert Aktivitäten und Rang, es gibt Netze mit LB2 > LB und mit Optimum > LB2, jede Spalte der Messreihen hat mehr als einen Wert, jedes Preset zeigt die versprochene Verdikt-Zeile.
- **Verdikte** (`tests/test_verdicts.py`), **Randfälle** (`tests/test_edge_cases.py`: zwei Linien, eine Linie, keine Umstiege, Reglergrenzen), **Messreihe** (`tests/test_results.py`: Aufbau, Erzeuger-Hash, Stichprobe gegen frische Rechnung), **Aussagen** (`tests/test_claims.py`: jede Zahl dieser README).
- **Oberfläche:** AppTest-Smoke-Test, jede Auswahl, der ▶️-Knopf einzeln, Permalink, PDF (`tests/test_app.py`, `tests/test_app_steps.py`), Layout und Footer (`tests/test_layout.py`, `tests/test_footer.py`), Laufzeit-Importe.
- **Testzahl:** 166 Tests (`pytest --collect-only -q tests`).

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore` | venv, Caches, Streamlit-Secrets |
| `.streamlit/config.toml` | Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `app.py` | Streamlit-App (drei Schritte, fünf Experimente, Grenzen, Formeln) |
| `data/uan_results.json` | vorgerechnete Messreihe (600 Netze, Haltezeit-Reihe, Brücke, CP-SAT-Gegenprobe) |
| `requirements-dev.txt` | Laufzeit plus pytest |
| `requirements.txt` | Laufzeit-Bibliotheken (ungepinnt; OR-Tools nur für den Knopf) |
| `tools/sweep.py` | erzeugt die Messreihe in Teilen und fügt sie zusammen |
| `uan_clock.py` | Schritt 1: Wartezeit, Fahrplantafel, Schleifenzeit, c und c′ |
| `uan_constants.py` | Regler-Grenzen, feste Annahmen, Presets, Farben |
| `uan_evaluation.py` | Analyse eines Netzes, Ansichten, alle Verdikte |
| `uan_exact.py` | CP-SAT für das exakte Phasen-Optimum (nur auf Knopfdruck) |
| `uan_forest.py` | Liniengraph, Kreisrang, aufspannender Wald, Wald-Versätze |
| `uan_layout.py` | Fester Kopf (Stylesheet) |
| `uan_network.py`, `uan_rng.py`, `uan_timetable.py` | wörtliche Kopien aus taktfahrplan-demo |
| `uan_pair.py` | Schritt 2: Kostenkurve, Gut-Menge, Spiegel-, Gleichrichtungs-Paare, Linienpaar-Kurve |
| `uan_pdf_export.py` | PDF-Bericht (fpdf2) |
| `uan_presets.py` | Permalink (Begrenzen, Einrasten), Presets, Zufalls-Seed-Button |
| `uan_results.py` | lädt und wertet die vorgerechnete Messreihe aus |
| `uan_search.py` | Lokalsuche über die Versätze, Zufalls-Referenz |
| `uan_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `tests/` | Mini-Instanz, Orakel, Zweig-, Claims-, Ergebnis-, Verdikt-, Rand-, Layout-, AppTest-, Footer- und Laufzeit-Import-Tests |

## Bewusst nicht umgesetzt

- **Versatz-Regler am echten Netz, Zugfolge, Zusatzzüge, Suche nach Fahrplänen:** stehen in der Fall-Demo taktfahrplan-demo; hier wird erklärt, nicht gesucht.
- **Aufteilung der Wende-Standzeit** als Regler: nur als Brücke gemessen (Experiment 5), nicht als Teil des Netzmodells.
- **Fahrzeitverlängerung durch längere Haltezeiten** und Fahrzeugumlauf: nicht modelliert.
- **Kreise über drei und mehr Linien über eine Kreisbasis:** der Kreis-Rest wird gemessen, aber nicht erklärt; das ist Sache einer späteren Demo dieser Linie.
- **Unmögliche Pläne (Aperiodik-Vorstufe „Plan unmöglich, wenn …“):** gehört zu einer anderen Demo der Reihe und wird hier nicht wiederholt.
- **Echtdaten** und Aussagen über reale Netze.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, NumPy und OR-Tools (nur für den Knopf „Exakt prüfen“).

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zur Reihe: [Takt und Periodizität: Fahrplan im Stundentakt](https://sebastianhanisch.net/konzepte-takt-periodizitaet.html).
