"""
Activités pédagogiques clé en main, rattachées aux programmes de cycle 4.

Chaque activité est décrite par une fiche (`Activity`) que l'interface affiche et
par une fonction de production (`build`) qui assemble les graphiques et les
tableaux à projeter. Les activités couvrent les trois entrées du programme :

* **Sciences de la vie et de la Terre** — climat, effet de serre, cycle de l'eau ;
* **Physique-chimie** — température, changements d'état, pression atmosphérique ;
* **Mathématiques** — moyenne, écart, tendance, lecture de graphiques ;
* **Géographie** — climats régionaux, risques, adaptation.

Les durées sont indicatives pour une séance de 55 minutes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from . import analysis, catalog, places, viz


@dataclass
class Step:
    """Une étape d'activité : consigne, réponse attendue, prolongement."""

    title: str
    instruction: str
    expected: str = ""
    hint: str = ""


@dataclass
class Activity:
    """Fiche d'activité pédagogique."""

    key: str
    title: str
    levels: str
    duration: str
    subject: str
    dataset: str
    variables: tuple[str, ...]
    objective: str
    skills: tuple[str, ...]
    steps: tuple[Step, ...]
    #: Villes proposées par défaut pour l'activité.
    default_places: tuple[str, ...] = ()
    reference: tuple[int, int] = (1991, 2020)
    #: Conseil de mise en œuvre affiché à l'enseignant.
    teacher_tip: str = ""
    difficulty: int = 1



ACTIVITIES: list[Activity] = [
    Activity(
        key="saisons_occean_continent",
        title="Océan ou continent : pourquoi l'amplitude thermique change-t-elle ?",
        levels="5e / 4e",
        duration="55 min",
        subject="SVT · Physique-chimie · Géographie",
        dataset="monthly_means",
        variables=("2m_temperature",),
        objective=(
            "Comprendre qu'un même écart de latitude peut produire des climats très "
            "différents, et relier l'amplitude thermique annuelle à la distance à la mer."
        ),
        skills=(
            "Lire un graphique en courbes et un diagramme ombrothermique",
            "Calculer une moyenne et un écart",
            "Expliquer un résultat par un mécanisme (inertie thermique)",
        ),
        default_places=("Brest", "Strasbourg", "Lyon", "Marseille"),
        steps=(
            Step(
                title="1. Décrire les courbes",
                instruction=(
                    "Lancer l'activité avec Brest et Strasbourg. Décrire la forme des deux "
                    "courbes : où se situent les minimums et les maximums ? Quelle est la ville "
                    "la plus « plate » ?"
                ),
                expected=(
                    "Brest a une courbe de faible amplitude, des extrêmes peu marqués ; "
                    "Strasbourg a des hivers très froids et des étés chauds."
                ),
                hint="Regardez l'écart entre le point le plus bas et le point le plus haut.",
            ),
            Step(
                title="2. Mesurer l'amplitude",
                instruction=(
                    "Lire dans le tableau des indices l'amplitude thermique de chaque "
                    "ville, puis noter les valeurs dans un tableau commun à la classe."
                ),
                expected=(
                    "Brest ≈ 15 °C, Strasbourg ≈ 25 °C : une dizaine de degrés d'écart "
                    "alors que les deux villes sont à la même latitude."
                ),
            ),
            Step(
                title="3. Expliquer",
                instruction=(
                    "Formuler une hypothèse : qu'est-ce qui explique cette différence ? "
                    "Employer l'expression « inertie thermique » dans la réponse."
                ),
                expected=(
                    "L'océan se réchauffe et se refroidit lentement, ce qui lisse les "
                    "températures du littoral. Les terres font l'inverse."
                ),
                hint="Qui chauffe le plus vite en été, la pierre ou l'eau ? Justifiez.",
            ),
            Step(
                title="4. Transférer",
                instruction=(
                    "Ajouter une troisième ville au groupe (Lyon ou Marseille) et prédire "
                    "la forme de sa courbe avant de l'afficher."
                ),
                expected=(
                    "Marseille a une faible amplitude mais un été chaud : la mer tempère "
                    "l'hiver sans rafraîchir l'été."
                ),
            ),
        ),
        teacher_tip=(
            "Projeter le graphique avant les questions et laisser les élèves émettre leurs "
            "hypothèses au tableau. Le passage du graphique à l'explication mécanique est "
            "le cœur de la séance."
        ),
    ),
    Activity(
        key="cycle_eau_precipitations",
        title="Le cycle de l'eau : d'où viennent les précipitations ?",
        levels="5e / 4e",
        duration="55 min",
        subject="SVT · Physique-chimie (changements d'état)",
        dataset="monthly_means",
        variables=("total_precipitation", "2m_temperature"),
        objective=(
            "Relier l'évaporation et la condensation aux précipitations mesurées, et "
            "distinguer un régime équatorial d'un régime méditerranéen."
        ),
        skills=(
            "Construire et lire un diagramme ombrothermique",
            "Identifier un changement d'état dans un graphique",
            "Comparer des cumuls mensuels",
        ),
        default_places=("Marseille", "Brest", "Dakar", "Bordeaux"),
        steps=(
            Step(
                title="1. Repérer les extrêmes",
                instruction=(
                    "Sélectionner Marseille et Dakar. Comparer les douze mois des deux villes, "
                    "puis indiquer le mois le plus humide et le mois le plus sec pour chacune."
                ),
                expected=(
                    "Dakar est humide en été (mousson) ; Marseille est sèche en été."
                ),
            ),
            Step(
                title="2. Relier température et pluie",
                instruction=(
                    "Sur le diagramme ombrothermique, repérer les mois où la température "
                    "augmente. Décrire ce que deviennent les barres de pluie sur la même "
                    "période, puis expliquer le lien entre les deux."
                ),
                expected=(
                    "Quand la température augmente, l'air peut contenir plus de vapeur d'eau : "
                    "l'évaporation alimente la pluie. C'est le mécanisme de la mousson."
                ),
                hint="Reliez les mots « évaporation » et « condensation » aux deux courbes.",
            ),
            Step(
                title="3. Changer d'échelle",
                instruction=(
                    "Comparer les cumuls annuels des deux villes. Une ville peut-elle être "
                    "sèche en été et humide en hiver ? Justifier avec les données."
                ),
                expected=(
                    "Un cumul annuel élevé peut masquer un été très sec : la saisonnalité "
                    "compte autant que le total."
                ),
            ),
        ),
        teacher_tip=(
            "Rappeler l'expérience de la serre : l'air chaud chargé de vapeur se refroidit "
            "et se condense. Le nuage et la pluie ne sont que cela, à l'échelle du continent."
        ),
    ),
    Activity(
        key="rechauffement_climatique",
        title="Mesurer le réchauffement climatique à partir des données",
        levels="4e / 3e",
        duration="55 min",
        subject="SVT · Mathématiques",
        dataset="monthly_means",
        variables=("2m_temperature",),
        objective=(
            "Construire une courbe d'anomalies, estimer une tendance par décennie et "
            "discuter ce que cette tendance permet — et ne permet pas — d'affirmer."
        ),
        skills=(
            "Calculer un écart à une moyenne de référence",
            "Lire une tendance et son coefficient directeur",
            "Distinguer variabilité naturelle et tendance de fond",
        ),
        default_places=("Paris", "Strasbourg"),
        steps=(
            Step(
                title="1. Définir la normale",
                instruction=(
                    "Choisir la période de référence. Expliquer pourquoi on compare chaque "
                    "année à une moyenne calculée sur plusieurs années."
                ),
                expected=(
                    "La normale sert de point de comparaison : on parle alors d'anomalie, "
                    "et non de température absolue."
                ),
                hint="Que signifierait un écart de +2 °C si l'on ne disait pas par rapport à quoi ?",
            ),
            Step(
                title="2. Décrire l'évolution",
                instruction=(
                    "Sur le diagramme en barres, repérer les années les plus chaudes et les "
                    "plus froides. Décrire l'évolution générale : la température "
                    "augmente-t-elle ou diminue-t-elle sur l'ensemble de la période ?"
                ),
                expected=(
                    "La tendance est à la hausse malgré des années plus froides isolées : "
                    "c'est la variabilité naturelle, qui n'infirme pas la tendance."
                ),
            ),
            Step(
                title="3. Quantifier",
                instruction=(
                    "Lire la tendance par décennie affichée, puis la comparer à l'amplitude "
                    "des barres d'une année à l'autre."
                ),
                expected=(
                    "Une tendance de l'ordre de +0,2 à +0,3 °C par décennie se lit sur des "
                    "décennies, jamais sur deux années consécutives."
                ),
            ),
            Step(
                title="4. Critiquer",
                instruction=(
                    "Rédiger une phrase prudente résumant ce que les données permettent "
                    "d'affirmer, et une indiquant ce qu'elles ne permettent pas d'affirmer."
                ),
                expected=(
                    "On peut affirmer une hausse sur plusieurs décennies ; on ne peut pas "
                    "dater précisément le début du phénomène avec ce seul graphique."
                ),
            ),
        ),
        teacher_tip=(
            "Insister sur la normale 1991-2020 de l'OMM. Comparer une période à elle-même "
            "est la seule méthode qui rende les chiffres comparables entre villes et entre pays."
        ),
        difficulty=2,
    ),
    Activity(
        key="vent_pression",
        title="Pression atmosphérique et circulation du vent",
        levels="3e (physique) · 4e",
        duration="55 min",
        subject="Physique-chimie · SVT",
        dataset="monthly_means",
        variables=("mean_sea_level_pressure", "10m_u_component_of_wind", "10m_v_component_of_wind"),
        objective=(
            "Relier les zones de hautes et de basses pressions à la direction du vent, et "
            "comprendre pourquoi les vents soufflent des zones hautes vers les zones basses."
        ),
        skills=(
            "Lire des isobares",
            "Interpréter un vecteur vent",
            "Relier pression et mouvement de l'air",
        ),
        default_places=("Paris",),
        steps=(
            Step(
                title="1. Lire la pression",
                instruction=(
                    "Afficher la carte de pression en isobares. Repérer la valeur la plus "
                    "basse et la plus haute de la carte."
                ),
                expected=(
                    "La valeur de référence de la pression atmosphérique au niveau de la "
                    "mer est d'environ 1013 hPa."
                ),
            ),
            Step(
                title="2. Observer les vents",
                instruction=(
                    "Superposer la carte des vents. Les flèches partent-elles des zones de "
                    "hautes pressions vers les zones de basses pressions ?"
                ),
                expected=(
                    "Oui : l'air s'écoule des zones où la pression est élevée vers celles "
                    "où elle est faible, en se déviant à cause de la rotation de la Terre."
                ),
            ),
            Step(
                title="3. Expliquer",
                instruction=(
                    "Formuler une explication en utilisant la différence de pression comme "
                    "cause du mouvement. Que se passerait-il si la pression était uniforme ?"
                ),
                expected=(
                    "Sans gradient de pression, l'air ne serait pas accéléré : il n'y "
                    "aurait pas de vent."
                ),
            ),
        ),
        teacher_tip=(
            "Rappeler que le vent n'est pas horizontal : il s'incline le long des isobares "
            "à cause de la force de Coriolis. C'est ce qui explique qu'il tourne autour "
            "des dépressions dans l'hémisphère nord."
        ),
        difficulty=3,
    ),
    Activity(
        key="cartes_climatiques",
        title="Construire et lire une carte climatique",
        levels="4e / 3e",
        duration="55 min",
        subject="Géographie · SVT",
        dataset="monthly_means",
        variables=("2m_temperature", "total_precipitation"),
        objective=(
            "Lire une carte de températures ou de précipitations, choisir une échelle de "
            "couleurs adaptée, et distinguer climat et météo."
        ),
        skills=(
            "Lire une carte thématique",
            "Choisir une échelle de couleurs non trompeuse",
            "Distinguer une moyenne d'une situation ponctuelle",
        ),
        default_places=("Paris",),
        steps=(
            Step(
                title="1. Choisir la carte",
                instruction=(
                    "Sélectionner la carte des températures de janvier pour l'Europe. "
                    "Repérer le point le plus froid et le plus chaud."
                ),
                expected=(
                    "Le nord-est de l'Europe est le plus froid ; les côtes atlantiques et "
                    "la Méditerranée sont plus chaudes."
                ),
            ),
            Step(
                title="2. Changer l'échelle",
                instruction=(
                    "Passer de la carte en cellules à la carte en isothermes. Quelle "
                    "représentation est la plus facile à lire pour l'œil ?"
                ),
                expected=(
                    "Les isothermes permettent de suivre un même niveau de température ; "
                    "la carte en couleurs montre mieux les contrastes."
                ),
            ),
            Step(
                title="3. Climat ou météo ?",
                instruction=(
                    "Un échantillon de la même série sur trois ans suffit-il à décrire un "
                    "climat ? Justifier avec la notion de normale."
                ),
                expected=(
                    "Non : un climat se décrit sur au moins trente ans. Trois ans relèvent "
                    "de la météo, c'est-à-dire de l'état ponctuel de l'atmosphère."
                ),
                hint="Quelle durée l'OMM utilise-t-elle pour définir une normale ?",
            ),
        ),
        teacher_tip=(
            "Insister sur le fait qu'une carte de moyennes n'est pas une carte du temps. "
            "C'est la confusion la plus fréquente, et la plus coûteuse en examen."
        ),
        difficulty=2,
    ),
    Activity(
        key="canicule_sante",
        title="Compter les jours de chaleur : construire un indice",
        levels="3e · 4e",
        duration="55 min",
        subject="SVT · Mathématiques · EPS",
        dataset="daily_stats",
        variables=("2m_temperature",),
        objective=(
            "Compter des jours de canicule avec un critère à deux seuils et discuter du "
            "rôle de ce choix dans le résultat obtenu."
        ),
        skills=(
            "Définir un critère de comptage",
            "Utiliser des données journalières",
            "Sensibiliser au rôle du seuil dans une statistique",
        ),
        default_places=("Marseille", "Paris", "Brest"),
        steps=(
            Step(
                title="1. Fixer un seuil",
                instruction=(
                    "Choisir une valeur de seuil pour la température maximale (par exemple "
                    "35 °C), puis annoncer le nombre de jours que l'on s'attend à trouver "
                    "sur la période choisie."
                ),
                expected=(
                    "L'élève doit formuler une hypothèse chiffrée avant de regarder le "
                    "résultat, qui sera notée au tableau."
                ),
            ),
            Step(
                title="2. Compter et vérifier",
                instruction=(
                    "Lancer le comptage, puis comparer le nombre obtenu à l'hypothèse. "
                    "L'écart est-il important ? Expliquer pourquoi."
                ),
                expected=(
                    "L'hypothèse est souvent trop basse : les élèves sous-estiment la "
                    "fréquence des journées de forte chaleur."
                ),
            ),
            Step(
                title="3. Changer de définition",
                instruction=(
                    "Exiger maintenant aussi un minimum nocturne supérieur à 20 °C, "
                    "recalculer, puis comparer les deux comptages."
                ),
                expected=(
                    "Le second comptage est plus faible : une journée très chaude suivie "
                    "d'une nuit fraîche ne constitue pas une vraie nuit de canicule."
                ),
            ),
            Step(
                title="4. En déduire",
                instruction=(
                    "Le résultat dépend du seuil retenu. En déduire ce qu'il faudrait "
                    "imposer pour qu'un nombre annoncé constitue un indicateur solide."
                ),
                expected=(
                    "Un seuil unique, publié et identique pour toutes les villes, calculé "
                    "sur une période d'au moins trente ans."
                ),
            ),
        ),
        teacher_tip=(
            "Activité très riche en mathématiques : elle montre qu'un indicateur est un "
            "choix, pas une donnée. À prolonger par un débat sur les seuils d'alerte canicule."
        ),
        difficulty=3,
    ),
    Activity(
        key="latitude_rayonnement",
        title="Latitude et bilan radiatif : pourquoi fait-il froid aux pôles ?",
        levels="4e / 3e",
        duration="55 min",
        subject="Physique-chimie · SVT",
        dataset="monthly_means",
        variables=("2m_temperature",),
        objective=(
            "Relier la baisse de température avec la latitude à l'inclinaison des rayons "
            "solaires, en s'appuyant sur des données réelles."
        ),
        skills=(
            "Utiliser des données pour valider un raisonnement",
            "Construire un graphique à partir d'un tableau",
            "Rédiger une conclusion fondée sur des mesures",
        ),
        default_places=("Dakar", "Paris", "Reykjavik", "Longyearbyen"),
        steps=(
            Step(
                title="1. Prévoir",
                instruction=(
                    "Sans regarder les données, classer ces quatre villes de la plus chaude "
                    "à la plus froide en janvier. Écrire ce classement."
                ),
                expected=(
                    "Le classement spontané est souvent proche du bon, ce qui ne suffit pas "
                    "à le prouver."
                ),
            ),
            Step(
                title="2. Vérifier",
                instruction=(
                    "Afficher les températures de janvier et comparer au classement prédit. "
                    "Quelles villes déçoivent ?"
                ),
                expected=(
                    "Reykjavik est plus chaude qu'attendu pour sa latitude : le Gulf Stream "
                    "et l'océan Atlantique nord la réchauffent."
                ),
            ),
            Step(
                title="3. Expliquer",
                instruction=(
                    "Formuler l'explication du rôle de l'inclinaison des rayons. Qu'est-ce "
                    "qui change pour une même quantité de lumière reçue ?"
                ),
                expected=(
                    "À latitude élevée, les rayons sont plus obliques : la même énergie est "
                    "répartie sur une surface plus grande, donc l'échauffement est moindre."
                ),
                hint="Pensez à un faisceau de lumière et à la surface qu'il éclaire.",
            ),
            Step(
                title="4. Nuancer",
                instruction=(
                    "La latitude explique-t-elle tout ? Donner un contre-exemple tiré des "
                    "données de l'activité sur l'amplitude thermique."
                ),
                expected=(
                    "Non : la distance à la mer et l'altitude modifient fortement la "
                    "température, comme l'écart entre Brest et Strasbourg le montrait."
                ),
            ),
        ),
        teacher_tip=(
            "Dérouler l'activité en deux temps : d'abord la prédiction écrite, ensuite "
            "seulement la donnée. C'est la confrontation qui produit l'apprentissage."
        ),
        difficulty=2,
    ),
]


def get(key: str) -> Activity:
    """Renvoie une activité à partir de sa clé."""
    for activity in ACTIVITIES:
        if activity.key == key:
            return activity
    raise KeyError(
        f"Activité inconnue : {key!r}. Disponibles : {[a.key for a in ACTIVITIES]}"
    )


def as_options() -> list[tuple[str, str]]:
    """Liste (clé, titre) pour le menu déroulant de l'interface."""
    return [(a.key, a.title) for a in ACTIVITIES]


def by_level(level: str) -> list[Activity]:
    """Activités compatibles avec un niveau (5e, 4e, 3e, cycle 4…)."""
    needle = level.strip().lower()
    return [a for a in ACTIVITIES if needle in a.levels.lower()]


def summary_table() -> list[dict[str, Any]]:
    """Tableau de bord des activités, pour la page d'accueil."""
    return [
        {
            "Activité": a.title,
            "Niveau": a.levels,
            "Durée": a.duration,
            "Disciplines": a.subject,
            "Jeu de données": catalog.get(a.dataset).label,
            "Difficulté": "●" * a.difficulty + "○" * (3 - a.difficulty),
        }
        for a in ACTIVITIES
    ]
