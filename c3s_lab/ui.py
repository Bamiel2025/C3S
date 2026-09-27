"""
Composants d'interface réutilisables (Streamlit).

Ce module regroupe tout ce qui est affiché plusieurs fois : bandeau de titre,
bandeau de provenance des données, encadrés méthodologiques, tableau
d'indices climatiques. Le reste de l'application s'y réfère, ce qui garantit
que la mention « données simulées » apparaît partout où c'est nécessaire.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from . import analysis, catalog, config, data, places

# --------------------------------------------------------------------------- #
# Accès enseignant
# --------------------------------------------------------------------------- #

#: Code permettant d'ouvrir les onglets réservés et les corrigés.
#: Surchargeable par la variable d'environnement `C3S_TEACHER_CODE`, ce qui
#: évite de laisser le code en clair dans un dépôt public.
TEACHER_CODE = os.environ.get("C3S_TEACHER_CODE", "2027")

#: Clé de session mémorisant la validation du code.
SESSION_KEY = "teacher_unlocked"


def is_teacher() -> bool:
    """Vrai si le code enseignant a été saisi dans cette session."""
    return bool(st.session_state.get(SESSION_KEY, False))


def teacher_gate(title: str = "Espace enseignant") -> bool:
    """
    Demande le code, et renvoie `True` s'il est correct.

    Ce code n'est **pas une sécurité** : il protège les réponses d'une classe
    curieuse, rien de plus. Le vrai verrou est de ne pas publier le code, et de
    le changer si l'application est déployée publiquement.
    """
    if is_teacher():
        return True
    st.markdown(f"### 🔒 {title}")
    st.caption(
        "Cette section est réservée à l'enseignant. Saisissez le code pour y accéder."
    )
    code = st.text_input("Code enseignant", type="password", key=f"gate_{title}")
    if code:
        if code.strip() == TEACHER_CODE:
            st.session_state[SESSION_KEY] = True
            st.success("Code accepté.")
            st.rerun()
        else:
            st.error("Code incorrect.")
    return False


def lock_button() -> None:
    """Bouton de reverrouillage, affiché dans la barre latérale."""
    if is_teacher():
        st.sidebar.success("Mode enseignant actif")
        if st.sidebar.button("🔒 Verrouiller", use_container_width=True):
            st.session_state[SESSION_KEY] = False
            st.rerun()

CSS = """
<style>
  .c3s-banner {
      padding: 0.7rem 1rem; border-radius: 0.5rem; margin-bottom: 1rem;
      border-left: 5px solid #2a9d8f; background: #f0faf8;
  }
  .c3s-banner-warn {
      padding: 0.7rem 1rem; border-radius: 0.5rem; margin-bottom: 1rem;
      border-left: 5px solid #d1495b; background: #fdf3f4;
  }
  .c3s-method {
      padding: 0.8rem 1rem; border-radius: 0.5rem; margin: 1rem 0;
      background: #f7f7f9; border: 1px solid #e2e2e8; font-size: 0.92rem;
  }
  .c3s-method h4 { margin-top: 0; font-size: 1rem; }
  .c3s-step {
      padding: 0.7rem 0.9rem; border-radius: 0.4rem; margin: 0.5rem 0;
      background: #ffffff; border: 1px solid #dfe3e8; border-left: 4px solid #264653;
  }
</style>
"""


def inject_css() -> None:
    """Applique la feuille de style de l'application."""
    st.markdown(CSS, unsafe_allow_html=True)


def data_banner(result) -> None:
    """
    Affiche la provenance des données, de façon non ambiguë.

    Le mode simulé est annoncé explicitement : c'est une exigence de rigueur,
    une figure produite hors ligne ne doit jamais pouvoir être confondue avec
    une donnée Copernicus.
    """
    if result is None:
        return
    if result.simulated:
        st.markdown(
            f"""
            <div class="c3s-banner-warn">
                <strong>⚠️ Données simulées</strong><br>
                Aucune clé CDS n'est configurée : l'application affiche un jeu de
                données <em>simulé</em> pour vous permettre de préparer la séance.
                <br><small>{result.period} · variable {result.variable} · source : simulation.
                Ces chiffres ne doivent pas être communiqués comme des observations.</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="c3s-banner">
                <strong>✅ Données réelles — Copernicus C3S / ERA5</strong><br>
                <small>{result.period} · variable {result.variable} · source : {result.source}
                · {result.n_cells:,} cellules de grille (séparateur de milliers : espace).</small>
            </div>
            """,
            unsafe_allow_html=True,
        )


def method_note(title: str, body: str) -> None:
    """Encadré méthodologique, destiné à projeter ou à lire aux élèves."""
    st.markdown(f'<div class="c3s-method"><h4>{title}</h4>{body}</div>', unsafe_allow_html=True)


def code_gate(key: str, label: str = "Code enseignant") -> bool:
    """
    Demande le code enseignant et mémorise sa validation dans la session.

    Renvoie `True` dès que le code est correct. L'enseignant reste ensuite
    déverrouillé pour toute la session, sur toutes les pages : les onglets
    réservés et les corrigés deviennent accessibles sans ressaisie.
    """
    code = st.text_input(
        label, type="password", key=f"code_{key}", placeholder="Code enseignant"
    )
    if not code:
        return False
    if code.strip() == TEACHER_CODE:
        st.session_state[SESSION_KEY] = True
        st.success("Code accepté : les réponses attendues sont affichées.")
        st.rerun()
    st.error("Code incorrect.")
    return False


def show_steps(steps, activity_key: str = "") -> None:
    """
    Affiche la progression d'une activité, réponses masquées pour les élèves.

    Un onglet unique en tête permet à l'enseignant de saisir le code : les
    réponses attendues de toutes les étapes apparaissent alors, et les onglets
    réservés du menu également. Sans ce code, un élève peut cliquer sur « Voir la
    réponse » d'une étape, ce qui lui ouvre le même champ de saisie.
    """
    prefix = activity_key or str(id(steps))

    with st.expander("🔑 Code enseignant — afficher les réponses attendues"):
        st.caption(
            "Saisissez le code pour débloquer les corrigés de cette activité et les "
            "onglets *Accueil*, *Connexion CDS* et *Méthode* du menu."
        )
        if not is_teacher():
            code_gate(f"gate_{prefix}")
        else:
            st.success("Mode enseignant actif : toutes les réponses sont affichées.")

    for i, step in enumerate(steps, start=1):
        with st.expander(f"Étape {i} — {step.title}", expanded=(i == 1)):
            st.write(step.instruction)
            if step.hint:
                st.caption(f"💡 Piste : {step.hint}")

            if is_teacher():
                st.success(f"**Réponse attendue** — {step.expected}")
            else:
                st.button(
                    "🔒 Voir la réponse", key=f"btn_reponse_{prefix}_{i}",
                )
                st.caption(
                    "Réservé à l'enseignant : le code se saisit dans l'onglet "
                    "« Code enseignant » ci-dessus."
                )

    with st.expander(f"📚 Corrigé complet de l'activité ({len(steps)} étapes)"):
        st.caption(
            "Les consignes et les réponses attendues, étape par étape, pour "
            "préparer votre séance ou corriger en fin de cours."
        )
        if is_teacher():
            for i, step in enumerate(steps, start=1):
                st.markdown(f"**Étape {i} — {step.title}**")
                st.write(step.instruction)
                st.success(step.expected)
                st.divider()
        else:
            code_gate(f"corrige_{prefix}")


def indices_table(indices: list[analysis.ClimateIndex]) -> None:
    """Tableau des indices climatiques calculés."""
    rows = [
        {
            "Indice": idx.name,
            "Valeur": round(idx.value, 1),
            "Unité": idx.unit,
            "Définition": idx.definition,
            "Lecture": idx.interpretation,
        }
        for idx in indices
    ]
    if not rows:
        st.info("Aucune donnée suffisante pour calculer les indices.")
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def citation() -> None:
    """Mention de source obligatoire, en bas de chaque figure publiée."""
    st.caption(
        f"Source : {config.ERA5_CITATION} — {config.ERA5_ATTRIBUTION} "
        f"Licence : {config.ERA5_LICENCE}."
    )

# --------------------------------------------------------------------------- #
# Interface Streamlit
# --------------------------------------------------------------------------- #


@st.cache_data(show_spinner=False, ttl=3600)
def cached_field(
    key_url: str,
    key_key: str,
    dataset_key: str,
    variable: str,
    years: tuple[int, int],
    area: tuple[float, float, float, float],
    force_simulated: bool,
) -> pd.DataFrame:
    """
    Champ spatial filtré, mis en cache pour éviter les recalculs à chaque clic.

    Le résultat est renvoyé sous forme de tableau plutôt que de `DataArray` :
    c'est le format que Streamlit sait sérialiser dans son cache.
    """
    cfg = config.resolve_cds_config(key_url or None, key_key or None)
    result = data.fetch(
        cfg=cfg,
        dataset_key=dataset_key,
        variable=variable,
        years=years,
        area=area,
        force_simulated=force_simulated,
    )
    return result.field().to_pandas()


@st.cache_data(show_spinner=False, ttl=3600)
def cached_series(
    key_url: str,
    key_key: str,
    dataset_key: str,
    variable: str,
    years: tuple[int, int],
    lat: float,
    lon: float,
    force_simulated: bool,
) -> pd.DataFrame:
    """Série temporelle en un point, avec la même stratégie de cache."""
    cfg = config.resolve_cds_config(key_url or None, key_key or None)
    result = data.fetch(
        cfg=cfg,
        dataset_key=dataset_key,
        variable=variable,
        years=years,
        area=(lat + 1.0, lon - 1.0, lat - 1.0, lon + 1.0),
        force_simulated=force_simulated,
    )
    series = result.series_at(lat, lon, name=result.unit)
    return series.rename("valeur").to_frame()


def show_figure(fig, *, key: str = "figure") -> None:
    """Affiche une figure Plotly et la barre de téléchargement."""
    st.plotly_chart(fig, use_container_width=True, key=key)
    st.download_button(
        "Télécharger la figure (HTML, à ouvrir dans un navigateur)",
        fig.to_html(full_html=True, include_plotlyjs="cdn"),
        file_name=f"c3s_lab_{key}.html",
        mime="text/html",
    )


def sidebar_controls() -> dict[str, Any]:
    """
    Barre latérale : état de la connexion et réglages généraux.

    La clé API saisie ici n'est jamais écrite sur le disque : elle reste dans
    la session Streamlit et disparaît à la fermeture de l'onglet.
    """
    with st.sidebar:
        st.title("🌍 C3S Climate Lab")
        st.caption("Données climatiques Copernicus pour le cycle 4")

        if config.IS_READONLY_DEPLOYMENT:
            st.info(
                "☁️ **Déploiement en ligne** — les données téléchargées sont mises en "
                "cache dans un dossier temporaire, non conservé entre les sessions. "
                "La première requête de chaque séance sera donc plus lente."
            )

        cfg = config.resolve_cds_config(
            st.session_state.get("cds_url"), st.session_state.get("cds_key")
        )
        if cfg.is_configured:
            st.success("Clé CDS détectée")
            st.caption(f"Source : {cfg.source}")
        else:
            st.warning("Aucune clé CDS — mode simulation")
            if config.deployment_kind() == "cloud":
                st.caption(
                    "L'application tourne en ligne : la clé ne peut pas être saisie "
                    "dans ce navigateur, elle doit être déclarée par l'administrateur."
                )
                with st.expander("Comment déclarer la clé en ligne"):
                    st.markdown(config.cloud_secret_hint())
            else:
                st.caption(
                    "Rendez-vous sur la page **Connexion CDS** pour configurer la clé."
                )

        st.divider()
        st.subheader("Source des données")
        force_sim = st.toggle(
            "Forcer les données simulées",
            value=st.session_state.get("force_simulated", not cfg.is_configured),
            help="Utile pour préparer une séance hors connexion, ou pour comparer.",
        )
        st.session_state["force_simulated"] = force_sim

        st.divider()
        st.subheader("Période de référence")
        ref_options = [(1951, 1980), (1961, 1990), (1971, 2000), (1981, 2010), (1991, 2020)]
        default_ref = (
            config.WMO_NORMAL_PERIOD
            if config.WMO_NORMAL_PERIOD in ref_options
            else ref_options[-1]
        )
        ref = st.selectbox(
            "Normale climatique (OMM)",
            ref_options,
            index=ref_options.index(default_ref),
            format_func=lambda p: f"{p[0]}–{p[1]}",
        )
        st.caption(
            "Période sur laquelle sont calculées les moyennes servant de référence "
            "aux anomalies et aux normales."
        )

    return {"cfg": cfg, "force_simulated": force_sim, "reference": tuple(ref)}


def dataset_picker(default: str = "monthly_means") -> tuple[str, str, str]:
    """
    Sélecteur de jeu de données, de variable et de domaine géographique.

    Renvoie `(clé du jeu, identifiant CDS, variable)`.

    Note : `st.selectbox` renvoie l'étiquette choisie, qui est ici le couple
    `(clé, libellé)`. On en extrait la clé avant de poursuivre.
    """
    col1, col2 = st.columns([1, 1])
    with col1:
        chosen = st.selectbox(
            "Jeu de données", catalog.as_options(), index=0,
            format_func=lambda kv: catalog.get(kv[0]).label,
        )
    dataset_key = chosen[0] if isinstance(chosen, (tuple, list)) else chosen
    dataset = catalog.get(dataset_key)

    var_options = [(v.slug, v.label) for v in dataset.variables]
    slugs = [v[0] for v in var_options]
    default_index = slugs.index("2m_temperature") if "2m_temperature" in slugs else 0
    with col2:
        chosen_var = st.selectbox(
            "Variable", var_options, index=default_index,
            format_func=lambda kv: dict(var_options)[kv[0]],
        )
    variable = chosen_var[0] if isinstance(chosen_var, (tuple, list)) else chosen_var

    domain_names = [d.name for d in places.DOMAINS]
    domain_name = st.selectbox("Domaine géographique", domain_names, index=1)

    return dataset_key, dataset.id, variable


def years_picker(
    dataset_key: str, default: tuple[int, int] = (1991, 2020)
) -> tuple[int, int] | None:
    """
    Sélecteur de période, borné par la disponibilité du jeu de données.

    Renvoie `None` si la période demandée est incohérente, au lieu d'interrompre
    la page : un `st.stop()` ici faisait disparaître silencieusement toutes les
    figures de l'activité, sans message d'erreur.
    """
    dataset = catalog.get(dataset_key)
    start = max(dataset.start_year, 1940)
    end = config.LAST_COMPLETE_YEAR
    if end - start < 1:
        st.error("Ce jeu de données ne couvre pas de période exploitable.")
        return None
    col1, col2 = st.columns(2)
    with col1:
        y0 = st.number_input(
            "Année de début", min_value=start, max_value=end - 1,
            value=max(start, min(default[0], end - 1)), step=1,
        )
    with col2:
        y1 = st.number_input(
            "Année de fin", min_value=start + 1, max_value=end,
            value=max(start + 1, min(default[1], end)), step=1,
        )
    if y0 >= y1:
        st.error(
            "La période demandée est vide : l'année de début doit précéder "
            "l'année de fin."
        )
        return None
    return int(y0), int(y1)


def city_picker(selection: list[str], *, world: bool = False) -> list:
    """Sélecteur multiple de villes, avec recherche par nom."""
    pool = places.WORLD_CITIES if world else places.FRENCH_CITIES
    names = [p.name for p in pool]
    default = [n for n in selection if n in names] or names[:2]
    chosen = st.multiselect(
        "Villes à comparer", names, default=default,
        help="Les villes proposées par l'activité sont sélectionnées par défaut.",
    )
    return [p for p in pool if p.name in chosen]

