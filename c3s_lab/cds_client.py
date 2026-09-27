"""
Client du Climate Data Store (CDS) : connexion, test, téléchargement, cache.

La connexion s'appuie sur `cdsapi`, bibliothèque officielle installée avec
`pip install cdsapi`. Le client lit par défaut le fichier `%USERPROFILE%\\.cdsapirc`
comme le décrit la procédure ECMWF, mais l'application peut aussi lui passer
explicitement une `url` et une `key`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import config

ProgressFn = Callable[[float, str], None]


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class CDSError(RuntimeError):
    """Erreur fonctionnelle du CDS (mauvaise licence, quota, jeu inconnu…)."""


class CDSConfigError(CDSError):
    """Clé ou URL absente / invalide."""


class CDSDownloadError(CDSError):
    """Le téléchargement a échoué après plusieurs tentatives."""


# --------------------------------------------------------------------------- #
# Test de connexion
# --------------------------------------------------------------------------- #


@dataclass
class ConnectionReport:
    """Résultat du diagnostic de connexion, affiché dans l'interface."""

    ok: bool
    title: str
    detail: str
    hint: str = ""
    latency_s: float | None = None


def test_connection(cfg: config.CDSConfig, *, deep: bool = False) -> ConnectionReport:
    """
    Vérifie la configuration CDS.

    - `deep=False` : contrôle la présence de la clé et la joignabilité du
      portail CDS (pas de requête de données, donc aucun quota consommé) ;
    - `deep=True`  : demande l'un des jeux de données du catalogue pour valider
      réellement l'authentification et les licences acceptées.
    """
    if not cfg.is_configured:
        return ConnectionReport(
            ok=False,
            title="Aucune clé API détectée",
            detail=(
                "Le CDS n'a trouvé ni fichier `.cdsapirc`, ni variable "
                "d'environnement `CDSAPI_KEY`."
            ),
            hint=(
                f"Créez le fichier {config.cdsapirc_path()} contenant :\n"
                "  url: https://cds.climate.copernicus.eu/api\n"
                "  key: <votre clé personnelle>"
            ),
        )

    t0 = time.perf_counter()
    try:
        import requests
    except ImportError:  # pragma: no cover
        return ConnectionReport(False, "Client HTTP absent", "Installer `requests`.")

    try:
        r = requests.get(config.CDS_CATALOGUE_URL, params={"limit": 1}, timeout=15)
        reachable = r.status_code < 500
    except Exception as exc:  # pragma: no cover - dépend du réseau
        return ConnectionReport(
            False,
            "Portail CDS injoignable",
            f"{type(exc).__name__} : {exc}",
            hint="Vérifier la connexion Internet et les réglages du proxy.",
        )

    if not reachable:
        return ConnectionReport(
            False, "Portail CDS en erreur", f"Statut HTTP {r.status_code}."
        )

    if not deep:
        return ConnectionReport(
            True,
            "Configuration valide",
            (
                f"Clé reconnue par l'application (source : {cfg.source}). "
                "Le portail CDS répond ; le test d'authentification n'a pas été lancé."
            ),
            latency_s=time.perf_counter() - t0,
        )

    # Test en profondeur : lecture du catalogue, authentification comprise.
    try:
        client = _build_client(cfg)
        target = config.CACHE_DIR / "_connection_test.csv"
        client.retrieve(
            "reanalysis-era5-single-levels-timeseries",
            {
                "variable": ["2m_temperature"],
                "data_format": "csv",
                "area": [46.0, 2.0, 45.0, 3.0],
            },
            str(target),
        )
        if target.exists():
            target.unlink(missing_ok=True)
        return ConnectionReport(
            True,
            "Connexion CDS opérationnelle",
            (
                "Le CDS a accepté la requête et renvoyé des données pour un point "
                "test situé en France. Toutes les licences utilisées sont acceptées."
            ),
            latency_s=time.perf_counter() - t0,
        )
    except Exception as exc:  # noqa: BLE001 - dépend du compte et du CDS
        detail = f"{type(exc).__name__} : {exc}"
        lowered = str(exc).lower()

        # Un 403 « licences non acceptées » prouve au contraire que
        # l'authentification a réussi : le message doit le dire clairement,
        # sinon l'utilisateur cherche une erreur de clé inexistante.
        if "licen" in lowered and ("403" in lowered or "forbidden" in lowered):
            return ConnectionReport(
                True,
                "Clé acceptée — conditions d'utilisation à accepter",
                (
                    "Le CDS a reconnu votre jeton : le compte est authentifié. "
                    "Le téléchargement est bloqué uniquement parce que les "
                    "conditions d'utilisation des jeux de données n'ont pas encore "
                    "été acceptées. Ouvrez la page de chaque jeu de données, "
                    "descendez en bas du formulaire et cliquez sur « Accept »."
                ),
                hint=f"Pages à ouvrir : voir la section 5 de cette page.",
                latency_s=time.perf_counter() - t0,
            )

        if "401" in lowered or "unauthor" in lowered or "token" in lowered:
            return ConnectionReport(
                False,
                "Jeton refusé par le CDS",
                detail,
                hint=(
                    "Vérifiez que vous utilisez bien le jeton d'accès personnel du "
                    "profil CDS, et non le « Client ID » / « Client secret » de "
                    "votre compte ECMWF (qui sert à l'API Web ECMWF)."
                ),
            )

        return ConnectionReport(
            False,
            "Échec du test approfondi",
            detail,
            hint=(
                "Causes fréquentes : proxy bloquant la connexion, service "
                "temporairement indisponible, ou volume de requête refusé."
            ),
            latency_s=time.perf_counter() - t0,
        )


# --------------------------------------------------------------------------- #
# Diagnostic de la clé
# --------------------------------------------------------------------------- #

#: Valeurs saisies par oubli : ce sont des exemples de documentation.
PLACEHOLDERS = (
    "votre", "remplacez", "remplacer", "your", "changeme", "xxxx", "todo",
    "token", "cle", "key", "<", ">",
)

#: Un ancien identifiant ECMWF a la forme d'un UUID (8-4-4-4-12).
_UUID_CHUNK = 36


@dataclass
class KeyDiagnosis:
    """Verdict sur la clé saisie, avec une explication utilisable."""

    ok: bool
    label: str
    message: str
    hint: str = ""


def diagnose_key(key: str) -> KeyDiagnosis:
    """
    Analyse une clé API avant de tenter une connexion.

    Le CDS utilise un **jeton d'accès personnel** (*Personal Access Token*),
    et non l'ancien couple `identifiant:secret`, ni le *Client ID* / *Client
    secret* de l'API Web ECMWF. Ces trois formats se ressemblent et se
    confondent fréquemment ; les distinguer ici évite une erreur d'authentification
    difficile à interpréter ensuite.
    """
    value = (key or "").strip()

    if not value:
        return KeyDiagnosis(
            False, "clé absente",
            "Aucun jeton n'a été saisi.",
            "Collez le jeton affiché dans la section « Set up the CDS API "
            "personal access token » de votre profil CDS.",
        )

    lowered = value.lower()
    if any(marker in lowered for marker in PLACEHOLDERS) and len(value) < 60:
        return KeyDiagnosis(
            False, "valeur d'exemple",
            "La valeur saisie ressemble à un exemple de documentation, pas à un jeton réel.",
            "Copiez la valeur exacte affichée sur la page de votre profil CDS.",
        )

    if ":" in value:
        head, _, tail = value.partition(":")
        is_uuid = (
            len(head.strip()) == _UUID_CHUNK
            and head.strip().count("-") == 4
            and len(tail.strip()) > 8
        )
        return KeyDiagnosis(
            False,
            "ancien format identifiant:secret",
            (
                "Cette clé a l'ancien format `identifiant:secret`"
                + (", issu des identifiants ECMWF" if is_uuid else "")
                + ". Le CDS ne l'accepte plus depuis la migration de septembre 2024."
            ),
            "Il n'existe plus d'identifiant utilisateur au CDS. Récupérez le nouveau "
            "jeton personnel sur https://cds.climate.copernicus.eu/user (section "
            "« Set up the CDS API personal access token ») et remplacez la clé.",
        )

    if len(value) < 20:
        return KeyDiagnosis(
            False, "clé trop courte",
            f"La valeur saisie ne fait que {len(value)} caractères : elle est trop "
            "courte pour être un jeton du CDS.",
            "Le jeton du CDS est une longue chaîne. Attention : le « Client ID » et "
            "le « Client secret » de votre profil ECMWF servent à l'API Web ECMWF, "
            "pas au Climate Data Store — ils sont refusés ici.",
        )

    return KeyDiagnosis(
        True, "jeton d'accès personnel",
        "La valeur a la forme attendue d'un jeton d'accès personnel du CDS.",
        "Si le téléchargement échoue encore, vérifiez d'avoir accepté les conditions "
        "d'utilisation du jeu de données sur sa page CDS.",
    )


def _build_client(cfg: config.CDSConfig):
    """
    Instancie un client CDS.

    Depuis `cdsapi` 0.7.7, la bibliothèque choisit sa classe d'implémentation
    selon la forme de la clé : un jeton personnel (sans deux-points) active le
    nouveau client `ecmwf.datastores`, tandis qu'une clé historique
    `identifiant:secret` conserve l'ancien chemin. Les deux acceptent les mêmes
    arguments d'initialisation, d'où le passage direct.
    """
    if not cfg.is_configured:
        raise CDSConfigError(
            "Clé API absente. Voir la page « Connexion CDS » pour la configurer."
        )
    diagnosis = diagnose_key(cfg.key or "")
    if not diagnosis.ok:
        raise CDSConfigError(f"{diagnosis.message} {diagnosis.hint}")

    try:
        import cdsapi
    except ImportError as exc:  # pragma: no cover
        raise CDSConfigError(
            "La bibliothèque `cdsapi` est absente. L'installer avec : pip install cdsapi"
        ) from exc

    return cdsapi.Client(url=cfg.url, key=cfg.key, quiet=True)


def _cache_key(dataset: str, request: dict[str, Any]) -> str:
    """Empreinte stable d'une requête, servant de nom de fichier de cache."""
    payload = json.dumps(
        {"dataset": dataset, "request": request}, sort_keys=True, default=str
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def available_cached() -> list[dict[str, Any]]:
    """Inventaire des fichiers déjà téléchargés (page « Diagnostic »)."""
    rows: list[dict[str, Any]] = []
    for f in sorted(config.CACHE_DIR.glob("*"), key=lambda p: -p.stat().st_mtime):
        if f.is_dir():
            continue
        stat = f.stat()
        rows.append(
            {
                "Fichier": f.name,
                "Taille": f"{stat.st_size / 1e6:.2f} Mo",
                "Modifié le": time.strftime(
                    "%d/%m/%Y %H:%M", time.localtime(stat.st_mtime)
                ),
            }
        )
    return rows


def clear_cache() -> int:
    """Vide le cache ; renvoie le nombre de mégaoctets libérés."""
    freed = 0
    for f in list(config.CACHE_DIR.glob("*")) + list(config.MAPS_DIR.glob("*")):
        try:
            if f.is_file():
                freed += f.stat().st_size
                f.unlink()
        except OSError:  # pragma: no cover
            continue
    return freed / 1e6


def retrieve(
    cfg: config.CDSConfig,
    dataset: str,
    request: dict[str, Any],
    *,
    progress: ProgressFn | None = None,
    max_retries: int = 3,
    use_cache: bool = True,
) -> Path:
    """
    Télécharge une requête CDS et renvoie le chemin du fichier obtenu.

    Le fichier est mis en cache sous `data/cache/<empreinte>_<dataset>.nc` ; un
    second appel identique est instantané. Les archives ZIP retournées par le
    CDS sont automatiquement extraites.
    """
    stamp = _cache_key(dataset, request)
    target = config.CACHE_DIR / f"{stamp}_{dataset[:38]}.nc"

    if use_cache and target.exists() and target.stat().st_size > 0:
        if progress:
            progress(1.0, "Données déjà téléchargées (cache local).")
        return target

    client = _build_client(cfg)
    tmp = target.with_suffix(".part")

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            if progress:
                progress(
                    0.05,
                    f"Requête envoyée au CDS (essai {attempt}/{max_retries})…",
                )
            client.retrieve(dataset, request, str(tmp))
            break
        except Exception as exc:  # noqa: BLE001 - le CDS lève des exceptions variées
            last_error = exc
            if progress:
                progress(0.05, f"Échec : {exc}. Nouvelle tentative…")
            if attempt < max_retries:
                time.sleep(2 * attempt)
    else:
        raise CDSDownloadError(f"Téléchargement impossible : {last_error}")

    resolved = _normalise_output(tmp, target)
    if progress:
        size_mb = resolved.stat().st_size / 1e6
        progress(1.0, f"Téléchargement terminé ({size_mb:.1f} Mo).")
    return resolved


def _normalise_output(tmp: Path, target: Path) -> Path:
    """
    Le CDS renvoie soit un NetCDF, soit une archive ZIP contenant un ou
    plusieurs NetCDF. On normalise toujours vers un fichier NetCDF unique.
    """
    if not tmp.exists():
        raise CDSDownloadError("Le CDS n'a renvoyé aucun fichier.")

    if zipfile.is_zipfile(tmp):
        with zipfile.ZipFile(tmp) as zf:
            members = [m for m in zf.namelist() if m.lower().endswith((".nc", ".nc4", ".grib", ".csv"))]
            if not members:
                members = zf.namelist()
            with zf.open(members[0]) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        tmp.unlink(missing_ok=True)
        return target

    tmp.replace(target)
    return target


def open_dataset(path: Path):
    """Ouvre un fichier NetCDF avec xarray et le normalise (cftime -> datetime64)."""
    import xarray as xr

    ds = xr.open_dataset(path, engine="netcdf4")
    for dim in ("time", "valid_time"):
        if dim in ds.coords:
            try:
                ds[dim] = ds[dim].astype("datetime64[ns]")
            except (TypeError, ValueError):  # pragma: no cover
                pass
    return ds


def available_catalogue() -> list[dict[str, str]]:
    """Liste à jour des jeux de données ERA5 publiés au CDS (diagnostic)."""
    import requests

    resp = requests.get(config.CDS_CATALOGUE_URL, params={"limit": 500}, timeout=30)
    resp.raise_for_status()
    rows = []
    for c in resp.json().get("collections", []):
        title = c.get("title", "")
        if "ERA5" in title or "era5" in c.get("id", ""):
            rows.append({"Identifiant": c["id"], "Titre": title})
    return sorted(rows, key=lambda r: r["Identifiant"])
