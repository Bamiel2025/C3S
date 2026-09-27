"""
Villes, régions et domaines géographiques utilisés dans les activités.

Les coordonnées sont en degrés décimaux (latitude, longitude) au format WGS84,
c'est-à-dire dans le même système que la grille ERA5. L'altitude est donnée
en mètres : elle sert à illustrer le gradient thermique, car la température
ERA5 à 2 m est déjà ramenée au niveau du sol et ne « descend » pas avec
l'altitude de la station.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Place:
    """Une ville ou un point d'intérêt climatique."""

    name: str
    lat: float
    lon: float
    altitude: float = 0.0
    region: str = ""
    coastal: bool = False
    country: str = "France"
    #: Intérêt pédagogique associé, repris dans les activités.
    tag: str = ""


# --------------------------------------------------------------------------- #
# Villes françaises
# --------------------------------------------------------------------------- #

FRENCH_CITIES: tuple[Place, ...] = (
    Place("Paris", 48.86, 2.35, 35, "Île-de-France", True, tag="climat océanique atténué, influence urbaine"),
    Place("Brest", 48.39, -4.49, 60, "Bretagne", True, tag="climat océanique : amplitude faible"),
    Place("Nantes", 47.22, -1.55, 30, "Pays de la Loire", True, tag="transition océanique / continental"),
    Place("Bordeaux", 44.84, -0.58, 49, "Nouvelle-Aquitaine", True, tag="climat océanique aquitain, été sec"),
    Place("Marseille", 43.30, 5.37, 12, "Provence-Alpes-Côte d'Azur", True, tag="climat méditerranéen, été sec et caniculaire"),
    Place("Toulouse", 43.60, 1.44, 140, "Occitanie", False, tag="climat océanique dégradé, été chaud"),
    Place("Lyon", 45.76, 4.84, 165, "Auvergne-Rhône-Alpes", False, tag="continental atténué par l'altitude du site"),
    Place("Clermont-Ferrand", 45.78, 3.09, 390, "Auvergne-Rhône-Alpes", False, tag="continental, effet du relief"),
    Place("Strasbourg", 48.57, 7.75, 140, "Grand Est", False, tag="climat continental, hiver froid"),
    Place("Nancy", 48.69, 6.18, 220, "Grand Est", False, tag="forte continentalité"),
    Place("Paris — La Villette", 48.89, 2.36, 40, "Île-de-France", False, tag="exemple simplifié : Paris"),
    Place("Reykjavik", 64.15, -21.94, 61, "Island", True, country="Islande", tag="climat subarctique océanique"),
    Place("Bordeaux — Lac", 44.93, -0.72, 20, "Nouvelle-Aquitaine", True, tag="micro-climat d'eau douce"),
    Place("Le Puy-en-Velay", 45.04, 3.88, 625, "Auvergne-Rhône-Alpes", False, tag="altitude et gradient thermique"),
    Place("Grenoble", 45.19, 5.72, 212, "Auvergne-Rhône-Alpes", False, tag="continentale, plaine alpine"),
    Place("Ajaccio", 41.93, 8.74, 5, "Corse", True, tag="méditerranéen insulaire"),
    Place("Lille", 50.63, 3.06, 25, "Hauts-de-France", False, tag="transition océanique / continental"),
    Place("Caen", 49.18, -0.37, 20, "Normandie", True, tag="climat océanique normand"),
    Place("Perpignan", 42.69, 2.90, 30, "Occitanie", True, tag="méditerranéen insulaire, été très sec"),
    Place("Annecy", 45.90, 6.13, 448, "Auvergne-Rhône-Alpes", False, tag="climat montagnard lacustre"),
)


def fr_cities(coastal_only: bool = False) -> list[Place]:
    return [c for c in FRENCH_CITIES if c.coastal] if coastal_only else list(FRENCH_CITIES)


# --------------------------------------------------------------------------- #
# Villes du monde (comparaisons internationales)
# --------------------------------------------------------------------------- #

WORLD_CITIES: tuple[Place, ...] = (
    Place("Dakar", 14.69, -17.44, 22, "Afrique de l'Ouest", True, "Sénégal", tag="climat tropical sec et chaud"),
    Place("Bangalore", 12.97, 77.59, 920, "Inde", False, "Inde", tag="monsoon, saison très contrastée"),
    Place("Paris", 48.86, 2.35, 35, "Île-de-France", True, "France", tag="tempéré océanique"),
    Place("New York", 40.71, -74.01, 10, "Amérique du Nord", True, "États-Unis", tag="continental humide"),
    Place("Le Caire", 30.04, 31.24, 23, "Afrique du Nord", False, "Égypte", tag="désertique chaud"),
    Place("Tokyo", 35.68, 139.65, 40, "Asie de l'Est", True, "Japon", tag="monsoon humide"),
    Place("Ushuaia", -54.80, -68.30, 23, "Amérique du Sud", True, "Argentine", tag="climat polaire maritime"),
    Place("Sydney", -33.87, 151.21, 58, "Australie", True, "Australie", tag="hémisphère sud : saisons inversées"),
    Place("Longyearbyen", 78.22, 15.65, 30, "Svalbard", True, "Norvège", tag="climat polaire, été frais malgré la continuité"),
    Place("Singapore", 1.35, 103.82, 15, "Asie du Sud-Est", True, "Singapour", tag="tropical humide, équatorial"),
    Place("Moscow", 55.75, 37.62, 156, "Europe de l'Est", False, "Russie", tag="continental très contrasté"),
    Place("Mexico", 19.43, -99.13, 2240, "Amérique du Nord", False, "Mexique", tag="altitude et saison des pluies"),
)


# --------------------------------------------------------------------------- #
# Domaines géographiques
#
# Le CDS attend `area = [Nord, Ouest, Sud, Est]` en degrés décimaux
# (attention à l'ordre, qui n'est pas celui d'une bbox usuelle).
# L'ordre par défaut est `[90, -180, -90, 180]`, soit le monde entier.
# --------------------------------------------------------------------------- #

WORLD = (90.0, -180.0, -90.0, 180.0)


@dataclass(frozen=True)
class Domain:
    """Un domaine géographique nommé."""

    name: str
    area: tuple[float, float, float, float]
    description: str
    #: Taille typique d'un fichier mensuel annuel, en Mo (ordre de grandeur).
    size_hint_mb: float = 10.0


DOMAINS: tuple[Domain, ...] = (
    Domain("Monde", WORLD, "Planète entière.", 120.0),
    Domain("Europe", (72.0, -25.0, 33.0, 45.0), "Europe occidentale et centrale.", 30.0),
    Domain("Europe de l'Ouest", (62.0, -12.0, 36.0, 12.0), "France, Benelux, Royaume-Uni, nord de l'Espagne.", 18.0),
    Domain("France métropolitaine", (51.5, -5.5, 41.0, 10.0), "Hexagone et Corsique.", 12.0),
    Domain("Méditerranée occidentale", (45.0, -2.0, 30.0, 25.0), "Bassin méditerranéen, climaticement contrasté.", 20.0),
    Domain("Afrique de l'Ouest", (20.0, -20.0, 0.0, 20.0), "Golfe de Guinée et Sahel.", 20.0),
    Domain("Arctique", (90.0, -180.0, 60.0, 180.0), "Cercle polaire arctique et au-delà.", 60.0),
    Domain("Hémisphère nord", (90.0, -180.0, 0.0, 180.0), "Du nord de l'équateur au pôle Nord.", 60.0),
    Domain("Hémisphère sud", (0.0, -180.0, -90.0, 180.0), "De l'équateur au pôle Sud.", 60.0),
    Domain("Tropiques", (23.5, -180.0, -23.5, 180.0), "Bande tropicale, là où le changement est le plus rapide.", 55.0),
    Domain("Amerique du Nord", (84.0, -170.0, 7.0, -50.0), "Canada, États-Unis, Mexique, Caraïbes.", 55.0),
    Domain("Asie", (82.0, 25.0, -12.0, 180.0), "De la Sibérie à l'équateur.", 70.0),
)


def domain_options() -> list[tuple[str, Domain]]:
    return [(d.name, d) for d in DOMAINS]


def area_from_bounds(north: float, west: float, south: float, east: float) -> list[float]:
    """
    Construit le paramètre `area` du CDS et signale les erreurs d'ordre les plus
    fréquentes (l'interface demande Nord/Ouest/Sud/Est, un ordre contre-intuitif).
    """
    if not (-90 <= south < north <= 90):
        raise ValueError(
            f" latitudes incohérentes : sud={south} doit être inférieur à nord={north}."
        )
    if not (-180 <= west < east <= 180):
        raise ValueError(
            f" longitudes incohérentes : ouest={west} doit être inférieur à est={east}."
        )
    return [north, west, south, east]


def area_label(area: tuple[float, float, float, float]) -> str:
    """Description lisible d'un encadré, pour les titres de figures."""
    north, west, south, east = area
    if (north, west, south, east) == WORLD:
        return "Monde entier"
    if north >= 89.9 and west <= -179.9 and south <= -89.9:
        return "Monde entier"
    def fmt(x: float) -> str:
        return f"{abs(x):.0f}°{'N' if x >= 0 else 'S'}"

    def fmtlon(x: float) -> str:
        return f"{abs(x):.0f}°{'E' if x >= 0 else 'O'}"
    return f"{fmt(south)}–{fmt(north)} / {fmtlon(west)}–{fmtlon(east)}"
