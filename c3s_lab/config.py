"""
Configuration de l'application : chemins, réglages et résolution de la clé API CDS.

La procédure d'installation de la clé est celle documentée par le CKB ECMWF
(« How to install and use CDS API on Windows ») :
https://confluence.ecmwf.int/spaces/CKB/pages/121847376/

Le CDS attend un fichier `dotfile` `.cdsapirc` dans le dossier personnel de
l'utilisateur (`%USERPROFILE%` sous Windows). Ce fichier contient deux lignes :

    url: https://cds.climate.copernicus.eu/api
    key: <VOTRE_CLE_PERSONNELLE>

Pour rester robuste, `resolve_cds_config()` accepte la clé depuis plusieurs
sources, par ordre de priorité, sans jamais l'écrire sur le disque.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Chemins
# --------------------------------------------------------------------------- #

#: Racine du projet (dossier contenant `app.py`).
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _writable_dir(candidates: list[Path]) -> tuple[Path, bool]:
    """
    Choisit le premier dossier réellement inscriptible parmi `candidates`.

    Sur un hébergeur (Streamlit Community Cloud, Vercel, Heroku…), le code du
    projet est monté en lecture seule : écrire le cache NetCDF à côté du code
    échoue, et l'application ne démarre pas du tout. On bascule alors vers un
    dossier temporaire inscriptible.
    """
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".ecriture_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate, candidate == candidates[0]
        except OSError:
            continue
    # Dernier recours : le dossier temporaire du système, toujours inscriptible.
    fallback = Path(tempfile.gettempdir()) / "c3s_lab"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, False


#: Dossier de travail : cache NetCDF, fonds de carte, exports.
#: Surchargeable par la variable d'environnement `C3S_LAB_DATA_DIR`.
DATA_DIR, DATA_DIR_IS_DEFAULT = _writable_dir(
    [
        Path(os.environ["C3S_LAB_DATA_DIR"])
        if os.environ.get("C3S_LAB_DATA_DIR")
        else PROJECT_ROOT / "data",
        Path(tempfile.gettempdir()) / "c3s_lab",
    ]
)

#: Vrai lorsque l'application tourne sur un système de fichiers en lecture seule
#: et utilise donc un cache temporaire (donc non partagé entre les sessions).
IS_READONLY_DEPLOYMENT = not DATA_DIR_IS_DEFAULT

CACHE_DIR = DATA_DIR / "cache"
MAPS_DIR = DATA_DIR / "maps"
EXPORT_DIR = DATA_DIR / "exports"

for _d in (CACHE_DIR, MAPS_DIR, EXPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Réglages généraux
# --------------------------------------------------------------------------- #

#: Période de référence Climatique normale recommandée par l'OMM.
WMO_NORMAL_PERIOD = (1991, 2020)
DEFAULT_REFERENCE_PERIOD = (1991, 2020)

#: Année « présente » considérée comme complète (évite les mois partiels).
LAST_COMPLETE_YEAR = 2024

#: URL du Climate Data Store (portail CDS actuel).
CDS_URL = "https://cds.climate.copernicus.eu/api"

#: Point d'entrée du catalogue STAC du CDS, utilisé par la page de diagnostic.
CDS_CATALOGUE_URL = "https://cds.climate.copernicus.eu/api/catalogue/v1/collections"

#: Adresse de la procédure officielle d'installation sous Windows.
CDKB_WINDOWS_URL = (
    "https://confluence.ecmwf.int/spaces/CKB/pages/121847376/"
    "How+to+install+and+use+CDS+API+on+Windows"
)

#: Page où l'on récupère le jeton d'accès personnel (section
#: « Set up the CDS API personal access token », connecté au CDS).
CDKB_TOKEN_URL = "https://cds.climate.copernicus.eu/user"

#: Citation et DOI d'ERA5 (à citer dans tout travail scolaire publié).
ERA5_CITATION = (
    "Hersbach, H., Bell, B., Berrisford, P., et al. (2020). The ERA5 global "
    "reanalysis. Quarterly Journal of the Royal Meteorological Society, "
    "146(730), 1999-2049. https://doi.org/10.1002/qj.3803"
)

#: Mention de attribution Copernicus exigée par la licence CC-BY.
ERA5_ATTRIBUTION = (
    "Generated using Copernicus Climate Change Service information 2024 "
    "(C3S/CAMS), with the appropriate credit."
)

#: Licence du jeu de données ERA5 au CDS.
ERA5_LICENCE = "CC BY 4.0"


# --------------------------------------------------------------------------- #
# Résolution de la configuration CDS
# --------------------------------------------------------------------------- #


def user_home() -> Path:
    """Dossier personnel de l'utilisateur, y compris sous Windows."""
    return Path(os.environ.get("USERPROFILE") or Path.home())


def cdsapirc_path() -> Path:
    """Emplacement exact du fichier `.cdsapirc` attendu par le CDS."""
    return user_home() / ".cdsapirc"


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Lit un `.env` minimal (`CLE=valeur`), sans dépendance externe."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _parse_cdsapirc(path: Path) -> dict[str, str]:
    """
    Lit un `.cdsapirc`.

    Le format officiel est un petit YAML (`url:` puis `key:`).
    """
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        out[key.strip().lower()] = value.strip().strip("'\"")
    return out


@dataclass
class CDSConfig:
    """Configuration CDS effectivement retenue."""

    url: str | None = None
    key: str | None = None
    source: str = "introuvable"
    path: Path | None = None
    exists: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    def masked_key(self) -> str:
        """Clé tronquée : sûre à afficher à l'écran devant une classe."""
        if not self.key:
            return "—"
        if ":" in self.key:  # ancien format uid:secret
            head, _, tail = self.key.partition(":")
            return f"{head[:4]}…:{tail[:4]}…"
        return f"{self.key[:6]}…{self.key[-4:]}" if len(self.key) > 14 else "…"

    def python_snippet(self) -> str:
        """Extrait Python prêt à coller (équivalent de « Show API request »)."""
        return (
            "import cdsapi\n\n"
            "client = cdsapi.Client(\n"
            f'    url="{self.url}",\n'
            f'    key="{self.key}",\n'
            ")\n"
        )

    def cdsapirc_content(self) -> str:
        """Contenu du `.cdsapirc` correspondant à cette configuration."""
        return f"url: {self.url}\nkey: {self.key}\n"


def deployment_kind() -> str:
    """
    Détermine dans quel contexte l'application s'exécute.

    Les deux situations n'appellent pas la même procédure de configuration de la
    clé CDS : en local on écrit un fichier, sur un hébergeur on passe par les
    *Secrets* de la plateforme. Sans cette distinction, le message affiché ne dit
    pas à l'enseignant où agir.
    """
    for marker in ("STREAMLIT_APP_URL", "STREAMLIT_RUNTIME", "STREAMLIT_HOST"):
        if os.environ.get(marker):
            return "cloud"
    for marker in ("DYNO", "RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME"):
        if os.environ.get(marker):
            return "cloud"
    return "local"


def local_secret_hint() -> str:
    """Rappel des noms attendus, pour une configuration manuelle."""
    return (
        "Les noms attendus sont **CDSAPI_URL** et **CDSAPI_KEY**, sans espace ni "
        "guillemets superflus : c'est ainsi que la plateforme les transmet à "
        "l'application."
    )


def cloud_secret_hint() -> str:
    """Rappel des noms de secrets attendus sur un hébergeur."""
    return (
        "Dans **Settings → Secrets**, ajoutez ces deux lignes. Recopiez "
        "`CDSAPI_URL` tel quel ; pour `CDSAPI_KEY`, collez le jeton affiché sur "
        "votre profil CDS, dans la section *« Set up the CDS API personal access "
        "token »* de **https://cds.climate.copernicus.eu/user** :\n\n"
        '```toml\nCDSAPI_URL = "https://cds.climate.copernicus.eu/api"\n'
        'CDSAPI_KEY = "COLLEZ-ICI-VOTRE-JETON-PERSONNEL"\n```\n\n'
        "`COLLEZ-ICI-VOTRE-JETON-PERSONNEL` est un exemple, pas un jeton : il sera "
        "refusé, ce qui est normal. Le vrai jeton ressemble à `a1b2c3d4-…`.\n\n"
        "Ce n'est pas le *Client ID* ni le *Client secret* de votre compte ECMWF : "
        "ils appartiennent à l'API Web ECMWF et sont rejetés par le CDS.\n\n"
        "Après avoir enregistré, redémarrez l'application "
        "(*Manage app → Restart*) : les secrets ne sont lus qu'au démarrage."
    )


def _streamlit_secret(name: str) -> str | None:
    """
    Lit un secret depuis `st.secrets`, ou renvoie `None`.

    L'import de Streamlit est local et protégé : `config.py` est aussi utilisé
    par les scripts en ligne de commande (`prepare_data.py`, `export_activities.py`),
    où aucun contexte Streamlit n'existe. `st.secrets` lève alors une exception
    qu'il ne faut surtout pas laisser remonter.
    """
    try:
        import streamlit as st
    except Exception:  # noqa: BLE001 - Streamlit est optionnel hors application
        return None
    try:
        value = st.secrets.get(name)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 - aucun contexte / aucun secret configuré
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resolve_cds_config(override_url: str | None = None, override_key: str | None = None) -> CDSConfig:
    """
    Recherche la configuration CDS, par ordre de priorité décroissante.

    1. Saisie directe dans l'application (jamais écrite sur disque) ;
    2. Secrets de la plateforme (`st.secrets`, utilisé sur Streamlit Community
       Cloud) ;
    3. Variables d'environnement `CDSAPI_URL` / `CDSAPI_KEY` ;
    4. Fichier `.cdsapirc` du dossier personnel (méthode officielle CKB) ;
    5. Variables du fichier `.env` à la racine du projet ;
    6. Fichier `.cdsapirc` local au projet (équiper une salle de PC).
    """
    # 1. Saisie dans l'interface
    if override_url and override_key:
        return CDSConfig(
            url=override_url.strip().rstrip("/"),
            key=override_key.strip(),
            source="saisie directe dans l'application",
        )

    # 2. Secrets de la plateforme
    #
    #    C'est la source attendue sur un déploiement en ligne : les entrées de
    #    « Settings → Secrets » y sont exposées par Streamlit. Elles sont
    #    volontairement testées avant les variables d'environnement, afin qu'un
    #    secret explicitement saisi prime sur une valeur héritée du système.
    secret_url = _streamlit_secret("CDSAPI_URL") or _streamlit_secret("CDS_URL")
    secret_key = _streamlit_secret("CDSAPI_KEY") or _streamlit_secret("CDS_KEY")
    if secret_url and secret_key:
        return CDSConfig(
            url=secret_url.rstrip("/"),
            key=secret_key,
            source="secrets de la plateforme (Settings → Secrets)",
        )

    # 3. Variables d'environnement
    env_url = os.environ.get("CDSAPI_URL", "").strip()
    env_key = os.environ.get("CDSAPI_KEY", "").strip()
    if env_url and env_key:
        return CDSConfig(
            url=env_url.rstrip("/"),
            key=env_key,
            source="variables d'environnement CDSAPI_URL / CDSAPI_KEY",
        )

    # 3. Fichier officiel du dossier personnel
    official = cdsapirc_path()
    conf = _parse_cdsapirc(official)
    if conf.get("url") and conf.get("key"):
        return CDSConfig(
            url=conf["url"].rstrip("/"),
            key=conf["key"],
            source=f"fichier officiel {official}",
            path=official,
            exists=True,
        )

    # 4. Fichier .env du projet
    dotenv = _parse_dotenv(PROJECT_ROOT / ".env")
    if dotenv.get("CDSAPI_URL") and dotenv.get("CDSAPI_KEY"):
        return CDSConfig(
            url=dotenv["CDSAPI_URL"].rstrip("/"),
            key=dotenv["CDSAPI_KEY"],
            source="fichier .env du projet",
            path=PROJECT_ROOT / ".env",
            exists=True,
        )

    # 5. .cdsapirc local au projet
    local = PROJECT_ROOT / ".cdsapirc"
    conf = _parse_cdsapirc(local)
    if conf.get("url") and conf.get("key"):
        return CDSConfig(
            url=conf["url"].rstrip("/"),
            key=conf["key"],
            source=f"fichier local {local}",
            path=local,
            exists=True,
        )

    return CDSConfig(exists=official.is_file(), path=official)


def write_cdsapirc(url: str, key: str, *, location: str = "user") -> Path:
    """
    Écrit le fichier `.cdsapirc`.

    `location="user"` écrit dans le dossier personnel (emplacement attendu par le
    CDS). `location="project"` écrit à la racine du projet, utile pour équiper
    plusieurs postes d'une salle sans configurer chaque compte.
    """
    target = user_home() / ".cdsapirc" if location == "user" else PROJECT_ROOT / ".cdsapirc"
    target.write_text(f"url: {url.rstrip('/')}\nkey: {key}\n", encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Réglages de l'application
# --------------------------------------------------------------------------- #


@dataclass
class AppSettings:
    """Réglages modifiables depuis la barre latérale de l'application."""

    demo_mode: bool = field(default_factory=lambda: os.environ.get("C3S_LAB_DEMO", "") == "1")
    auto_download: bool = True
    use_cache: bool = True
    max_years_daily: int = 3
    show_advanced: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "demo_mode": self.demo_mode,
            "auto_download": self.auto_download,
            "use_cache": self.use_cache,
            "max_years_daily": self.max_years_daily,
            "show_advanced": self.show_advanced,
        }


def app_info() -> dict[str, Any]:
    """Résumé de l'environnement, affiché dans la page « Diagnostic »."""
    import platform
    import sys

    versions: dict[str, str] = {}
    for name in (
        "cdsapi", "ecmwf_datastores_client", "xarray", "numpy", "pandas",
        "plotly", "matplotlib", "netCDF4", "streamlit", "geopandas", "shapely",
    ):
        try:
            mod = __import__(name)
            versions[name] = getattr(mod, "__version__", "installé")
        except Exception:
            versions[name] = "absent"

    return {
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()}",
        "versions": versions,
        "data_dir": str(DATA_DIR),
        "cdsapirc": str(cdsapirc_path()),
    }
