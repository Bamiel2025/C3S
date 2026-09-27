"""
Test d'intégration : l'application doit-elle tenter un téléchargement réel
(la clé est présente) et gérer proprement le refus du CDS ?

Ce test interroge réellement le portail. Il est donc lent et dépend du réseau ;
il est volontairement isolé des tests de pages.

Usage :  python -m pytest test_live_cds.py -q
   ou :  python test_live_cds.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

from c3s_lab import cds_client, config

_RUNNER = """import app
import c3s_lab.ui as ui

ui.inject_css()
app.page_cartes()
"""


def main() -> int:
    cfg = config.resolve_cds_config()
    print("=" * 68)
    print("  Test d'intégration — chemin réel du CDS")
    print("=" * 68)
    print(f"Clé configurée : {cfg.is_configured} ({cfg.source})")

    if not cfg.is_configured:
        print("Aucune clé : rien à tester sur le chemin réel.")
        return 0

    print("\n1. La clé est-elle acceptée par le portail ?")
    report = cds_client.test_connection(cfg, deep=True)
    print(f"   {report.title}")
    print(f"   {report.detail[:200]}")

    # Le titre du rapport distingue désormais les cas : clé acceptée mais
    # licences manquantes, contre clé franchement refusée.
    licence_pending = "conditions" in report.title.lower()
    print(f"   diagnostic : {'LICENCES A ACCEPTER' if licence_pending else 'cle operee'}")

    print("\n2. L'application gère-t-elle correctement le refus ?")
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "live.py"
        runner.write_text(_RUNNER, encoding="utf-8")
        at = AppTest.from_file(str(runner), default_timeout=300)
        at.run()

    crashed = bool(at.exception)
    if crashed:
        print(f"   ÉCHEC : {at.exception[0].message[:300]}")
        return 1

    # La page doit s'arrêter proprement (`st.stop`) et expliquer la situation,
    # plutôt que de renvoyer une page vide.
    warnings = [w.value for w in at.warning]
    errors = [e.value for e in at.error]
    explained = any("conditions" in text.lower() for text in warnings + errors)
    print(f"   exception            : {'oui' if crashed else 'non'}")
    print(f"   message explicite    : {'oui' if explained else 'non'}")
    print(f"   avertissements       : {len(warnings)}")
    print(f"   messages d'erreur    : {len(errors)}")

    if licence_pending and not explained:
        print("   PROBLÈME : le refus du CDS n'est pas expliqué à l'utilisateur.")
        return 1

    print("\nComportement conforme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
