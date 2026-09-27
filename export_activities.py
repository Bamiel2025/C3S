"""
Génère les fiches d'activités autonomes au format HTML.

Chaque fiche contient ses graphiques, ses cartes, ses consignes et ses
réponses attendues, le tout dans un fichier unique qui s'ouvre hors ligne.
Les données sont de vraies données ERA5, téléchargées sur le CDS (voir
`prepare_data.py`) : les chiffres affichés sont ceux du modèle.

Usage :
    python export_activities.py               # toutes les fiches
    python export_activities.py 08 09         # seulement celles-ci
    python export_activities.py --index        # la page d'accueil seule

Les fichiers sont écrits dans `activites_html/`.
"""

from __future__ import annotations

import sys
import time

# La console Windows est souvent en cp1252, incapable d'afficher les symboles
# décoratifs. On force l'UTF-8 pour que la progression reste lisible.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover
    pass

from c3s_lab import sheets


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]

    if "--index" in argv:
        target = sheets.index_page()
        print(f"Page d'accueil : {target}")
        return 0

    cfg_needed = True
    try:
        from c3s_lab import config
        cfg_needed = not config.resolve_cds_config().is_configured
    except Exception:  # noqa: BLE001
        pass
    if cfg_needed and not args:
        print(
            "Aucune cle CDS configuree : les fiches ne pourront pas utiliser de\n"
            "donnees reelles. Lancez d'abord prepare_data.py, ou fournissez la cle."
        )
        return 1

    print("=" * 66)
    print("  Generation des fiches HTML — C3S Climate Lab")
    print("=" * 66)
    hub = sheets.DataHub()
    only = tuple(args) if args else ()
    t0 = time.perf_counter()
    written = sheets.build_all(hub, only=only)
    index = sheets.index_page()
    for path in written:
        print(f"  {path.name:42} {path.stat().st_size / 1e6:5.2f} Mo")
    print(f"  {index.name:42} (page d'accueil)")
    print("=" * 66)
    print(f"  {len(written)} fiche(s) en {time.perf_counter() - t0:.0f} s")
    print(f"  Dossier : {sheets.OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
