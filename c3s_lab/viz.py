"""
Graphiques interactifs (Plotly) pour l'exploitation des données en classe.

Deux conventions sont appliquées partout, car elles conditionnent la
lisibilité scientifique d'une figure :

* **format français** : virgule décimale, espace comme séparateur de milliers,
 Dates à la française — chiffres et non lettres, pour éviter les ambiguïtés ;
* **code couleur homogène** : le bleu pour la température, le vert pour les
  précipitations, le rouge pour une anomalie positive, le bleu pour une
  anomalie négative. Le même code est repris dans toutes les activités, ce qui
  permet aux élèves de lire les figures sans les réapprendre.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import analysis

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #

C_TEMP = "#d1495b"
C_PRECIP = "#2a9d8f"
C_PRESSURE = "#457b9d"
C_SNOW = "#8ecae6"
C_NEUTRAL = "#6c757d"
C_REF = "#264653"

#: Palette divergente pour les anomalies : froid -> neutre -> chaud.
ANOMALY_SCALE = [
    [0.0, "#08306b"],
    [0.25, "#2171b5"],
    [0.5, "#f7f7f7"],
    [0.75, "#cb181d"],
    [1.0, "#67000d"],
]

#: Palette séquentielle pour les températures (classe « diverging » de ColorBrewer).
TEMP_SCALE = [
    [0.0, "#313695"],
    [0.15, "#4575b4"],
    [0.3, "#74add1"],
    [0.45, "#abd9e9"],
    [0.5, "#ffffbf"],
    [0.6, "#fee090"],
    [0.75, "#f46d43"],
    [0.9, "#d73027"],
    [1.0, "#a50026"],
]

#: Palette séquentielle pour les précipitations.
PRECIP_SCALE = [
    [0.0, "#f7fcf0"],
    [0.2, "#ccebc5"],
    [0.4, "#7bccc4"],
    [0.6, "#43a2ca"],
    [0.8, "#0868ac"],
    [1.0, "#084081"],
]

PRESSURE_SCALE = [
    [0.0, "#5e3c99"],
    [0.3, "#7570b3"],
    [0.5, "#f7f7f7"],
    [0.7, "#d7301f"],
    [1.0, "#7f0000"],
]

FR_LAYOUT = dict(
    separators=", ",
    font=dict(family="Segoe UI, Arial, sans-serif", size=13),
    margin=dict(l=60, r=25, t=70, b=55),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)


def base_figure(title: str, *, height: int = 460) -> go.Figure:
    """Figure Plotly pré-stylée selon les conventions françaises."""
    fig = go.Figure()
    fig.update_layout(title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)), height=height, **FR_LAYOUT)
    return fig


def _style_axes(fig: go.Figure, x_title: str, y_title: str) -> go.Figure:
    fig.update_xaxes(title_text=x_title, showgrid=True, gridcolor="#eceff1", zeroline=False)
    fig.update_yaxes(title_text=y_title, showgrid=True, gridcolor="#eceff1", zeroline=False)
    return fig



# --------------------------------------------------------------------------- #
# Séries temporelles
# --------------------------------------------------------------------------- #


def time_series(
    series: pd.Series,
    title: str,
    unit: str,
    *,
    anomalies: pd.Series | None = None,
    reference: tuple[int, int] | None = None,
    color: str = C_TEMP,
    height: int = 440,
) -> go.Figure:
    """
    Courbe d'évolution, avec bande de la période de référence si elle est
    fournie, et surcouche des anomalies (barres positives / négatives).
    """
    fig = go.Figure()

    if reference:
        ref = series.loc[f"{reference[0]}-01-01": f"{reference[1]}-12-31"].dropna()
        if not ref.empty:
            mean = float(ref.mean())
            std = float(ref.std())
            fig.add_hrect(
                y0=mean - std, y1=mean + std, fillcolor=C_REF, opacity=0.10,
                line_width=0, annotation_text=f"variabilité {reference[0]}-{reference[1]}",
                annotation_position="top left", annotation_font=dict(size=10, color=C_REF),
            )
            fig.add_hline(y=mean, line=dict(color=C_REF, width=1.5, dash="dash"),
                          annotation_text=f"normale {mean:.2f} {unit}",
                          annotation_position="bottom left",
                          annotation_font=dict(size=11, color=C_REF))

    fig.add_trace(
        go.Scatter(
            x=series.index, y=series.values, mode="lines", name=title,
            line=dict(color=color, width=2.2),
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f} " + unit + "<extra></extra>",
        )
    )

    if anomalies is not None and not anomalies.empty:
        fig.add_trace(
            go.Bar(
                x=anomalies.index, y=anomalies.values, name=f"anomalie ({unit})",
                yaxis="y2", opacity=0.45,
                marker=dict(
                    color=[C_TEMP if v >= 0 else "#457b9d" for v in anomalies.values]
                ),
                hovertemplate="%{x|%d/%m/%Y}<br>anomalie %{y:+.2f} " + unit + "<extra></extra>",
            )
        )
        fig.update_layout(
            yaxis2=dict(title=f"Anomalie ({unit})", overlaying="y", side="right",
                        showgrid=False, zeroline=True, zerolinecolor="#999",
                        zerolinewidth=1, range=[-max(3, abs(anomalies).max() * 1.2)] * 2)
        )

    _style_axes(fig, "", f"{title} ({unit})")
    return fig


def annual_anomaly_bars(
    annual: pd.Series,
    anomalies: pd.Series,
    title: str,
    unit: str,
    reference: tuple[int, int],
    *,
    height: int = 440,
) -> go.Figure:
    """
    Diagramme en barres des anomalies annuelles.

    Le graphique de référence du réchauffement climatique : chaque barre est
    l'écart d'une année à la normale 1991-2020.
    """
    fig = go.Figure()
    colors = [C_TEMP if v >= 0 else "#457b9d" for v in anomalies.values]
    fig.add_trace(
        go.Bar(
            x=anomalies.index, y=anomalies.values, marker=dict(color=colors),
            name="écart à la normale",
            customdata=annual.values,
            hovertemplate="%{x}<br>température %{customdata:.2f} " + unit
                          + "<br>écart à la normale %{y:+.2f} " + unit + "<extra></extra>",
        )
    )
    fig.add_hline(y=0, line=dict(color="#555", width=1.2))
    fig.add_hrect(
        y0=float(anomalies.std()), y1=-float(anomalies.std()),
        fillcolor=C_NEUTRAL, opacity=0.10, line_width=0,
    )
    _style_axes(fig, "Année", f"Écart à la normale {reference[0]}-{reference[1]} ({unit})")
    fig.update_layout(title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)), height=height, **FR_LAYOUT)
    return fig


# --------------------------------------------------------------------------- #
# Climatologies et comparaisons
# --------------------------------------------------------------------------- #


def monthly_climato_chart(
    temp: pd.Series,
    precip: pd.Series | None,
    title: str,
    *,
    temp_color: str = C_TEMP,
    precip_color: str = C_PRECIP,
    height: int = 460,
) -> go.Figure:
    """
    Graphique des moyennes mensuelles (« climatogramme » en deux axes).

    L'axe des températures est placé à gauche et celui des précipitations à
    droite, avec une graduation inversée pour les précipitations : c'est la
    convention du diagramme ombrothermique, l'axe de droite diminue vers le
    haut. Cela permet de superposer les deux courbes sur un même repère.
    """
    fig = go.Figure()
    months = analysis.MONTH_LABELS

    if precip is not None and not precip.empty:
        fig.add_trace(
            go.Bar(
                x=months, y=precip.values, name="Précipitations (mm)",
                marker=dict(color=precip_color, opacity=0.75), yaxis="y2",
                hovertemplate="%{x}<br>%{y:.0f} mm<extra></extra>",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=months, y=temp.values, name="Température (°C)", mode="lines+markers",
            line=dict(color=temp_color, width=3), marker=dict(size=9),
            fill="tozeroy", fillcolor="rgba(209,73,91,0.12)",
            hovertemplate="%{x}<br>%{y:.1f} °C<extra></extra>",
        )
    )

    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)),
        height=height,
        yaxis=dict(title="Température (°C)", showgrid=True, gridcolor="#eceff1"),
        yaxis2=dict(
            title="Précipitations (mm)", overlaying="y", side="right", showgrid=False,
            autorange="reversed",
        ),
        xaxis=dict(showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        separators=", ",
        font=dict(family="Segoe UI, Arial, sans-serif", size=13),
        margin=dict(l=60, r=60, t=70, b=45),
        hovermode="x",
    )
    return fig


def bar_comparison(
    labels: list[str],
    values: list[float],
    title: str,
    unit: str,
    *,
    color: str = C_TEMP,
    height: int = 430,
    show_values: bool = True,
) -> go.Figure:
    """Diagramme en barres horizontal, lisible pour comparer des villes."""
    colors = [color] * len(values)
    fig = go.Figure(
        go.Bar(
            x=values, y=labels, orientation="h",
            marker=dict(color=colors),
            text=[f"{v:.1f} {unit}" for v in values] if show_values else None,
            textposition="outside",
            hovertemplate="%{y}<br>%{x:.2f} " + unit + "<extra></extra>",
        )
    )
    span = (max(values) - min(values)) or 1.0
    fig.update_xaxes(range=[min(values) - 0.12 * span, max(values) + 0.28 * span], showgrid=True, gridcolor="#eceff1")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)),
        height=max(height, 120 + 42 * len(labels)),
        separators=", ",
        font=dict(family="Segoe UI, Arial, sans-serif", size=13),
        margin=dict(l=140, r=70, t=70, b=50),
        xaxis_title=unit,
    )
    return fig


def multi_city_climato(
    series_by_city: dict[str, pd.Series],
    title: str,
    unit: str,
    *,
    height: int = 470,
) -> go.Figure:
    """
    Courbes mensuelles superposées pour plusieurs villes.

    Les couleurs suivent une séquence qualitative distincte, car il ne s'agit pas
    d'une échelle quantitative mais de catégories.
    """
    palette = [
        "#d1495b", "#00798c", "#edae49", "#66a182", "#7d5ba6",
        "#c1666b", "#2a9d8f", "#8a6d3b", "#3d5a80", "#bc4749",
    ]
    fig = go.Figure()
    for i, (city, s) in enumerate(series_by_city.items()):
        if s.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=analysis.MONTH_LABELS, y=s.values, name=city, mode="lines+markers",
                line=dict(color=palette[i % len(palette)], width=2.6),
                marker=dict(size=7),
                hovertemplate=city + " — %{x}<br>%{y:.1f} " + unit + "<extra></extra>",
            )
        )
    _style_axes(fig, "", unit)
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)),
        height=height, **FR_LAYOUT,
    )
    return fig


# --------------------------------------------------------------------------- #
# Relations entre variables et tendances
# --------------------------------------------------------------------------- #


def scatter_with_fit(
    x: pd.Series,
    y: pd.Series,
    title: str,
    x_title: str,
    y_title: str,
    trend,
    *,
    height: int = 470,
    x_range: tuple[int, int] | None = None,
) -> go.Figure:
    """
    Nuage de points avec droite de régression.

    Utilisé notamment pour l'activité sur l'effet de serre : chaque point
    représente une année, et la droite de tendance résume l'évolution d'ensemble.
    """
    x_vals = np.asarray(getattr(x, "values", x), dtype="float64")
    y_vals = np.asarray(getattr(y, "values", y), dtype="float64")
    labels = np.asarray(getattr(x, "index", np.arange(len(x_vals))), dtype=object)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_vals, y=y_vals, mode="markers", name="observations annuelles",
            marker=dict(size=9, color="#3d5a80", opacity=0.72, line=dict(width=0.5, color="white")),
            customdata=labels,
            hovertemplate="année %{customdata}<br>%{x:.1f}<br>" + y_title + " %{y:.1f}<extra></extra>",
        )
    )

    xlim = x_range or (int(np.nanmin(x_vals)), int(np.nanmax(x_vals)))
    grid = np.array([xlim[0], xlim[1]], dtype="float64")
    fig.add_trace(
        go.Scatter(
            x=grid, y=trend.predict(grid), mode="lines", name="droite de tendance",
            line=dict(color=C_TEMP, width=3, dash="dash"),
            hovertemplate="tendance : %{y:.2f} " + y_title.split()[-1] + "<extra></extra>",
        )
    )
    _style_axes(fig, x_title, y_title)
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)),
        height=height, **FR_LAYOUT,
    )
    return fig


def trend_chart(
    series: pd.Series,
    trend,
    title: str,
    y_title: str,
    *,
    height: int = 450,
) -> go.Figure:
    """Série temporelle avec droite de tendance et intervalle de variabilité."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=series.index, y=series.values, mode="lines+markers", name="valeurs observées",
            line=dict(color=C_NEUTRAL, width=1.6), marker=dict(size=6),
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}<extra></extra>",
        )
    )
    years = np.asarray(series.index, dtype="datetime64").astype("datetime64[Y]").astype(int) + 1970
    fig.add_trace(
        go.Scatter(
            x=years, y=trend.predict(years), mode="lines", name="tendance linéaire",
            line=dict(color=C_TEMP, width=3),
            hovertemplate="tendance %{y:.2f}<extra></extra>",
        )
    )
    _style_axes(fig, "", y_title)
    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)),
        height=height, **FR_LAYOUT,
    )
    return fig


def ombrothermic_diagram(
    temp: pd.Series,
    precip: pd.Series,
    title: str,
    *,
    temp_limit: float = 30.0,
    precip_limit: float | None = None,
    height: int = 520,
) -> go.Figure:
    """
    Diagramme ombrothermique de Walter-Lieth simplifié.

    Convention : 10 mm de précipitations sont dessinés comme 1 °C, pour que les
    deux échelles soient directement comparables. La courbe des températures est
    tracée en °C, les barres de précipitations en mm ramenés à la même échelle.
    """
    if precip_limit is None:
        precip_limit = max(float(precip.max()) * 1.15, 10.0)
    scale = temp_limit / precip_limit  # px par mm

    months = analysis.MONTH_LABELS_LONG
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=months, y=precip.values, name="Précipitations (mm, axe du bas)",
            marker=dict(color=C_PRECIP, opacity=0.80),
            hovertemplate="%{x}<br>%{y:.0f} mm<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=months, y=temp.values, name="Température (°C, axe de gauche)",
            mode="lines+markers", line=dict(color=C_TEMP, width=3.5),
            marker=dict(size=8), yaxis="y2",
            hovertemplate="%{x}<br>%{y:.1f} °C<extra></extra>",
        )
    )
    # Barres d'échelle comparables : 1 °C = 10 mm
    for i, (t, p) in enumerate(zip(temp.values, precip.values)):
        if float(t) <= 0:
            continue
        fig.add_shape(
            type="line", x0=months[i], x1=months[i],
            y0=0, y1=float(t) / scale, line=dict(color="rgba(0,0,0,0.18)", width=1),
        )

    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=17)),
        height=height,
        yaxis=dict(title="Précipitations (mm)", range=[0, precip_limit], showgrid=True, gridcolor="#eceff1"),
        yaxis2=dict(title="Température (°C)", overlaying="y", side="left",
                    range=[-temp_limit * 0.4, temp_limit * 1.1], showgrid=False),
        xaxis=dict(showgrid=False, tickangle=-30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        separators=", ",
        font=dict(family="Segoe UI, Arial, sans-serif", size=12),
        margin=dict(l=70, r=30, t=70, b=90),
        barmode="overlay",
        hovermode="x",
    )
    return fig


# --------------------------------------------------------------------------- #
# Avant / après
# --------------------------------------------------------------------------- #


def before_after_charts(
    before: pd.Series,
    after: pd.Series,
    before_label: str,
    after_label: str,
    *,
    unit: str = "°C",
    title: str = "Comparaison de deux périodes",
    height: int = 400,
) -> go.Figure:
    """
    Deux courbes superposées : la période de référence et la période récente.

    L'écart entre les deux courbes est colorée : le réchauffement devient
    visible sans aucun calcul, ce qui est l'essentiel pour des élèves de cycle 4.
    """
    fig = go.Figure()
    common = before.index.union(after.index)
    b = before.reindex(common)
    a = after.reindex(common)

    fig.add_trace(
        go.Scatter(
            x=common, y=b, mode="lines", name=before_label,
            line=dict(color="#457b9d", width=3),
            hovertemplate=f"{before_label}<br>%{{x}}|%{{y:.2f}} {unit}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=common, y=a, mode="lines", name=after_label,
            line=dict(color="#d1495b", width=3),
            hovertemplate=f"{after_label}<br>%{{x}}|%{{y:.2f}} {unit}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(common) + list(common[::-1]),
            y=list(a.values) + list(b.values[::-1]),
            fill="toself", fillcolor="rgba(209,73,91,0.16)", mode="lines",
            line=dict(width=0), name="écart entre les deux périodes",
            hoverinfo="skip",
        )
    )
    _style_axes(fig, "", f"{title} ({unit})")
    fig.update_layout(height=height, **FR_LAYOUT)
    return fig


def delta_scale(values) -> tuple[list, float, float]:
    """
    Échelle divergente centrée sur zéro, pour une carte d'écart.

    Une échelle divergente signale le signe de l'anomalie ; une échelle
    séquentielle le masquerait et fausserait la lecture.
    """
    finite = np.asarray(values, dtype="float64")
    finite = finite[np.isfinite(finite)]
    limit = float(np.nanmax(np.abs(finite))) if finite.size else 1.0
    limit = max(limit, 0.1)
    scale = [
        [0.0, "#08306b"], [0.25, "#2171b5"], [0.5, "#f7f7f7"],
        [0.75, "#cb181d"], [1.0, "#67000d"],
    ]
    return scale, -limit, limit


def delta_bars(
    labels: list[str],
    deltas: list[float],
    unit: str = "°C",
    *,
    title: str = "Écart de température",
    height: int = 400,
) -> go.Figure:
    """Barres d'écart, colorées selon le signe : froid en bleu, chaud en rouge."""
    colors = ["#d1495b" if d >= 0 else "#457b9d" for d in deltas]
    fig = go.Figure(
        go.Bar(
            x=labels, y=deltas, marker=dict(color=colors),
            text=[f"{d:+.1f} {unit}" for d in deltas],
            textposition="outside",
            hovertemplate="%{x}<br>écart %{y:+.2f} " + unit + "<extra></extra>",
        )
    )
    fig.add_hline(y=0, line=dict(color="#333", width=1.2))
    _style_axes(fig, "", f"{title} ({unit})")
    fig.update_layout(height=height, **FR_LAYOUT, showlegend=False)
    return fig

    return fig
