"""
Test de résolution des noms de variables dans les fichiers CDS.

Le CDS écrit le code court du paramètre (`tp`, `t2m`…) et non le nom long
utilisé dans la requête. Ces tests reproduisent ce comportement.

Usage :  python test_variable_names.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import xarray as xr

from c3s_lab import data

#: (nom demandé, nom dans le fichier, unité source, conversion attendue du maximum)
#: Le maximum de la grille vaut 6 dans toutes les cases ; on vérifie la valeur
#: obtenue pour 6, après conversion. La conversion est décrite en toutes lettres
#: pour éviter toute ambiguïté de signe.
CASES = [
    ("total_precipitation", "tp", "m", 6000.0, "mm"),              # 6 m  -> 6000 mm
    ("2m_temperature", "t2m", "K", 6.0 - 273.15, "°C"),             # 6 K  -> -267.15 °C
    ("mean_sea_level_pressure", "msl", "Pa", 0.06, "hPa"),          # 6 Pa -> 0.06 hPa
    ("total_precipitation", "total_precipitation", "m", 6000.0, "mm"),
    ("2m_temperature", "t2m", "degC", 6.0, "°C"),                   # déjà en °C
]

GRID_MAX = 6.0  # valeur maximale de la grille de test


def build_dataset(name: str, unit: str) -> xr.Dataset:
    """Fichier NetCDF minimal, avec une dimension d'ensemble parasite."""
    times = pd.date_range("2020-01-01", periods=3, freq="MS")
    lats = np.array([45.0, 46.0])
    lons = np.array([2.0, 3.0])
    # Grille de 3 pas de temps x 2 latitudes x 2 longitudes ; maximum = 6.
    values = np.array(
        [[1.0, 2.0, 3.0, 4.0], [2.0, 3.0, 4.0, 5.0], [3.0, 4.0, 5.0, 6.0]]
    ).reshape(3, 2, 2)
    # Les attributs (dont `units`) appartiennent à la variable, pas au jeu de
    # données : c'est ainsi que le CDS écrit ses fichiers NetCDF.
    return xr.Dataset(
        {name: (("time", "latitude", "longitude"), values,
                {"units": unit, "long_name": name})},
        coords={
            "valid_time": times,
            "latitude": lats,
            "longitude": lons,
        },
    )


def main() -> int:
    failures = 0
    for requested, in_file, unit, expected, target_unit in CASES:
        ds = build_dataset(in_file, unit)
        try:
            da = data._find_variable(ds, requested)
            out, out_unit = data._apply_file_units(da, requested)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[ECHEC] {requested:26} (fichier : {in_file:6}) -> {exc}")
            continue

        converted = float(np.nanmax(out.values))

        ok_dims = "time" in da.dims and "latitude" in da.dims
        ok_unit = out_unit == target_unit
        ok_value = abs(converted - expected) < 1e-6

        if ok_dims and ok_unit and ok_value:
            print(f"[OK    ] {requested:26} (fichier : {in_file:6}) -> "
                  f"{out_unit:4} max={converted:.2f}")
        else:
            failures += 1
            print(f"[ECHEC] {requested:26} (fichier : {in_file:6})")
            print(f"         dimensions attendues : {ok_dims}")
            print(f"         unité  : attendu {target_unit!r}, obtenu {out_unit!r}")
            print(f"         valeur : attendu {expected:.4f}, obtenu {converted:.4f}")

    # Cas d'erreur : variable réellement absente.
    try:
        data._find_variable(build_dataset("tp", "m"), "snow_depth")
        print("[ECHEC] variable absente : aucune erreur levée")
        failures += 1
    except KeyError as exc:
        print(f"[OK    ] variable absente détectée -> {str(exc)[:58]}…")

    total = len(CASES) + 1
    print(f"\n{total - failures}/{total} cas de résolution corrects.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
