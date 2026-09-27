"""
Vérifie, pour une clé donnée, quelles licences de jeux de données sont
acceptées. Interroge réellement le CDS : c'est le seul moyen fiable de savoir
quels formulaires l'utilisateur doit encore ouvrir.

Usage :  python -m c3s_lab.probe_key --licences <url> <clé>
"""
from __future__ import annotations

import sys

import requests

from . import catalog, config

#: Jeu de données -> requête minimale, suffisamment légère pour un test.
PROBE_REQUESTS = {
    "monthly_means": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "request": {
            "product_type": "monthly_averaged_reanalysis",
            "variable": ["2m_temperature"],
            "year": ["2020"],
            "month": ["01"],
            "time": "00:00",
            "area": [46.0, 2.0, 45.0, 3.0],
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        "licence_url": (
            "https://cds.climate.copernicus.eu/datasets/"
            "reanalysis-era5-single-levels-monthly-means?tab=download#manage-licences"
        ),
    },
    "daily_stats": {
        "dataset": "derived-era5-single-levels-daily-statistics",
        "request": {
            "product_type": "reanalysis",
            "variable": ["2m_temperature"],
            "year": ["2020"],
            "month": ["01"],
            "day": ["01"],
            "daily_statistic": "daily_mean",
            "time_zone": "utc+00:00",
            "frequency": "1_hourly",
            "area": [46.0, 2.0, 45.0, 3.0],
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        "licence_url": (
            "https://cds.climate.copernicus.eu/datasets/"
            "derived-era5-single-levels-daily-statistics?tab=download#manage-licences"
        ),
    },
    "pressure_levels": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "request": {
            "product_type": "monthly_averaged_reanalysis",
            "variable": ["geopotential"],
            "year": ["2020"],
            "month": ["01"],
            "time": "00:00",
            "pressure_level": ["500"],
            "area": [46.0, 2.0, 45.0, 3.0],
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        "licence_url": (
            "https://cds.climate.copernicus.eu/datasets/"
            "reanalysis-era5-pressure-levels-monthly-means?tab=download#manage-licences"
        ),
    },
    "timeseries": {
        "dataset": "reanalysis-era5-single-levels-timeseries",
        "request": {
            "variable": ["2m_temperature"],
            "data_format": "csv",
            "area": [46.0, 2.0, 45.0, 3.0],
        },
        "licence_url": (
            "https://cds.climate.copernicus.eu/datasets/"
            "reanalysis-era5-single-levels-timeseries?tab=download#manage-licences"
        ),
    },
}


def check_licences(url: str, key: str) -> dict[str, str]:
    """Interroge le CDS pour chaque jeu de données et renvoie l'état."""
    import cdsapi

    client = cdsapi.Client(url=url, key=key, quiet=True)
    results: dict[str, str] = {}

    for key_name, spec in PROBE_REQUESTS.items():
        target = config.CACHE_DIR / f"_licence_{key_name}.probe"
        try:
            client.retrieve(spec["dataset"], spec["request"], str(target))
            target.unlink(missing_ok=True)
            results[key_name] = "autorisee"
        except Exception as exc:  # noqa: BLE001
            text = str(exc)
            if "licence" in text.lower():
                results[key_name] = "licence-refusee"
            elif "403" in text or "Forbidden" in text:
                results[key_name] = "refusee-403"
            elif "401" in text or "unauthor" in text.lower():
                results[key_name] = "cle-refusee"
            else:
                results[key_name] = f"autre-erreur: {text[:80]}"
    return results


def main(argv: list[str]) -> int:
    # argv[0] est le nom du module ; l'URL et la clé suivent.
    args = [a for a in argv[1:] if a != "--licences"]
    if len(args) < 2:
        print("Usage : python -m c3s_lab.licence_check <url> <clé>")
        return 2
    url, key = args[0], args[1]

    print("=" * 70)
    print("  Verification des licences CDS")
    print("=" * 70)
    results = check_licences(url, key)

    to_accept = []
    for name, state in results.items():
        dataset = catalog.get(name)
        marker = {
            "autorisee": "[OK]        ",
            "licence-refusee": "[A ACCEPTER]",
        }.get(state, "[ERREUR]    ")
        print(f"\n{marker} {dataset.label}")
        print(f"             identifiant CDS : {dataset.id}")
        print(f"             état            : {state}")
        if state == "licence-refusee":
            to_accept.append(PROBE_REQUESTS[name]["licence_url"])

    if to_accept:
        print("\n" + "-" * 70)
        print("  Pages à ouvrir pour accepter les conditions :\n")
        for link in to_accept:
            print(f"    {link}\n")
        print("  Sur chaque page, descendez jusqu'en bas du formulaire et")
        print("  cliquez sur « Accept » / « Accepter ».")
        return 1

    print("\nToutes les licences sont acceptées. L'application peut télécharger.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
