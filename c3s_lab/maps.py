"""
Cartes climatiques interactives.

Note technique : depuis Plotly 6, les sous-graphiques géographiques n'acceptent plus
que les traces `Scattergeo` et `Choropleth`. Un champ numérique est donc rendu en
**carrés colorés** positionnés sur la grille (trace `Scattergeo` à symboles
carrés), et les isothermes / isobares sont calculés par l'algorithme de
*Marching squares* de matplotlib puis tracés en lignes géographiques.

Trois principes de rigueur cartographique sont appliqués :

1. **Aucune interpolation cachée** : les cellules sont dessinées telles quelles.
   Le lissage est offert comme option, jamais appliqué d'office, car il crée des
   valeurs qui n'existent pas dans les données.
2. **Échelle déclarée** : chaque figure indique son unité, sa résolution et sa
   période, pour rester interprétable une fois exportée ou imprimée.
3. **Précision sur la valeur lue** : une valeur extraite en un point n'est pas
   une mesure de station mais la moyenne du modèle sur une cellule de 0,25°
   (environ 25 km de côté, soit 14 km d'incertitude de position).
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import basemaps, viz

#: Nombre maximal de cellules dessinées ; au-delà, la grille est sous-échantillonnée.
MAX_DISPLAY_CELLS = 6000


def _geo_layout(
    area: tuple[float, float, float, float],
    *,
    show_land: bool = True,
    show_borders: bool = True,
    height: int = 560,
) -> tuple[dict, dict | None]:
    """
    Mise en page géographique commune (projection, cadrage, fonds).

    La largeur de la figure est calculée pour conserver le rapport de la
    projection équirectangulaire : sans cela, la carte serait déformée et les
    cellules ne seraient plus carrées.

    Le fond des terres émergées est rendu par le moteur `geo` de Plotly, qui
    embarque sa propre base Natural Earth : cela évite un téléchargement. Les
    frontières, elles, sont superposées depuis le GeoJSON local, plus détaillé.
    """
    north, west, south, east = area
    width, _ = figure_size(area, height)

    layout: dict = {
        "geo": {
            "projection": {"type": "equirectangular"},
            "lataxis": {"range": [south, north]},
            "lonaxis": {"range": [west, east]},
            "showland": bool(show_land),
            "landcolor": "#e9ede3",
            "showocean": False,
            "oceancolor": "#dfe8f5",
            "showframe": False,
            "showcoastlines": False,
            "coastlinecolor": "#8a97a8",
            "bgcolor": "#f4f7fb",
            "domain": {"x": [0, 1], "y": [0, 1]},
        },
        "margin": {"l": 10, "r": 10, "t": 70, "b": 30},
        "paper_bgcolor": "#f4f7fb",
        "plot_bgcolor": "#f4f7fb",
        "width": width,
        "height": height,
        "font": {"family": "Segoe UI, Arial, sans-serif", "size": 12},
    }

    borders = None
    if show_borders:
        try:
            borders = basemaps.load_basemap("countries")
            layout["geo"]["showcountries"] = False
            layout["geo"]["showcoastlines"] = False
        except basemaps.BasemapUnavailable:
            # Repli sur le fond intégré de Plotly si le réseau est coupé.
            borders = None
            layout["geo"]["showcountries"] = True
            layout["geo"]["countrycolor"] = "#9aa0a6"

    return layout, borders


def _geojson_trace_props(geojson: dict) -> dict:
    """
    Convertit un GeoJSON (`FeatureCollection`) en coordonnées pour `Scattergeo`.

    Plotly n'accepte pas un GeoJSON brut dans `Scattergeo` : il faut aplatir les
    géométries en un simple triplet `lon` / `lat` / `text`. Les segments sont
    séparés par `None` pour que les pays ne soient pas reliés entre eux.
    """
    lons: list = []
    lats: list = []
    labels: list = []
    for feature in geojson.get("features", []):
        name = _feature_label(feature)
        for ring in _iter_rings(feature.get("geometry") or {}):
            coords = ring
            lons.extend([c[0] for c in coords] + [None])
            lats.extend([c[1] for c in coords] + [None])
            labels.extend([name] * (len(coords) + 1))
    return {
        "lon": lons,
        "lat": lats,
        "text": labels,
        "mode": "lines",
        "connectgaps": False,
    }


def _feature_label(feature: dict) -> str:
    """Nom d'un pays, en privilégiant les propriétés en français."""
    props = feature.get("properties") or {}
    for key in ("NAME_FR", "name_fr", "NAME", "ADMIN", "name"):
        if props.get(key):
            return str(props[key])
    return ""


def _iter_rings(geometry: dict):
    """Parcourt les anneaux extérieurs d'une géométrie GeoJSON."""
    gtype = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        return
    if gtype == "Polygon":
        for ring in coordinates[:1]:  # contour extérieur seul
            yield ring
    elif gtype == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon[:1]:
                yield ring
    elif gtype == "LineString":
        yield coordinates
    elif gtype == "MultiLineString":
        for line in coordinates:
            yield line


# --------------------------------------------------------------------------- #
# Carte d'un champ 2D
# --------------------------------------------------------------------------- #


def _shift_longitudes(lon: np.ndarray) -> np.ndarray:
    """
    Recentre chaque valeur sur sa cellule.

    Plotly situe une valeur d'après les coordonnées exactes ; sans ce décalage
    de 0,125°, la maille 48,5°N serait dessinée en 48,5° alors qu'elle couvre
    en réalité 48,375°-48,625°.
    """
    if lon.size < 2:
        return lon
    step = float(np.median(np.diff(lon)))
    return lon + step / 2.0


def grid_step(lat: np.ndarray, lon: np.ndarray) -> tuple[float, float]:
    """Pas de la grille en degrés, déduit de l'écart médian entre coordonnées."""
    lat_step = float(np.median(np.abs(np.diff(lat)))) if lat.size > 1 else 1.0
    lon_step = float(np.median(np.abs(np.diff(lon)))) if lon.size > 1 else 1.0
    return max(lat_step, 1e-6), max(lon_step, 1e-6)


def cell_size_px(area, height: int, steps: tuple[float, float]) -> float:
    """
    Taille en pixels d'une maille, en projection équirectangulaire.

    En projection équirectangulaire, un degré de latitude occupe exactement la
    même place qu'un degré de longitude. La figure étant dimensionnée pour
    conserver ce rapport, une maille de `step` degrés occupe
    `hauteur_px / (nord − sud) × step` pixels. Les cellules se touchent alors
    parfaitement, sans intervalle blanc entre elles.
    """
    north, _, south, _ = area
    span_y = max(north - south, 0.5)
    lat_step, lon_step = steps
    # La maille la plus contraignante dimensionne le carré ; on ajoute 8 % pour
    # que les cellules voisines se recouvrent légèrement et masquent le fond.
    size = height / span_y * min(lat_step, lon_step) * 1.08
    return max(size, 0.4)


def figure_size(area, height: int) -> tuple[int, int]:
    """
    Dimensions (largeur, hauteur) respectant le rapport de la projection.

    Sans cet ajustement, une zone 39° de haut sur 32° de large serait étirée ou
    tassée, et les cellules ne seraient plus carrées à l'écran.
    """
    north, west, south, east = area
    span_x = max(east - west, 0.5)
    span_y = max(north - south, 0.5)
    # Marge pour la barre de couleurs et les titres.
    width = int(round(height * span_x / span_y)) + 170
    return max(width, 420), height


def _subsample(lat: np.ndarray, lon: np.ndarray, z: np.ndarray, max_cells: int):
    """Sous-échantillonne la grille pour rester sous `max_cells` points."""
    n_lat, n_lon = z.shape
    total = n_lat * n_lon
    if total <= max_cells:
        return lat, lon, z
    stride = int(np.ceil(np.sqrt(total / max_cells)))
    return lat[::stride], lon[::stride], z[::stride, ::stride]


def _grid_cells(lat: np.ndarray, lon: np.ndarray, z: np.ndarray):
    """Aplatit une grille en coordonnées de cellules centrées."""
    lat_c, lon_c = np.meshgrid(lat, lon, indexing="ij")
    return lat_c.ravel(), lon_c.ravel(), z.ravel()


def _subsample2(lat, lon, u, v, speed, max_cells: int = MAX_DISPLAY_CELLS):
    """Sous-échantillonne un couple de composantes vectorielles."""
    n_lat, n_lon = speed.shape
    stride = int(np.ceil(np.sqrt((n_lat * n_lon) / max_cells)))
    if stride <= 1:
        return lat, lon, u, v, speed, 1
    sl = (slice(None, None, stride), slice(None, None, stride))
    return lat[::stride], lon[::stride], u[sl], v[sl], speed[sl], stride


def _add_filled_cells(
    fig: go.Figure,
    lat: np.ndarray,
    lon: np.ndarray,
    z: np.ndarray,
    scale,
    zmin,
    zmax,
    unit: str,
    area,
    height: int,
    hover_extra: str,
) -> None:
    """Superpose les cellules colorées de la grille sur la figure."""
    lat_s, lon_s, z_s = _subsample(lat, lon, z, MAX_DISPLAY_CELLS)
    lat_c, lon_c, z_c = _grid_cells(lat_s, lon_s, z_s)
    fig.add_trace(
        go.Scattergeo(
            lat=lat_c, lon=lon_c, mode="markers", geo="geo", showlegend=False,
            marker=dict(
                symbol="square", size=cell_size_px(area, height, grid_step(lat_s, lon_s)),
                color=z_c, colorscale=scale, cmin=zmin, cmax=zmax,
                showscale=True, opacity=0.95, line=dict(width=0),
                colorbar=dict(
                    title=dict(text=unit, side="right", font=dict(size=12)),
                    thickness=14, len=0.75, outlinewidth=0.5, outlinecolor="#555",
                ),
            ),
            hovertemplate=(
                "latitude %{lat:.2f}°N · longitude %{lon:.2f}°E<br>"
                "<b>%{marker.color:.2f} " + unit + "</b>" + hover_extra + "<extra></extra>"
            ),
        )
    )


def _contour_levels(z: np.ndarray, zmin, zmax, count: int = 10) -> list[float]:
    """Niveaux « ronds » (multiples de 2 ou 5) couvrant l'amplitude du champ."""
    finite = z[np.isfinite(z)]
    if finite.size == 0:
        return []
    lo = float(np.nanmin(finite) if zmin is None else zmin)
    hi = float(np.nanmax(finite) if zmax is None else zmax)
    if hi <= lo:
        return [lo]
    step = _nice_step((hi - lo) / count)
    first = np.ceil(lo / step) * step
    levels = []
    level = first
    while level <= hi and len(levels) < 40:
        levels.append(float(round(level, 6)))
        level += step
    return levels


def _nice_step(raw: float) -> float:
    """Arrondit un pas de contour à 1, 2, 5 ou 10 fois une puissance de dix."""
    if raw <= 0:
        return 1.0
    exponent = np.floor(np.log10(raw))
    base = 10.0**exponent
    for factor in (1.0, 2.0, 5.0, 10.0):
        if raw <= factor * base:
            return float(factor * base)
    return float(10.0 * base)


def _contour_paths(lat, lon, z, level: float):
    """
    Segments d'une isovale, calculés par l'algorithme de marching squares
    (matplotlib), puis convertis en listes de coordonnées géographiques.
    """
    import matplotlib

    matplotlib.use("Agg", force=False)
    from matplotlib import pyplot as plt

    fig, ax = plt.subplots()
    try:
        cs = ax.contour(lon, lat, z, levels=[level])
        segments = []
        # `allsegs[0]` est un tableau structuré dshape (N, 2-3) : chaque element
        # contient les sommets (lon, lat, code) d'une polyligne de l'isovale.
        for polyline in cs.allsegs[0]:
            pts = np.asarray(polyline)
            if pts.ndim != 2 or pts.shape[0] < 2 or pts.shape[1] < 2:
                continue
            segments.append((pts[:, 0], pts[:, 1]))
        cs.remove()
    finally:
        plt.close(fig)
    return segments


def field_map(
    da,
    *,
    title: str,
    unit: str,
    period: str,
    area: tuple[float, float, float, float],
    colorscale: list | None = None,
    zmin: float | None = None,
    zmax: float | None = None,
    contours: bool = False,
    show_borders: bool = True,
    show_land: bool = True,
    hover_extra: str = "",
    height: int = 570,
) -> go.Figure:
    """
    Carte d'un champ spatial (température, pression, précipitations…).

    Le rendu par défaut utilise des cellules pleines, ce qui correspond
    exactement à la grille du modèle : chaque carré représente 0,25° x 0,25°,
    soit environ 25 km de côté. L'option `contours=True` trace des isothermes ou
    des isobares, plus parlantes qu'une carte de couleurs pour un champ lissé.
    """
    lat = np.asarray(da["latitude"].values, dtype="float64")
    lon = np.asarray(da["longitude"].values, dtype="float64")
    z = np.asarray(da.values, dtype="float64")
    if z.ndim != 2:
        raise ValueError(
            "field_map attend un champ à deux dimensions (latitude, longitude)."
        )

    # Plotly attend des latitudes croissantes ; ERA5 les fournit décroissantes.
    if lat[0] > lat[-1]:
        lat = lat[::-1]
        z = z[::-1, :]

    scale = colorscale or viz.TEMP_SCALE
    layout, borders = _geo_layout(
        area, show_land=show_land, show_borders=show_borders, height=height
    )

    fig = go.Figure()

    if contours:
        # Fond coloré, puis isothermes / isobares par-dessus.
        _add_filled_cells(fig, lat, lon, z, scale, zmin, zmax, unit, area, height, hover_extra)
        for level in _contour_levels(z, zmin, zmax, 10):
            for seg_lon, seg_lat in _contour_paths(lat, lon, z, level):
                fig.add_trace(
                    go.Scattergeo(
                        lon=seg_lon, lat=seg_lat, mode="lines", showlegend=False,
                        line=dict(width=1.6, color="rgba(30,30,30,0.85)"),
                        hoverinfo="skip", geo="geo",
                    )
                )
    else:
        _add_filled_cells(fig, lat, lon, z, scale, zmin, zmax, unit, area, height, hover_extra)

    if borders is not None:
        fig.add_trace(
            go.Scattergeo(
                **_geojson_trace_props(borders), showlegend=False, hoverinfo="skip",
                line=dict(width=0.6, color="rgba(110,110,110,0.8)"),
            )
        )

    fig.update_layout(
        **layout,
        title=dict(
            text=f"{title}<br><sup>{period} — grille ERA5 0,25° — unité : {unit}</sup>",
            x=0.02, xanchor="left", font=dict(size=16),
        ),
    )
    return fig


def wind_map(
    u,
    v,
    *,
    title: str,
    period: str,
    area: tuple[float, float, float, float],
    height: int = 570,
) -> go.Figure:
    """
    Carte des vecteurs de vent, avec une teinte proportionnelle à la vitesse.

    Les composantes u (vers l'est) et v (vers le nord) sont combinées : la vitesse
    vaut `sqrt(u² + v²)`. Les flèches sont tracées en segments géographiques
    explicites (départ, arrivée, pointe), car les sous-graphiques `geo` de
    Plotly 6 n'acceptent plus les attributs vectoriels `u` / `v`.
    """
    lat = np.asarray(_coord(u, "latitude"), dtype="float64")
    lon = np.asarray(_coord(u, "longitude"), dtype="float64")
    u_vals = np.asarray(u.values, dtype="float64")
    v_vals = np.asarray(v.values, dtype="float64")
    speed = np.sqrt(u_vals**2 + v_vals**2)

    if lat[0] > lat[-1]:
        lat = lat[::-1]
        u_vals, v_vals, speed = u_vals[::-1, :], v_vals[::-1, :], speed[::-1, :]

    lat_s, lon_s, u_s, v_s, speed_s, _ = _subsample2(lat, lon, u_vals, v_vals, speed)
    lat_c, lon_c = np.meshgrid(lat_s, lon_s, indexing="ij")
    layout, borders = _geo_layout(area, height=height)
    vmax = float(np.nanpercentile(speed_s, 98)) if speed_s.size else 1.0

    # Longueur d'une flèche, en degrés, bornée pour rester lisible.
    arrow_deg = 0.55
    safe_speed = np.where(speed_s > 1e-6, speed_s, np.nan)
    dx = u_s / safe_speed * arrow_deg
    dy = v_s / safe_speed * arrow_deg
    # En longitude, un degré de déplacement vaut cos(lat) fois moins en distance.
    dx = dx / np.maximum(np.cos(np.deg2rad(lat_c)), 0.2)

    x0 = lon_c.ravel()
    y0 = lat_c.ravel()
    x1 = x0 + np.nan_to_num(dx).ravel()
    y1 = y0 + np.nan_to_num(dy).ravel()
    colors = speed_s.ravel()

    # Angle de chaque flèche, en radians mesuré depuis l'est et non l'ouest :
    # c'est ce repère qu'attend le symbole `triangle-up` de Plotly.
    angles = np.degrees(np.arctan2(dy.ravel(), dx.ravel() * np.cos(np.deg2rad(y0))))

    fig = go.Figure()
    # 1. Traînée de chaque flèche. Les `None` intercalaires empêchent Plotly de
    #    relier la fin d'une flèche au début de la suivante.
    fig.add_trace(
        go.Scattergeo(
            lon=_with_gaps(x0, x1),
            lat=_with_gaps(y0, y1),
            mode="lines", geo="geo", showlegend=False,
            line=dict(width=1.2, color="#44546a"),
            hoverinfo="skip", connectgaps=False,
        )
    )
    # 2. Pointes orientées, porteuses de l'information au survol.
    fig.add_trace(
        go.Scattergeo(
            lon=x1, lat=y1, mode="markers", geo="geo", showlegend=False,
            marker=dict(
                symbol="triangle-up", size=9, angle=angles,
                color=colors, colorscale="Viridis", cmin=0, cmax=vmax, opacity=0.95,
                colorbar=dict(
                    title=dict(text="m/s", side="right"), thickness=12, len=0.7,
                    outlinewidth=0.5, outlinecolor="#555",
                ),
            ),
            customdata=np.stack([y0, x0, u_s.ravel(), v_s.ravel()], axis=1),
            hovertemplate=(
                "lat %{customdata[0]:.2f}°N · lon %{customdata[1]:.2f}°E<br>"
                "vitesse %{marker.color:.1f} m/s"
                "<br>vers l'est %{customdata[2]:.1f} m/s, vers le nord %{customdata[3]:.1f} m/s"
                "<extra></extra>"
            ),
        )
    )

    if borders is not None:
        fig.add_trace(
            go.Scattergeo(**_geojson_trace_props(borders), showlegend=False,
                          hoverinfo="skip",
                          line=dict(width=0.6, color="rgba(110,110,110,0.8)"))
        )

    fig.update_layout(
        **layout,
        title=dict(
            text=f"{title}<br><sup>{period} — vitesse et direction du vent à 10 m</sup>",
            x=0.02, xanchor="left", font=dict(size=16),
        ),
    )
    return fig


def _with_gaps(starts: np.ndarray, ends: np.ndarray) -> list:
    """
    Assemble des segments `(départ, arrivée)` en une seule trace de lignes.

    Un `None` est inséré entre deux segments : sans lui, Plotly relierait la fin
    d'une flèche au début de la suivante par un segment parasite.
    """
    out: list = []
    for a, b in zip(starts, ends):
        out.extend([a, b, None])
    return out


def _coord(da, name: str) -> np.ndarray:
    """Coordonnées d'un DataArray, quelle que soit la casse des noms CDS."""
    for candidate in (name, "lat" if name == "latitude" else "lon"):
        if candidate in da.coords:
            return da.coords[candidate].values
    raise KeyError(f"Coordonnée « {name} » absente du champ.")


def animated_map(
    da_time,
    *,
    title: str,
    unit: str,
    area: tuple[float, float, float, float],
    colorscale: list | None = None,
    zmin: float | None = None,
    zmax: float | None = None,
    show_borders: bool = True,
    height: int = 500,
) -> go.Figure:
    """
    Carte animée dans le temps (curseur sous la figure).

    Chaque pas de temps devient une image de la pile de la figure : c'est le moyen
    le plus direct de faire sentir aux élèves qu'une anomalie est un *décalage* du
    champ par rapport à une moyenne, et non une nouvelle « carte du climat ».
    """
    lat = np.asarray(da_time["latitude"].values, dtype="float64")
    lon = np.asarray(da_time["longitude"].values, dtype="float64")
    if lat[0] > lat[-1]:
        lat = lat[::-1]

    times = pd.to_datetime(da_time["time"].values)
    lat_s, lon_s, _ = _subsample(lat, lon, np.zeros((len(lat), len(lon))), MAX_DISPLAY_CELLS)
    lat_c, lon_c, _ = _grid_cells(lat_s, lon_s, np.zeros((len(lat_s), len(lon_s))))
    size = cell_size_px(area, height, grid_step(lat_s, lon_s))
    scale = colorscale or viz.TEMP_SCALE

    def _frame_values(i: int):
        z = np.asarray(da_time.isel(time=i).values, dtype="float64")[:: _stride_of(lat, lat_s), :: _stride_of(lon, lon_s)]
        return z.ravel()

    frames = []
    steps = []
    for i, t in enumerate(times):
        trace = go.Scattergeo(
            lat=lat_c, lon=lon_c, mode="markers", geo="geo",
            marker=dict(
                symbol="square", size=size, color=_frame_values(i),
                colorscale=scale, cmin=zmin, cmax=zmax, showscale=True,
                line=dict(width=0),
                colorbar=dict(
                    title=dict(text=unit, side="right"), thickness=14, len=0.7,
                ),
            ),
            hovertemplate=(
                "lat %{lat:.2f}°N · lon %{lon:.2f}°E<br>"
                "<b>%{marker.color:.2f} " + unit + "</b><extra></extra>"
            ),
        )
        frames.append(go.Frame(name=str(t.date()), data=[trace]))
        # Un pas de curseur est un dictionnaire, pas un objet Frame.
        steps.append({
            "label": str(t.date()),
            "method": "animate",
            "args": [[str(t.date())], {"mode": "immediate", "frame": {"duration": 0}}],
        })

    layout, borders = _geo_layout(area, show_borders=show_borders, height=height)
    fig = go.Figure(data=frames[0].data if frames else [], frames=frames)
    fig.update_layout(
        **layout,
        sliders=[{
            "active": 0, "steps": steps,
            "currentvalue": {"prefix": "Date : "},
            "x": 0.1, "len": 0.8, "y": -0.06, "pad": {"t": 45},
        }],
        title=dict(text=f"{title}<br><sup>grille ERA5 0,25° — unité : {unit}</sup>",
                   x=0.02, xanchor="left", font=dict(size=16)),
    )
    if borders is not None:
        fig.add_trace(go.Scattergeo(**_geojson_trace_props(borders), showlegend=False, hoverinfo="skip",
                                    line=dict(width=0.6, color="rgba(110,110,110,0.8)")))
    return fig


def _stride_of(full: np.ndarray, sampled: np.ndarray) -> int:
    """Pas d'échantillonnage reliant une grille complète à sa version réduite."""
    if full.size < 2 or sampled.size < 2:
        return 1
    return max(int(round(abs(full[1] - full[0]) / max(abs(sampled[1] - sampled[0]), 1e-9))), 1)
