"""
Test empirique d'une authentification CDS, sans rien écrire sur le disque.

Interroge réellement le portail et affiche le verdict, afin de trancher entre
les causes possibles (jeton valide, format obsolète, conditions non acceptées).

Usage :  python -m c3s_lab.probe_key <url> <clé>
"""
from __future__ import annotations

import sys

import requests

from . import cds_client, config


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Usage : python -m c3s_lab.probe_key <url> <clé>")
        return 2
    url, key = argv[1], argv[2]

    print("=" * 64)
    print("  Sonde d'authentification CDS")
    print("=" * 64)

    verdict = cds_client.diagnose_key(key)
    print(f"\n1. Analyse du format")
    print(f"   verdict  : {'OK' if verdict.ok else 'REFUSE'}")
    print(f"   catégorie: {verdict.label}")
    print(f"   détail   : {verdict.message}")
    if verdict.hint:
        print(f"   conseil  : {verdict.hint}")

    print(f"\n2. Test auprès du portail")
    try:
        client = cdsapi_client(url, key)
    except Exception as exc:  # noqa: BLE001
        print(f"   construction du client impossible : {exc}")
        return 1

    target = config.CACHE_DIR / "_sonde.nc"
    request = {
        "variable": ["2m_temperature"],
        "data_format": "csv",
        "area": [46.0, 2.0, 45.0, 3.0],
    }
    try:
        client.retrieve("reanalysis-era5-single-levels-timeseries", request, str(target))
    except Exception as exc:  # noqa: BLE001
        print(f"   ECHEC : {type(exc).__name__}")
        print(f"   {str(exc)[:700]}")
        return 1

    if target.exists():
        size = target.stat().st_size
        target.unlink(missing_ok=True)
        print(f"   SUCCESS : requête acceptée ({size} octets reçus)")
    else:
        print("   fichier absent malgré un retour sans erreur")
        return 1
    return 0


def cdsapi_client(url: str, key: str):
    import cdsapi

    return cdsapi.Client(url=url, key=key, quiet=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
