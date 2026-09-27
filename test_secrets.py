"""
Vérifie que la lecture des secrets fonctionne dans un contexte Streamlit.

Simule ce que fait Streamlit Community Cloud : un fichier `secrets.toml` exposé
par la variable `STREAMLIT_SECRETS_FILE`. Le résultat est écrit dans un fichier,
car la sortie d'un `AppTest` n'est pas toujours capturée par la console.

Usage :  python test_secrets.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

#: Secret de démonstration, volontairement sans valeur réelle.
FAKE_KEY = "abcd-1234-test-key"

RUNNER = """
import streamlit as st
from c3s_lab import config

value = config._streamlit_secret("CDSAPI_KEY")
cfg = config.resolve_cds_config()
with open(RESULT_PATH, "w", encoding="utf-8") as handle:
    handle.write(f"secret_lu={value}\\n")
    handle.write(f"configure={cfg.is_configured}\\n")
    handle.write(f"source={cfg.source}\\n")
    handle.write(f"kind={config.deployment_kind()}\\n")
st.write("ok")
"""


def main() -> int:
    # Console Windows en cp1252 : on force l'UTF-8 pour afficher les accents.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    original = Path.cwd()
    tmp = Path(tempfile.mkdtemp())
    (tmp / ".streamlit").mkdir()
    with_secrets = "--sans-secret" not in original.name
    if with_secrets:
        secrets_file = tmp / ".streamlit" / "secrets.toml"
        secrets_file.write_text(
            'CDSAPI_URL = "https://cds.climate.copernicus.eu/api"\n'
            f'CDSAPI_KEY = "{FAKE_KEY}"\n',
            encoding="utf-8",
        )
    result = tmp / "r.txt"
    runner = tmp / "run.py"
    runner.write_text(
        f'import sys\nsys.path.insert(0, r"{original}")\n'
        f'RESULT_PATH = r"{result}"\n' + RUNNER,
        encoding="utf-8",
    )

    os.chdir(tmp)
    try:
        at = AppTest.from_file(str(runner), default_timeout=90)
        at.run()
    finally:
        os.chdir(original)

    if at.exception:
        print(f"[ECHEC] exception : {at.exception[0].message[:300]}")
        return 1
    if not result.is_file():
        print("[ECHEC] le script n'a rien écrit : les secrets ne sont pas lus.")
        return 1

    lines = result.read_text(encoding="utf-8").strip().splitlines()
    values = dict(line.split("=", 1) for line in lines if "=" in line)
    print(lines[0])
    failures = 0
    if values.get("secret_lu") != FAKE_KEY:
        print(f"[ECHEC] secret non lu : {values.get('secret_lu')}")
        failures += 1
    else:
        print("[OK] le secret est lu depuis st.secrets")
    if values.get("configure") == "True":
        print(f"[OK] clé reconnue, source : {values.get('source')}")
    else:
        print(f"[ECHEC] clé non reconnue (configure={values.get('configure')})")
        failures += 1
    print(f"[INFO] contexte détecté : {values.get('kind')}")
    print(f"\n{'OK' if not failures else 'ECHEC'} : {2 - failures}/2 vérifications.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
