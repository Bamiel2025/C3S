"""
Catalogue des jeux de données Copernicus (CDS) retenus pour un usage en classe.

Chaque entrée décrit la requête API exacte (identifiants et noms de paramètres
vérifiés sur le catalogue officiel du CDS), l'unité, la résolution et le coût
approximatif du téléchargement — information décisive en salle de cours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

# --------------------------------------------------------------------------- #
# Description d'un jeu de données
# --------------------------------------------------------------------------- #

VariableKind = Literal["temperature", "precipitation", "pressure", "wind", "snow", "cloud", "geo"]


@dataclass(frozen=True)
class Variable:
    """Une variable météorologique disponible dans un jeu de données."""

    slug: str
    label: str
    unit: str
    long_name: str
    kind: VariableKind
    #: Statistiques journalières compatibles avec ce jeu de données.
    daily_stats: tuple[str, ...] = ("daily_mean",)
    #: Leçon du programme de cycle 4 à laquelle la variable se rattache.
    lesson: str = "climat"


@dataclass(frozen=True)
class Dataset:
    """Un jeu de données du CDS et sa méthode d'appel."""

    id: str
    label: str
    summary: str
    frequency: str
    start_year: int
    resolution: str
    doc_url: str
    licence: str
    variables: tuple[Variable, ...]
    size_hint_mb: float = 5.0
    timeseries: bool = False
    notes: str = ""
    difficulty: int = 1

    def var(self, slug: str) -> Variable | None:
        return next((v for v in self.variables if v.slug == slug), None)


# --------------------------------------------------------------------------- #
# Variables communes aux différents jeux de données
# --------------------------------------------------------------------------- #

T2M = Variable(
    "2m_temperature", "Température de l'air à 2 m", "°C",
    "Temperature at 2 metres above ground surface", "temperature",
    daily_stats=("daily_mean", "daily_maximum", "daily_minimum"),
    lesson="saisons et effet de serre",
)
PRCP = Variable(
    "total_precipitation", "Précipitations totales", "mm",
    "Total precipitation (rain, snow and convective)", "precipitation",
    daily_stats=("daily_sum",), lesson="cycle de l'eau",
)
MSLP = Variable(
    "mean_sea_level_pressure", "Pression au niveau de la mer", "hPa",
    "Mean sea level pressure (MSLP)", "pressure", lesson="vents et pression",
)
SNOW = Variable(
    "snow_depth", "Épaisseur de neige", "m",
    "Snow depth (water equivalent excluded)", "snow",
    lesson="cryosphère et changement climatique",
)
CLOUD = Variable(
    "total_cloud_cover", "Nébulosité totale", "%",
    "Total cloud cover (0-100)", "cloud", lesson="météo et effet radiatif",
)
WIND_U = Variable(
    "10m_u_component_of_wind", "Vent à 10 m (composante U, vers l'est)", "m/s",
    "Eastward component of the 10 metre wind", "wind", lesson="vents",
)
WIND_V = Variable(
    "10m_v_component_of_wind", "Vent à 10 m (composante V, vers le nord)", "m/s",
    "Northward component of the 10 metre wind", "wind", lesson="vents",
)
GEOPOT = Variable(
    "geopotential", "Géopotentiel", "m²/s²",
    "Geopotential (accélération de pesanteur x hauteur)", "geo",
    daily_stats=("daily_mean", "daily_maximum", "daily_minimum"),
    lesson="circulation atmosphérique",
)
T850 = Variable(
    "temperature", "Température à 850 hPa (≈ 1,5 km d'altitude)", "K",
    "Temperature on pressure level 850 hPa", "temperature",
    lesson="stabilité de l'atmosphère",
)

DOC_SL = "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means"
DOC_DAILY = "https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics"
DOC_PL = "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels-monthly-means"
DOC_TS = "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries"

# --------------------------------------------------------------------------- #
# Jeux de données
# --------------------------------------------------------------------------- #

DATASETS: dict[str, Dataset] = {
    "monthly_means": Dataset(
        id="reanalysis-era5-single-levels-monthly-means",
        label="ERA5 — moyennes mensuelles (niveaux de surface)",
        summary=(
            "Température, précipitations et pression moyennées par mois sur toute "
            "la planète, depuis 1940. C'est le jeu de référence pour construire des "
            "normales climatiques et des courbes d'évolution."
        ),
        frequency="mensuel",
        start_year=1940,
        resolution="0,25° x 0,25° (≈ 25 km)",
        doc_url=DOC_SL,
        licence="CC BY 4.0",
        variables=(T2M, PRCP, MSLP, SNOW, CLOUD, WIND_U, WIND_V),
        size_hint_mb=12.0,
        notes=(
            "La température est en kelvins dans le fichier, l'application la "
            "convertit en °C. Le CDS n'accepte plus le paramètre `grid` : le "
            "sous-échelonnement se fait après téléchargement."
        ),
    ),
    "daily_stats": Dataset(
        id="derived-era5-single-levels-daily-statistics",
        label="ERA5 — statistiques journalières (niveaux de surface)",
        summary=(
            "Statistiques quotidiennes calculées par le CDS à partir des données "
            "horaires : moyenne, somme, maximum, minimum. Indispensable pour "
            "compter les jours de canicule ou de gel."
        ),
        frequency="quotidien",
        start_year=1940,
        resolution="0,25° x 0,25° (≈ 25 km)",
        doc_url=DOC_DAILY,
        licence="CC BY 4.0",
        variables=(T2M, PRCP, MSLP, CLOUD, SNOW),
        size_hint_mb=25.0,
        difficulty=2,
        notes=(
            "Le paramètre `time_zone` est essentiel : sans lui, une « journée » est "
            "calée sur UTC et non sur le temps civil français."
        ),
    ),
    "pressure_levels": Dataset(
        id="reanalysis-era5-pressure-levels-monthly-means",
        label="ERA5 — moyennes mensuelles (niveaux de pression)",
        summary=(
            "L'atmosphère à différentes altitudes, exprimée en pression "
            "(850 hPa, 500 hPa...). Permet de visualiser la circulation et le "
            "renforcement des continents en altitude."
        ),
        frequency="mensuel",
        start_year=1940,
        resolution="0,25° x 0,25°",
        doc_url=DOC_PL,
        licence="CC BY 4.0",
        variables=(GEOPOT, T850),
        size_hint_mb=20.0,
        difficulty=3,
        notes="Les températures sont en kelvins (0 K = −273,15 °C).",
    ),
    "timeseries": Dataset(
        id="reanalysis-era5-single-levels-timeseries",
        label="ERA5 — série temporelle en un point",
        summary=(
            "Le CDS extrait lui-même la série en une ville : le fichier est "
            "minuscule (quelques ko) et s'ouvre dans un tableur. Idéal pour un "
            "premier contact avec les données."
        ),
        frequency="horaire",
        start_year=1940,
        resolution="point (moyenne sur la boîte sélectionnée)",
        doc_url=DOC_TS,
        licence="CC BY 4.0",
        variables=(T2M, PRCP, MSLP, CLOUD),
        size_hint_mb=0.2,
        timeseries=True,
        notes=(
            "La boîte `area` est ici un encadré : la valeur est la moyenne "
            "spatiale de la boîte, pas la valeur du pixel central."
        ),
    ),
}

def get(dataset_key: str) -> Dataset:
    """Renvoie la description d'un jeu de données à partir de sa clé courte."""
    if dataset_key not in DATASETS:
        raise KeyError(
            f"Jeu de données inconnu : {dataset_key!r}. Disponibles : {sorted(DATASETS)}"
        )
    return DATASETS[dataset_key]


def as_options() -> list[tuple[str, str]]:
    """Liste (clé, libellé) pour les menus déroulants Streamlit."""
    return [(k, d.label) for k, d in DATASETS.items()]


def summary_table() -> list[dict[str, Any]]:
    """Tableau récapitulatif affiché dans la page « Jeux de données »."""
    rows = []
    for key, d in DATASETS.items():
        rows.append(
            {
                "Clé": key,
                "Jeu de données": d.label,
                "Identifiant CDS": d.id,
                "Fréquence": d.frequency,
                "Début": d.start_year,
                "Résolution": d.resolution,
                "Poids (Europe, ~1 an)": f"≈ {d.size_hint_mb:.0f} Mo",
                "Difficulté": "●" * d.difficulty + "○" * (3 - d.difficulty),
            }
        )
    return rows
