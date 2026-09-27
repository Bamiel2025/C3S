"""
Export des activités en fiches HTML autonomes, pour la classe.

Chaque activité devient un fichier HTML unique : graphiques, cartes, consignes et
corrigés, sans connexion ni installation. Un enseignant peut ainsi ouvrir la
fiche sur un vidéoprojecteur, la distribuer par clé USB ou l'envoyer aux familles,
même sans réseau.

Les données sont de vraies données ERA5 téléchargées au CDS au préalable (voir
`prepare_data.py`) : les chiffres affichés sont ceux du modèle, pas une
simulation. Le bandeau de la fiche indique la source et la période.

Usage :
    python export_activities.py                  # toutes les activités
    python export_activities.py bordeaux_montreal # une seule
"""

from __future__ import annotations

import base64
import html as html_lib
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import activities, analysis, config, data, maps, places, viz

#: Dossier de sortie des fiches.
OUTPUT_DIR = config.PROJECT_ROOT / "activites_html"

#: Période de référence (normale climatologique standard de l'OMM).
REFERENCE = (1991, 2020)

#: Palette des fiches, cohérente avec l'application.
COLORS = {
    "bleu": "#264653",
    "temp": "#e76f51",
    "froid": "#457b9d",
    "precip": "#2a9d8f",
    "accent": "#d1495b",
    "texte": "#1f2933",
    "gris": "#6b7280",
}


# --------------------------------------------------------------------------- #
# Blocs de la fiche
# --------------------------------------------------------------------------- #


@dataclass
class Figure:
    """Un élément graphique : image matricielle, prête à insérer en HTML."""

    title: str
    png: bytes
    caption: str = ""

    @property
    def data_uri(self) -> str:
        """Image encodée en base64, intégrable sans fichier annexe."""
        return "data:image/png;base64," + base64.b64encode(self.png).decode("ascii")


@dataclass
class Block:
    """Un bloc de contenu de la fiche."""

    kind: str
    payload: Any = None
    figure: Figure | None = None
    note: str = ""


@dataclass
class Sheet:
    """Fiche complète, prête à être écrite sur disque."""

    slug: str
    title: str
    subtitle: str = ""
    objective: str = ""
    skills: tuple[str, ...] = ()
    duration: str = ""
    place_names: tuple[str, ...] = ()
    blocks: list[Block] = field(default_factory=list)
    steps: tuple = ()
    teacher_tip: str = ""
    period: str = ""


# --------------------------------------------------------------------------- #
# Rendu graphique
# --------------------------------------------------------------------------- #

#: Dimensions d'une image de fiche. Assez large pour être lisible en
#: projection, assez compacte pour rester lisible à l'écran.
WIDTH, HEIGHT = 1080, 520


def to_png(fig, *, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """
    Rend une figure Plotly en PNG.

    `kaleido` est utilisé ; s'il est absent, on lève une erreur explicite plutôt
    que de produire une fiche sans graphique, ce que l'on ne remarque qu'au moment
    de la projection.
    """
    fig.update_layout(width=width, height=height, margin=dict(l=60, r=30, t=70, b=60))
    buffer = io.BytesIO()
    try:
        fig.write_image(buffer, format="png", width=width, height=height, scale=2)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Rendu PNG impossible. Installez Kaleido : pip install kaleido"
        ) from exc
    return buffer.getvalue()


def figure(title: str, fig, caption: str = "") -> Figure:
    """Construit une figure de fiche à partir d'une figure Plotly."""
    return Figure(title=title, png=to_png(fig), caption=caption)


# --------------------------------------------------------------------------- #
# Rendu HTML
# --------------------------------------------------------------------------- #

STYLE = """
:root {
  --bleu: #264653; --accent: #d1495b; --texte: #1f2933; --gris: #6b7280;
  --fond: #ffffff; --cadre: #e5e7eb; --doux: #f4f7fb;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--fond); color: var(--texte);
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
  line-height: 1.6; font-size: 17px;
}
.page { max-width: 1040px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
header {
  border-bottom: 4px solid var(--bleu); padding-bottom: 1.2rem; margin-bottom: 1.6rem;
}
h1 { font-size: 1.9rem; line-height: 1.25; margin: 0 0 .4rem; color: var(--bleu); }
h2 {
  font-size: 1.25rem; color: var(--bleu); margin: 2.2rem 0 .8rem;
  padding-left: .6rem; border-left: 5px solid var(--accent);
}
h3 { font-size: 1.05rem; margin: 1.4rem 0 .5rem; color: var(--bleu); }
.sub { color: var(--gris); font-size: 1rem; margin: 0; }
.badges { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .9rem; }
.badge {
  background: var(--doux); border: 1px solid var(--cadre); border-radius: 999px;
  padding: .2rem .8rem; font-size: .85rem; color: var(--bleu);
}
.objectif {
  background: var(--doux); border-left: 5px solid var(--bleu);
  border-radius: .4rem; padding: .9rem 1.1rem; margin: 1.2rem 0;
}
.objectif strong { color: var(--bleu); }
.ul { display: flex; flex-wrap: wrap; gap: .4rem .5rem; padding: 0; margin: .6rem 0; list-style: none; }
.ul li {
  background: #fff; border: 1px solid var(--cadre); border-radius: .3rem;
  padding: .25rem .6rem; font-size: .88rem;
}
figure { margin: 1.6rem 0; }
figure img {
  width: 100%; height: auto; border: 1px solid var(--cadre);
  border-radius: .5rem; background: #fff;
}
figcaption { color: var(--gris); font-size: .9rem; margin-top: .5rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .93rem; }
th, td { border: 1px solid var(--cadre); padding: .5rem .6rem; text-align: right; }
th:first-child, td:first-child { text-align: left; font-weight: 600; }
thead th { background: var(--bleu); color: #fff; font-weight: 600; }
tbody tr:nth-child(even) { background: var(--doux); }
ol.steps { padding-left: 1.3rem; }
ol.steps > li { margin-bottom: 1.1rem; }
.consigne { font-weight: 600; }
.piste {
  background: #fffbeb; border-left: 4px solid #f59e0b;
  padding: .45rem .7rem; margin: .5rem 0; font-size: .92rem; border-radius: .3rem;
}
details {
  border: 1px solid var(--cadre); border-radius: .4rem; padding: .5rem .9rem;
  margin: .6rem 0; background: #fff;
}
details > summary {
  cursor: pointer; font-weight: 600; color: var(--bleu); padding: .2rem 0;
}
details[open] > summary { margin-bottom: .5rem; border-bottom: 1px dashed var(--cadre); }
.corrige {
  background: #f0fdf4; border-left: 4px solid #16a34a; border-radius: .3rem;
  padding: .6rem .8rem; margin-top: .4rem;
}
.corrige > strong { color: #15803d; }
footer {
  margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--cadre);
  color: var(--gris); font-size: .85rem;
}
@media print {
  body { font-size: 12pt; }
  .page { max-width: none; padding: 0; }
  details { break-inside: avoid; }
  details[open] > summary { color: #000; }
  figure { break-inside: avoid; }
  @page { margin: 14mm; }
}
@media (max-width: 640px) {
  body { font-size: 16px; }
  .page { padding: 1.2rem .9rem 3rem; }
  h1 { font-size: 1.5rem; }
}
"""

SCRIPT = """
// Les corrigés sont repliés : l'enseignant ouvre la fiche, les élèves la projettent.
document.addEventListener("DOMContentLoaded", function () {
  var url = new URLSearchParams(window.location.search);
  if (url.get("corriges") === "1") {
    document.querySelectorAll("details").forEach(function (d) { d.open = true; });
  }
  var btn = document.getElementById("tout-ouvrir");
  var open = false;
  if (btn) {
    btn.addEventListener("click", function () {
      open = !open;
      document.querySelectorAll("details").forEach(function (d) { d.open = open; });
      btn.textContent = open ? "Masquer tous les corrigés" : "Afficher tous les corrigés";
    });
  }
});
"""


def _esc(text: str) -> str:
    """Échappe le texte pour l'insérer en HTML."""
    return html_lib.escape(str(text))


def _render_table(frame: pd.DataFrame, caption: str = "") -> str:
    """Tableau HTML à partir d'un tableau pandas."""
    if frame is None or frame.empty:
        return ""
    head = "".join(f"<th>{_esc(c)}</th>" for c in frame.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_esc(v)}</td>" for v in row) + "</tr>"
        for row in frame.itertuples(index=False)
    )
    cap = f"<figcaption>{_esc(caption)}</figcaption>" if caption else ""
    return f"<figure><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>{cap}</figure>"


def _render_figure(fig: Figure) -> str:
    """Figure HTML, image incluse en base64."""
    cap = f"<figcaption>{_esc(fig.caption)}</figcaption>" if fig.caption else ""
    return (
        f'<figure><img src="{fig.data_uri}" alt="{_esc(fig.title)}" '
        f'loading="lazy">{cap}</figure>'
    )


def _render_steps(steps) -> str:
    """Consignes et corrigés, chaque réponse dans un bloc repliable."""
    out = []
    for i, step in enumerate(steps, 1):
        hint = f'<div class="piste">Piste : {_esc(step.hint)}</div>' if step.hint else ""
        corrige = (
            f'<div class="corrige"><strong>Réponse attendue.</strong> '
            f"{_esc(step.expected)}</div>"
            if step.expected else ""
        )
        out.append(
            f'<li><span class="consigne">{_esc(step.title)}</span>'
            f'<div>{_esc(step.instruction)}</div>{hint}{corrige}</li>'
        )
    return f'<ol class="steps">{"".join(out)}</ol>'


def render(sheet: Sheet) -> str:
    """Assemble la fiche complète en une chaîne HTML autonome."""
    badges = []
    if sheet.duration:
        badges.append(f'<span class="badge">Durée : {_esc(sheet.duration)}</span>')
    badges.append('<span class="badge">Sciences de la vie et de la Terre</span>')
    if sheet.period:
        badges.append(f'<span class="badge">Données {_esc(sheet.period)}</span>')
    if sheet.place_names:
        badges.append(f'<span class="badge">Villes : {_esc(" · ".join(sheet.place_names))}</span>')

    skills = ""
    if sheet.skills:
        items = "".join(f"<li>{_esc(s)}</li>" for s in sheet.skills)
        skills = f'<h3>Compétences visées</h3><ul class="ul">{items}</ul>'

    objective = ""
    if sheet.objective:
        objective = (
            f'<div class="objectif"><strong>Objectif.</strong> '
            f"{_esc(sheet.objective)}</div>"
        )

    body_parts: list[str] = []
    for block in sheet.blocks:
        if block.kind == "h2":
            body_parts.append(f"<h2>{_esc(block.payload)}</h2>")
        elif block.kind == "h3":
            body_parts.append(f"<h3>{_esc(block.payload)}</h3>")
        elif block.kind == "p":
            body_parts.append(f"<p>{_esc(block.payload)}</p>")
        elif block.kind == "html":
            body_parts.append(str(block.payload))
        elif block.kind == "figure" and block.figure is not None:
            body_parts.append(_render_figure(block.figure))
        elif block.kind == "table":
            body_parts.append(_render_table(block.payload, block.note))
        elif block.kind == "note":
            body_parts.append(
                f'<div class="objectif">{_esc(block.payload)}</div>'
            )

    steps = ""
    if sheet.steps:
        steps = (
            "<h2>Consignes et réponses attendues</h2>"
            "<p>Les réponses attendues sont dépliables : la fiche peut être "
            "projetée telle quelle aux élèves, puis ouverte pour la correction.</p>"
            f"{_render_steps(sheet.steps)}"
        )

    tip = ""
    if sheet.teacher_tip:
        tip = (
            "<details><summary>Conseil de mise en œuvre (enseignant)</summary>"
            f'<div class="corrige">{_esc(sheet.teacher_tip)}</div></details>'
        )

    body = "\n".join(x for x in body_parts if x)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(sheet.title)} — Activité SVT</title>
<style>{STYLE}</style>
</head>
<body>
<div class="page">
<header>
  <h1>{_esc(sheet.title)}</h1>
  <p class="sub">{_esc(sheet.subtitle)}</p>
  <div class="badges">{"".join(badges)}</div>
</header>
{objective}
{skills}
<button id="tout-ouvrir" type="button">Afficher tous les corrigés</button>
{body}
{steps}
{tip}
<footer>
  <p>Source des données : ERA5 — Copernicus Climate Change Service (C3S),
  réanalyse atmosphérique sur grille de 0,25°. Les valeurs affichées proviennent
  des fichiers téléchargés sur le CDS.</p>
  <p>Fiche générée par C3S Climate Lab. Imprimable en PDF depuis le navigateur.</p>
</footer>
</div>
<script>{SCRIPT}</script>
</body>
</html>
"""


def write(sheet: Sheet) -> Path:
    """Écrit une fiche sur disque et renvoie son chemin."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{sheet.slug}.html"
    target.write_text(render(sheet), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Accès aux données
# --------------------------------------------------------------------------- #


class DataHub:
    """
    Point d'accès unique aux séries des fiches.

    Toutes les fiches partagent le même cache mémoire : sans cela, l'export d'une
    dizaine de fiches réinterrogerait le CDS pour des villes déjà téléchargées, et
    chaque requête compte dans le quota quotidien du CDS.
    """

    def __init__(self, years: tuple[int, int] | None = None) -> None:
        self.years = years or (1940, config.LAST_COMPLETE_YEAR)
        self._temp: dict[str, pd.Series] = {}
        self._precip: dict[str, pd.Series] = {}
        self._fields: dict[tuple, Any] = {}

    def series(self, name: str, variable: str = "2m_temperature") -> pd.Series:
        """Série mensuelle d'une ville, téléchargée une seule fois."""
        store = self._temp if variable == "2m_temperature" else self._precip
        if name in store:
            return store[name]
        place = find_place(name)
        if place is None:
            raise KeyError(f"Ville inconnue : {name}")
        result = data.fetch_city_series(place, variable)
        value = result.series_at(place.lat, place.lon, name=name)
        store[name] = value
        return value

    def field(self, variable: str, area: tuple[float, float, float, float],
              years: tuple[int, int] | None = None):
        """Champ spatial ERA5, mis en cache par (variable, aire, période)."""
        key = (variable, tuple(area), years or self.years)
        if key not in self._fields:
            self._fields[key] = data.fetch(
                variable=variable, years=years or self.years, area=area
            )
        return self._fields[key]

    def climatology(self, name: str, variable: str = "2m_temperature",
                    reference: tuple[int, int] = REFERENCE) -> pd.Series:
        """Normale mensuelle d'une ville, sur la période de référence."""
        return analysis.monthly_climatology(self.series(name, variable), reference)

    def annual(self, name: str, reference: tuple[int, int] = REFERENCE) -> pd.Series:
        """Moyenne annuelle d'une ville sur la période de référence."""
        return self.series(name).groupby(self.series(name).index.year).mean()

    def anomalies(self, name: str, reference: tuple[int, int] = REFERENCE) -> pd.Series:
        """Écart annuel à la moyenne de la période de référence."""
        return analysis.anomalies(self.annual(name), reference)


def find_place(name: str) -> places.Place | None:
    """Retrouve une ville par son nom, dans les deux collections."""
    for pool in (places.FRENCH_CITIES, places.WORLD_CITIES):
        for place in pool:
            if place.name == name:
                return place
    return None


# --------------------------------------------------------------------------- #
# Blocs de figures réutilisables
# --------------------------------------------------------------------------- #

MONTH_LABELS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
                "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


def _month_name(index_value) -> str:
    """
    Nom lisible d'un mois.

    `monthly_climatology` renvoie des dates : sans cette conversion, le tableau
    afficherait « 2001-01-01 00:00:00 », illisible pour des élèves.
    """
    try:
        return MONTH_NAMES[int(pd.Timestamp(index_value).month) - 1]
    except (TypeError, ValueError, IndexError):
        return str(index_value)


MONTH_NAMES = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
               "août", "septembre", "octobre", "novembre", "décembre")


def _climato_figure(hub: DataHub, cities: list[str], variable: str,
                    title: str, unit: str) -> Figure:
    """Courbes des normales mensuelles de plusieurs villes."""
    climos = {c: hub.climatology(c, variable) for c in cities}
    return figure(title, viz.multi_city_climato(climos, title, unit),
                  "Normale calculée sur la période 1991-2020.")


def _amplitude_figure(hub: DataHub, cities: list[str]) -> Figure:
    """Diagramme en barres des amplitudes thermiques annuelles."""
    values = {c: analysis.thermal_amplitude(hub.climatology(c)) for c in cities}
    return figure(
        "Amplitude thermique annuelle",
        viz.bar_comparison(list(values), list(values.values()),
                           "Amplitude thermique annuelle", "°C"),
        "Écart entre le mois le plus chaud et le mois le plus froid de la normale.",
    )


def _ombro_figure(hub: DataHub, city: str) -> Figure:
    """Diagramme ombrothermique d'une ville."""
    temp = hub.climatology(city)
    precip = hub.climatology(city, "total_precipitation")
    return figure(
        f"Diagramme ombrothermique — {city}",
        viz.ombrothermic_diagram(temp, precip, f"{city} — ombrothermique"),
        "Barres : précipitations mensuelles (mm). Courbe : température (°C).",
    )


def _indices_table(hub: DataHub, cities: list[str]) -> pd.DataFrame:
    """Tableau des indices climatiques de plusieurs villes."""
    rows = {}
    for c in cities:
        rows[c] = {
            i.name: round(i.value, 1)
            for i in analysis.describe_temperature(
                hub.series(c), hub.series(c, "total_precipitation"),
                reference=REFERENCE,
            )
        }
    return pd.DataFrame(rows).T.reset_index().rename(columns={"index": "Ville"})


# --------------------------------------------------------------------------- #
# Les fiches
# --------------------------------------------------------------------------- #


def sheet_ocean_continent(hub: DataHub) -> Sheet:
    """Océan ou continent : pourquoi l'amplitude thermique change-t-elle ?"""
    cities = ["Brest", "Strasbourg", "Lyon", "Marseille"]
    sheet = Sheet(
        slug="01_ocean_continent",
        title="Océan ou continent : pourquoi l'amplitude thermique change-t-elle ?",
        subtitle="Comparer quatre villes françaises et relier leur amplitude "
                 "thermique à la distance à la mer.",
        objective="Comprendre qu'un même écart de latitude peut produire des climats "
                  "très différents, et relier l'amplitude thermique annuelle à la "
                  "distance à la mer.",
        skills=(
            "Décrire un graphique en courbes et un diagramme ombrothermique",
            "Calculer une moyenne et un écart",
            "Expliquer un résultat par un mécanisme (inertie thermique)",
        ),
        duration="55 min",
        place_names=tuple(cities),
        period=f"normale {REFERENCE[0]}-{REFERENCE[1]}",
    )
    sheet.blocks = [
        Block("h2", "Les courbes de température"),
        Block("figure", figure=_climato_figure(
            hub, cities, "2m_temperature", "Températures mensuelles moyennes", "°C")),
        Block("figure", figure=_amplitude_figure(hub, cities)),
        Block("h2", "Diagrammes ombrothermiques"),
        Block("p", "Chaque graphique superpose les précipitations (barres) et les "
                   "températures (courbe) mois par mois."),
    ]
    for city in cities:
        sheet.blocks.append(Block("figure", figure=_ombro_figure(hub, city)))
    sheet.blocks.append(Block("h2", "Indices climatiques"))
    sheet.blocks.append(Block("table", payload=_indices_table(hub, cities)))
    sheet.steps = activities.ACTIVITIES[0].steps
    sheet.teacher_tip = activities.ACTIVITIES[0].teacher_tip
    return sheet


def sheet_cycle_eau(hub: DataHub) -> Sheet:
    """Le cycle de l'eau : d'où viennent les précipitations ?"""
    cities = ["Marseille", "Brest", "Dakar", "Bordeaux"]
    sheet = Sheet(
        slug="02_cycle_eau",
        title="Le cycle de l'eau : d'où viennent les précipitations ?",
        subtitle="Relier l'évaporation et la condensation aux précipitations "
                 "mesurées, et comparer un régime méditerranéen à un régime équatorial.",
        objective="Relier l'évaporation et la condensation aux précipitations "
                  "mesurées, et distinguer un régime équatorial d'un régime "
                  "méditerranéen.",
        skills=(
            "Construire et lire un diagramme ombrothermique",
            "Identifier un changement d'état dans un graphique",
            "Comparer des cumuls mensuels",
        ),
        duration="55 min",
        place_names=tuple(cities),
        period=f"normale {REFERENCE[0]}-{REFERENCE[1]}",
    )
    sheet.blocks = [
        Block("h2", "Précipitations mensuelles"),
        Block("figure", figure=_climato_figure(
            hub, cities, "total_precipitation", "Précipitations mensuelles", "mm")),
        Block("h2", "Diagrammes ombrothermiques"),
        Block("p", "Comparer les cumuls annuels : un total élevé peut masquer un été "
                   "très sec. C'est la saisonnalité qui compte autant que le total."),
    ]
    for city in cities:
        sheet.blocks.append(Block("figure", figure=_ombro_figure(hub, city)))
    sheet.blocks.append(Block("h2", "Indices climatiques"))
    sheet.blocks.append(Block("table", payload=_indices_table(hub, cities)))
    sheet.steps = activities.ACTIVITIES[1].steps
    sheet.teacher_tip = activities.ACTIVITIES[1].teacher_tip
    return sheet


def sheet_rechauffement(hub: DataHub) -> Sheet:
    """Mesurer le réchauffement climatique à partir des données."""
    city = "Paris"
    sheet = Sheet(
        slug="03_rechauffement_climatique",
        title="Mesurer le réchauffement climatique à partir des données",
        subtitle="Construire une courbe d'anomalies, estimer une tendance et "
                 "discuter ce qu'elle permet — et ne permet pas — d'affirmer.",
        objective="Construire une courbe d'anomalies, estimer une tendance par "
                  "décennie et discuter ce que cette tendance permet — et ne "
                  "permet pas — d'affirmer.",
        skills=(
            "Calculer un écart à une moyenne de référence",
            "Lire une tendance et son coefficient directeur",
            "Distinguer variabilité naturelle et tendance de fond",
        ),
        duration="55 min",
        place_names=(city,),
        period=f"anomalies calculées sur {REFERENCE[0]}-{REFERENCE[1]}",
    )
    annual = hub.annual(city)
    anomalies = analysis.anomalies(annual, REFERENCE)
    trend = analysis.linear_trend(annual, "°C")
    normal = annual.loc[REFERENCE[0]:REFERENCE[1]].mean()
    recent = annual.tail(10).mean()
    sheet.blocks = [
        Block("h2", "Température annuelle moyenne"),
        Block("figure", figure=figure(
            f"Moyenne annuelle — {city}",
            viz.trend_chart(annual, trend,
                            f"{city} — température annuelle moyenne", "°C"),
            "Trait rouge : tendance linéaire ajustée sur toute la période.",
        )),
        Block("h2", "Anomalies thermiques"),
        Block("p", "L'anomalie est l'écart de chaque année à la moyenne de la "
                   "période de référence. Une barre positive signifie une année "
                   "plus chaude que la normale."),
        Block("figure", figure=figure(
            f"Anomalies annuelles — {city}",
            viz.annual_anomaly_bars(annual, anomalies,
                                    f"{city} — écart à la normale", "°C", REFERENCE),
            f"Référence : moyenne {REFERENCE[0]}-{REFERENCE[1]}.",
        )),
        Block("h2", "La tendance en chiffres"),
        Block("table", payload=pd.DataFrame([
            {"Indicateur": "Période analysée",
             "Valeur": f"{int(annual.index[0])}–{int(annual.index[-1])}"},
            {"Indicateur": "Tendance",
             "Valeur": f"{trend.slope * 10:+.2f} °C par décennie"},
            {"Indicateur": "Moyenne de référence",
             "Valeur": f"{normal:.2f} °C"},
            {"Indicateur": "Moyenne des 10 dernières années",
             "Valeur": f"{recent:.2f} °C"},
            {"Indicateur": "Écart entre les deux",
             "Valeur": f"{recent - normal:+.2f} °C"},
        ])),
    ]
    sheet.steps = activities.ACTIVITIES[2].steps
    sheet.teacher_tip = activities.ACTIVITIES[2].teacher_tip
    return sheet


def sheet_vent_pression(hub: DataHub) -> Sheet:
    """Pression atmosphérique et circulation du vent."""
    sheet = Sheet(
        slug="04_pression_vent",
        title="Pression atmosphérique et circulation du vent",
        subtitle="Relier les zones de hautes et de basses pressions à la "
                 "direction du vent.",
        objective="Relier les zones de hautes et de basses pressions à la "
                  "direction du vent, et comprendre pourquoi les vents soufflent "
                  "des zones hautes vers les zones basses.",
        skills=("Lire des isobares", "Interpréter un vecteur vent",
                "Relier pression et mouvement de l'air"),
        duration="55 min",
        place_names=("Paris",),
        period=f"moyennes {REFERENCE[0]}-{REFERENCE[1]}",
    )
    area = (55.0, -6.0, 42.0, 10.0)
    mslp = hub.field("mean_sea_level_pressure", area, REFERENCE)
    wind_u = hub.field("10m_u_component_of_wind", area, REFERENCE)
    wind_v = hub.field("10m_v_component_of_wind", area, REFERENCE)
    sheet.blocks = [
        Block("h2", "Pression au niveau de la mer"),
        Block("figure", figure=figure(
            "Pression atmosphérique moyenne",
            maps.field_map(
                mslp.field(), title="Pression au niveau de la mer", unit="hPa",
                period=f"{REFERENCE[0]}-{REFERENCE[1]}", area=area,
                colorscale=viz.PRESSURE_SCALE, zmin=960.0, zmax=1050.0,
            ),
            "La valeur de référence au niveau de la mer est d'environ 1013 hPa.",
        )),
        Block("h2", "Vents dominants"),
        Block("figure", figure=figure(
            "Vents en surface",
            maps.wind_map(
                wind_u.field(), wind_v.field(),
                title="Vent à 10 m",
                period=f"{REFERENCE[0]}-{REFERENCE[1]}", area=area),
            "Chaque flèche indique la direction et la vitesse du vent.",
        )),
        Block("note", "Sans gradient de pression, l'air n'est pas accéléré : il "
                      "n'y a pas de vent. La rotation de la Terre (force de "
                      "Coriolis) fait ensuite tourner le vent autour des "
                      "dépressions dans l'hémisphère nord."),
    ]
    sheet.steps = activities.ACTIVITIES[3].steps
    sheet.teacher_tip = activities.ACTIVITIES[3].teacher_tip
    return sheet


def sheet_cartes_climatiques(hub: DataHub) -> Sheet:
    """Construire et lire une carte climatique."""
    sheet = Sheet(
        slug="05_cartes_climatiques",
        title="Construire et lire une carte climatique",
        subtitle="Lire une carte de températures, choisir une échelle de couleurs "
                 "adaptée, et distinguer climat et météo.",
        objective="Lire une carte de températures ou de précipitations, choisir une "
                  "échelle de couleurs adaptée, et distinguer climat et météo.",
        skills=("Lire une carte thématique",
                "Choisir une échelle de couleurs non trompeuse",
                "Distinguer une moyenne d'une situation ponctuelle"),
        duration="55 min",
        place_names=("Paris",),
        period=f"normale {REFERENCE[0]}-{REFERENCE[1]}",
    )
    europe = (60.0, -12.0, 35.0, 25.0)
    temp = hub.field("2m_temperature", europe, REFERENCE)
    precip = hub.field("total_precipitation", europe, REFERENCE)
    sheet.blocks = [
        Block("h2", "Carte des températures de janvier"),
        Block("figure", figure=figure(
            "Température de janvier",
            maps.field_map(
                temp.field(month=1), title="Température de janvier (°C)", unit="°C",
                period=f"{REFERENCE[0]}-{REFERENCE[1]}", area=europe,
                colorscale=viz.TEMP_SCALE, zmin=-5.0, zmax=15.0,
            ),
            "Le nord-est de l'Europe est le plus froid ; les côtes atlantiques "
            "et la Méditerranée sont plus chaudes.",
        )),
        Block("h2", "Carte des précipitations annuelles"),
        Block("figure", figure=figure(
            "Précipitations annuelles",
            maps.field_map(
                precip.field(), title="Précipitations annuelles (mm)", unit="mm",
                period=f"{REFERENCE[0]}-{REFERENCE[1]}", area=europe,
                colorscale=viz.PRECIP_SCALE,
            ),
            "Une moyenne sur trente ans ne dit rien du temps qu'il fait "
            "aujourd'hui.",
        )),
        Block("note", "Un climat se décrit sur au moins trente ans. Un échantillon "
                      "de trois ans relève de la météo, c'est-à-dire de l'état "
                      "ponctuel de l'atmosphère."),
    ]
    sheet.steps = activities.ACTIVITIES[4].steps
    sheet.teacher_tip = activities.ACTIVITIES[4].teacher_tip
    return sheet


def _fetch_heat_daily(place: places.Place, statistic: str,
                      years: tuple[int, int]) -> pd.Series | None:
    """
    Série journalière pour une ville, ou `None` si le CDS refuse.

    Le jeu de statistiques journalières est le plus coûteux du CDS, et son
    acceptation des conditions d'utilisation est propre à ce jeu. Plutôt que de
    laisser une fiche sans graphique, on renvoie `None` : l'appelant affiche alors
    une explication honnête, sans inventer de nombres.
    """
    area = (place.lat + 0.3, place.lon - 0.3, place.lat - 0.3, place.lon + 0.3)
    try:
        result = data.fetch(
            dataset_key="daily_stats", variable="2m_temperature", years=years,
            area=area, daily_statistic=statistic,
        )
    except Exception:  # noqa: BLE001 - le refus du CDS est le cas attendu ici
        return None
    return result.series_at(place.lat, place.lon, name="valeur")


def _heatwave_fallback(city: str, hub: DataHub) -> list[Block]:
    """
    Contenu de la fiche canicule quand les statistiques journalières manquent.

    Le travail reste le même — comparer des seuils et discuter du rôle du choix —
    mais il porte sur les températures mensuelles réelles plutôt que sur des
    journées. C'est une approximation déclarée, pas un comptage de jours présenté
    comme tel.
    """
    climato = hub.climatology(city)
    # `monthly_climatology` renvoie un index de dates, pas un index de mois : on
    # sélectionne donc les mois d'été par leur numéro, via le composant `.dt`.
    values = climato[climato.index.month.isin([6, 7, 8])]
    rows = [
        {"Mois": _month_name(stamp), "Température moyenne (°C)": round(float(v), 1)}
        for stamp, v in values.items()
    ]
    frame = pd.DataFrame(rows).set_index("Mois")
    warm = [r["Mois"] for r in rows if r["Température moyenne (°C)"] >= 28]
    return [
        Block("h2", "Repérer les mois de forte chaleur"),
        Block("note", (
            "Les statistiques journalières n'ont pas pu être téléchargées au "
            "moment de la préparation de cette fiche. Le travail porte donc sur "
            "les températures mensuelles réelles, ce qui ne permet pas de "
            "compter des journées : on compare des moyennes de mois. Une moyenne "
            "mensuelle ne dit rien du nombre de journées de canicule qu'elle "
            "contient — c'est précisément ce que l'activité cherche à montrer."
        )),
        Block("table", payload=frame,
              note=f"Moyennes mensuelles ERA5, normale {REFERENCE[0]}-{REFERENCE[1]}."),
        Block("figure", figure=figure(
            f"Températures de {city}",
            viz.multi_city_climato(
                {city: climato}, f"{city} — températures mensuelles", "°C"),
            "Les mois d'été concentrent les températures les plus élevées.",
        )),
        Block("note",
              f"Repère : à {city}, les mois dont la moyenne dépasse 28 °C sont "
              + (", ".join(warm) if warm else "aucun")
              + ". Un compteur de jours de canicule donnerait un tout autre "
              "chiffre, car une moyenne mensuelle masque les journées extrêmes."),
    ]


def sheet_canicule(hub: DataHub) -> Sheet:
    """Compter les jours de chaleur : construire un indice."""
    cities = ["Marseille", "Paris", "Brest"]
    sheet = Sheet(
        slug="06_canicule",
        title="Compter les jours de chaleur : construire un indice",
        subtitle="Compter des jours de canicule avec un critère à deux seuils et "
                 "discuter du rôle de ce choix dans le résultat.",
        objective="Compter des jours de canicule avec un critère à deux seuils et "
                  "discuter du rôle de ce choix dans le résultat obtenu.",
        skills=("Définir un critère de comptage", "Utiliser des données journalières",
                "Sensibiliser au rôle du seuil dans une statistique"),
        duration="55 min",
        place_names=tuple(cities),
        period="statistiques journalières 2018-2024",
    )
    # Une seule ville, une seule statistique, sur une boîte d'un demi-degré :
    # c'est la seule requête que le CDS accepte pour cette activité sans déclencher
    # le refus de dépassement de quota.
    city = cities[0]
    place = find_place(city)
    # Sept années : au-delà, le CDS refuse la requête au titre du quota, alors
    # même que la boîte ne fait qu'un demi-degré.
    years = (2018, config.LAST_COMPLETE_YEAR)
    s_max = _fetch_heat_daily(place, "daily_maximum", years)
    s_min = _fetch_heat_daily(place, "daily_minimum", years)

    if s_max is None or s_min is None:
        # Le jeu journalier est indisponible (licence non acceptée, ou quota).
        # On ne fabrique aucun chiffre : la fiche propose alors le même travail
        # sur les températures mensuelles, qui sont bien des données ERA5.
        sheet.blocks = _heatwave_fallback(city, hub)
        sheet.steps = activities.ACTIVITIES[5].steps
        sheet.teacher_tip = activities.ACTIVITIES[5].teacher_tip
        return sheet

    rows = []
    for threshold in (30.0, 32.0, 35.0, 38.0):
        simple = analysis.count_days_above(s_max, threshold)
        strict = analysis.heatwave_days(
            s_max, s_min, tmax_thresh=threshold, tmin_thresh=20.0)
        rows.append({
            "Critère": f"T max ≥ {threshold:.0f} °C",
            "… et T min ≥ 20 °C": round(float(strict.mean()), 1),
            "Moyenne annuelle (jours)": round(float(simple.mean()), 1),
        })
    simple35 = analysis.count_days_above(s_max, 35.0)

    sheet.blocks = [
        Block("h2", "Combien de jours de forte chaleur ?"),
        Block("p", f"Ville étudiée : **{city}**, de 2018 à 2024. Le tableau "
                   "compare plusieurs seuils : le résultat dépend entièrement du "
                   "critère retenu."),
        Block("table", payload=pd.DataFrame(rows).set_index("Critère"),
              note="Moyenne annuelle de jours remplissant le critère."),
        Block("figure", figure=figure(
            f"Jours de forte chaleur — {city}",
            viz.time_series(simple35.rename(f"T max ≥ 35 °C — {city}"),
                            f"{city} — jours de forte chaleur par an", "jours",
                            color=viz.C_TEMP),
            "Chaque point donne le nombre de jours de l'année concernée.",
        )),
        Block("note", "Une journée très chaude suivie d'une nuit fraîche "
                      "n'est pas une vraie journée de canicule. D'où la "
                      "définition à deux seuils, plus restrictive mais plus "
                      "significative. Aucun indicateur n'est faux : chacun "
                      "répond à une question différente — c'est pourquoi il doit "
                      "être publié avec sa définition."),
    ]
    sheet.steps = activities.ACTIVITIES[5].steps
    sheet.teacher_tip = activities.ACTIVITIES[5].teacher_tip
    return sheet


def sheet_latitude(hub: DataHub) -> Sheet:
    """Latitude et bilan radiatif : pourquoi fait-il froid aux pôles ?"""
    cities = ["Marseille", "Bordeaux", "Paris", "Reykjavik", "Longyearbyen"]
    sheet = Sheet(
        slug="07_latitude_rayonnement",
        title="Latitude et bilan radiatif : pourquoi fait-il froid aux pôles ?",
        subtitle="Relier la température de janvier à la latitude et au bilan "
                 "radiatif reçu.",
        objective="Relier la température moyenne annuelle à la latitude et "
                  "expliquer le rôle de l'angle d'incidence des rayons solaires.",
        skills=("Lire un graphique en nuage de points",
                "Relier une grandeur géographique à une grandeur physique",
                "Identifier les limites d'un facteur explicatif"),
        duration="55 min",
        place_names=tuple(cities),
        period=f"janvier, normale {REFERENCE[0]}-{REFERENCE[1]}",
    )
    values, labels, lats = [], [], []
    for city in cities:
        climo = hub.climatology(city)
        place = find_place(city)
        values.append(float(climo.iloc[0]))
        labels.append(city)
        lats.append(place.lat)
    frame = pd.Series(values, index=labels, dtype="float64")
    lats_series = pd.Series(lats, index=labels, dtype="float64")
    # La tendance se calcule sur la latitude (un index numérique) : la lui passer
    # la série des températures, indexée par des noms de villes, échouerait.
    trend = analysis.linear_trend(pd.Series(lats, dtype="float64"), "°C")
    sheet.blocks = [
        Block("h2", "Température de janvier"),
        Block("figure", figure=figure(
            "Température de janvier par ville",
            viz.bar_comparison(list(frame.index), list(frame.values),
                               "Température de janvier", "°C"),
            "Même grandeur, villes réparties du sud au nord.",
        )),
        Block("figure", figure=figure(
            "Température et latitude", viz.scatter_with_fit(
                lats_series, frame, "Température de janvier en fonction de la latitude",
                "latitude (°N)", "température (°C)", trend),
            "La température décroît d'environ 0,5 °C par degré de latitude.",
        )),
        Block("note", "La latitude explique la tendance générale, mais pas tout : "
                      "à latitude égale, deux villes peuvent différer de plusieurs "
                      "degrés. Les deux autres facteurs dominants sont la distance "
                      "à la mer et l'altitude."),
    ]
    sheet.steps = activities.ACTIVITIES[6].steps
    sheet.teacher_tip = activities.ACTIVITIES[6].teacher_tip
    return sheet


def _steps_origine_rechauffement() -> tuple:
    """Consignes de l'activité sur l'origine du réchauffement."""
    return (
        activities.Step(
            title="1. Expliquer l'effet de serre",
            instruction=(
                "Expliquer en une phrase d'où vient la température moyenne de la "
                "surface terrestre. Employer l'expression « effet de serre »."
            ),
            expected=(
                "Le Soleil éclaire la Terre, qui absorbe le rayonnement. L'atmosphère "
                "retient une partie de la chaleur et la renvoie vers le sol : sans "
                "cet effet, la température de surface serait négative."
            ),
            hint="Que se passerait-il si l'atmosphère n'existait plus ?",
        ),
        activities.Step(
            title="2. Mesurer à Aubagne",
            instruction=(
                "Lire le graphique d'anomalies. Décrire la tendance générale : la "
                "température augmente-t-elle ou diminue-t-elle ? Indiquer la valeur "
                "de la tendance en °C par décennie."
            ),
            expected=(
                "La température augmente d'environ +0,2 à +0,3 °C par décennie, "
                "malgré quelques années plus froides isolées."
            ),
        ),
        activities.Step(
            title="3. Identifier la cause",
            instruction=(
                "En déduire la cause du réchauffement observé. Écarter les causes "
                "naturelles (activité du Soleil, volcanisme) en justifiant la réponse."
            ),
            expected=(
                "La cause est l'activité humaine : la combustion des énergies "
                "fossiles augmente la concentration en dioxyde de carbone, gaz à "
                "effet de serre. L'activité du Soleil ne varie pas sur cette "
                "échelle de temps."
            ),
            hint="Qu'est-ce qui a changé depuis 1850 ?",
        ),
        activities.Step(
            title="4. En déduire",
            instruction=(
                "Expliquer pourquoi le réchauffement de l'air est plus lent que "
                "celui de l'océan. En déduire une conséquence sur la vie marine."
            ),
            expected=(
                "L'océan absorbe l'essentiel de la chaleur excédentaire. Il se "
                "réchauffe moins vite, mais s'acidifie, ce qui menace le plancton "
                "et les coraux."
            ),
        ),
    )


def sheet_origine_rechauffement(hub: DataHub) -> Sheet:
    """
    Origine et causes du réchauffement climatique, observées à Aubagne.

    Deux questions distinctes, souvent confondues : d'où vient l'énergie qui
    réchauffe la surface (le bilan radiatif) et qu'est-ce qui provoque le
    réchauffement observé (les activités humaines). Aubagne sert de point
    d'observation : on mesure l'écart à la normale, puis on relie ce chiffre au
    mécanisme de l'effet de serre.
    """
    city = "Aubagne"
    sheet = Sheet(
        slug="10_origine_rechauffement",
        title="Origine et causes du réchauffement climatique",
        subtitle="Comprendre d'où vient la chaleur de surface, pourquoi elle "
                 "s'accumule aujourd'hui, et le mesurer à Aubagne.",
        objective="Expliquer l'origine du réchauffement climatique en reliant le "
                  "bilan radiatif de la Terre à l'effet de serre, distinguer la "
                  "variabilité naturelle de la tendance humaine, et mesurer cette "
                  "tendance sur les données réelles d'Aubagne.",
        skills=(
            "Expliquer un phénomène par le bilan radiatif",
            "Relier une cause anthropique à un effet mesurable",
            "Distinguer variabilité naturelle et tendance de fond",
            "Lire une courbe d'anomalies et interpréter une tendance",
        ),
        duration="55 min",
        place_names=(city,),
        period=f"anomalies calculées sur {REFERENCE[0]}-{REFERENCE[1]}",
    )
    annual = hub.annual(city)
    anomalies = hub.anomalies(city)
    trend = analysis.linear_trend(annual, "°C")
    normal = annual.loc[REFERENCE[0]:REFERENCE[1]].mean()
    recent = annual.tail(10).mean()
    first30 = annual.head(30).mean()

    sheet.blocks = [
        Block("h2", "1. D'où vient la chaleur de la surface ?"),
        Block("note", (
            "Le Soleil envoie vers la Terre une énergie qui est en très grande "
            "partie renvoyée vers l'espace : la Terre est en équilibre thermique. "
            "L'atmosphère ne laisse pourtant pas repartir tout le rayonnement "
            "infrarouge — les <strong>gaz à effet de serre</strong> en absorbent "
            "une partie et la réémettent vers le sol. C'est l'origine de la "
            "température habitable d'une planète sans atmosphère."
        )),
        Block("h2", f"2. Ce que mesurent les données à {city}"),
        Block("figure", figure=figure(
            f"{city} — écart annuel à la normale",
            viz.annual_anomaly_bars(annual, anomalies,
                                    f"{city} — écart à la normale", "°C", REFERENCE),
            f"Chaque barre est l'écart de l'année à la moyenne "
            f"{REFERENCE[0]}-{REFERENCE[1]}. Une barre positive signifie une année "
            "plus chaude que la normale.",
        )),
        Block("h2", "3. Les chiffres"),
        Block("table", payload=pd.DataFrame([
            {"Indicateur": f"Moyenne {REFERENCE[0]}–{REFERENCE[1]} (normale)",
             "Valeur": f"{normal:.2f} °C"},
            {"Indicateur": "Moyenne des 30 premières années",
             "Valeur": f"{first30:.2f} °C"},
            {"Indicateur": "Moyenne des 10 dernières années",
             "Valeur": f"{recent:.2f} °C"},
            {"Indicateur": "Écart entre ces deux périodes",
             "Valeur": f"{first30 - recent:+.2f} °C"},
            {"Indicateur": "Tendance sur toute la période",
             "Valeur": f"{trend.slope * 10:+.2f} °C par décennie"},
        ]).set_index("Indicateur")),
        Block("h2", "4. Pourquoi cela s'accélère-t-il ?"),
        Block("p", (
            "La cause du réchauffement actuel n'est pas l'inertie thermique, ni "
            "les cycles naturels du Soleil : c'est l'activité humaine. La "
            "combustion du charbon, du pétrole et du gaz rejette du "
            "<strong>dioxyde de carbone</strong>, gaz à effet de serre dont la "
            "concentration dans l'atmosphère a fortement augmenté depuis la "
            "révolution industrielle. Davantage de gaz à effet de serre retiennent "
            "davantage de chaleur : c'est l'effet de serre renforcé, d'origine "
            "humaine."
        )),
        Block("h2", "5. Le rôle de l'océan"),
        Block("p", (
            "L'océan a absorbé l'essentiel de la chaleur excédentaire : c'est "
            "pourquoi le réchauffement de l'air est plus lent que celui de "
            "l'océan. Ce rôle d'éponge limite le réchauffement de surface, mais il "
            "correspond à une acidification des océans, qui menace le plancton et "
            "les récifs coralliens."
        )),
    ]
    sheet.steps = _steps_origine_rechauffement()
    sheet.teacher_tip = (
        "Bien poser la distinction de l'étape 3 : la question n'est pas « le "
        "réchauffement existe-t-il ? » mais « ses causes sont-elles humaines ? ». "
        "C'est la seconde qui est démontrée par l'accord entre la concentration "
        "de CO₂ et la température. Aubagne est un choix pertinent : son "
        "urbanisation et sa situation en cuvette en font un cas d'école pour la "
        "question du réchauffement à l'échelle locale."
    )
    return sheet


def build_all(hub: DataHub | None = None,
              only: tuple[str, ...] = ()) -> list[Path]:
    """
    Génère les fiches HTML demandées.

    `only` permet de ne produire qu'une partie des fiches, par exemple
    `("08",)` pour la seule activité Bordeaux / Montréal.
    """
    hub = hub or DataHub()
    written: list[Path] = []
    for builder in BUILDERS:
        sheet = builder(hub)
        if only and not any(sheet.slug.startswith(prefix) for prefix in only):
            continue
        written.append(write(sheet))
    return written


def index_page() -> Path:
    """
    Page d'accueil du dossier des fiches.

    Un simple lien par fichier : ces fiches sont autonomes et se distribuent
    très bien par copie, une page d'accueil unique compliquerait le partage
    d'une seule activité.
    """
    body = (
        "<p>Chaque fiche est autonome : elle contient ses graphiques, ses "
        "consignes et ses corrigés, et s'ouvre sans connexion. Les données "
        "proviennent d'ERA5 (Copernicus Climate Change Service).</p>"
        "<p><strong>Les réponses attendues sont repliées.</strong> Utilisez le "
        "bouton en haut de chaque fiche, ou ajoutez <code>?corriges=1</code> à "
        "son adresse, pour tout déplier d'un coup.</p>"
    )
    listing = "".join(
        f'<li><a href="{slug}.html">{_esc(slug.replace("_", " "))}</a></li>'
        for slug in _SLUGS
    )
    page = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Activités SVT — C3S Climate Lab</title><style>{STYLE}</style></head>
<body><div class="page">
<header><h1>Activités SVT — C3S Climate Lab</h1>
<p class="sub">Fiches autonomes, données réelles ERA5.</p></header>
{body}
<h2>Les fiches</h2><ul>{listing}</ul>
<footer><p>Généré par C3S Climate Lab.</p></footer>
</div></body></html>"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / "index.html"
    target.write_text(page, encoding="utf-8")
    return target


#: Les identifiants de fichiers, dans l'ordre de `BUILDERS`.
_SLUGS = (
    "01_ocean_continent",
    "02_cycle_eau",
    "03_rechauffement_climatique",
    "04_pression_vent",
    "05_cartes_climatiques",
    "06_canicule",
    "07_latitude_rayonnement",
    "08_bordeaux_montreal",
    "09_meteo_climat",
    "10_origine_rechauffement",
)


def _steps_bordeaux_montreal() -> tuple:
    """Consignes de l'activité Bordeaux / Montréal."""
    return (
        activities.Step(
            title="1. Décrire les courbes",
            instruction=(
                "Comparer les courbes de Bordeaux et de Montréal, mois par mois. "
                "Décrire la forme de chacune et repérer la ville la plus « plate »."
            ),
            expected=(
                "Montréal a une courbe fortement bosselée : des hivers très froids "
                "et des étés chauds. Bordeaux a une courbe beaucoup plus douce."
            ),
        ),
        activities.Step(
            title="2. Mesurer l'écart",
            instruction=(
                "Lire les deux amplitudes thermiques du tableau et calculer leur "
                "différence. En déduire à quelle catégorie appartient chaque ville."
            ),
            expected=(
                "L'amplitude de Montréal dépasse le double de celle de Bordeaux : "
                "c'est la signature d'un climat continental, loin de la mer."
            ),
            hint="Un écart de plus de 20 °C entre janvier et juillet caractérise un climat continental.",
        ),
        activities.Step(
            title="3. Expliquer par les vents",
            instruction=(
                "Expliquer pourquoi l'air qui arrive à Montréal a perdu son "
                "caractère maritime. Introduire la circulation des vents d'ouest "
                "en moyennes latitudes."
            ),
            expected=(
                "Les vents d'ouest soufflent d'ouest en est : l'air qui atteint "
                "l'Europe vient de l'Atlantique et reste doux. Cet air continue "
                "sa trajectoire vers l'Amérique du Nord en traversant tout le "
                "continent : il devient sec et se refroidit fortement en hiver."
            ),
            hint="D'où vient l'air en Europe de l'Ouest ? Et en Amérique du Nord ?",
        ),
        activities.Step(
            title="4. En déduire",
            instruction=(
                "En déduire si la latitude suffit à prévoir le climat d'une ville. "
                "Formuler une règle applicable à une ville jamais étudiée."
            ),
            expected=(
                "Non : il faut connaître la distance à l'océan et la direction des "
                "vents dominants. Deux villes de même latitude peuvent avoir des "
                "climats opposés."
            ),
        ),
    )


def _steps_meteo_climat() -> tuple:
    """Consignes de l'activité météorologie / climatologie."""
    return (
        activities.Step(
            title="1. Définir",
            instruction=(
                "Donner une définition du mot « climat » et une du mot « météo ». "
                "En déduire lequel des deux décrit une situation constatée en ce "
                "moment."
            ),
            expected=(
                "Le climat décrit les caractéristiques moyennes d'un lieu sur "
                "trente ans ; la météo décrit l'atmosphère à un instant donné. "
                "La météo est donc le mot du jour."
            ),
        ),
        activities.Step(
            title="2. Vérifier avec les chiffres",
            instruction=(
                "Comparer les trois moyennes du tableau. Les deux fenêtres de "
                "quatre ans donnent-elles le même résultat ? En déduire ce que "
                "permet — et ne permet pas — une moyenne sur quatre ans."
            ),
            expected=(
                "Non : les moyennes de quatre ans diffèrent nettement. Une "
                "moyenne sur quatre ans décrit un épisode, pas un climat."
            ),
            hint="Écrire les deux valeurs au tableau avant de conclure.",
        ),
        activities.Step(
            title="3. Expliquer",
            instruction=(
                "Expliquer pourquoi la durée d'observation change le résultat. "
                "Utiliser l'expression « variabilité naturelle »."
            ),
            expected=(
                "La température varie naturellement d'une année à l'autre : sur "
                "peu d'années, une année très froide ou très chaude pèse beaucoup "
                "sur la moyenne. Trente ans suffisent pour que ces excursions se "
                "compensent."
            ),
        ),
        activities.Step(
            title="4. En déduire",
            instruction=(
                "En déduire ce qu'un quotidien local peut — et ne peut pas — "
                "dire du climat d'une région."
            ),
            expected=(
                "Un quotidien décrivant une seule journée relève de la "
                "météorologie. Pour parler du climat, il faut une série longue et "
                "une normale calculée sur trente ans."
            ),
        ),
    )


def sheet_meteo_climat(hub: DataHub) -> Sheet:
    """
    Différence entre météorologie et climatologie.

    Deux mots souvent confondus : la météo décrit l'état ponctuel de
    l'atmosphère, le climat ses caractéristiques statistiques sur trente ans.
    L'activité le démontre avec la même ville, sur des fenêtres de durées
    différentes : plus la fenêtre est courte, plus les moyennes varient.
    """
    city = "Marseille"
    sheet = Sheet(
        slug="09_meteo_climat",
        title="Météorologie et climatologie : quelle différence ?",
        subtitle="Le même lieu, le même jeu de données, deux façons de le "
                 "décrire — et des résultats très différents.",
        objective="Distinguer la météorologie, qui décrit l'état ponctuel de "
                  "l'atmosphère, de la climatologie, qui en décrit les "
                  "statistiques sur au moins trente ans, et montrer par les "
                  "données que la durée d'observation change le résultat.",
        skills=(
            "Distinguer une situation ponctuelle d'une statistique",
            "Calculer une moyenne sur des fenêtres de durées différentes",
            "Discuter de la durée nécessaire pour décrire un climat",
        ),
        duration="55 min",
        place_names=(city,),
        period="données mensuelles 1940-2024",
    )
    series = hub.series(city)
    annual = series.groupby(series.index.year).mean()
    short1 = annual.loc[2021:2024].mean()
    short2 = annual.loc[2010:2013].mean()
    reference_mean = annual.loc[REFERENCE[0]:REFERENCE[1]].mean()
    coldest, warmest = annual.idxmin(), annual.idxmax()
    frame = pd.DataFrame([
        {"Fenêtre d'observation": f"{REFERENCE[0]}–{REFERENCE[1]} (normale)",
         "Durée": "30 ans", "Moyenne annuelle": f"{reference_mean:.2f} °C",
         "Statut": "décrit un climat"},
        {"Fenêtre d'observation": f"{coldest} (année la plus froide)",
         "Durée": "1 an", "Moyenne annuelle": f"{annual[coldest]:.2f} °C",
         "Statut": "décrit une année"},
        {"Fenêtre d'observation": f"{warmest} (année la plus chaude)",
         "Durée": "1 an", "Moyenne annuelle": f"{annual[warmest]:.2f} °C",
         "Statut": "décrit une année"},
        {"Fenêtre d'observation": "2010–2013", "Durée": "4 ans",
         "Moyenne annuelle": f"{short2:.2f} °C", "Statut": "décrit un épisode"},
        {"Fenêtre d'observation": "2021–2024", "Durée": "4 ans",
         "Moyenne annuelle": f"{short1:.2f} °C", "Statut": "décrit un épisode"},
    ]).set_index("Fenêtre d'observation")

    sheet.blocks = [
        Block("h2", "Deux définitions"),
        Block("note", (
            "<strong>La météorologie</strong> décrit l'état de l'atmosphère à un "
            "endroit et à un instant donnés : c'est le bulletin de 18 h. "
            "<strong>La climatologie</strong> en décrit les caractéristiques "
            "statistiques sur au moins trente ans : c'est la normale, qui "
            "permet de comparer deux lieux ou deux périodes."
        )),
        Block("h2", f"Ce que donne la même ville ({city}) selon la fenêtre"),
        Block("table", payload=frame,
              note="Même série de données, trois lectures différentes."),
        Block("figure", figure=figure(
            f"{city} — température annuelle",
            viz.time_series(annual.rename(city), f"{city} — température annuelle", "°C",
                            color=viz.C_TEMP),
            "Chaque point est la moyenne de douze mois. Les points isolés très "
            "bas ou très haut relèvent de la variabilité naturelle.",
        )),
        Block("h2", "Pourquoi trente ans ?"),
        Block("p", (
            "Sur une courte période, la moyenne dépend fortement des années "
            "choisies : deux fenêtres de quatre ans peuvent donner des moyennes "
            "très différentes. Sur trente ans, l'alternance des années froides et "
            "chaudes s'équilibre, et la moyenne devient un indicateur fiable. "
            "C'est pourquoi l'Organisation météorologique mondiale fixe la "
            "normale climatologique sur une période de trente ans."
        )),
    ]
    sheet.steps = _steps_meteo_climat()
    sheet.teacher_tip = (
        "Activité courte et très rentable : elle évite un contresens fréquent aux "
        "examens, où l'on présente une carte de moyenne sur trois ans en la "
        "qualifiant de « carte du climat ». Faire remarquer que la fenêtre de "
        "quatre ans n'est pas fausse : elle répond à une autre question, celle "
        "de « ces années-là »."
    )
    return sheet


def sheet_bordeaux_montreal(hub: DataHub) -> Sheet:
    """
    Bordeaux et Montréal : mêmes latitudes, climats opposés.

    Les deux villes sont à moins d'un degré de latitude, mais l'une est en
    bordure de l'océan Atlantique sur la façade ouest d'un continent, l'autre au
    fond d'un immense continent nord-américain. C'est l'occasion d'introduire
    les vents d'ouest dominants et le rôle régulateur de l'océan.
    """
    cities = ["Bordeaux", "Montréal"]
    sheet = Sheet(
        slug="08_bordeaux_montreal",
        title="Bordeaux et Montréal : pourquoi deux climats à la même latitude ?",
        subtitle="Même latitude, deux climats très différents : expliquer le rôle "
                 "des vents d'ouest, de l'océan et de la continentalité.",
        objective="Expliquer pourquoi deux villes situées à moins d'un degré de "
                  "latitude l'une de l'autre ont des climats très différents, en "
                  "mettant en cause les vents d'ouest, le rôle thermique de "
                  "l'océan et la continentalité.",
        skills=(
            "Comparer des climats à partir de données réelles",
            "Relier une différence climatique à un mécanisme (vents, océan, continent)",
            "Identifier le rôle de la circulation atmosphérique globale",
        ),
        duration="55 min",
        place_names=tuple(cities),
        period=f"normale {REFERENCE[0]}-{REFERENCE[1]}",
    )
    temp_climos = {c: hub.climatology(c) for c in cities}
    precip_climos = {c: hub.climatology(c, "total_precipitation") for c in cities}
    bord, mont = (find_place(c) for c in cities)
    amps = {c: analysis.thermal_amplitude(temp_climos[c]) for c in cities}

    sheet.blocks = [
        Block("h2", "Une parenthèse à faire d'abord"),
        Block("note", (
            f"Bordeaux est à {bord.lat:.2f}° N et Montréal à {mont.lat:.2f}° N : "
            f"l'écart de latitude n'est que de {abs(bord.lat - mont.lat):.2f}°. "
            "Tout ce qui suit se passe pourtant à cette échelle : la latitude "
            "n'explique pas ces climats."
        )),
        Block("h2", "Températures mensuelles"),
        Block("figure", figure=_climato_figure(
            hub, cities, "2m_temperature",
            "Bordeaux et Montréal — températures mensuelles", "°C")),
        Block("h2", "Amplitude thermique : la signature de la continentalité"),
        Block("figure", figure=_amplitude_figure(hub, cities)),
        Block("h2", "Diagrammes ombrothermiques"),
    ]
    for city in cities:
        sheet.blocks.append(Block("figure", figure=_ombro_figure(hub, city)))
    sheet.blocks.append(Block("h2", "Les chiffres à retenir"))
    sheet.blocks.append(Block("table", payload=pd.DataFrame([
        {"Critère": "Latitude", "Bordeaux": f"{bord.lat:.2f}° N",
         "Montréal": f"{mont.lat:.2f}° N"},
        {"Critère": "Distance à l'océan",
         "Bordeaux": "≈ 100 km (façade atlantique)",
         "Montréal": "≈ 1 000 km (intérieur du continent)"},
        {"Critère": "Amplitude thermique annuelle",
         "Bordeaux": f"{amps['Bordeaux']:.1f} °C",
         "Montréal": f"{amps['Montréal']:.1f} °C"},
        {"Critère": "Mois le plus froid",
         "Bordeaux": f"{_month_name(temp_climos['Bordeaux'].idxmin())} "
                     f"({temp_climos['Bordeaux'].min():.1f} °C)",
         "Montréal": f"{_month_name(temp_climos['Montréal'].idxmin())} "
                     f"({temp_climos['Montréal'].min():.1f} °C)"},
        {"Critère": "Mois le plus chaud",
         "Bordeaux": f"{_month_name(temp_climos['Bordeaux'].idxmax())} "
                     f"({temp_climos['Bordeaux'].max():.1f} °C)",
         "Montréal": f"{_month_name(temp_climos['Montréal'].idxmax())} "
                     f"({temp_climos['Montréal'].max():.1f} °C)"},
        {"Critère": "Précipitations annuelles",
         "Bordeaux": f"{precip_climos['Bordeaux'].sum():.0f} mm",
         "Montréal": f"{precip_climos['Montréal'].sum():.0f} mm"},
    ]).set_index("Critère")))

    sheet.blocks.append(Block("h2", "Le mécanisme : les vents d'ouest"))
    sheet.blocks.append(Block("p", (
        "Aux moyennes latitudes, l'air circule d'ouest en est : ce sont les "
        "<strong>vents d'ouest</strong>, produits par la bascule des vents vers "
        "les hautes pressions dans les cellules de Ferrel. En Europe de "
        "l'Ouest, ce flux apporte un air doux venu de l'océan Atlantique, "
        "encore adouci par le Gulf Stream et la dérive nord-atlantique. Ce même "
        "flux, en traversant l'Atlantique, devient continental : il a perdu son "
        "effet thermique maritime bien avant d'atteindre Montréal."
    )))
    sheet.steps = _steps_bordeaux_montreal()
    sheet.teacher_tip = (
        "C'est l'activité la plus rentable pour démolir le réflexe « plus on va "
        "au nord, plus il fait froid ». Comparer visuellement les deux courbes "
        "avant de poser la question : le contraste de forme est plus parlant "
        "qu'une définition. Si un élève évoque le Gulf Stream, valoriser la "
        "réponse puis préciser son effet réel, plus modeste qu'on ne le dit "
        "souvent."
    )
    return sheet

#: Les fiches à generer, dans l'ordre d'utilisation en classe. Defini en fin de
#: module : toutes les fonctions doivent exister quand cette tuple est evaluee.
BUILDERS = (
    sheet_ocean_continent,
    sheet_cycle_eau,
    sheet_rechauffement,
    sheet_vent_pression,
    sheet_cartes_climatiques,
    sheet_canicule,
    sheet_latitude,
    sheet_bordeaux_montreal,
    sheet_meteo_climat,
    sheet_origine_rechauffement,
)
