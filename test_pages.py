"""
Test de non-régression : exécute chaque page et chaque activité.

`AppTest` attend un chemin de script, et `from_function` ne recopie que le corps
de la fonction (sans ses imports). On génère donc, pour chaque page, un petit
fichier qui importe l'application réelle puis appelle la page voulue : le
contexte d'exécution est ainsi identique à celui de la production.

Usage :  python test_pages.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app as A
from c3s_lab import activities

PAGE_FUNCTIONS = [
    "page_accueil",
    "page_connexion",
    "page_cartes",
    "page_graphiques",
    "page_villes",
    "page_activites",
    "page_methode",
]

_PAGE_RUNNER = """import app
import c3s_lab.ui as ui

ui.inject_css()
app.{function}()
"""

#: La page des activités rend la première activité par défaut ; on force
#: l'autre pour que les sept soient couvertes.
_ACTIVITY_RUNNER = """import app
import c3s_lab.ui as ui
import c3s_lab.activities as activities

ui.inject_css()
activity = activities.get("{key}")
app._activity_figures(activity)
"""


def _asciify(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def _run(path: Path) -> AppTest:
    at = AppTest.from_file(str(path), default_timeout=300)
    at.session_state["force_simulated"] = True
    at.run()
    return at


def main() -> int:
    lines: list[str] = []
    failures = 0

    with tempfile.TemporaryDirectory() as tmp:
        # --- Toutes les pages de l'application.
        for function in PAGE_FUNCTIONS:
            runner = Path(tmp) / f"{function}.py"
            runner.write_text(_PAGE_RUNNER.format(function=function), encoding="utf-8")
            at = _run(runner)
            if at.exception:
                failures += 1
                lines.append(f"[ECHEC] {function} : {at.exception[0].message[:600]}")
            else:
                lines.append(
                    f"[OK] {function} : titres={len(at.title)} "
                    f"markdown={len(at.markdown)} tableaux={len(at.dataframe)} "
                    f"figures={len(at.get('plotly_chart'))} boutons={len(at.button)}"
                )

        # --- Les figures de chacune des sept activités.
        for activity in activities.ACTIVITIES:
            runner = Path(tmp) / f"act_{activity.key}.py"
            runner.write_text(
                _ACTIVITY_RUNNER.format(key=activity.key), encoding="utf-8"
            )
            at = _run(runner)
            if at.exception:
                failures += 1
                lines.append(
                    f"[ECHEC] activite {activity.key} : {at.exception[0].message[:600]}"
                )
            else:
                lines.append(
                    f"[OK] activite {activity.key} : "
                    f"figures={len(at.get('plotly_chart'))} "
                    f"tableaux={len(at.dataframe)}"
                )

    total = len(PAGE_FUNCTIONS) + len(activities.ACTIVITIES)
    lines.append(f"\n{total - failures}/{total} tests sans exception.")
    report = "\n".join(lines)
    print(_asciify(report))
    Path("test_report.txt").write_text(report, encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())


