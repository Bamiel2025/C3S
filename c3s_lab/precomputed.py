"""
Pré-calcul des données des activités, pour un accès immédiat en classe.

Télécharger ERA5 demande plusieurs secondes à plusieurs minutes par requête. Devant
une classe, ce délai est rédhibitoire. On prépare donc une fois pour toutes un
fichier de séries par ville (`data/precomputed/villes_*.csv`) et quelques champs
spatiaux, que l'application lit ensuite instantanément.

Ces fichiers sont produits par `prepare_data.py`, versionnés dans le dépôt, et
donc disponibles dès le premier affichage — y compris en déploiement, où le
système de fichiers est en lecture seule.

Format : une colonne par ville, une ligne par pas de temps mensuel, séparateur
`;` et décimale `,` pour un affichage direct dans un tableur français.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config

#: Dossier des données préparées, versionnées dans le dépôt.
PRECOMPUTED_DIR = config.PROJECT_ROOT / "data" / "precomputed"

#: Fichiers produits, avec leur description.
FILES = {
    "villes_temperature.csv": "Température mensuelle à 2 m (°C), 1940-2024",
    "villes_precipitations.csv": "Précipitations mensuelles (mm), 1940-2024",
    "champs_annuels_temperature.csv": "Champ annuel de température (°C), Europe",
    "domaines_annuels_temperature.csv": "Champ annuel, France et Europe",
}

#: Format numérique lisible sous Excel en configuration française.
FLOAT_FORMAT = "%.2f"


def path_for(name: str) -> Path:
    """Chemin d'un fichier préparé."""
    return PRECOMPUTED_DIR / name


def is_available(name: str) -> bool:
    """Vrai si le fichier préparé existe et n'est pas vide."""
    p = path_for(name)
    return p.is_file() and p.stat().st_size > 200


def save(name: str, frame: pd.DataFrame) -> Path:
    """Enregistre un tableau de données préparées."""
    PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
    target = path_for(name)
    frame.to_csv(
        target, sep=";", float_format=FLOAT_FORMAT,
        encoding="utf-8-sig", date_format="%Y-%m-%d",
    )
    return target


def load(name: str) -> pd.DataFrame | None:
    """
    Charge un fichier préparé, ou `None` s'il est absent.

    Le premier élément sert d'index temporel (les dates des lignes) : c'est la
    disposition la plus lisible dans un tableur.
    """
    if not is_available(name):
        return None
    try:
        return pd.read_csv(path_for(name), sep=";", index_col=0, parse_dates=True)
    except Exception:  # noqa: BLE001 - fichier corrompu : on le retélécharge
        return None


def load_city_series(name: str) -> pd.Series | None:
    """
    Série d'une ville, prête à l'emploi.

    `name` est la clé du fichier (`"villes_temperature"`) ; la colonne demandée
    est le nom de la ville.
    """
    frame = load(name)
    if frame is None or city not in frame.columns:
        return None
    return frame[city].rename(city)


def inventory() -> list[dict[str, str]]:
    """État des fichiers préparés, affiché dans la page Méthode."""
    rows = []
    for name, description in FILES.items():
        p = path_for(name)
        rows.append({
            "Fichier": name,
            "Contenu": description,
            "État": "prêt" if p.is_file() and p.stat().st_size > 200 else "absent",
            "Taille": f"{p.stat().st_size / 1e3:.0f} ko" if p.is_file() else "—",
        })
    return rows


def total_size_mb() -> float:
    """Poids total des données préparées."""
    if not PRECOMPUTED_DIR.is_dir():
        return 0.0
    return sum(f.stat().st_size for f in PRECOMPUTED_DIR.glob("*.csv")) / 1e6


def coverage() -> str:
    """Résumé lisible de ce qui est disponible, pour l'interface."""
    ready = [n for n in FILES if is_available(n)]
    if not ready:
        return (
            "Aucune donnée préparée. Lancez `python prepare_data.py` pour "
            "pré-télécharger les séries des activités."
        )
    return f"{len(ready)}/{len(FILES)} jeux de données prêts — {total_size_mb():.1f} Mo"
