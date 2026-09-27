"""
Couche d'accès aux données : un point d'entrée unique, réel ou simulé.

C'est ce module que l'interface appelle. Il choisit automatiquement entre :

* **les données réelles** du CDS, si une clé est configurée ;
* **les données simulées**, sinon, afin que l'application reste utilisable.

Le résultat a toujours la même forme : un `xarray.DataArray` portant les
coordonnées `time`, `latitude`, `longitude`, et une attribution qui indique sans
ambiguïté d'où viennent les chiffres.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
import xarray as xr

from . import analysis, catalog, cds_client, config, demo, places

#: Facteur de conversion vers les unités affichées, par variable.
UNIT_CONVERSION = {
    "2m_temperature": ("degC", 1.0, "°C"),
    "maximum_2m_temperature": ("degC", 1.0, "°C"),
    "minimum_2m_temperature": ("degC", 1.0, "°C"),
    "total_precipitation": ("mm", 1.0, "mm"),
    "mean_sea_level_pressure": ("hPa", 1.0, "hPa"),
    "surface_pressure": ("hPa", 1.0, "hPa"),
    "total_cloud_cover": ("%", 1.0, "%"),
    "snow_depth": ("m", 1.0, "m"),
    "10m_u_component_of_wind": ("m s-1", 1.0, "m/s"),
    "10m_v_component_of_wind": ("m s-1", 1.0, "m/s"),
}

#: Le CDS livre la température en kelvins : conversion en degrés Celsius.
KELVIN_VARIABLES = {
    "2m_temperature",
    "maximum_2m_temperature",
    "minimum_2m_temperature",
    "2m_dewpoint_temperature",
    "temperature",
}


@dataclass
class FetchResult:
    """Résultat d'une récupération de données, avec sa provenance."""

    data: xr.DataArray
    unit: str
    source: str  # "CDS (ERA5)" ou "simulation"
    simulated: bool
    request: dict[str, Any]
    variable: str
    period: str
    #: Nombre de cellules de la grille, utile pour juger du poids du fichier.
    n_cells: int = 0

    def series_at(self, lat: float, lon: float, *, name: str = "valeur") -> pd.Series:
        """Série temporelle en un point, par cellule la plus proche."""
        return analysis.point_series(self.data, lat, lon).rename(name)

    def box_mean_at(self, lat: float, lon: float, radius: float = 0.25) -> pd.Series:
        """Série temporelle moyennée sur une petite boîte autour du point."""
        return analysis.box_series(self.data, lat, lon, radius)

    def area_mean(self):
        """Moyenne spatiale pondérée par le cosinus de la latitude."""
        return analysis.area_weighted_series(self.data)

    def field(self, *, month: int | None = None, season: str | None = None):
        """
        Champ 2D prêt à cartographier.

        `month` (1-12) sélectionne un mois ; `season` accepte "annee", "djf",
        "mam", "jja", "son". Sans précision, toute la période est moyennée.
        """
        if month is not None:
            return self.data.sel(time=self.data.time.dt.month == month).mean(dim="time")
        if season is not None:
            groups = {"djf": [12, 1, 2], "mam": [3, 4, 5], "jja": [6, 7, 8], "son": [9, 10, 11]}
            months = groups.get(season.lower(), groups["djf"])
            mask = self.data.time.dt.month.isin(months)
            return self.data.sel(time=mask).mean(dim="time")
        return self.data.mean(dim="time")


def _to_display_units(da: xr.DataArray, variable: str) -> tuple[xr.DataArray, str]:
    """Convertit une variable dans son unité d'affichage (°C, mm, hPa…)."""
    unit = UNIT_CONVERSION.get(variable, ("", 1.0, ""))[2]
    out = da
    if variable in KELVIN_VARIABLES:
        out = out - 273.15
        unit = "°C"
    return out, unit or getattr(da, "units", "")


# --------------------------------------------------------------------------- #
# Construction des requêtes CDS
# --------------------------------------------------------------------------- #


def build_monthly_request(
    variable: str,
    years: list[int],
    months: list[str],
    area: list[float],
    *,
    time: str = "00:00",
    product_type: str = "monthly_averaged_reanalysis",
) -> dict[str, Any]:
    """
    Requête pour les moyennes mensuelles ERA5.

    Le CDS attend les années et les mois sous forme de chaînes, et `area` dans
    l'ordre `[Nord, Ouest, Sud, Est]`.
    """
    return {
        "product_type": product_type,
        "variable": [variable],
        "year": [str(y) for y in years],
        "month": [f"{m:02d}" for m in months],
        "time": time,
        "area": area,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def build_daily_request(
    variable: str,
    years: list[int],
    months: list[str],
    days: list[str],
    area: list[float],
    *,
    daily_statistic: str = "daily_mean",
    time_zone: str = "utc+01:00",
    frequency: str = "1_hourly",
) -> dict[str, Any]:
    """
    Requête pour les statistiques journalières ERA5.

    `time_zone` est calé sur l'heure d'hiver française (UTC+1) : sans ce
    réglage, une journée commence à 00 h UTC et non à minuit local, ce qui décale
    les totaux de précipitations et les maximums de température.
    """
    return {
        "product_type": "reanalysis",
        "variable": [variable],
        "year": [str(y) for y in years],
        "month": [f"{m:02d}" for m in months],
        "day": [f"{d:02d}" for d in days],
        "daily_statistic": daily_statistic,
        "time_zone": time_zone,
        "frequency": frequency,
        "area": area,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def _find_variable(ds: xr.Dataset, variable: str) -> xr.DataArray:
    """
    Retrouve le champ demandé dans le fichier téléchargé.

    Le CDS nomme parfois la variable `valid_time` au lieu de `time`, et peut
    ajouter des dimensions (par exemple `number` pour un membre d'ensemble).
    """
    if variable in ds:
        da = ds[variable]
    else:
        candidates = [
            v
            for v in ds.data_vars
            if variable.split("_")[0] in v or v.lower().startswith("var")
        ]
        if not candidates:
            raise KeyError(
                f"Variable « {variable} » absente du fichier. "
                f"Variables disponibles : {list(ds.data_vars)}"
            )
        da = ds[candidates[0]]

    # On se dégage des dimensions inutiles (membre d'ensemble, niveau).
    for dim in ("number", "expver", "depth", "level"):
        if dim in da.dims and da.sizes[dim] == 1:
            da = da.squeeze(dim, drop=True)
    if "valid_time" in da.dims and "time" not in da.dims:
        da = da.rename({"valid_time": "time"})
    return da


# --------------------------------------------------------------------------- #
# Point d'entrée principal
# --------------------------------------------------------------------------- #


def fetch(
    *,
    cfg: config.CDSConfig | None = None,
    dataset_key: str = "monthly_means",
    variable: str = "2m_temperature",
    years: tuple[int, int] = (1991, 2020),
    area: tuple[float, float, float, float] = (72.0, -12.0, 33.0, 25.0),
    months: list[int] | None = None,
    days: list[int] | None = None,
    daily_statistic: str = "daily_mean",
    force_simulated: bool = False,
    progress: Callable[[float, str], None] | None = None,
    use_cache: bool = True,
) -> FetchResult:
    """
    Récupère un champ ERA5, ou sa version simulée si aucune clé n'est disponible.

    Paramètres
    ----------
    years : période demandée, bornes comprises.
    area  : encadré `(Nord, Ouest, Sud, Est)` en degrés décimaux.
    force_simulated : impose le mode hors-ligne, même si une clé est configurée.
    """
    dataset = catalog.get(dataset_key)
    y0, y1 = max(years[0], dataset.start_year), min(years[1], config.LAST_COMPLETE_YEAR)
    if y0 > y1:
        raise ValueError(
            f"Période vide : {years[0]}-{years[1]} est antérieure aux données "
            f"disponibles (à partir de {dataset.start_year})."
        )
    month_list = months or list(range(1, 13))
    area_list = list(area)
    period = f"{y0}-{y1}"

    cfg = cfg or config.resolve_cds_config()
    use_real = cfg.is_configured and not force_simulated

    if not use_real:
        return _simulated(
            variable, (y0, y1), area, month_list,
            progress=progress, dataset_key=dataset_key,
        )

    if dataset_key == "daily_stats":
        request = build_daily_request(
            variable, list(range(y0, y1 + 1)), month_list,
            days or list(range(1, 32)), area_list, daily_statistic=daily_statistic,
        )
    elif dataset_key == "pressure_levels":
        request = build_monthly_request(variable, list(range(y0, y1 + 1)), month_list, area_list)
    else:
        request = build_monthly_request(variable, list(range(y0, y1 + 1)), month_list, area_list)

    if progress:
        progress(
            0.02,
            f"Requête {variable} · {period} · {places.area_label(area)} "
            f"(poids estimé ≈ {dataset.size_hint_mb:.0f} Mo pour l'Europe).",
        )

    path = cds_client.retrieve(
        cfg, dataset.id, request, progress=progress, use_cache=use_cache
    )
    ds = cds_client.open_dataset(path)
    da = _find_variable(ds, variable)
    da, unit = _to_display_units(da, variable)
    da = da.transpose("time", "latitude", "longitude")

    if progress:
        progress(1.0, f"Données ERA5 chargées ({da.sizes['time']} pas de temps).")

    return FetchResult(
        data=da,
        unit=unit,
        source="CDS (ERA5)",
        simulated=False,
        request=request,
        variable=variable,
        period=period,
        n_cells=int(da.sizes["latitude"] * da.sizes["longitude"]),
    )


def _simulated(
    variable: str,
    years: tuple[int, int],
    area: tuple[float, float, float, float],
    months: list[int],
    *,
    progress: Callable[[float, str], None] | None = None,
    dataset_key: str = "monthly_means",
) -> FetchResult:
    """Construit la version simulée du champ demandé."""
    if progress:
        progress(0.3, "Génération du jeu de données simulé (mode hors-ligne)…")

    builders = {
        "2m_temperature": (demo.synthetic_temperature, "°C"),
        "total_precipitation": (demo.synthetic_precipitation, "mm"),
        "mean_sea_level_pressure": (demo.synthetic_pressure, "hPa"),
        "maximum_2m_temperature": (demo.synthetic_temperature, "°C"),
        "minimum_2m_temperature": (demo.synthetic_temperature, "°C"),
    }
    builder, unit = builders.get(variable, (demo.synthetic_temperature, "°C"))
    da = builder(years=years, area=area)

    if months != list(range(1, 13)):
        da = da.sel(time=da.time.dt.month.isin(months))

    if progress:
        progress(1.0, "Jeu de données simulé prêt.")

    return FetchResult(
        data=da,
        unit=unit,
        source="simulation",
        simulated=True,
        request={"variable": variable, "area": list(area), "years": list(years)},
        variable=variable,
        period=f"{years[0]}-{years[1]}",
        n_cells=int(da.sizes["latitude"] * da.sizes["longitude"]),
    )


def fetch_many(
    variables: tuple[str, ...],
    **kwargs,
) -> dict[str, FetchResult]:
    """Récupère plusieurs variables avec une seule configuration CDS."""
    cfg = kwargs.pop("cfg", None) or config.resolve_cds_config()
    results: dict[str, FetchResult] = {}
    for i, variable in enumerate(variables):
        def sub_progress(fraction: float, message: str, i: int = i) -> None:
            if kwargs.get("progress"):
                kwargs["progress"]((i + fraction) / len(variables), message)

        results[variable] = fetch(variable=variable, cfg=cfg, progress=sub_progress, **kwargs)
    return results
