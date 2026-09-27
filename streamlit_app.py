"""
Point d'entrée attendu par Streamlit Community Cloud.

Le nom `streamlit_app.py` n'est pas un choix esthétique : c'est le nom de fichier
que Streamlit Community Cloud **propose par défaut** dans le champ « Main file
path » de son écran de déploiement. Un dépôt dont le script s'appelle `app.py` se
heurte donc à « This file does not exist » tant que le champ n'est pas corrigé à
la main — et l'erreur est notoriously facile à rater.

Ce fichier rend le déploiement direct : le champ peut rester sur sa valeur par
défaut. Il ne fait que déléguer à `app.main()`, afin de n'avoir qu'un seul point
d'entrée à maintenir.
"""

from __future__ import annotations

import app

#: Nom de fichier attendu par Streamlit Community Cloud, à ne pas renommer.
ENTRYPOINT = "streamlit_app.py"

app.main()
