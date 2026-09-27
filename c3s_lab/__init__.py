"""
C3S Climate Lab — laboratoire pédagogique du climat (cycle 4 / collège).

Sert de bibliothèque interne à l'application Streamlit :
  * config      : résolution de la clé API CDS et chemins de l'application
  * cds_client  : connexion, test, téléchargement et cache des données ERA5/C3S
  * catalog     : catalogue des jeux de données CDS utilisables en classe
  * places      : villes, régions et domaines géographiques
  * analysis    : calculs climatologiques rigoureux (normales, anomalies, indices)
  * viz / maps  : graphiques et cartes scientifiques
  * demo        : jeu de données simulé pour un fonctionnement hors-ligne
  * activities  : activités pédagogiques clé en main
"""

__version__ = "1.0.0"
__all__ = [
    "config",
    "cds_client",
    "catalog",
    "places",
    "analysis",
    "viz",
    "maps",
    "demo",
    "activities",
]
