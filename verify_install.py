"""
Diagnostic de l'installation de C3S Climate Lab.

Vérifie, dans l'ordre :

1. la présence et la version des dépendances Python ;
2. la localisation du fichier `.cdsapirc` attendu par le CDS ;
3. la validité de la configuration (clé et URL) ;
4. la joignabilité du portail CDS ;
5. l'accès aux fonds de carte Natural Earth.

Usage :
    python verify_install.py

Code de sortie : 0 si tout est correct, 1 sinon.
"""

from __future__ import annotations

import sys

# La console Windows utilise souvent cp1252, qui ne sait pas encoder les tirets
# cadratins ni certains symboles utilisés ci-dessous. On bascule la sortie
# standard en UTF-8 avec remplacement, pour que le diagnostic s'affiche toujours
# en entier plutôt que de s'interrompre sur une erreur d'encodage.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

from c3s_lab import basemaps, cds_client, config

OK = "  [OK]    "
KO = "  [MANQUE]"
WARN = "  [ATTENTION]"


def _line(status: str, message: str) -> str:
    return f"{status} {message}"


def check_dependencies() -> bool:
    """Contrôle les versions installées."""
    print("1. Dépendances Python")
    info = config.app_info()
    # matplotlib sert au tracé des isothermes et isobares ; il n'est donc pas
    # vraiment optionnel, contrairement à geopandas et shapely.
    required = (
        "cdsapi", "xarray", "numpy", "pandas", "plotly",
        "matplotlib", "netCDF4", "streamlit",
    )
    all_ok = True
    for name in required:
        version = info["versions"].get(name, "absent")
        if version == "absent":
            print(_line(KO, f"{name}"))
            all_ok = False
        else:
            print(_line(OK, f"{name} {version}"))
    optional = ("geopandas", "shapely")
    for name in optional:
        version = info["versions"].get(name, "absent")
        status = OK if version != "absent" else WARN
        print(_line(status, f"{name} {version}"))
    print(f"       Python {info['python']} — {info['platform']}")
    if not all_ok:
        print("\n  Installez les dépendances manquantes :")
        print("      pip install -r requirements.txt\n")
    return all_ok


def check_cds_file() -> None:
    """Indique où le CDS cherche sa configuration."""
    print("\n2. Fichier .cdsapirc")
    path = config.cdsapirc_path()
    print(_line(OK if path.exists() else WARN, str(path)))
    if not path.exists():
        print("       Créer ce fichier avec install_cds_key.ps1, ou saisir la clé")
        print("       directement dans la page « Connexion CDS » de l'application.\n")


def check_connection(cfg: config.CDSConfig) -> bool:
    """Vérifie la configuration puis la joignabilité du portail."""
    print("\n3. Configuration CDS")
    if cfg.is_configured:
        print(_line(OK, f"source : {cfg.source}"))
        print(_line(OK, f"URL    : {cfg.url}"))
        print(_line(OK, f"clé    : {cfg.masked_key()}"))
    else:
        print(_line(WARN, "aucune clé API détectée — l'application fonctionnera en mode simulation"))
        print(f"       Fichier attendu : {config.cdsapirc_path()}\n")
        return False

    print("\n4. Portail CDS")
    report = cds_client.test_connection(cfg)
    print(_line(OK if report.ok else KO, report.title))
    print(f"       {report.detail}")
    if report.hint:
        print(f"       {report.hint}")
    return report.ok


def check_basemaps() -> None:
    """Vérifie la présence des fonds de carte."""
    print("\n5. Fonds de carte (Natural Earth)")
    for name, meta in basemaps.BASEMAPS.items():
        exists = basemaps.basemap_path(name).exists()
        print(_line(OK if exists else WARN, meta["label"]))
    if not all(basemaps.basemap_path(n).exists() for n in basemaps.BASEMAPS):
        print("       Téléchargeables depuis la page « Méthode » de l'application.")


def main() -> int:
    print("=" * 68)
    print("  C3S Climate Lab — diagnostic de l'installation")
    print("=" * 68)

    deps_ok = check_dependencies()
    check_cds_file()
    cfg = config.resolve_cds_config()
    cds_ok = check_connection(cfg)
    check_basemaps()

    print("\n" + "=" * 68)
    if deps_ok and cds_ok:
        print("  Installation complète. Lancez : streamlit run app.py")
        return 0
    if deps_ok:
        print("  Dépendances OK, mais le CDS n'est pas encore configuré.")
        print("  L'application fonctionne en mode simulation. Pour les données réelles :")
        print("      .\\install_cds_key.ps1")
        return 0
    print("  Des dépendances manquent. Lancez : pip install -r requirements.txt")
    return 1


if __name__ == "__main__":
    sys.exit(main())
