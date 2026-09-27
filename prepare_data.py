"""
Pré-télécharge les données nécessaires aux activités.

Usage :
    python prepare_data.py            # tout
    python prepare_data.py villes     # seulement les séries par ville
    python prepare_data.py cartes     # seulement les champs spatiaux
    python prepare_data.py chaleur     # statistiques journalières (activité canicule)

Les fichiers produits sont versionnés dans `data/precomputed/` : l'application
les lit ensuite instantanément, sans requête au CDS, ce qui est indispensable
en classe. Chaque requête est limitée pour rester sous le plafond de coût du CDS.
"""

from __future__ import annotations

import sys
import time

import pandas as pd

# La console Windows est souvent en cp1252, incapable d'afficher les symboles
# décoratifs utilisés ci-dessous. On force l'UTF-8 pour que la progression reste
# lisible au lieu de s'interrompre.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover
    pass

from c3s_lab import config, data, places, precomputed

START_YEAR = 1940
END_YEAR = 2024

CITIES_FILE = "villes_temperature.csv"
PRECIP_FILE = "villes_precipitations.csv"

#: Plafond de coût observé pour les statistiques journalières : une ville,
#: quelques années. Au-delà, le CDS répond « cost limits exceeded ».
HEAT_YEARS = (2018, 2024)

HEAT_CITIES = ("Marseille", "Paris", "Lyon", "Brest", "Bordeaux", "Strasbourg")


def _log(message: str) -> None:
    print(message, flush=True)


def fetch_cities(cities: list[places.Place], variable: str) -> pd.DataFrame:
    """
    Télécharge une série mensuelle pour une liste de villes.

    On procède ville par ville plutôt qu'en une seule requête : chaque ville
    utilise une boîte d'environ 0,5° de côté, ce qui reste très en deçà du
    plafond de coût du CDS, et l'échec d'une ville n'invalide pas les autres.

    Chaque ville est écrite dès qu'elle arrive. En cas d'interruption, les villes
    déjà téléchargées sont conservées et le lancement suivant ne reprend que
    celles qui manquent.

    Attention : la reprise réutilise tel quel le fichier existant. Si celui-ci
    contient des valeurs simulées ou un jeu de test, elles sont conservées et
    passeront pour des données ERA5. En cas de doute, supprimez le fichier avant
    de relancer.
    """
    series: dict[str, pd.Series] = {}
    existing = precomputed.load(_file_for(variable))
    if existing is not None:
        series.update({c: existing[c].dropna() for c in existing.columns})
        _log(f"  {len(series)} ville(s) déjà préparée(s), reprises telles quelles")

    for i, place in enumerate(cities, 1):
        if place.name in series:
            _log(f"  [{i}/{len(cities)}] {place.name} — déjà disponible")
            continue
        area = (place.lat + 0.3, place.lon - 0.4, place.lat - 0.3, place.lon + 0.4)
        try:
            result = data.fetch(
                variable=variable, years=(START_YEAR, END_YEAR), area=area
            )
            series[place.name] = result.series_at(place.lat, place.lon, name=place.name)
            _log(f"  [{i}/{len(cities)}] {place.name} — {len(series[place.name])} valeurs")
            _checkpoint(series, variable)
        except Exception as exc:  # noqa: BLE001
            _log(f"  [{i}/{len(cities)}] {place.name} — ECHEC : {str(exc)[:70]}")
        time.sleep(0.4)
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series)


def _checkpoint(series: dict[str, pd.Series], variable: str) -> None:
    """Enregistre l'avancement, pour ne pas perdre une longue exécution."""
    try:
        precomputed.save(_file_for(variable), pd.DataFrame(series))
    except Exception as exc:  # noqa: BLE001
        _log(f"  (sauvegarde impossible : {str(exc)[:50]})")


def _file_for(variable: str) -> str:
    """Nom du fichier préparé associé à une variable."""
    return PRECIP_FILE if variable == "total_precipitation" else CITIES_FILE


def prepare_villes() -> None:
    """Séries mensuelles de température et de précipitations par ville."""
    cities = list(places.FRENCH_CITIES) + list(places.WORLD_CITIES)
    _log(f"\n■ Séries par ville ({len(cities)} villes)")

    _log(" — temperature…")
    temp = fetch_cities(cities, "2m_temperature")
    if not temp.empty:
        target = precomputed.save(CITIES_FILE, temp)
        _log(f"   enregistre : {target.name} ({target.stat().st_size / 1e6:.1f} Mo)")

    _log(" — precipitations…")
    precip = fetch_cities(cities, "total_precipitation")
    if not precip.empty:
        target = precomputed.save(PRECIP_FILE, precip)
        _log(f"   enregistre : {target.name} ({target.stat().st_size / 1e6:.1f} Mo)")


def prepare_champs() -> None:
    """Champ annuel de température sur la France et l'Europe."""
    _log("\n■ Champs spatiaux annuels")
    areas = {
        "France": (51.5, -5.5, 41.0, 10.0),
        "Europe": (72.0, -25.0, 33.0, 45.0),
    }
    for label, area in areas.items():
        try:
            result = data.fetch(
                variable="2m_temperature", years=(START_YEAR, END_YEAR), area=area
            )
            field = result.field().to_pandas()
            target = precomputed.save(f"champ_{label.lower()}.csv", field)
            _log(f"   {label} : {field.shape[0]} x {field.shape[1]} "
                 f"({target.stat().st_size / 1e6:.1f} Mo)")
        except Exception as exc:  # noqa: BLE001
            _log(f"   {label} — ECHEC : {str(exc)[:80]}")


def prepare_chaleur() -> None:
    """
    Statistiques journalières pour l'activité « canicule ».

    Le CDS plafonne le coût d'une requête : on limite donc à une ville à la fois,
    sur sept années, et à une boîte d'environ 0,4° de côté. Une requête plus large
    échoue avec « cost limits exceeded », ce que l'utilisateur a rencontré.
    """
    _log(f"\n■ Statistiques journalières ({HEAT_YEARS[0]}-{HEAT_YEARS[1]})")
    cities = [p for p in places.FRENCH_CITIES if p.name in HEAT_CITIES]
    frames: dict[str, dict[str, pd.Series]] = {"tmax": {}, "tmin": {}}
    for i, place in enumerate(cities, 1):
        area = (place.lat + 0.2, place.lon - 0.3, place.lat - 0.2, place.lon + 0.3)
        for key, stat in (("tmax", "daily_maximum"), ("tmin", "daily_minimum")):
            try:
                result = data.fetch(
                    dataset_key="daily_stats", variable="2m_temperature",
                    years=HEAT_YEARS, area=area, daily_statistic=stat,
                )
                frames[key][place.name] = result.series_at(
                    place.lat, place.lon, name=place.name
                )
            except Exception as exc:  # noqa: BLE001
                _log(f"  [{i}/{len(cities)}] {place.name} {key} — ECHEC : {str(exc)[:60]}")
        got = len(frames["tmax"].get(place.name, []))
        _log(f"  [{i}/{len(cities)}] {place.name} — {got} jours")
        time.sleep(0.5)

    for key, filename in (("tmax", "chaleur_tmax.csv"), ("tmin", "chaleur_tmin.csv")):
        if frames[key]:
            frame = pd.DataFrame(frames[key])
            frame = frame[[c for c in frame.columns if not frame[c].isna().all()]]
            target = precomputed.save(filename, frame)
            _log(f"   enregistre : {target.name} ({target.stat().st_size / 1e6:.1f} Mo)")


def main(argv: list[str]) -> int:
    cfg = config.resolve_cds_config()
    if not cfg.is_configured:
        _log("Aucune cle CDS : impossible de preparer les donnees reelles.")
        _log("Configurez la cle (page Connexion CDS), puis relancez.")
        return 1

    _log("=" * 62)
    _log("  Preparation des donnees — C3S Climate Lab")
    _log("=" * 62)

    tasks = argv[1:] or ["villes", "cartes", "chaleur"]
    t0 = time.perf_counter()
    if "villes" in tasks:
        prepare_villes()
    if "cartes" in tasks:
        prepare_champs()
    if "chaleur" in tasks:
        prepare_chaleur()

    _log("\n" + "=" * 62)
    _log(f"  Termine en {time.perf_counter() - t0:.0f} s")
    for row in precomputed.inventory():
        _log(f"  {row['État']:6} {row['Fichier']:38} {row['Taille']}")
    _log("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
