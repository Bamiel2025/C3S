# 🌍 C3S Climate Lab

**Application pédagogique pour étudier le climat avec les vraies données du
Copernicus Climate Change Service — cycle 4 (5e, 4e, 3e).**

L'application télécharge les données climatiques **ERA5** publiées au Climate
Data Store, en construit des graphiques et des cartes, et fournit sept activités
clé en main calées sur les programmes de cycle 4.

---

## Sommaire

1. [Ce que fait l'application](#1-ce-que-fait-lapplication)
2. [Installation](#2-installation)
3. [Configuration de la clé API CDS](#3-configuration-de-la-clé-api-cds)
4. [Lancement](#4-lancement)
5. [Les activités pédagogiques](#5-les-activités-pédagogiques)
6. [Les jeux de données utilisés](#6-les-jeux-de-données-utilisés)
7. [Choix méthodologiques](#7-choix-méthodologiques)
8. [Mode simulation](#8-mode-simulation)
9. [Déploiement en ligne](#9-déploiement-en-ligne)
10. [Fiches HTML autonomes](#10-fiches-html-autonomes)
11. [Structure du projet](#11-structure-du-projet)
12. [Dépannage](#12-dépannage)
13. [Citer les données](#13-citer-les-données)

---

## 1. Ce que fait l'application

| Page | Contenu |
|---|---|
| **Accueil** | Vue d'ensemble, indicateurs, accès rapide |
| **Connexion CDS** | Configuration et diagnostic de la clé API |
| **Cartes** | Cartes de température, précipitations et pression, en cellules ou en isothermes |
| **Graphiques** | Séries temporelles, anomalies à la normale, tendance linéaire |
| **Villes** | Comparaison de villes, diagrammes ombrothermiques, indices climatiques |
| **Activités** | Sept séquences pédagogiques avec déroulé et corrigés |
| **Méthode** | Choix scientifiques, catalogue des jeux de données, citation |

L'application fonctionne **sans connexion** grâce à un jeu de données simulé,
ce qui permet de préparer une séance hors ligne. Toutes les figures issues de
ce mode portent la mention « DONNÉES SIMULÉES ».

---

## 2. Installation

### Prérequis

- **Python 3.10 ou supérieur** ([téléchargement](https://www.python.org/downloads/))
  — cochez **« Add Python to PATH »** à l'installation sous Windows.
- Une connexion Internet (pour le CDS et les fonds de carte).

### Installation des dépendances

Ouvrez une invite de commandes dans le dossier du projet, puis :

```bash
pip install -r requirements.txt
```

Vérifiez ensuite que tout est en place :

```bash
python verify_install.py
```

Le script affiche l'état de chaque dépendance, l'emplacement du fichier de
configuration et l'accessibilité du portail CDS.

---

## 3. Configuration de la clé API CDS

### 3.0 Quelle clé utiliser ? (la confusion la plus fréquente)

Trois identifiants se ressemblent, mais **le CDS n'en accepte qu'un seul**.

| Identifiant | Où le trouver | Sert au CDS ? |
|---|---|---|
| **Jeton d'accès personnel** (*Personal Access Token*) | Profil CDS → « Set up the CDS API personal access token » | ✅ **C'est celui-ci** |
| *Client ID* / *Client secret* | Profil ECMWF (ecmwf.int) | ❌ Réservés à l'**API Web ECMWF** (`webservices.ecmwf.int`) |
| Ancien couple `identifiant:secret` | Anciens fichiers `.cdsapirc` | ❌ Obsolète depuis septembre 2024 |

> **Le *Client ID* et le *Client secret* de votre compte ECMWF ne suffisent
> pas.** Ce sont des identifiants OAuth2 pour les services web de l'ECMWF, pas
> pour le Climate Data Store. Le CDS exige son propre jeton, affiché sur la page
> de votre profil CDS. *(Confirmation d'un responsable ECMWF : « il n'existe
> plus d'identifiant utilisateur au CDS ».)*

L'application vérifie le format du jeton avant toute tentative de connexion, et
signale explicitement ces trois cas.

### 3.1 Obtenir le jeton

1. Créez un compte gratuit sur le [Climate Data Store](https://cds.climate.copernicus.eu/user).
2. Connectez-vous, ouvrez la page *Your profile* (votre profil) et copiez le bloc
   **« Set up the CDS API personal access token »** : il contient deux lignes,
   `url:` et `key:`.
3. **Acceptez les conditions d'utilisation** de chaque jeu de données que vous
   souhaitez utiliser. Cette étape est obligatoire : sans elle, le CDS renvoie
   une erreur de permission, même avec un jeton parfaitement valide.

Le jeton est une **longue chaîne sur une seule ligne**, à coller telle quelle
après `key:`, sans guillemets ni espaces.

> **Procédure officielle ECMWF** : [How to install and use CDS API on Windows](https://confluence.ecmwf.int/spaces/CKB/pages/121847376/How+to+install+and+use+CDS+API+on+Windows)

### 3.2 Installer la clé

Trois méthodes, de la plus recommandée à la plus provisoire.

**a) Le script fourni (recommandé) :**

```powershell
.\install_cds_key.ps1
```

Le script demande la clé de manière masquée, vérifie son format, puis écrit
le fichier `%USERPROFILE%\.cdsapirc` — la méthode documentée par l'ECMWF.

**b) Le fichier `.env` du projet :**

Créez un fichier `.env` à la racine du projet contenant deux lignes :

```
CDSAPI_URL=https://cds.climate.copernicus.eu/api
CDSAPI_KEY=votre-jeton-d-acces-personnel
```

> ⚠️ **Une seule valeur par ligne.** Ne collez pas le bloc complet
> `url: … / key: …` : c'est le piège le plus fréquent, et l'application lira
> alors une clé fausse. `.env` est ignoré par git.

**c) Directement dans l'application :**

Page *Connexion CDS* → onglet « Saisie directe ». La valeur reste dans la
session du navigateur et n'est jamais écrite sur le disque ; il faut la
ressaisir après un redémarrage.

### 3.3 Accepter les conditions d'utilisation — **indispensable**

Une clé valide ne suffit pas. Le CDS vérifie **pour chaque jeu de données** que
vous avez accepté ses conditions ; sinon il répond
*« required licences not accepted »*.

Sur la page du jeu de données, descendez jusqu'en bas du formulaire et cliquez
sur **« Accept licence » / « Accepter »**. L'accord est définitif.

Les quatre pages nécessaires sont listées dans l'application (page *Connexion
CDS* → section 5), avec un bouton qui interroge le CDS et indique exactement
lesquelles restent à accepter.

En ligne de commande :

```bash
python -m c3s_lab.licence_check https://cds.climate.copernicus.eu/api <votre-clé>
```

### 3.4 Ordre de recherche de la configuration

| # | Source | Comment la définir |
|---|---|---|
| 1 | Saisie directe | Page *Connexion CDS* → onglet « Saisie directe » |
| 2 | Variables d'environnement | `CDSAPI_URL` et `CDSAPI_KEY` |
| 3 | `%USERPROFILE%\.cdsapirc` | **Méthode officielle ECMWF** |
| 4 | `.env` à la racine du projet | Fichier écrit par l'utilisateur |
| 5 | `.cdsapirc` du projet | Pour un déploiement en salle |

> ⚠️ **Sécurité.** Les fichiers `.env` et `.cdsapirc` contiennent la clé en clair.
> Ils sont ignorés par git (voir `.gitignore`) ; **`.env.example` ne l'est pas**
> et ne doit donc jamais recevoir la clé. Ne partagez pas ces fichiers sur une
> machine collective.

---

## 4. Lancement

```bash
streamlit run app.py
```

L'application s'ouvre sur <http://localhost:8501>. La barre latérale affiche en
permanence l'état de la connexion et permet de choisir la période de référence
climatique (normale OMM).

---

## 5. Les activités pédagogiques

| # | Activité | Niveau | Durée | Disciplines |
|---|---|---|---|---|
| 1 | Océan ou continent : pourquoi l'amplitude thermique change-t-elle ? | 5e / 4e | 55 min | SVT, Physique, Géographie |
| 2 | Le cycle de l'eau : d'où viennent les précipitations ? | 5e / 4e | 55 min | SVT, Physique |
| 3 | Mesurer le réchauffement climatique à partir des données | 4e / 3e | 55 min | SVT, Mathématiques |
| 4 | Pression atmosphérique et circulation du vent | 3e / 4e | 55 min | Physique, SVT |
| 5 | Construire et lire une carte climatique | 4e / 3e | 55 min | Géographie, SVT |
| 6 | Compter les jours de chaleur : construire un indice | 3e / 4e | 55 min | SVT, Mathématiques, EPS |
| 7 | Latitude et bilan radiatif : pourquoi fait-il froid aux pôles ? | 4e / 3e | 55 min | Physique, SVT |

Chaque fiche contient l'objectif, les compétences visées, le déroulé étape par
étape, les indices et les réponses attendues, ainsi qu'un conseil de mise en
œuvre. Elle est exportable en Markdown depuis l'interface.

### Compétences couvertes

- **SVT** — climat et ses variations, effet de serre, cycle de l'eau, cryosphère
- **Physique-chimie** — température, changements d'état, pression atmosphérique, rayonnement
- **Mathématiques** — moyenne, écart à une référence, tendance linéaire, lecture de graphiques
- **Géographie** — climats régionaux, lecture cartographique, risques climatiques
- **EPS / culture scientifique** — esprit critique sur les indicateurs

---

## 6. Les jeux de données utilisés

| Clé | Identifiant CDS | Fréquence | Résolution | Remarque |
|---|---|---|---|---|
| `monthly_means` | `reanalysis-era5-single-levels-monthly-means` | mensuel | 0,25° | Normales et tendances |
| `daily_stats` | `derived-era5-single-levels-daily-statistics` | quotidien | 0,25° | Comptage de jours |
| `pressure_levels` | `reanalysis-era5-pressure-levels-monthly-means` | mensuel | 0,25° | Circulation en altitude |
| `timeseries` | `reanalysis-era5-single-levels-timeseries` | horaire | point | Très léger, idéal pour débuter |

Variables principalement utilisées : `2m_temperature`, `total_precipitation`,
`mean_sea_level_pressure`, `10m_u_component_of_wind`, `10m_v_component_of_wind`.

---

## 7. Choix méthodologiques

Ces choix sont expliqués aux élèves dans l'interface (page *Méthode*), car ils
conditionnent la validité scientifique des résultats.

| Sujet | Choix retenu | Justification |
|---|---|---|
| Moyenne spatiale | Pondérée par `cos(latitude)` | Les cellules polaires sont plus petites ; sans cette pondération, l'Arctique serait surestimé |
| Point de mesure | Cellule la plus proche | Une interpolation lisserait les extrêmes, ce qui est moins honnête |
| Précision | 0,25° ≈ 25 km, soit ±14 km | Une maille n'est pas un point : l'incertitude de position est réelle |
| Normale | 1991-2020 (OMM) | Trente ans, la durée qui caractérise un climat |
| Anomalie | `valeur − normale` | Seule façon de rendre deux périodes comparables |
| Années | Uniquement les années à 12 mois | Une année à 3 mois fausserait la moyenne |
| Tendance | Moindres carrés | R² mesure l'ajustement, ce n'est pas une probabilité |
| Cartes | Cellules non lissées | Une interpolation invente des valeurs entre les points |
| Couleurs | Échelles séquentielles ou divergentes | Un arc-en-ciel fabrique des contours qui n'existent pas |

**À savoir sur ERA5** : c'est une *réanalyse*, c'est-à-dire un modèle couplé à
l'assimilation d'observations. Les précipitations sont une quantité **prévue**,
non assimilée. La version provisoire (ERA5T) peut être corrigée 2 à 3 mois plus
tard.

---

## 8. Mode simulation

Sans clé API, l'application génère un jeu de données synthétique pour rester
utilisable. Ce mode est adapté à la préparation de séances.

**Précautions :**
- Toutes les figures affichent un bandeau « DONNÉES SIMULÉES » en rouge.
- L'erreur du modèle atteint environ **4 °C** sur les températures de janvier et
  de juillet : les moyennes annuelles et les hivers sont proches des valeurs
  réelles, les étés sont sous-estimés de quelques degrés.
- Ces chiffres **ne doivent jamais** être communiqués comme des observations.

Pour basculer vers les données réelles, il suffit de configurer la clé : l'option
« Forcer les données simulées » de la barre latérale revient alors à la normale.

---

## 9. Déploiement en ligne

### Streamlit Community Cloud (recommandé)

Déploiement en trois clics, sans configuration.

1. Connectez-vous sur <https://share.streamlit.io> avec votre compte GitHub.
2. *New app* → sélectionnez le dépôt `Bamiel2025/C3S` → **Deploy**.
3. Dans *Settings → Secrets*, ajoutez :

   ```
   CDSAPI_KEY = <votre jeton d'accès personnel>
   CDSAPI_URL = https://cds.climate.copernicus.eu/api
   C3S_TEACHER_CODE = <votre code, si vous ne souhaitez pas laisser 2027 en clair>
   ```

L'application lit ces variables automatiquement (priorité 2 dans l'ordre de
recherche). Sans elles, elle démarre en mode simulation — ce qui reste utile
pour présenter l'interface à une classe.

L'URL publique obtenue est partageable telle quelle aux élèves.

### Le champ « Main file path »

Streamlit Community Cloud affiche un champ **Main file path** pré-rempli avec
`streamlit_app.py`, et signale *« This file does not exist »* si ce fichier
est absent du dépôt. C'est le cas le plus courant : `streamlit_app.py` est le
nom de fichier **par défaut** de la plateforme, pas une obligation technique.

Deux solutions, au choix :

| Solution | Ce qu'il faut faire |
|---|---|
| **Recommandée** | Ne rien changer : le dépôt contient `streamlit_app.py`, qui délègue à `app.py`. Le champ reste sur sa valeur par défaut. |
| Alternative | Saisir `app.py` à la place de `streamlit_app.py` dans le champ, **avec le dossier du dépôt bien spécifié** au-dessus. |

Le dépôt fournit `streamlit_app.py` pour éviter l'erreur : il ne contient que
deux lignes utiles, qui évitent d'avoir à se souvenir du chemin.

```python
# streamlit_app.py
import app

app.main()
```

> Si vous déployez en copiant manuellement des fichiers plutôt que le dépôt
> GitHub, vérifiez que `streamlit_app.py` se trouve **à la racine** du dépôt :
> c'est sa racine qui est analysée, pas le dossier où vous vous situez.

### La clé CDS en ligne

En local, la clé est lue dans votre fichier `.env` ou `.cdsapirc`. **Ces fichiers
ne sont pas versionnés** (voir `.gitignore`) : c'est volontaire, pour qu'aucun
jeton ne soit publié. Sur un déploiement, ils sont donc absents, et la clé doit
être déclarée par l'administrateur.

Dans **Settings → Secrets** de Streamlit Community Cloud, ajoutez :

```toml
CDSAPI_URL = "https://cds.climate.copernicus.eu/api"
CDSAPI_KEY = "<votre jeton d'accès personnel>"
```

Puis **Manage app → Restart** : les secrets ne sont lus qu'au démarrage.

> Les noms sont sensibles à la casse et ne doivent pas contenir d'espace. Un
> `CDSAPI_KEY` écrit avec des guillemets simples, ou `CDS API KEY`, sera ignoré
> silencieusement — l'application basculera alors en mode simulation.

Tant que la clé manque, la barre latérale l'affiche clairement, et l'onglet
*Connexion CDS* reste inaccessible aux élèves : c'est normal et sans risque.

### Pourquoi pas Vercel ?

Streamlit Communique avec le navigateur par **WebSockets** (serveur Tornado).
Or les fonctions serverless de Vercel ne gèrent les WebSockets que sur les
offres payantes avec *Fluid compute*. Sur le plan gratuit, aucun contournement
n'est possible.

De plus, Vercel intercepte `app.py` comme point d'entrée d'une fonction
Python, et exige qu'elle exporte une variable `app`, `application` ou `handler`
de type ASGI/WSGI — ce qu'un script Streamlit ne peut pas faire.

La vraie raison décisive : même avec un contournement, les requêtes ERA5
prennent de 30 secondes à plusieurs minutes, alors que les fonctions serverless
sont interrompues bien avant.

### Contrainte de version de Python

Le fichier `runtime.txt` épingle **Python 3.11**. Ce n'est pas arbitraire :
`netCDF4` ne publie pas de roue binaire pour Python 3.12 et 3.13. Sans cet
épinglage, `pip` tenterait de compiler la bibliothèque HDF5 depuis les sources,
ce qui échoue ou prend très longtemps sur une plateforme de déploiement.

### Système de fichiers en lecture seule

Les plateformes de déploiement montent le code en lecture seule. L'application
le détecte et bascule son cache vers un dossier temporaire inscriptible ; un
message l'indique dans la barre latérale. Conséquence : le cache n'est pas
conservé entre les sessions, la première requête de chaque séance est plus
lente.

---

## 10. Fiches HTML autonomes

En plus de l'application en ligne, le projet produit **dix fiches HTML
autonomes** : chaque activité devient un fichier unique contenant ses
graphiques, ses cartes, ses consignes et ses réponses attendues. Ces fichiers
s'ouvrent sans connexion ni installation — sur un vidéoprojecteur, une clé USB
ou par courriel aux familles.

```bash
python export_activities.py          # les dix fiches + la page d'accueil
python export_activities.py 08 09    # seulement celles qui commencing par 08, 09
```

Les fichiers sont écrits dans `activites_html/`. Ouvrez `index.html` pour la
liste complète.

| Fiche | Activité |
|---|---|
| `01_ocean_continent` | Océan ou continent : amplitude thermique |
| `02_cycle_eau` | Le cycle de l'eau et les précipitations |
| `03_rechauffement_climatique` | Mesurer le réchauffement climatique |
| `04_pression_vent` | Pression atmosphérique et circulation du vent |
| `05_cartes_climatiques` | Construire et lire une carte climatique |
| `06_canicule` | Compter les jours de chaleur |
| `07_latitude_rayonnement` | Latitude et bilan radiatif |
| `08_bordeaux_montreal` | **Bordeaux et Montréal : mêmes latitudes, climats opposés** |
| `09_meteo_climat` | **Météorologie et climatologie** |
| `10_origine_rechauffement` | **Origine et causes du réchauffement (Aubagne)** |

Toutes les fiches sont th **Sciences de la vie et de la Terre**, avec les
graphiques et cartes issus de vraies données ERA5 téléchargées sur le CDS.

### Corrigés masqués

Les réponses attendues sont **repliées** dans chaque fiche : la fiche peut être
projetée aux élèves sans risque. Deux moyens de tout déplier :

- le bouton en haut de la fiche ;
- l'ajout de `?corriges=1` à l'adresse du fichier.

### Préparation préalable

Ces fiches utilisent des données réelles. Avant la première génération, il faut
pré-télécharger les séries utilisées, sans quoi chaque fiche déclencherait des
requêtes au CDS — lentes, et comptabilisées dans votre quota quotidien :

```bash
python prepare_data.py
```

Le rendu des images demande **Kaleido** (`pip install kaleido`), déjà présent
dans `requirements.txt`.

## 11. Structure du projet

```
C3S/
├── app.py                    Application Streamlit (7 pages)
├── requirements.txt          Dépendances
├── verify_install.py         Diagnostic de l'installation
├── install_cds_key.ps1       Configuration de la clé sous Windows
├── test_pages.py             Test de non-régression (pages + activités)
├── test_key_diagnosis.py     Test du diagnostic de clé API
├── .env.example              Modèle de configuration
│
├── c3s_lab/
│   ├── config.py             Chemins, réglages, résolution de la clé CDS
│   ├── cds_client.py         Connexion, test, téléchargement, cache
│   ├── catalog.py            Catalogue des jeux de données CDS
│   ├── data.py               Point d'entrée unifié (réel ou simulé)
│   ├── places.py             Villes et domaines géographiques
│   ├── analysis.py           Normales, anomalies, tendances, indices
│   ├── viz.py                Graphiques interactifs
│   ├── maps.py               Cartes scientifiques
│   ├── basemaps.py           Fonds de carte Natural Earth
│   ├── demo.py               Données simulées (mode hors ligne)
│   ├── activities.py         Définition des activités
│   └── ui.py                 Composants d'interface partagés
│
└── data/                     Cache NetCDF, fonds de carte, exports
```

### Tests

```bash
python test_pages.py          # pages + activités
python test_key_diagnosis.py  # diagnostic de clé
python test_live_cds.py       # chemin réel (interroge le portail)
```

Le premier exécute les sept pages et les sept activités et signale toute
exception. Résultats attendus : `14/14 tests sans exception` et
`7/7 cas de diagnostic corrects`.

---

## 12. Dépannage

**« Aucune clé CDS — mode simulation »**
La clé n'a pas été détectée. Lancez `python verify_install.py` pour connaître
l'emplacement attendu, ou configurez-la depuis la page *Connexion CDS*.

**« Le CDS a refusé la requête »**
Trois causes possibles :
1. **Licences non acceptées** — c'est la cause la plus fréquente. Ouvrez la page
   de chaque jeu de données sur le CDS et acceptez les conditions.
2. **Clé expirée ou mal copiée** — régénérez-la depuis votre profil.
3. **Requête trop volumineuse** — réduisez la période ou le domaine
   géographique.

**Le téléchargement est très lent**
C'est normal pour la première requête : ERA5 produit plusieurs gigaoctets par
jour. Limitez-vous à une zone restreinte. Les fichiers sont ensuite mis en cache
dans `data/cache/`.

**Erreur `UnicodeEncodeError` sous Windows**
La console n'est pas en UTF-8. Lancez Streamlit avec :
```powershell
$env:PYTHONUTF8 = "1"
streamlit run app.py
```

**Carte qui ne s'affiche pas**
Vérifiez que les fonds de carte ont été téléchargés (page *Méthode*, bouton
« Télécharger les fonds de carte »). Sans réseau, l'application bascule sur un
affichage sans contours.

---

## 13. Citer les donn

Dans tout travail scolaire ou publication utilisant ces figures :

> **Hersbach, H., Bell, B., Berrisford, P., et al. (2020).** The ERA5 global
> reanalysis. *Quarterly Journal of the Royal Meteorological Society*, 146(730),
> 1999-2049. <https://doi.org/10.1002/qj.3803>
>
> *Generated using Copernicus Climate Change Service information 2024
> (C3S/CAMS), with the appropriate credit.*

Licence : **CC BY 4.0**. Fonds de carte : **Natural Earth** (domaine public).

---

## Liens utiles

- [Climate Data Store](https://cds.climate.copernicus.eu) — portail de téléchargement
- [Procédure d'installation du CDS API sous Windows (ECMWF)](https://confluence.ecmwf.int/spaces/CKB/pages/121847376/How+to+install+and+use+CDS+API+on+Windows)
- [Copernicus Climate Change Service](https://climate.copernicus.eu)
