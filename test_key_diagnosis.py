"""Test du diagnostic de clé API : vérifie que les erreurs fréquentes
(ancien format, Client ID/Secret, valeur d'exemple) sont détectées et
expliquées, et qu'un jeton valide est accepté.

Usage :  python -m pytest test_key_diagnosis.py -q
   ou :  python test_key_diagnosis.py
"""
from __future__ import annotations

import sys

from c3s_lab import cds_client

CASES = [
    # (clé, verdict attendu, fragment attendu dans l'explication)
    ("", False, "jeton"),
    ("votre-cle-personnelle", False, "exemple de documentation"),
    ("<PERSONAL-ACCESS-TOKEN>", False, "exemple de documentation"),
    ("abcd1234-ef56-7890-abcd-ef1234567890:SECRETVALEUR", False, "ancien format"),
    ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc", True, ""),
    ("a" * 96, True, ""),
    # Cas limite : un Client ID / Client secret courts sont refusés avec
    # un message qui oriente vers l'API Web ECMWF.
    ("Kk3dF7bQ9xZ2mNpR", False, "API Web ECMWF"),
]


def main() -> int:
    failures = 0
    for key, expected_ok, expected_fragment in CASES:
        verdict = cds_client.diagnose_key(key)
        label = key[:34] + ("…" if len(key) > 34 else "") if key else "(vide)"
        combined = f"{verdict.message} {verdict.hint}"
        ok = verdict.ok == expected_ok and expected_fragment.lower() in combined.lower()
        status = "OK  " if ok else "ECHEC"
        if not ok:
            failures += 1
        print(f"[{status}] {label!r:40} -> {verdict.label}")
        if not ok:
            print(f"         attendu: ok={expected_ok} fragment={expected_fragment!r}")
            print(f"         obtenu : ok={verdict.ok} message={verdict.message}")

    total = len(CASES)
    print(f"\n{total - failures}/{total} cas de diagnostic corrects.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
