"""
Fonds de carte Natural Earth, téléchargés une seule fois puis mis en cache.

Sans ces fichiers, les cartes s'afficheraient sur un quadrillage vide. Le
téléchargement est facultatif : en cas de coupure, l'application bascule sur un
fond « grille nue » et prévient l'enseignant plutôt que d'échouer.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import requests

from . import config

NATURAL_EARTH_BASE = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson"
)

#: Fonds disponibles. `resolution` est un suffixe de fichier Natural Earth.
BASEMAPS: dict[str, dict[str, str]] = {
    "land": {
        "file": "ne_110m_land.geojson",
        "label": "Terres émergées (110m)",
        "url": f"{NATURAL_EARTH_BASE}/ne_110m_land.geojson",
    },
    "countries": {
        "file": "ne_110m_admin_0_countries.geojson",
        "label": "Frontières et pays (110m)",
        "url": f"{NATURAL_EARTH_BASE}/ne_110m_admin_0_countries.geojson",
    },
    "coastline": {
        "file": "ne_110m_coastline.geojson",
        "label": "Littoraux (110m)",
        "url": f"{NATURAL_EARTH_BASE}/ne_110m_coastline.geojson",
    },
}


class BasemapUnavailable(RuntimeError):
    """Le fond de carte n'a pas pu être obtenu et n'est pas en cache."""


def basemap_path(name: str) -> Any:
    """Chemin local du fond de carte, sans téléchargement."""
    if name not in BASEMAPS:
        raise KeyError(f"Fond de carte inconnu : {name!r}")
    return config.MAPS_DIR / BASEMAPS[name]["file"]


@lru_cache(maxsize=8)
def load_basemap(name: str = "land") -> dict:
    """
    Charge un fond de carte GeoJSON, en le téléchargeant si nécessaire.

    Le résultat est mis en cache par `functools.lru_cache`, donc le fichier
    n'est lu qu'une fois par session Streamlit.
    """
    if name not in BASEMAPS:
        raise KeyError(f"Fond de carte inconnu : {name!r}. Disponibles : {sorted(BASEMAPS)}")

    path = basemap_path(name)
    if not path.exists():
        try:
            resp = requests.get(BASEMAPS[name]["url"], timeout=60)
            resp.raise_for_status()
            path.write_bytes(resp.content)
        except Exception as exc:  # noqa: BLE001
            raise BasemapUnavailable(
                f"Fond de carte « {BASEMAPS[name]['label']} » indisponible : {exc}. "
                "Vérifier la connexion Internet ; l'affichage se fera sans fond."
            ) from exc

    return json.loads(path.read_text(encoding="utf-8"))


def prefetch(names: tuple[str, ...] = ("land", "countries", "coastline")) -> dict[str, str]:
    """
    Télécharge les fonds de carte par anticipation.

    Renvoie un état par fond : « ok », « déjà présent » ou le message d'erreur.
    """
    status: dict[str, str] = {}
    for name in names:
        try:
            existed = basemap_path(name).exists()
            load_basemap(name)
            status[name] = "déjà présent" if existed else "téléchargé"
        except BasemapUnavailable as exc:
            status[name] = f"échec : {exc}"
    return status
