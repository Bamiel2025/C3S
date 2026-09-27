"""
Traitements climatologiques : extraction ponctuelle, moyennes pondérées, normales,
anomalies, tendances et indices.

Choix méthodologiques (ils sont expliqués aux élèves dans l'interface) :

* **Moyenne spatiale pondérée** : la moyenne arithmétique naïve d'une grille
  latitude/longitude surestime les hautes latitudes, dont les cellules sont
  plus petites. On utilise donc des poids `cos(latitude)`, ce qui revient à
  integrating over the sphere.
* **Cellule la plus proche** : la valeur lue en un point n'est pas une mesure de
  station, mais la moyenne du modèle sur une cellule de 0,25° (environ 25 km à
  l'équateur, 20 km en France). L'incertitude de position est donc de l'ordre de
  0,125°, soit environ 14 km.
* **Normale** : moyenne calculée sur une période de 30 ans (1991-2020 pour
  l'OMM). Toute anomalie est exprimée par rapport à cette normale.
* **Tendance** : régression linéaire des moindres carrés. L'autocorrélation des
  séries annuelles réduit l'efficacité de l'estimation : la significativité n'est
  donc jamaisbee affirmée sans prudence.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MONTH_LABELS = [
    "Janv.", "Févr.", "Mars", "Avril", "Mai", "Juin",
    "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc.",
]
MONTH_LABELS_LONG = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

#: Conversion kelvins -> degrés Celsius.
KELVIN_OFFSET = 273.15


def kelvin_to_celsius(values):
    """Convertit des kelvins en degrés Celsius (tableau, série ou DataArray)."""
    return values - KELVIN_OFFSET



# --------------------------------------------------------------------------- #
# Extraction spatiale
# --------------------------------------------------------------------------- #


def nearest_index(coord: np.ndarray, value: float) -> int:
    """Index du point de grille le plus proche de `value`."""
    return int(np.abs(np.asarray(coord) - value).argmin())


def point_series(
    da,
    lat: float,
    lon: float,
    *,
    nearest: bool = True,
) -> pd.Series:
    """
    Extrait la série temporelle en un point.

    `nearest=True` renvoie la valeur de la cellule la plus proche (comportement
    d'ERA5, le plus utile en classe). `nearest=False` interpole bilinéairement,
    ce qui lisse et n'est pas recommandé pour les extrêmes.
    """
    lat_c = da["latitude"].values
    lon_c = da["longitude"].values
    if nearest:
        return pd.Series(
            da.isel(latitude=nearest_index(lat_c, lat),
                    longitude=nearest_index(lon_c, lon)).values,
            index=pd.to_datetime(da["time"].values),
        )
    point = da.interp(latitude=lat, longitude=lon)
    return pd.Series(point.values, index=pd.to_datetime(da["time"].values))


def plain_series(da) -> pd.Series:
    """
    Convertit un tableau de données sans dimension spatiale en série pandas.

    Les séries déjà téléchargées pour une ville n'ont qu'une dimension temporelle :
    il n'y a donc pas de point à extraire, et la série est reprise telle quelle.
    """
    values = da.squeeze(drop=True).values
    return pd.Series(values, index=pd.to_datetime(da["time"].values))


def box_series(da, lat: float, lon: float, half_size_deg: float = 0.25) -> pd.Series:
    """
    Moyenne sur une petite boîte autour d'un point.

    Se rapproche davantage d'une valeur de station, car elle lisse le bruit de
    maille. Le rayon par défaut (0,25°, soit 25 km) correspond à la taille d'une
    station et de son environnement.
    """
    lat_c = da["latitude"].values
    lon_c = da["longitude"].values
    sub = da.sel(
        latitude=slice(
            max(float(lat_c.min()), lat - half_size_deg),
            min(float(lat_c.max()), lat + half_size_deg),
        ),
        longitude=slice(
            _wrap_lon(lon - half_size_deg, lon_c.min()),
            _wrap_lon(lon + half_size_deg, lon_c.max()),
        ),
    )
    if sub.sizes.get("latitude", 0) == 0 or sub.sizes.get("longitude", 0) == 0:
        return point_series(da, lat, lon)
    return sub.mean(dim=["latitude", "longitude"]).to_series()


def _wrap_lon(lon: float, reference_min: float) -> float:
    """Gère le passage de 180° à −180° sans casser les tranches."""
    if lon > 180.0:
        lon -= 360.0
    if lon < -180.0:
        lon += 360.0
    return lon



# --------------------------------------------------------------------------- #
# Moyennes spatiales
# --------------------------------------------------------------------------- #


def area_weights(lat: np.ndarray) -> np.ndarray:
    """
    Poids d'aire de chaque ligne de latitude, `cos(latitude)`.

    Intégrer un champ sur la sphère avec ces poids revient à une moyenne
    pondérée par la surface réelle de chaque bande. Sans eux, la moyenne
    arithmétique surestime systématiquement les régions polaires.
    """
    return np.cos(np.deg2rad(np.asarray(lat, dtype="float64")))


def area_weighted_mean(da) -> float:
    """Moyenne spatiale d'un champ 2D pondérée par le cosinus de la latitude."""
    weights = area_weights(da["latitude"].values)
    arr = da.values.astype("float64")
    mask = np.isfinite(arr)
    if not mask.any():
        return float("nan")
    w = np.broadcast_to(weights[:, None], arr.shape)
    return float(np.nansum(np.where(mask, arr, 0.0) * w) / np.nansum(np.where(mask, w, 0.0)))


def area_weighted_series(da) -> pd.Series:
    """Moyenne spatiale pondérée, conservant la dimension temporelle."""
    weights = area_weights(da["latitude"].values)
    shape = [1] * (da.ndim - 2) + [len(weights), 1]
    w = weights.reshape(shape)
    arr = da.transpose(..., "latitude", "longitude").values.astype("float64")
    mask = np.isfinite(arr)
    num = np.nansum(np.where(mask, arr, 0.0) * w, axis=(-2, -1))
    den = np.nansum(np.where(mask, w, 0.0), axis=(-2, -1))
    out = np.divide(num, den, out=np.full_like(num, np.nan), where=den > 0)
    return pd.Series(out, index=pd.to_datetime(da["time"].values))


def apply_land_mask(da, land_mask) -> object:
    """Restringit un champ à la partie terrestre à l'aide d'un masque booléen."""
    return da.where(land_mask)


# --------------------------------------------------------------------------- #
# Normales, anomalies, tendances
# --------------------------------------------------------------------------- #


def monthly_climatology(series: pd.Series, reference: tuple[int, int]) -> pd.Series:
    """
    Climatologie mensuelle : moyenne de chaque mois sur la période de référence.

    Renvoie une série de longueur 12, replacée sur une année « type » 2001 afin
    de tracer un diagramme ombrothermique.
    """
    ref = series.loc[f"{reference[0]}-01-01": f"{reference[1]}-12-31"]
    if ref.empty:
        return pd.Series(dtype="float64")
    climat = ref.groupby(ref.index.month).mean()
    idx = pd.date_range("2001-01-01", periods=12, freq="MS")
    return pd.Series(climat.values, index=idx)


def annual_mean(series: pd.Series, complete_years_only: bool = True) -> pd.Series:
    """
    Moyenne annuelle d'une série mensuelle.

    Une année contenant moins de 12 mois est exclue : une « moyenne 2025 »
    calculée sur trois mois n'est pas comparable aux autres.
    """
    if series.empty:
        return series
    groups = series.groupby(series.index.year)
    annual = groups.mean()
    if complete_years_only:
        counts = groups.count()
        annual = annual[counts == 12]
    return annual


def anomalies(series: pd.Series, reference: tuple[int, int]) -> pd.Series:
    """
    Écart à la normale : `valeur − moyenne de la période de référence`.

    C'est la grandeur qui rend comparables deux périodes, deux lieux ou deux
    scénarios. Une anomalie de +2 °C ne signifie pas qu'il fait 2 °C de plus
    qu'avant, mais que la période est 2 °C plus chaude que sa propre normale.
    """
    ref = series.loc[f"{reference[0]}-01-01": f"{reference[1]}-12-31"]
    if ref.empty:
        return series - series.mean()
    return series - ref.mean()


def anomaly_relative_to_climatology(
    series: pd.Series, climatology: pd.Series
) -> pd.Series:
    """Anomalie mensuelle par rapport à la climatologie du mois correspondant."""
    if series.empty or climatology.empty:
        return series
    base = pd.Series(climatology.values, index=climatology.index.month)
    return series - series.index.month.map(base)


@dataclass
class Trend:
    """Résultat d'une régression linéaire des moindres carrés."""

    slope: float
    intercept: float
    r_squared: float
    n: int
    per_decade: float
    first: float
    last: float
    #: Écart-type des résidus : mesure grossière de la variabilité interannuelle.
    residual_std: float
    unit: str = ""

    def predict(self, x):
        return self.intercept + self.slope * np.asarray(x)

    def equation(self) -> str:
        unit = f" {self.unit}/an" if self.unit else "/an"
        return f"y = {self.slope:.4f}{unit} × x + {self.intercept:.2f}"

    def summary(self) -> str:
        return (
            f"Tendance de {self.slope * 10:+.2f} {self.unit} par décennie "
            f"sur {self.n} ans (R² = {self.r_squared:.2f})"
        )


def _numeric_years(index) -> np.ndarray:
    """
    Extrait des années numériques d'un index, qu'il soit daté (`DatetimeIndex`)
    ou déjà annuel (`Int64Index`, cas des moyennes annuelles).
    """
    if hasattr(index, "year"):
        return index.year.values.astype("float64")
    return np.asarray(index, dtype="float64")


def linear_trend(series: pd.Series, unit: str = "") -> Trend:
    """
    Tendance linéaire d'une série temporelle (x = année).

    Les moindres carrés supposent des résidus indépendants, ce qui n'est pas
    vérifié ici : c'est pourquoi R² est rapporté comme un indicateur de qualité
    d'ajustement, et non comme une probabilité.
    """
    clean = series.dropna()
    if len(clean) < 3:
        return Trend(0.0, 0.0, 0.0, len(clean), 0.0, 0.0, 0.0, 0.0, unit)
    x = _numeric_years(clean.index)
    y = clean.values.astype("float64")
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    residuals = y - pred
    return Trend(
        slope=float(slope),
        intercept=float(intercept),
        r_squared=r2,
        n=len(clean),
        per_decade=float(slope * 10),
        first=float(y[0]),
        last=float(y[-1]),
        residual_std=float(np.std(residuals, ddof=2)) if len(clean) > 2 else 0.0,
        unit=unit,
    )

# --------------------------------------------------------------------------- #
# Indices climatiques
#
# Ces indices reprennent les définitions standards (ETCCDI / WMO), ce qui rend
# les résultats comparables à ceux publiés par Météo-France ou le GIEC.
# --------------------------------------------------------------------------- #


@dataclass
class ClimateIndex:
    """Un indice climatique calculé et affichable dans un tableau."""

    name: str
    value: float
    unit: str
    definition: str
    interpretation: str = ""


def thermal_amplitude(temp_climatology: pd.Series) -> float:
    """
    Amplitude thermique annuelle : mois le plus chaud moins mois le plus froid.

    C'est l'indicateur qui distingue un climat océanique (petite amplitude) d'un
    climat continental (grande amplitude). Elle dépend surtout de la distance à
    la mer et du relief, pas seulement de la latitude.
    """
    if temp_climatology.empty:
        return float("nan")
    return float(temp_climatology.max() - temp_climatology.min())


def growing_degree_days(
    daily_max: pd.Series, daily_min: pd.Series, base: float = 10.0
) -> pd.Series:
    """
    Degrés-jours de croissance (somme thermique).

    Pour chaque jour, on retient la moyenne entre maximum et minimum, retranchée
    du seuil de 10 °C, et bornée entre 0 et 30 °C. C'est la méthode utilisée par
    Météo-France pour dater la floraison et la maturité des céréales.
    """
    mean = (daily_max + daily_min) / 2.0
    contribution = (mean - base).clip(lower=0.0, upper=30.0)
    return contribution.groupby(contribution.index.year).sum()


def count_days_above(daily: pd.Series, threshold: float) -> pd.Series:
    """Nombre de jours par an où la valeur dépasse un seuil."""
    above = (daily > threshold).astype(float)
    return above.groupby(above.index.year).sum()


def count_days_below(daily: pd.Series, threshold: float) -> pd.Series:
    """Nombre de jours par an où la valeur reste sous un seuil."""
    below = (daily < threshold).astype(float)
    return below.groupby(below.index.year).sum()


def heatwave_days(
    tmax: pd.Series, tmin: pd.Series, *, tmax_thresh: float = 35.0, tmin_thresh: float = 20.0
) -> pd.Series:
    """
    Jours de « chaleur » selon les seuils usuels français : maximum ≥ 35 °C et
    minimum nocturne ≥ 20 °C. Ce second critère distingue une vraie nuit tropicale
    d'un simple pic de chaleur l'après-midi.
    """
    hot = (tmax >= tmax_thresh) & (tmin >= tmin_thresh)
    return hot.astype(float).groupby(hot.index.year).sum()


def describe_temperature(
    temp_monthly: pd.Series,
    precip_monthly: pd.Series | None = None,
    *,
    reference: tuple[int, int] = (1991, 2020),
) -> list[ClimateIndex]:
    """
    Calcule un tableau d'indices climatiques à partir de deux séries mensuelles.
    """
    if temp_monthly.empty:
        return []

    t_clim = monthly_climatology(temp_monthly, reference)
    indices: list[ClimateIndex] = []

    if not t_clim.empty:
        indices.append(
            ClimateIndex(
                "Température moyenne annuelle",
                float(t_clim.mean()),
                "°C",
                "Moyenne des 12 moyennes mensuelles de la normale.",
                "Indicateur de rigueur ou de douceur du climat.",
            )
        )
        indices.append(
            ClimateIndex(
                "Mois le plus chaud",
                float(t_clim.max()),
                "°C",
                f"Valeur maximale, atteinte en {MONTH_LABELS_LONG[int(t_clim.idxmax().month) - 1]}.",
            )
        )
        indices.append(
            ClimateIndex(
                "Mois le plus froid",
                float(t_clim.min()),
                "°C",
                f"Valeur minimale, atteinte en {MONTH_LABELS_LONG[int(t_clim.idxmin().month) - 1]}.",
            )
        )
        indices.append(
            ClimateIndex(
                "Amplitude thermique annuelle",
                thermal_amplitude(t_clim),
                "°C",
                "Écart entre le mois le plus chaud et le mois le plus froid.",
                "Petite amplitude : influence de la mer. Grande amplitude : continentalité.",
            )
        )

    if precip_monthly is not None and not precip_monthly.empty:
        p_clim = monthly_climatology(precip_monthly, reference)
        if not p_clim.empty:
            indices.append(
                ClimateIndex(
                    "Cumul annuel de précipitations",
                    float(p_clim.sum()),
                    "mm",
                    "Somme des 12 cumuls mensuels de la normale.",
                    "Un cumul annuel cache souvent une forte saisonnalité : voir la répartition.",
                )
            )
            indices.append(
                ClimateIndex(
                    "Mois le plus humide",
                    float(p_clim.max()),
                    "mm",
                    f"Maximum mensuel ({MONTH_LABELS_LONG[int(p_clim.idxmax().month) - 1]}).",
                )
            )
            indices.append(
                ClimateIndex(
                    "Mois le plus sec",
                    float(p_clim.min()),
                    "mm",
                    f"Minimum mensuel ({MONTH_LABELS_LONG[int(p_clim.idxmin().month) - 1]}).",
                )
            )
            indices.append(
                ClimateIndex(
                    "Nombre de mois humide",
                    float((p_clim >= 2 * p_clim.mean()).sum()),
                    "mois",
                    "Mois dont le cumul dépasse le double de la moyenne mensuelle.",
                )
            )
            indices.append(
                ClimateIndex(
                    "Nombre de mois sec",
                    float((p_clim <= p_clim.mean() / 2).sum()),
                    "mois",
                    "Mois dont le cumul est inférieur à la moitié de la moyenne mensuelle.",
                    "Sec en été : typique des climats méditerranéens.",
                )
            )
    return indices


def daily_range(tmax: pd.Series, tmin: pd.Series) -> pd.Series:
    """
    Écart diurne (amplitude journalière).

    Un écart faible signifie un ciel couvert la nuit : les nuages agissent comme
    une couverture isolante et empêchent le refroidissement radiatif.
    """
    return tmax - tmin


def count_nights_above(nights: pd.Series, threshold: float = 20.0) -> pd.Series:
    """
    Nombre de « nuits tropicales » par an : minimum nocturne ≥ seuil.

    Cette grandeur est très utilisée en tourisme et en santé publique.
    """
    return (nights >= threshold).astype(float).groupby(nights.index.year).sum()

