"""
Jeu de données simulé, pour travailler sans connexion au CDS.

**Ces données ne sont pas des observations.** Elles sont produites par un modèle
simplifié, expressément destiné à faire tourner l'application et à préparer des
séances hors connexion. Toute figure issue de ce mode porte la mention
« DONNÉES SIMULÉES » et ne doit jamais être présentée comme une donnée
Copernicus. Le passage à des données réelles se fait en un clic sur le bouton
« Données réelles », qui relance exactement la même demande auprès du CDS.

Le modèle reproduit quelques ordres de grandeur physiques reconnaissables :
diminution de la température avec la latitude, cycle saisonnal inversé entre
hémisphères, continentalité (amplitude plus forte loin des océans), effet
thermique du Gulf Stream, zone de convergence intertropicale.

**Ordre de grandeur attendu.** Sur un échantillon de villes européennes et
tropicales, l'erreur quadratique moyenne du modèle atteint environ 4 °C sur les
températures de janvier et de juillet : les moyennes annuelles et les hivers
sont proches des valeurs observées, les étés sont généralement sous-estimés de
quelques degrés. Ce niveau de précision suffit pour préparer une séance ou
vérifier l'interface ; il ne permet en aucun cas de produire un résultat
opposable à une publication. Toute valeur issue de ce mode doit donc être
convertie en données CDS avant d'être communiquée.

**Limite connue sur les statistiques journalières.** Le jeu simulé produit bien
une série quotidienne, mais l'amplitude de ses extrêmes n'est pas calibrée avec
la même rigueur que les moyennes mensuelles. Les activités qui comptent des
journées de chaleur (activité « canicule ») donnent donc des chiffres peu
fiables hors ligne : utilisez les données CDS pour cette activité, ou
présentez-la comme une mise en situation sans valeur chiffrée.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

DEMO_BANNER = "DONNÉES SIMULÉES — ne pas utiliser comme source"

#: Semences fixes : deux exécutions donnent exactement la même simulation, ce qui
#: permet de citer un résultat d'un cours à l'autre.
SEED = 20240617


def synthetic_temperature(
    years: tuple[int, int] = (1970, 2024),
    area: tuple[float, float, float, float] | None = None,
    *,
    seed: int = SEED,
    daily: bool = False,
) -> xr.DataArray:
    """
    Température de l'air à 2 m simulée, en °C, sur la grille demandée.

    Construction, du Nord au Sud :
      * gradient thermique moyen de 0,55 °C par degré de latitude ;
      * amplitude saisonnière croissante avec la latitude, réduite en
        continentalité oceanicité (proximité de l'océan) ;
      * réchauffement de fond de +0,9 °C depuis 1970, avec un bruit
        interannuel de type « anneau rouge » ;
      * réchauffement de plusieurs degrés en Europe occidentale (Gulf Stream).
    """
    rng = np.random.default_rng(seed)
    y0, y1 = years
    north, west, south, east = area or (90.0, -180.0, -90.0, 180.0)

    lat = np.arange(north, south - 1e-9, -0.25)
    lon = np.arange(west, east - 1e-9, 0.25)
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    # En mode journalier, on génère un pas de temps par jour : c'est la seule
    # façon de produire de vraies journées de chaleur. Sinon, un pas par mois.
    times = (
        pd.date_range(f"{y0}-01-01", f"{y1}-12-31", freq="D")
        if daily
        else pd.date_range(f"{y0}-01-01", f"{y1}-12-01", freq="MS")
    )

    # --- Composante de base : moyenne annuelle ajustée sur des normales réelles
    #     par moindres carrés (T = a + b|φ| + c φ²), sur une quinzaine de villes
    #     réparties entre l'équateur et les pôles.
    annual = 26.45 - 0.2052 * np.abs(LA) - 0.00234 * LA**2

    # --- Océanité : proximité de l'Atlantique (côté ouest du domaine), qui
    #     lisse le cycle saisonnier. La largeur du lobe est calée pour que
    #     l'ensemble du bassin soit concerné.
    atlantic = np.exp(-((LO + 5.0) ** 2) / 70.0)
    pacific = (
        np.exp(-((LO - 180.0) ** 2) / 900.0) + np.exp(-((LO + 170.0) ** 2) / 900.0)
    )
    indian = np.exp(-((LO - 75.0) ** 2) / 500.0) + np.exp(-((LO + 60.0) ** 2) / 500.0)
    oceanity = np.clip(np.maximum(np.maximum(atlantic, pacific), indian), 0.0, 1.0)

    # --- Réchauffement hivernal de l'Europe occidentale (effet Gulf Stream).
    #     L'anomalie est forte en hiver et quasi absente en été.
    gulf = 4.0 * np.exp(-((LO - 8.0) ** 2) / 260.0 - ((LA - 52.0) ** 2) / 420.0)

    # --- Demi-amplitude saisonnière : croissante avec la latitude et avec
    #     l'éloignement de l'océan (inertie thermique des terres).
    lat_abs = np.abs(LA)
    amplitude = (
        -5.14
        + 0.4779 * lat_abs
        - 0.00394 * lat_abs**2
        + 18.97 * oceanity
        - 0.4964 * lat_abs * oceanity
    )
    amplitude = np.clip(amplitude, 0.3, 35.0)

    month = times.month.values.astype("float64")
    # Le maximum de saison est en juillet au nord, en janvier au sud.
    peak_north = np.cos(2 * np.pi * (month - 7.0) / 12.0)
    peak_south = np.cos(2 * np.pi * (month - 1.0) / 12.0)
    # Diffusion de la phase sur la grille (1, n_lat, 1) pour broadcaster ensuite.
    phase = np.where(LA > 0, peak_north[:, None, None], peak_south[:, None, None])
    # L'effet du Gulf Stream ne se manifeste qu'en hiver (phase négative).
    seasonal = amplitude[None, :, :] * phase - gulf[None, :, :] * np.clip(-phase, 0.0, 1.0)

    # --- Tendance de fond et variabilité interannuelle
    years_arr = times.year.values.astype("float64")
    warming = 0.9 * (years_arr - y0) / max(y1 - y0, 1)
    # Bruit lissé : moyenne de trois tirages, ce qui ressemble à un « anneau rouge ».
    interannual = np.mean(
        [rng.normal(0.0, 0.45, size=(len(times), 1, 1)) for _ in range(3)], axis=0
    )

    values = annual[None, :, :] + seasonal + warming[:, None, None] + interannual

    if daily:
        # Les moyennes mensuelles ne permettent pas de compter des journées de
        # chaleur. On superpose une variabilité journalière plausible : un cycle
        # annuel fin, une amplitude diurne, un passage de fronts tous les dix
        # jours environ, et quelques pics de chaleur. Le facteur d'échelle est
        # ajusté pour qu'un été continental simulé dépasse 35 °C quelques
        # jours par an, comme en réalité.
        doy = times.dayofyear.values.astype("float64")[:, None, None]
        annual_cycle = np.sin(2 * np.pi * (doy - 200.0) / 365.25)
        continental = np.broadcast_to(1.0 - oceanity, (1,) + oceanity.shape)
        # Amplitude diurne : faible sur les côtes, forte à l'intérieur.
        diurnal = 4.0 * annual_cycle * (0.5 + 0.9 * continental)
        # Fronts froids : période d'une dizaine de jours.
        fronts = 5.0 * np.sin(2 * np.pi * doy / 9.5) * continental
        # Pics de chaleur : quelques journées nettement au-dessus. Le facteur
        # continental accentue les extrêmes loin des côtes.
        heat = (rng.gamma(3.0, 3.0, size=values.shape) - 6.0) * continental
        values = values + diurnal + fronts + heat

    return xr.DataArray(
        values,
        dims=("time", "latitude", "longitude"),
        coords={"time": times, "latitude": lat, "longitude": lon},
        name="2m_temperature",
        attrs={
            "units": "degC",
            "long_name": "SIMULATION — température de l'air à 2 m",
            "comment": DEMO_BANNER,
        },
    )


def synthetic_precipitation(
    years: tuple[int, int] = (1970, 2024),
    area: tuple[float, float, float, float] | None = None,
    *,
    seed: int = SEED + 1,
) -> xr.DataArray:
    """
    Précipitations mensuelles simulées, en mm.

    Trois maxima de pluie reproduits : la zone de convergence intertropicale
    (ceinture équatoriale), la mousson d'Asie et l'été méditerranéen plus sec.
    """
    rng = np.random.default_rng(seed)
    y0, y1 = years
    north, west, south, east = area or (90.0, -180.0, -90.0, 180.0)

    lat = np.arange(north, south - 1e-9, -0.25)
    lon = np.arange(west, east - 1e-9, 0.25)
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    times = pd.date_range(f"{y0}-01-01", f"{y1}-12-01", freq="MS")

    # Climat de base : maximum équatorial, décroissance vers les subtropiques secs.
    itcz = 95.0 * np.exp(-(LA**2) / 160.0)
    subtropical_dry = 1.0 - 0.55 * np.exp(-(((np.abs(LA) - 25.0) ** 2)) / 200.0)
    base = (18.0 + itcz) * np.maximum(subtropical_dry, 0.25)

    # Mousson d'Asie du Sud et de l'Est : été humide, hiver sec.
    monsoon = 55.0 * np.exp(
        -(((LA - 22.0) ** 2)) / 400.0 - (((LO - 88.0) ** 2)) / 2600.0
    )
    # Saison des pluies tropicale (Afrique de l'Ouest, Amazonie).
    tropical_rain = 60.0 * np.exp(
        -(((LA - 6.0) ** 2)) / 120.0
    ) * np.exp(-(((LO - (-15.0 if west < 0 else 0.0)) ** 2)) / 2500.0)

    month = times.month.values.astype("float64")
    summer = np.cos(2 * np.pi * (month - 7.0) / 12.0)  # +1 en juillet

    monthly = (
        base[None, :, :]
        + monsoon[None, :, :] * (0.5 + 0.5 * summer)[:, None, None]
        + tropical_rain[None, :, :] * (0.5 - 0.5 * summer)[:, None, None]
    )
    # Bruit mensuel : les précipitations sont très variables d'un mois à l'autre.
    noise = 1.0 + 0.35 * rng.normal(0.0, 1.0, size=monthly.shape)
    values = np.clip(monthly * noise, 0.0, None)

    return xr.DataArray(
        values,
        dims=("time", "latitude", "longitude"),
        coords={"time": times, "latitude": lat, "longitude": lon},
        name="total_precipitation",
        attrs={
            "units": "mm",
            "long_name": "SIMULATION — précipitations mensuelles totales",
            "comment": DEMO_BANNER,
        },
    )


def synthetic_pressure(
    years: tuple[int, int] = (1970, 2024),
    area: tuple[float, float, float, float] | None = None,
    *,
    seed: int = SEED + 2,
) -> xr.DataArray:
    """Pression au niveau de la mer simulée, en hPa, avec des ondulations synoptiques."""
    rng = np.random.default_rng(seed)
    y0, y1 = years
    north, west, south, east = area or (90.0, -180.0, -90.0, 180.0)

    lat = np.arange(north, south - 1e-9, -0.25)
    lon = np.arange(west, east - 1e-9, 0.25)
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    times = pd.date_range(f"{y0}-01-01", f"{y1}-12-01", freq="MS")

    # 1013 hPa de référence, avec une alternance de dépressions et d'anticyclones
    # de plusieurs milliers de kilomètres d'extension, plus un gradient de pression vers les pôles.
    wave = 9.0 * np.sin(2 * np.pi * (LO / 35.0 + 0.3 * np.sin(2 * np.pi * LA / 60.0)))
    lat_gradient = -1.1 * (np.abs(LA) - 35.0)
    drift = 1.2 * (times.year.values - y0) / max(y1 - y0, 1)

    values = (
        1013.0 + wave[None, :, :] + lat_gradient[None, :, :]
        + drift[:, None, None]
        + 2.5 * rng.normal(0.0, 1.0, size=(len(times), 1, 1))
    )
    return xr.DataArray(
        values,
        dims=("time", "latitude", "longitude"),
        coords={"time": times, "latitude": lat, "longitude": lon},
        name="mean_sea_level_pressure",
        attrs={
            "units": "hPa",
            "long_name": "SIMULATION — pression moyenne au niveau de la mer",
            "comment": DEMO_BANNER,
        },
    )


def point_timeseries(
    da: xr.DataArray, lat: float, lon: float, *, name: str = "valeur"
) -> pd.Series:
    """Série mensuelle simulée en un point, par cellule la plus proche."""
    from . import analysis

    return analysis.point_series(da, lat, lon).rename(name)


def demo_dataset(variables: tuple[str, ...] = ("2m_temperature", "total_precipitation")):
    """
    Jeu de démonstration complet, couvrant l'Europe, prêt à explorer.

    Sert à valider l'interface et à préparer une séance lorsque le réseau ou la
    clé CDS ne sont pas disponibles.
    """
    area = (72.0, -12.0, 33.0, 25.0)
    builders = {
        "2m_temperature": synthetic_temperature,
        "total_precipitation": synthetic_precipitation,
        "mean_sea_level_pressure": synthetic_pressure,
    }
    data = {}
    for name in variables:
        builder = builders.get(name)
        if builder is not None:
            data[name] = builder(area=area)
    return data
