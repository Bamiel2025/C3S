"""
C3S Climate Lab — laboratoire pédagogique du climat (cycle 4).

Application Streamlit multi-pages dédiée à l'exploitation des données
climatiques du Copernicus Climate Change Service (ERA5) en classe de collège.

Lancement :
    streamlit run app.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from c3s_lab import activities, analysis, basemaps, catalog, cds_client
from c3s_lab import config, data, maps, places, ui, viz

st.set_page_config(
    page_title="C3S Climate Lab — climat et données Copernicus",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _cfg() -> config.CDSConfig:
    """Configuration CDS de la session courante."""
    return config.resolve_cds_config(
        st.session_state.get("cds_url"), st.session_state.get("cds_key")
    )


def _fetch(**kwargs):
    """
    Récupère des données en affichant une barre de progression.

    Les erreurs du CDS sont transformées en message lisible : devant une classe,
    une trace de Python n'aide personne à avancer.
    """
    progress = st.progress(0.0, text="Préparation de la requête…")
    try:
        result = data.fetch(
            cfg=_cfg(),
            progress=lambda f, m: progress.progress(min(f, 1.0), text=m),
            **kwargs,
        )
    except cds_client.CDSError as exc:
        progress.empty()
        message = str(exc)
        lowered = message.lower()
        st.error(f"Le CDS a refusé la requête : {exc}" if len(message) < 300
                 else "Le CDS a refusé la requête — voir le détail ci-dessous.")

        if "licen" in lowered:
            st.warning(
                "**Les conditions d'utilisation ne sont pas encore acceptées.**"
            )
            st.markdown(
                """
Votre clé est donc correcte : le CDS vous a identifié, mais refuse de
livrer les données tant que vous n'avez pas accepté les conditions du jeu de
données concerné. C'est une manipulation que vous devez faire vous-même, depuis
votre navigateur, car elle nécessite une session connectée.

**La marche à suivre :**

1. Ouvrez la page du jeu de données (le bouton ci-dessous l'ouvre directement).
2. Descendez jusqu'en bas, jusqu'au bouton **« Accept licence » / « Accepter »**.
3. Recommencez. L'accord est définitif : il ne sera plus demandé.
                """
            )
            st.markdown(_licence_links(), unsafe_allow_html=True)
        elif "401" in lowered or "unauthor" in lowered or "token" in lowered:
            st.warning("**Jeton refusé.**")
            st.info(
                "Vérifiez qu'il s'agit bien du jeton d'accès personnel affiché sur "
                "votre profil CDS, et non du *Client ID* / *Client secret* de votre "
                "compte ECMWF, qui sert à l'API Web ECMWF et non au Climate Data "
                "Store. La page « Connexion CDS » permet de vérifier le format."
            )
        else:
            st.info(
                "Causes fréquentes : conditions d'utilisation non acceptées, "
                "requête trop volumineuse, ou temporairement indisponible. "
                "Voir la page **Connexion CDS**."
            )
        st.stop()
    except Exception as exc:  # noqa: BLE001
        progress.empty()
        st.error(f"Erreur inattendue : {type(exc).__name__} — {exc}")
        st.stop()
    progress.empty()
    return result


def _licence_links() -> str:
    """Liste des pages CDS où accepter les conditions, avec leur identifiant."""
    lines = ["**Pages à ouvrir** (une seule fois chacune) :", ""]
    for key, dataset in catalog.DATASETS.items():
        url = f"{dataset.doc_url}?tab=download#manage-licences"
        lines.append(f"- [{dataset.label}]({url})  \n  `{dataset.id}`")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Page 1 — Accueil
# --------------------------------------------------------------------------- #


def page_accueil() -> None:
    st.title("🌍 C3S Climate Lab")
    st.markdown(
        "### Explorer le climat avec les vraies données du **Copernicus Climate Change Service**"
    )
    st.markdown(
        "Cette application télécharge des données climatiques **ERA5**, calculées par "
        "le Centre européen pour les prévisions météorologiques (ECMWF), et les "
        "transforme en graphiques et en cartes que les élèves peuvent analyser."
    )

    cfg = _cfg()
    if cfg.is_configured:
        st.success(
            f"Connexion au Climate Data Store active — clé lue depuis "
            f"**{cfg.source}**."
        )
        st.info(
            "Dernière étape pour obtenir les données réelles : ouvrir chaque page de "
            "jeu de données et accepter les conditions d'utilisation. La page "
            "**Connexion CDS** → *Conditions d'utilisation* permet de vérifier "
            "immédiatement lesquelles restent à accepter."
        )
    else:
        st.warning(
            "Aucune clé API n'est détectée : l'application fonctionne avec un jeu de "
            "données **simulé**, utile pour préparer une séance. Voir la page "
            "**Connexion CDS** pour enregistrer votre clé et obtenir les données réelles."
        )

    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Activités prêtes", len(activities.ACTIVITIES))
        st.caption("fiche + figures + corrigés")
    with col2:
        st.metric("Jeux de données CDS", len(catalog.DATASETS))
        st.caption("moyennes mensuelles, journalières, niveaux de pression")
    with col3:
        st.metric("Villes couvertes", len(places.FRENCH_CITIES) + len(places.WORLD_CITIES))
        st.caption("France et monde")

    st.divider()
    st.subheader("Programme d'activités")
    st.dataframe(activities.summary_table(), use_container_width=True, hide_index=True)

    st.subheader("Ce que l'application apporte")
    st.markdown(
        """
- **Des données scientifiques réelles**, pas des chiffres inventés : les figures
  portent leur source, leur unité et leur résolution.
- **Une méthode visible** : normale de l'OMM 1991-2020, moyenne pondérée par le
  cosinus de la latitude, écart à la normale explicite.
- **Des activités calibrées** sur les programmes de cycle 4, avec les questions
  posées aux élèves et les réponses attendues.
- **Un mode hors ligne** pour préparer une séance sans connexion.
        """
    )

    st.subheader("Démarrage en trois étapes")
    st.markdown(
        f"""
1. **Installer la clé CDS** — suivez la [procédure officielle ECMWF]({config.CDKB_WINDOWS_URL})
   ou utilisez le script `install_cds_key.ps1` fourni.
2. **Tester la connexion** — page *Connexion CDS*, bouton « Tester la connexion ».
3. **Lancer une activité** — page *Activités*, choisissez un niveau et un thème.
        """
    )


# --------------------------------------------------------------------------- #
# Page 2 — Connexion CDS
# --------------------------------------------------------------------------- #


def page_connexion() -> None:
    st.title("🔑 Connexion au Climate Data Store")
    st.markdown(
        "Le Climate Data Store (CDS) exige une clé personnelle pour télécharger des "
        "données. Cette page explique comment l'obtenir et comment la vérifier ; "
        "l'application reste utilisable sans elle, en mode simulation."
    )

    cfg = _cfg()
    st.subheader("1. État de la configuration")
    if cfg.is_configured:
        st.success(f"Clé configurée — source : **{cfg.source}**")
        st.code(cfg.cdsapirc_content(), language="text")
    else:
        st.error("Aucune clé API détectée.")
        st.markdown(
            f"""
L'application cherche la configuration dans cet ordre :

| Priorité | Source | Comment la définir |
|---|---|---|
| 1 | Saisie directe ci-dessous | Champ *clé* — la plus rapide pour un essai |
| 2 | Variables d'environnement | `CDSAPI_URL` et `CDSAPI_KEY` |
| 3 | `{config.cdsapirc_path()}` | **Méthode officielle** (fichier `.cdsapirc`) |
| 4 | `.env` à la racine du projet | `CDSAPI_URL=…` et `CDSAPI_KEY=…` |
| 5 | `.cdsapirc` du projet | Pour équiper une salle de PC |
            """
        )

    st.divider()
    st.subheader("2. Obtenir votre clé")
    st.markdown(
        f"""
1. Créez un compte sur le [Climate Data Store]({config.CDKB_TOKEN_URL}) (gratuit).
2. Connectez-vous, ouvrez la page *Your profile* (votre profil) et copiez le bloc
   **Set up the CDS API personal access token** : il contient deux lignes,
   `url:` et `key:`.
3. Pour chaque jeu de données que vous souhaitez utiliser, ouvrez sa page et
   acceptez les **Conditions d'utilisation**. C'est obligatoire : sans cela, le
   téléchargement est refusé.

> **Pourquoi ces deux étapes ?** Le CDS vérifie à la fois *qui* vous êtes (le
> jeton) et *à quoi* vous avez droit (les licences acceptées). Un jeton valide
> mais des licences non acceptées produit un message d'erreur qui parle de
> « permission », non de clé.
        """
    )

    with st.expander("⚠️ Quelle clé utiliser ? (la confusion la plus fréquente)"):
        st.markdown(
            """
Trois identifiants se ressemblent mais **n'ont rien à voir**. Le CDS n'en
accepte qu'un seul.

| Identifiant | Où le trouver | Sert au CDS ? |
|---|---|---|
| **Jeton d'accès personnel** (*Personal Access Token*) | Profil CDS → « Set up the CDS API personal access token » | ✅ **C'est celui-ci** |
| *Client ID* / *Client secret* | Profil ECMWF (ecmwf.int) | ❌ Réservés à l'**API Web ECMWF** (`webservices.ecmwf.int`) |
| Ancien couple `identifiant:secret` | Anciens fichiers `.cdsapirc` | ❌ Obsolète depuis septembre 2024 |

Le **Client ID** et le **Client secret** de votre compte ECMWF **ne suffisent
pas** : ce sont des identifiants OAuth2 pour les services web de l'ECMWF, pas
pour le Climate Data Store. Le CDS exige son propre jeton, affiché sur la page
de votre profil CDS.

Le jeton est une **longue chaîne d'une seule ligne**, à coller telle quelle
après `key:` — sans guillemets ni espaces.
            """
        )
        with st.expander("Coller le jeton ici pour le vérifier immédiatement"):
            probe = st.text_input("Jeton d'accès personnel", type="password",
                                  key="probe_key")
            if probe:
                verdict = cds_client.diagnose_key(probe)
                if verdict.ok:
                    st.success(f"✅ Format reconnu — {verdict.label}.")
                    st.caption(verdict.hint)
                else:
                    st.error(f"❌ {verdict.message}")
                    st.info(verdict.hint)

    st.divider()
    st.subheader("3. Enregistrer la clé")
    tab_direct, tab_file = st.tabs(["Saisie directe", "Écrire le .cdsapirc"])

    with tab_direct:
        st.caption(
            "La clé reste dans la session du navigateur et n'est jamais écrite sur "
            "le disque. Pratique pour un essai, à ressaisir après un redémarrage."
        )
        col_a, col_b = st.columns(2)
        with col_a:
            url_input = st.text_input(
                "URL du CDS", value=st.session_state.get("cds_url", config.CDS_URL)
            )
        with col_b:
            key_input = st.text_input(
                "Clé personnelle",
                value=st.session_state.get("cds_key", ""),
                type="password",
            )
        col1, col2 = st.columns(2)
        if col1.button("Appliquer pour cette session", use_container_width=True):
            st.session_state["cds_url"] = url_input
            st.session_state["cds_key"] = key_input
            st.success("Clé appliquée, valable jusqu'à la fermeture de l'onglet.")
            st.rerun()
        if col2.button("Tester la connexion", use_container_width=True):
            with st.spinner("Test en cours…"):
                report = cds_client.test_connection(
                    config.resolve_cds_config(url_input, key_input)
                )
            (st.success if report.ok else st.error)(report.title)
            st.write(report.detail)
            if report.hint:
                st.info(report.hint)

    with tab_file:
        st.caption(
            "Écrit la clé dans le fichier `.cdsapirc`. C'est la méthode recommandée "
            "par l'ECMWF : la configuration est reprise à chaque lancement."
        )
        col1, col2 = st.columns(2)
        with col1:
            url_file = st.text_input("URL", value=config.CDS_URL, key="file_url")
        with col2:
            key_file = st.text_input("Clé", value="", type="password", key="file_key")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Écrire dans mon dossier personnel", use_container_width=True):
                if not key_file:
                    st.error("Renseignez d'abord la clé.")
                else:
                    path = config.write_cdsapirc(url_file, key_file, location="user")
                    st.success(f"Fichier écrit : `{path}`")
                    st.rerun()
        with col2:
            if st.button("Écrire à la racine du projet", use_container_width=True):
                if not key_file:
                    st.error("Renseignez d'abord la clé.")
                else:
                    path = config.write_cdsapirc(url_file, key_file, location="project")
                    st.success(f"Fichier écrit : `{path}`")
                    st.rerun()
        st.markdown(
            f"""
#### Équiper une salle de mathématiques

Le fichier `{config.cdsapirc_path()}` est propre à chaque compte Windows. Pour
éviter de saisir la clé sur chaque poste, écrivez le `.cdsapirc` **à la racine
du projet** : l'application le lit, et il suffit ensuite de copier le dossier
sur les autres machines.
            """
        )

    st.divider()
    st.subheader("4. Diagnostic")
    if st.button("Lancer le diagnostic complet", type="primary"):
        with st.spinner("Vérification en cours…"):
            report = cds_client.test_connection(cfg, deep=True)
        (st.success if report.ok else st.error)(report.title)
        st.write(report.detail)
        if report.latency_s is not None:
            st.caption(f"Temps de réponse : {report.latency_s:.2f} s")
        if report.hint:
            st.info(report.hint)

    st.subheader("5. Conditions d'utilisation")
    st.markdown(
        """
Une clé valide ne suffit pas : le CDS vérifie aussi, pour **chaque jeu de
données**, que vous avez accepté ses conditions. Sans cela, le téléchargement
renvoie une erreur *« required licences not accepted »*.
"""
    )
    st.markdown(_licence_links(), unsafe_allow_html=True)

    if cfg.is_configured and st.button("Vérifier quelles licences sont acceptées"):
        from c3s_lab import licence_check

        with st.spinner("Interrogation du CDS…"):
            results = licence_check.check_licences(cfg.url, cfg.key)
        pending = []
        for name, state in results.items():
            dataset = catalog.get(name)
            if state == "autorisee":
                st.success(f"✅ {dataset.label}")
            elif state == "licence-refusee":
                st.error(f"❌ {dataset.label} — conditions à accepter")
                pending.append(name)
            else:
                st.warning(f"⚠️ {dataset.label} — {state}")
        if pending:
            st.error(
                f"{len(pending)} jeu(x) de données nécessite(nt) l'acceptation des "
                "conditions ci-dessus."
            )
        else:
            st.success("Toutes les conditions sont acceptées. L'application est prête.")

    with st.expander("Contenu attendu du fichier .cdsapirc"):
        st.code(f"url: {config.CDS_URL}\nkey: <votre clé personnelle>", language="text")
        st.caption(
            f"Emplacement Windows : `{config.cdsapirc_path()}`\n\n"
            f"Procédure officielle : {config.CDKB_WINDOWS_URL}"
        )


# --------------------------------------------------------------------------- #
# Page — Avant / après (outil de comparaison d'époques)
# --------------------------------------------------------------------------- #

#: Périodes proposées par défaut, avec leur libellé pédagogique.
EPOCH_PRESETS = {
    "Hier (1970-1989) vs aujourd'hui (2015-2024)": ((1970, 1989), (2015, 2024)),
    "Avant (1950-1969) vs après (2005-2024)": ((1950, 1969), (2005, 2024)),
    "Normale 1991-2020 vs 2015-2024": ((1991, 2020), (2015, 2024)),
    "Écart direct : 1960 vs 2020": ((1960, 1960), (2020, 2020)),
}


def page_avant_apres() -> None:
    st.title("🔄 Avant / Après : le climat a-t-il changé ?")
    st.markdown(
        "Comparez deux périodes et observez la différence. C'est l'outil le plus "
        "efficace pour rendre le réchauffement visible sans calcul compliqué."
    )

    col1, col2 = st.columns(2)
    with col1:
        scope = st.selectbox("Où regarder ?", ["Une ville", "France", "Europe"])
    with col2:
        variable = st.selectbox(
            "Donnée",
            ["2m_temperature", "total_precipitation"],
            format_func=lambda v: (
                "Température de l'air (°C)" if "temp" in v else "Précipitations (mm)"
            ),
        )
    unit = "°C" if "temp" in variable else "mm"

    if scope == "Une ville":
        city = st.selectbox("Ville", [p.name for p in places.FRENCH_CITIES])
        place = next(p for p in places.FRENCH_CITIES if p.name == city)
        area = (place.lat + 1.5, place.lon - 1.5, place.lat - 1.5, place.lon + 1.5)
        st.caption(f"📍 {place.lat:.2f}°N, {place.lon:.2f}°E — {place.region}")

        def extract(r, _p=place):
            return r.series_at(_p.lat, _p.lon, name=unit)
    else:
        area = {"France": (51.5, -5.5, 41.0, 10.0),
                "Europe": (72.0, -25.0, 33.0, 45.0)}[scope]
        st.caption(
            f"📍 {places.area_label(area)} — moyenne pondérée par le cosinus de la latitude."
        )

        def extract(r):
            return r.area_mean()

    # --- 1. Choix des deux périodes ---------------------------------------------
    st.subheader("1. Choisir deux périodes")
    preset = st.selectbox("Comparaison rapide", list(EPOCH_PRESETS), index=0)
    (b0, b1), (a0, a1) = EPOCH_PRESETS[preset]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        b0 = st.number_input("Période 1 : début", 1940, 2024, int(b0), 1)
    with col2:
        b1 = st.number_input("Période 1 : fin", int(b0) + 1, 2024, int(b1), 1)
    with col3:
        a0 = st.number_input("Période 2 : début", 1940, 2024, int(a0), 1)
    with col4:
        a1 = st.number_input("Période 2 : fin", int(a0) + 1, 2024, int(a1), 1)
    if b0 >= b1 or a0 >= a1:
        st.error("Chaque période doit contenir au moins deux années.")
        st.stop()

    with st.spinner("Récupération des données sur les deux périodes…"):
        result = _fetch(
            dataset_key="monthly_means", variable=variable,
            years=(min(b0, a0), max(b1, a1)), area=area,
        )
    ui.data_banner(result)

    series = extract(result)
    before = analysis.monthly_climatology(series, (b0, b1))
    after = analysis.monthly_climatology(series, (a0, a1))
    if before.empty or after.empty:
        st.warning("Pas assez de données sur l'une des deux périodes.")
        st.stop()

    label_b, label_a = f"{b0}–{b1}", f"{a0}–{a1}"
    delta = (after - before).reindex(analysis.MONTH_LABELS_LONG)
    mean_delta = float((after - before).mean())

    # --- 2. Les deux courbes -----------------------------------------------------
    st.subheader("2. Les deux périodes, mois par mois")
    ui.show_figure(
        viz.before_after_charts(
            before, after, label_b, label_a, unit=unit,
            title=f"{scope} — {label_b} comparé à {label_a}",
        ),
        key="avant_apres_courbes",
    )
    ui.show_figure(
        viz.delta_bars(
            list(delta.index), list(delta.values), unit,
            title=f"Écart : {label_a} moins {label_b}",
        ),
        key="avant_apres_barres",
    )
    col1, col2, col3 = st.columns(3)
    col1.metric(f"Moyenne {label_b}", f"{float(before.mean()):.2f} {unit}")
    col2.metric(f"Moyenne {label_a}", f"{float(after.mean()):.2f} {unit}")
    col3.metric("Écart moyen", f"{mean_delta:+.2f} {unit}", delta_color="off")

    # --- 3. Le curseur ----------------------------------------------------------
    st.subheader("3. Faites glisser pour voir le changement")
    if scope == "Une ville":
        st.info(
            "En mode ville, la comparaison se fait sur les courbes ci-dessus : "
            "une ville ne représente qu'un point, il n'y a pas de carte à animer. "
            "Choisissez « France » ou « Europe » pour utiliser le curseur."
        )
    else:
        st.markdown(
            "Faites glisser le curseur : la carte se transforme progressivement de "
            "la première période vers la seconde. Repérez les zones qui changent le plus."
        )
        st.caption(
            "Chaque carré correspond à la même maille de 0,25° dans les deux cartes : "
            "la comparaison est donc rigoureuse, et non illustrative."
        )
        with st.spinner("Construction des deux cartes…"):
            data = result.data
            field_b = data.sel(time=data.time.dt.year.isin(range(b0, b1 + 1))).mean("time")
            field_a = data.sel(time=data.time.dt.year.isin(range(a0, a1 + 1))).mean("time")
        scale, zmin, zmax = viz.delta_scale((field_a - field_b).values)
        fig_b = maps.field_map(
            field_b, title=label_b, unit=unit, period=label_b, area=area,
            colorscale=scale, zmin=zmin, zmax=zmax,
        )
        fig_a = maps.field_map(
            field_a, title=label_a, unit=unit, period=label_a, area=area,
            colorscale=scale, zmin=zmin, zmax=zmax,
        )
        st.plotly_chart(
            maps.blend_frames([fig_b, fig_a], [label_b, label_a]),
            use_container_width=True, key="avant_apres_curseur",
        )
        st.caption(
            f"Échelle de couleurs centrée sur zéro : le bleu signale un écart négatif "
            f"(refroidissement), le rouge un écart positif (réchauffement). "
            f"Amplitude retenue : ±{abs(zmax):.1f} {unit}."
        )

    # --- 4. Questions -----------------------------------------------------------
    st.subheader("4. Questions pour la classe")
    for i, q in enumerate([
        "De combien la valeur moyenne a-t-elle changé entre ces deux périodes ?",
        "L'écart est-il le même en janvier qu'en juillet ? Pourquoi ?",
        "Sur la carte, quelles zones changent le plus ? Lesquelles le moins ?",
        "Cette différence pourrait-elle venir de la seule météo ? Justifier.",
    ], 1):
        st.markdown(f"{i}. {q}")

    if ui.is_teacher():
        ui.method_note(
            "Éléments de correction",
            f"Écart moyen de **{mean_delta:+.2f} {unit}** entre {label_b} et {label_a} "
            f"sur {scope}. L'écart croît généralement avec la latitude et la "
            "continentalité. L'argument « simple météo » se réfute en montrant que "
            "la variabilité naturelle est de l'ordre de ±0,3 °C, très inférieure à "
            "l'écart mesuré sur trente ans.",
        )
    ui.citation()



    st.subheader("Questions pour la classe")
    questions = [
        "De combien la température moyenne a-t-elle augmenté entre ces deux périodes ?",
        "L'écart est-il le même en janvier qu'en juillet ? Pourquoi ?",
        "Sur la carte, quelles régions ont le plus changé ? Lesquelles le moins ?",
        "Cette différence pourrait-elle s'expliquer seulement par la météo ? Justifier.",
    ]
    for i, q in enumerate(questions, 1):
        st.markdown(f"{i}. {q}")

    if ui.is_teacher():
        ui.method_note(
            "Éléments de correction",
            f"Écart moyen de **{deltas:+.2f} {unit}** entre {label_b} et {label_a} sur "
            f"{scope}. L'écart croît généralement avec la latitude et l continentalité. "
            "L'argument « météo » se réfute en montrant que la variabilité naturelle "
            "est de l'ordre de ±0,3 °C, bien inférieure à l'écart mesuré sur trente ans.",
        )

    ui.citation()


SEASONS = {
    "Année": None,
    "Hiver (djf)": "djf",
    "Printemps (mam)": "mam",
    "Été (jja)": "jja",
    "Automne (son)": "son",
}

#: Couleurs adaptées à chaque variable ; le type de grandeur pilote le choix.
SCALES = {
    "2m_temperature": viz.TEMP_SCALE,
    "maximum_2m_temperature": viz.TEMP_SCALE,
    "minimum_2m_temperature": viz.TEMP_SCALE,
    "total_precipitation": viz.PRECIP_SCALE,
    "mean_sea_level_pressure": viz.PRESSURE_SCALE,
}


def page_cartes() -> None:
    st.title("🗺️ Cartes climatiques")
    st.markdown(
        "Construisez des cartes de température, de précipitations ou de pression à "
        "partir des données ERA5. Chaque carte indique son unité, sa résolution et sa "
        "période, pour rester interprétable une fois imprimée."
    )

    dataset_key, cds_id, variable = ui.dataset_picker("monthly_means")
    dataset = catalog.get(dataset_key)
    years = ui.years_picker(dataset_key)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        season_label = st.selectbox("Période représentée", list(SEASONS), index=0)
    with col2:
        month = st.selectbox(
            "Mois isolé",
            [0] + list(range(1, 13)),
            format_func=lambda m: "— toute l'année —" if m == 0 else analysis.MONTH_LABELS_LONG[m - 1],
        )
    with col3:
        contours = st.toggle("Isothermes / isobares", value=False)

    variable_meta = dataset.var(variable)
    unit = variable_meta.unit if variable_meta else ""

    area = (72.0, -12.0, 33.0, 25.0)
    domain = places.DOMAINS[1]
    area = domain.area

    with st.spinner("Récupération des données…"):
        result = _fetch(
            dataset_key=dataset_key,
            variable=variable,
            years=years,
            area=area,
            months=[month] if month else None,
        )

    ui.data_banner(result)

    field = result.field(month=month or None, season=SEASONS[season_label])
    spec = viz.TEMP_SCALE
    for key, scale in SCALES.items():
        if variable.startswith(key):
            spec = scale
            break

    zmin = zmax = None
    if "temperature" in variable:
        zmin, zmax = -30.0, 45.0
    elif "precipitation" in variable:
        zmin, zmax = 0.0, 200.0
    elif "pressure" in variable:
        zmin, zmax = 960.0, 1050.0

    fig = maps.field_map(
        field,
        title=f"{variable_meta.label if variable_meta else variable} — {season_label.lower()}",
        unit=unit,
        period=f"moyenne {years[0]}-{years[1]}",
        area=area,
        colorscale=spec,
        zmin=zmin,
        zmax=zmax,
        contours=contours,
    )
    ui.show_figure(fig, key="carte_champ")

    ui.citation()
    ui.method_note(
        "Comment lire cette carte",
        f"""
- Chaque carré représente une cellule de **0,25° x 0,25°**, soit environ
  **25 km de côté**. Ce n'est pas un relevé de station : c'est la moyenne du
  modèle sur cette maille.
- La projection est **équirectangulaire** : les degrés de latitude et de
  longitude occupent la même place, ce qui conserve les proportions.
- {'Les lignes relient les points de valeur identique : ce sont des isothermes.' if contours else 'Les couleurs montrent la valeur dans chaque maille.'}
- La valeur lue en un point a une incertitude de position d'environ **14 km**
  (une demi-maille) : une ville n'est pas un point mathématique.
        """,
    )

    with st.expander("Télécharger les données de cette carte (CSV)"):
        table = field.to_pandas()
        st.download_button(
            "CSV de la grille (une colonne par longitude)",
            table.to_csv(sep=";").encode("utf-8-sig"),
            file_name="c3s_lab_carte.csv",
            mime="text/csv",
        )
        st.caption(
            "Séparateur décimal `;` pour Excel en configuration française. "
            "Les cellules de terre et de mer sont toutes conservées."
        )


# --------------------------------------------------------------------------- #
# Page 4 — Graphiques
# --------------------------------------------------------------------------- #


def page_graphiques() -> None:
    st.title("📈 Graphiques et séries temporelles")
    st.markdown(
        "Suivez l'évolution d'une ville, d'un domaine ou de la planète entière, et "
        "mesurez la tendance comme on l'enseigne en cours de mathématiques."
    )

    reference = st.session_state.get("reference", config.WMO_NORMAL_PERIOD)
    col1, col2 = st.columns(2)
    with col1:
        scope_label = st.selectbox(
            "Périmètre d'étude",
            ["Une ville", "Domaine (moyenne spatiale)", "Europe", "Hémisphère nord"],
        )
    with col2:
        variable = st.selectbox(
            "Variable",
            ["2m_temperature", "total_precipitation", "mean_sea_level_pressure"],
            format_func=lambda v: {
                "2m_temperature": "Température de l'air à 2 m (°C)",
                "total_precipitation": "Précipitations (mm)",
                "mean_sea_level_pressure": "Pression au niveau de la mer (hPa)",
            }[v],
        )

    unit = {"2m_temperature": "°C", "total_precipitation": "mm",
            "mean_sea_level_pressure": "hPa"}[variable]

    if scope_label == "Une ville":
        city = st.selectbox("Ville", [p.name for p in places.FRENCH_CITIES])
        place = next(p for p in places.FRENCH_CITIES if p.name == city)
        st.caption(f"📍 {place.lat:.2f}°N, {place.lon:.2f}°E — {place.region}"
                   f" · {place.tag}")
        area = (place.lat + 1.5, place.lon - 1.5, place.lat - 1.5, place.lon + 1.5)
        years = ui.years_picker("monthly_means", (1991, 2024))
        result = _fetch(
            dataset_key="monthly_means", variable=variable,
            years=years, area=area,
        )
        series = result.series_at(place.lat, place.lon, name=unit)
    else:
        area = {"Domaine (moyenne spatiale)": (51.5, -5.5, 41.0, 10.0),
                "Europe": (72.0, -25.0, 33.0, 45.0),
                "Hémisphère nord": (90.0, -180.0, 0.0, 180.0)}[scope_label]
        years = ui.years_picker("monthly_means", (1979, 2024))
        st.caption(
            f"📍 {places.area_label(area)} — moyenne pondérée par le cosinus de la latitude."
        )
        result = _fetch(
            dataset_key="monthly_means", variable=variable,
            years=years, area=area,
        )
        series = result.area_mean()

    ui.data_banner(result)

    st.subheader("Série mensuelle")
    monthly_anom = analysis.anomaly_relative_to_climatology(
        series, analysis.monthly_climatology(series, reference)
    )
    fig = viz.time_series(series, f"{scope_label} — {variable}", unit,
                          anomalies=monthly_anom)
    ui.show_figure(fig, key="serie_mensuelle")

    st.subheader("Moyenne annuelle et écart à la normale")
    annual = analysis.annual_mean(series)
    if len(annual) < 3:
        st.info("Série trop courte pour calculer une tendance.")
        st.stop()
    anomalies = analysis.anomalies(annual, reference)
    fig2 = viz.annual_anomaly_bars(
        annual, anomalies,
        f"Écart à la normale {reference[0]}-{reference[1]}",
        unit, reference,
    )
    ui.show_figure(fig2, key="anomalies")

    trend = analysis.linear_trend(annual, unit)
    col1, col2, col3 = st.columns(3)
    col1.metric("Tendance par décennie", f"{trend.per_decade:+.2f} {unit}")
    col2.metric("Coefficient R²", f"{trend.r_squared:.2f}")
    col3.metric("Nombre d'années", trend.n)

    st.caption(f"Équation de la droite : `{trend.equation()}`")
    st.plotly_chart(
        viz.trend_chart(series, trend, "Série et tendance linéaire", unit),
        use_container_width=True,
    )

    ui.citation()
    ui.method_note(
        "Méthode : anomalies, normales et tendance",
        f"""
- **Normale {reference[0]}-{reference[1]}** : moyenne calculée sur trente ans, la
  durée recommandée par l'OMM. C'est la seule référence qui rend les chiffres
  comparables.
- **Anomalie** : `valeur − normale`. Elle dit *écart par rapport à quoi*, ce qu'une
  température absolue ne dit pas.
- **Tendance** : droite des moindres carrés sur {trend.n} années complètes. Les
  années incomplètes sont exclues, sinon une année à trois mois compterait autant
  qu'une année entière.
- **R² = {trend.r_squared:.2f}** mesure la qualité de l'ajustement, pas une probabilité.
  Une tendance peut être significative sans que R² soit proche de 1.
- **Prudence** : les années ont une variabilité naturelle de l'ordre de
  ±0,3 °C en France. Une année isolée ne prouve rien ; seule la tendance compte.
        """,
    )

    st.subheader("Données chiffrées")
    st.dataframe(
        annual.rename("valeur").to_frame().join(
            anomalies.rename("écart à la normale")
        ),
        use_container_width=True,
    )
    st.download_button(
        "Télécharger la série annuelle (CSV)",
        pd.DataFrame({"valeur": annual, "ecart_normal": anomalies})
        .rename_axis("annee").to_csv(sep=";").encode("utf-8-sig"),
        file_name="c3s_lab_serie.csv",
        mime="text/csv",
    )


# --------------------------------------------------------------------------- #
# Page 5 — Comparaison de villes
# --------------------------------------------------------------------------- #


def page_villes() -> None:
    st.title("🏙️ Comparer des villes")
    st.markdown(
        "Comparez les normales climatiques de plusieurs villes et calculez les "
        "indices qui caractérisent un climat."
    )

    reference = st.session_state.get("reference", config.WMO_NORMAL_PERIOD)
    with_world = st.toggle("Inclure des villes du monde", value=False)
    selection = ui.city_picker(["Brest", "Strasbourg", "Marseille"], world=with_world)
    if not selection:
        st.info("Choisissez au moins une ville pour lancer la comparaison.")
        st.stop()

    years = ui.years_picker("monthly_means", reference)
    st.caption(f"Normale de référence : {reference[0]}–{reference[1]}")

    # Un domaine englobant toutes les villes sélectionnées suffit : la valeur
    # extraite ensuite en chaque point est indépendante de la taille de la boîte.
    lats = [p.lat for p in selection]
    lons = [p.lon for p in selection]
    area = (max(lats) + 1.0, min(lons) - 1.0, min(lats) - 1.0, max(lons) + 1.0)

    with st.spinner("Récupération des données pour toutes les villes…"):
        temp = _fetch(
            dataset_key="monthly_means", variable="2m_temperature",
            years=years, area=area,
        )
        precip = _fetch(
            dataset_key="monthly_means", variable="total_precipitation",
            years=years, area=area,
        )

    ui.data_banner(temp)
    if precip.simulated != temp.simulated:
        st.warning("Sources de données incohérentes entre température et précipitations.")

    temp_series = {p.name: temp.series_at(p.lat, p.lon, name=p.name) for p in selection}
    precip_series = {
        p.name: precip.series_at(p.lat, p.lon, name=p.name) for p in selection
    }
    temp_clim = {k: analysis.monthly_climatology(v, reference) for k, v in temp_series.items()}
    precip_clim = {k: analysis.monthly_climatology(v, reference) for k, v in precip_series.items()}

    st.subheader("Courbes mensuelles de température")
    ui.show_figure(
        viz.multi_city_climato(temp_clim, "Températures mensuelles moyennes", "°C"),
        key="villes_temp",
    )

    st.subheader("Diagrammes ombrothermiques")
    cols = st.columns(min(3, len(selection)))
    for i, place in enumerate(selection):
        with cols[i % len(cols)]:
            name = place.name
            fig = viz.ombrothermic_diagram(
                temp_clim[name], precip_clim[name],
                f"{name} — diagramme ombrothermique",
            )
            st.plotly_chart(fig, use_container_width=True, key=f"ombro_{i}")

    st.subheader("Indices climatiques")
    all_indices: dict[str, list] = {}
    for place in selection:
        name = place.name
        all_indices[name] = analysis.describe_temperature(
            temp_series[name], precip_series[name], reference=reference
        )

    names = [i.name for i in all_indices[selection[0].name]]
    table = pd.DataFrame(
        {
            p.name: {i.name: round(i.value, 1) for i in all_indices[p.name]}
            for p in selection
        }
    ).reindex(names)
    units = {i.name: i.unit for i in all_indices[selection[0].name]}
    st.dataframe(table, use_container_width=True)
    st.caption("Unités : " + ", ".join(f"{k} → {v}" for k, v in units.items()))

    # Diagrammes en barres, un par grandeur clé.
    for label, key in [
        ("Température moyenne annuelle", "Température moyenne annuelle"),
        ("Amplitude thermique annuelle", "Amplitude thermique annuelle"),
        ("Cumul annuel de précipitations", "Cumul annuel de précipitations"),
    ]:
        if key not in table.index:
            continue
        values = [float(table.loc[key, p.name]) for p in selection]
        fig = viz.bar_comparison(
            [p.name for p in selection], values, label, units.get(key, "")
        )
        ui.show_figure(fig, key=f"bar_{key[:12]}")

    st.download_button(
        "Télécharger le tableau des indices (CSV)",
        table.to_csv(sep=";").encode("utf-8-sig"),
        file_name="c3s_lab_indices.csv",
        mime="text/csv",
    )

    ui.citation()
    ui.method_note(
        "Ce que disent vraiment ces indices",
        f"""
- **Température moyenne annuelle** : moyenne des douze moyennes mensuelles. Elle
  décrit la rigueur du climat, pas la chaleur d'un jour donné.
- **Amplitude thermique annuelle** : écart entre le mois le plus chaud et le plus
  froid. C'est l'indicateur de continentalité : petite près de la mer, grande à
  l'intérieur des terres.
- **Cumul annuel de précipitations** : somme des douze mois. Il masque la
  saisonnalité — Marseille et Brest peuvent avoir des cumuls proches avec des
  régimes opposés. Regardez toujours la répartition.
- Tous ces indices sont calculés sur la normale **{reference[0]}–{reference[1]}**,
  et non sur l'année en cours.
        """,
    )


# --------------------------------------------------------------------------- #
# Page 6 — Activités
# --------------------------------------------------------------------------- #


def page_activites() -> None:
    st.title("🎓 Activités pédagogiques")
    st.markdown(
        "Sept séquences clé en main, alignées sur les programmes de cycle 4. "
        "Chaque fiche indique l'objectif, les compétences visées, les questions "
        "poser aux élèves et les réponses attendues."
    )

    col1, col2 = st.columns(2)
    with col1:
        level = st.selectbox("Filtrer par niveau", ["Tous", "5e", "4e", "3e"])
    with col2:
        subject = st.selectbox(
            "Filtrer par discipline",
            ["Toutes", "SVT", "Mathématiques", "Physique", "Géographie"],
        )

    catalogue = activities.ACTIVITIES
    if level != "Tous":
        catalogue = activities.by_level(level)
    if subject != "Toutes":
        catalogue = [a for a in catalogue if subject.lower() in a.subject.lower()]

    if not catalogue:
        st.warning("Aucune activité ne correspond à ces filtres.")
        st.stop()

    keys = [a.key for a in catalogue]
    chosen_key = st.selectbox(
        "Activité sélectionnée",
        keys,
        format_func=lambda k: next(a.title for a in catalogue if a.key == k),
    )
    activity = activities.get(chosen_key)

    st.markdown(f"## {activity.title}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Niveau", activity.levels)
    col2.metric("Durée", activity.duration)
    col3.metric("Disciplines", activity.subject.split("·")[0].strip())
    col4.metric("Difficulté", "●" * activity.difficulty + "○" * (3 - activity.difficulty))

    st.markdown("**Objectif** — " + activity.objective)

    with st.expander("Compétences visées"):
        for skill in activity.skills:
            st.markdown(f"- {skill}")

    if activity.teacher_tip:
        ui.method_note("Conseil de mise en œuvre", activity.teacher_tip)

    st.divider()
    st.subheader("Données de l'activité")
    with st.spinner("Préparation des données…"):
        _activity_figures(activity)

    st.divider()
    st.subheader("Déroulé")
    ui.show_steps(activity.steps)

    st.divider()
    if not ui.is_teacher():
        with st.expander("🔒 Espace enseignant — codes et corrigés"):
            st.caption(
                "Les onglets *Accueil*, *Connexion CDS* et *Méthode* sont réservés. "
                "Saisissez le code ci-dessous pour les débloquer ; vous les "
                "reverrouillerez depuis la barre latérale."
            )
            code = st.text_input("Code enseignant", type="password", key="gate_activites")
            if code:
                if code.strip() == ui.TEACHER_CODE:
                    st.session_state["teacher_unlocked"] = True
                    st.success("Code accepté. Les onglets réservés apparaissent en bas "
                               "du menu — rechargez la page pour les voir.")
                    st.rerun()
                else:
                    st.error("Code incorrect.")

    with st.expander("Fiche imprimable (PDF / impression)"):
        st.markdown(_activity_sheet(activity))
        st.download_button(
            "Télécharger la fiche (Markdown)",
            _activity_sheet(activity).encode("utf-8"),
            file_name=f"activite_{activity.key}.md",
            mime="text/markdown",
        )


def _activity_sheet(activity) -> str:
    """Fiche d'activité au format Markdown, utilisable en classe ou en archive."""
    lines = [
        f"# {activity.title}",
        "",
        f"**Niveau** : {activity.levels}  ",
        f"**Durée** : {activity.duration}  ",
        f"**Disciplines** : {activity.subject}  ",
        f"**Jeu de données** : {catalog.get(activity.dataset).label}  ",
        f"**Villes proposées** : {', '.join(activity.default_places)}",
        "",
        "## Objectif",
        activity.objective,
        "",
        "## Compétences",
    ]
    lines += [f"- {s}" for s in activity.skills]
    lines += ["", "## Déroulé"]
    for i, step in enumerate(activity.steps, start=1):
        lines += [f"### Étape {i} — {step.title}", "", step.instruction]
        if step.hint:
            lines += ["", f"> **Indice** : {step.hint}"]
        lines += ["", f"**Réponse attendue** : {step.expected}", ""]
    if activity.teacher_tip:
        lines += ["## Conseil de mise en œuvre", activity.teacher_tip, ""]
    lines += [
        "## Source des données",
        f"{config.ERA5_CITATION}",
        "",
        config.ERA5_ATTRIBUTION,
        "",
    ]
    return "\n".join(lines)


def _activity_figures(activity) -> None:
    """
    Produit les figures spécifiques à une activité.

    Chaque activité a ses propres besoins : certaines comparent des villes,
    d'autres montrent l'évolution annuelle ou une carte. Cette fonction joue le
    rôle de « cook » : elle construit exactement ce qui est utile et rien de plus.
    """
    reference = st.session_state.get("reference", activity.reference)
    key = activity.key

    if key in ("saisons_occean_continent", "cycle_eau_precipitations"):
        _figures_city_comparison(activity, reference)
    elif key == "rechauffement_climatique":
        _figures_warming(activity, reference)
    elif key == "vent_pression":
        _figures_wind_pressure(activity, reference)
    elif key == "cartes_climatiques":
        _figures_maps(activity, reference)
    elif key == "canicule_sante":
        _figures_heatwave(activity, reference)
    elif key == "latitude_rayonnement":
        _figures_latitude(activity, reference)
    else:  # repli prudent si une activité est ajoutée sans figure dédiée
        st.info("Aucune figure dédiée à cette activité pour l'instant.")


def _activity_cities(activity) -> list:
    """Villes de l'activité, complétées par des valeurs par défaut sensées."""
    names = [p.name for p in places.FRENCH_CITIES]
    chosen = [n for n in activity.default_places if n in names]
    return [p for p in places.FRENCH_CITIES if p.name in chosen]


def _bbox(points: list, pad: float = 1.0) -> tuple[float, float, float, float]:
    """Encadré englobant une liste de villes."""
    lats = [p.lat for p in points]
    lons = [p.lon for p in points]
    return (max(lats) + pad, min(lons) - pad, min(lats) - pad, max(lons) + pad)


def _figures_city_comparison(activity, reference) -> None:
    cities = _activity_cities(activity)
    if not cities:
        st.info("Aucune ville disponible pour cette activité.")
        return
    area = _bbox(cities, 1.5)
    years = (reference[0], reference[1])

    temp = _fetch(dataset_key="monthly_means", variable="2m_temperature",
                  years=years, area=area)
    precip = _fetch(dataset_key="monthly_means", variable="total_precipitation",
                    years=years, area=area)
    ui.data_banner(temp)

    t_series = {p.name: temp.series_at(p.lat, p.lon, name=p.name) for p in cities}
    p_series = {p.name: precip.series_at(p.lat, p.lon, name=p.name) for p in cities}
    t_clim = {k: analysis.monthly_climatology(v, reference) for k, v in t_series.items()}
    p_clim = {k: analysis.monthly_climatology(v, reference) for k, v in p_series.items()}

    ui.show_figure(
        viz.multi_city_climato(t_clim, "Températures mensuelles moyennes", "°C"),
        key=f"act_{activity.key}_temp",
    )

    amplitudes = {
        p.name: analysis.thermal_amplitude(t_clim[p.name]) for p in cities
    }
    ui.show_figure(
        viz.bar_comparison(
            list(amplitudes), list(amplitudes.values()),
            "Amplitude thermique annuelle", "°C", color=viz.C_TEMP,
        ),
        key=f"act_{activity.key}_amp",
    )

    st.subheader("Diagrammes ombrothermiques")
    for i, place in enumerate(cities):
        st.plotly_chart(
            viz.ombrothermic_diagram(
                t_clim[place.name], p_clim[place.name],
                f"{place.name} — diagramme ombrothermique",
            ),
            use_container_width=True, key=f"act_{activity.key}_ombro_{i}",
        )

    table = pd.DataFrame({
        p.name: {
            i.name: round(i.value, 1)
            for i in analysis.describe_temperature(
                t_series[p.name], p_series[p.name], reference=reference
            )
        }
        for p in cities
    })
    st.dataframe(table, use_container_width=True)
    st.download_button(
        "Télécharger le tableau des indices (CSV)",
        table.to_csv(sep=";").encode("utf-8-sig"),
        file_name=f"indices_{activity.key}.csv", mime="text/csv",
    )
    ui.citation()


def _figures_warming(activity, reference) -> None:
    city = st.selectbox("Ville étudiée", [p.name for p in places.FRENCH_CITIES], index=0)
    place = next(p for p in places.FRENCH_CITIES if p.name == city)
    y0, y1 = ui.years_picker("monthly_means", (1979, 2024))
    st.caption(
        f"📍 {place.lat:.2f}°N, {place.lon:.2f}°E — {place.region}. "
        f"Normale de référence : {reference[0]}–{reference[1]}."
    )

    result = _fetch(
        dataset_key="monthly_means", variable="2m_temperature",
        years=(y0, y1), area=_bbox([place], 1.5),
    )
    ui.data_banner(result)
    series = result.series_at(place.lat, place.lon, name="°C")
    annual = analysis.annual_mean(series)
    anomalies = analysis.anomalies(annual, reference)
    trend = analysis.linear_trend(annual, "°C")

    ui.show_figure(
        viz.annual_anomaly_bars(
            annual, anomalies, f"{city} — écart annuel à la normale", "°C", reference
        ),
        key=f"act_{activity.key}_anom",
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Tendance par décennie", f"{trend.per_decade:+.2f} °C")
    col2.metric("R²", f"{trend.r_squared:.2f}")
    col3.metric("Années complètes", trend.n)
    st.plotly_chart(
        viz.trend_chart(series, trend, f"{city} — série et tendance", "°C"),
        use_container_width=True, key=f"act_{activity.key}_trend",
    )
    ui.citation()
    ui.method_note(
        "Comment lire la tendance",
        f"""
La droite donne **{trend.per_decade:+.2f} °C par décennie** sur {trend.n} années.
Une année isolée peut s'écarter de la normale de ±0,3 à ±0,5 °C sans que cela
dise quoi que ce soit : c'est la variabilité naturelle. Seule la pente de la
droite, lue sur plusieurs décennies, est un signal.
        """,
    )


def _figures_wind_pressure(activity, reference) -> None:
    area = (72.0, -12.0, 33.0, 25.0)
    month = st.selectbox(
        "Mois représenté",
        list(range(1, 13)),
        format_func=lambda m: analysis.MONTH_LABELS_LONG[m - 1],
        index=0,
    )
    year = st.number_input("Année", min_value=1940, max_value=config.LAST_COMPLETE_YEAR,
                           value=2020, step=1)
    y0, y1 = ui.years_picker("monthly_means", (year, year + 1))
    month_list = [month]

    mslp = _fetch(dataset_key="monthly_means", variable="mean_sea_level_pressure",
                  years=(y0, y1), area=area, months=month_list)
    ui.data_banner(mslp)
    field = mslp.field(month=month)

    ui.show_figure(
        maps.field_map(
            field,
            title=f"Pression au niveau de la mer — {analysis.MONTH_LABELS_LONG[month - 1]} {y0}",
            unit="hPa", period=f"moyenne mensuelle {y0}", area=area,
            colorscale=viz.PRESSURE_SCALE, zmin=960.0, zmax=1050.0,
            contours=True,
        ),
        key=f"act_{activity.key}_mslp",
    )

    if st.checkbox("Ajouter le champ de vent à 10 m (deux requêtes supplémentaires)"):
        u = _fetch(dataset_key="monthly_means", variable="10m_u_component_of_wind",
                   years=(y0, y1), area=area, months=month_list)
        v = _fetch(dataset_key="monthly_means", variable="10m_v_component_of_wind",
                   years=(y0, y1), area=area, months=month_list)
        ui.show_figure(
            maps.wind_map(
                u.field(month=month), v.field(month=month),
                title="Vent à 10 m — vitesse et direction",
                period=f"{analysis.MONTH_LABELS_LONG[month - 1]} {y0}", area=area,
            ),
            key=f"act_{activity.key}_wind",
        )

    ui.citation()
    ui.method_note(
        "Pression, isobares et mouvement de l'air",
        """
- La **pression atmosphérique** est le poids de l'air sur une surface. Elle se
  mesure en **hectopascals (hPa)** ; au niveau de la mer, sa moyenne mondiale
  vaut environ **1013 hPa**.
- Des points de même pression reliés forment des **isobares**. Plus elles sont
  serrées, plus le vent est fort.
- L'air s'écoule des zones de **hautes pressions** (H, anticyclone) vers les zones
  de **basses pressions** (L, dépression). Sans écart de pression, pas de vent.
- À cause de la rotation de la Terre, le vent s'incline le long des isobares :
  dans l'hémisphère nord, il tourne dans le sens horaire autour d'un
  anticyclone.
        """,
    )


def _figures_maps(activity, reference) -> None:
    domain = st.selectbox("Domaine", [d.name for d in places.DOMAINS], index=1)
    area = next(d for d in places.DOMAINS if d.name == domain).area
    variable = st.selectbox(
        "Variable cartographiée",
        ["2m_temperature", "total_precipitation", "mean_sea_level_pressure"],
        format_func=lambda v: {
            "2m_temperature": "Température à 2 m",
            "total_precipitation": "Précipitations",
            "mean_sea_level_pressure": "Pression au niveau de la mer",
        }[v],
    )
    year = st.number_input("Année", min_value=1940, max_value=config.LAST_COMPLETE_YEAR,
                           value=2020, step=1)
    y0, y1 = ui.years_picker("monthly_means", (reference[0], reference[1]))
    month = st.selectbox(
        "Mois isolé", [0] + list(range(1, 13)),
        format_func=lambda m: "— toute l'année —" if m == 0 else analysis.MONTH_LABELS_LONG[m - 1],
    )
    style = st.radio("Représentation", ["Cellules colorées", "Isothermes / isobares"],
                     horizontal=True)

    result = _fetch(dataset_key="monthly_means", variable=variable,
                    years=(y0, y1), area=area, months=[month] if month else None)
    ui.data_banner(result)
    field = result.field(month=month or None)

    unit = result.unit
    scale = viz.TEMP_SCALE
    zmin, zmax = -30.0, 45.0
    if "precipitation" in variable:
        scale, zmin, zmax = viz.PRECIP_SCALE, 0.0, 200.0
    elif "pressure" in variable:
        scale, zmin, zmax = viz.PRESSURE_SCALE, 960.0, 1050.0

    ui.show_figure(
        maps.field_map(
            field,
            title=f"{variable} — {places.area_label(area)}",
            unit=unit, period=f"{y0}-{y1}", area=area,
            colorscale=scale, zmin=zmin, zmax=zmax,
            contours=(style == "Isothermes / isobares"),
        ),
        key=f"act_{activity.key}_map",
    )
    ui.citation()
    ui.method_note(
        "Choisir une représentation honnête",
        """
- **Cellules colorées** : chaque maille de 0,25° est une valeur. Le contraste
  régional est visible immédiatement, mais l'œil peut se laisser porter par un
  continu, là où il n'y a qu'une discontinuité entre deux cellules.
- **Isothermes / isobares** : les lignes relient les valeurs égales. On suit
  alors un gradient, mais la couleur de fond devient secondaire.
- Dans les deux cas, **aucune interpolation n'est appliquée** : les valeurs
  affichées sont celles du modèle. Une carte lissée agréable mais qui invente
  des valeurs entre les points n'est pas une carte de données.
        """,
    )


def _figures_heatwave(activity, reference) -> None:
    """
    Comptage des jours de chaleur à partir des statistiques journalières.

    L'activité montre que le résultat dépend du seuil retenu : c'est le point
    pédagogique central, d'où les deux définitions comparées.
    """
    cities = _activity_cities(activity) or list(places.FRENCH_CITIES[:3])
    area = _bbox(cities, 1.0)
    col1, col2 = st.columns(2)
    with col1:
        y0, y1 = ui.years_picker("daily_stats", (2015, config.LAST_COMPLETE_YEAR))
    with col2:
        tmax_thresh = st.slider("Seuil de température maximale (°C)", 25.0, 42.0, 35.0, 0.5)

    tmax = _fetch(dataset_key="daily_stats", variable="maximum_2m_temperature",
                  years=(y0, y1), area=area, daily_statistic="daily_maximum")
    tmin = _fetch(dataset_key="daily_stats", variable="minimum_2m_temperature",
                  years=(y0, y1), area=area, daily_statistic="daily_minimum")
    ui.data_banner(tmax)
    if tmax.simulated:
        st.info(
            "**Comptage illustratif.** L'amplitude des extrêmes du jeu simulé "
            "n'est pas calibrée : ces nombres servent à comprendre la méthode, "
            "pas à établir un résultat. Passez aux données CDS pour chiffrer."
        )

    rows = []
    for place in cities:
        series_max = tmax.series_at(place.lat, place.lon, name="tmax")
        series_min = tmin.series_at(place.lat, place.lon, name="tmin")
        simple = analysis.count_days_above(series_max, tmax_thresh)
        nights = analysis.count_nights_above(series_min, 20.0)
        strict = analysis.heatwave_days(
            series_max, series_min, tmax_thresh=tmax_thresh, tmin_thresh=20.0
        )
        rows.append(
            {
                "Ville": place.name,
                f"Jours ≥ {tmax_thresh:.0f} °C (moy/an)": round(float(simple.mean()), 1),
                "dont avec min. nocturne ≥ 20 °C (moy/an)": round(float(strict.mean()), 1),
                "Nuits tropicales (min. ≥ 20 °C)": round(float(nights.mean()), 1),
            }
        )
    table = pd.DataFrame(rows)
    st.dataframe(table, use_container_width=True, hide_index=True)

    city = st.selectbox("Ville pour la courbe annuelle", [p.name for p in cities])
    place = next(p for p in cities if p.name == city)
    series_max = tmax.series_at(place.lat, place.lon, name="T max")
    series_min = tmin.series_at(place.lat, place.lon, name="T min")
    simple = analysis.count_days_above(series_max, tmax_thresh)
    strict = analysis.heatwave_days(
        series_max, series_min, tmax_thresh=tmax_thresh, tmin_thresh=20.0
    )
    ui.show_figure(
        viz.time_series(
            simple.rename("critere simple"), f"{city} — jours de forte chaleur", "jours",
            color=viz.C_TEMP,
        ),
        key=f"act_{activity.key}_days",
    )
    st.plotly_chart(
        viz.time_series(
            strict.rename("critere strict"), f"{city} — jours de canicule (2 seuils)",
            "jours", color="#8b0000",
        ),
        use_container_width=True, key=f"act_{activity.key}_days2",
    )
    st.download_button(
        "Télécharger le tableau (CSV)", table.to_csv(sep=";").encode("utf-8-sig"),
        file_name="canicule.csv", mime="text/csv",
    )
    ui.citation()
    ui.method_note(
        "Un indicateur est un choix",
        """
Deux définitions légitimes du même mot « jour de canicule » :

| Définition | Critère | Ce qu'elle compte |
|---|---|---|
| Seuil simple | T max ≥ le seuil | Un pic de chaleur, même suivi d'une nuit fraîche |
| Seuils croisés | T max ≥ seuil **et** T min ≥ 20 °C | Une vraie journée chaude, jour **et** nuit |

La seconde donne toujours un nombre inférieur ou égal à la première. Aucune des
deux n'est « fausse » : chacune répond à une question différente. C'est
précisément pourquoi un indicateur doit être **publié avec sa définition**, comme
le fait Météo-France pour son indice de chaleur.
        """,
    )


def _figures_latitude(activity, reference) -> None:
    """Températures de janvier pour des villes réparties sur plusieurs latitudes."""
    pool = {p.name: p for p in list(places.FRENCH_CITIES) + list(places.WORLD_CITIES)}
    default = [n for n in activity.default_places if n in pool]
    selected = st.multiselect(
        "Villes à classer par température de janvier", list(pool), default=default,
    )
    if not selected:
        st.info("Sélectionnez au moins une ville.")
        st.stop()
    cities = [pool[n] for n in selected]
    area = (
        max(p.lat for p in cities) + 1.0, min(p.lon for p in cities) - 1.0,
        min(p.lat for p in cities) - 1.0, max(p.lon for p in cities) + 1.0,
    )

    result = _fetch(dataset_key="monthly_means", variable="2m_temperature",
                    years=reference, area=area)
    ui.data_banner(result)

    values, labels, lats = [], [], []
    for place in cities:
        series = result.series_at(place.lat, place.lon, name=place.name)
        values.append(float(analysis.monthly_climatology(series, reference).iloc[0]))
        labels.append(place.name)
        lats.append(place.lat)

    order = np.argsort(values)[::-1]
    ui.show_figure(
        viz.bar_comparison(
            [labels[i] for i in order], [values[i] for i in order],
            f"Température de janvier — normale {reference[0]}-{reference[1]}", "°C",
        ),
        key=f"act_{activity.key}_jan",
    )

    fig = viz.scatter_with_fit(
        pd.Series(lats, index=labels, dtype="float64"),
        pd.Series(values, index=labels, dtype="float64"),
        "Température de janvier en fonction de la latitude",
        "latitude (°N)", "température (°C)",
        analysis.linear_trend(pd.Series(values, index=lats, dtype="float64"), "°C"),
    )
    st.plotly_chart(fig, use_container_width=True, key=f"act_{activity.key}_lat")
    ui.citation()
    ui.method_note(
        "Ce que la latitude explique, et ce qu'elle n'explique pas",
        """
- La latitude **explique bien** la tendance générale : la température moyenne
  annuelle décroît d'environ 0,5 °C par degré de latitude vers le nord dans
  l'hémisphère nord. Raison physique : les rayons solaires arrivent plus
  obliques et s'étalent sur une surface plus grande.
- Elle **n'explique pas tout** : à latitude égale, deux villes peuvent différer de
  plusieurs degrés. Les deux autres facteurs dominants sont la **distance à la
  mer** (inertie thermique) et l'**altitude**.
- Reykjavik, à 64° N, est plus chaude que Prague (50° N) : c'est le meilleur
  contre-exemple à donner aux élèves contre une explication purement
  géographique.
        """,
    )


# --------------------------------------------------------------------------- #
# Page 7 — Méthode et jeux de données
# --------------------------------------------------------------------------- #


def page_methode() -> None:
    st.title("📐 Méthode et jeux de données")
    st.markdown(
        "Les choix méthodologiques de l'application, et la façon de citer "
        "correctement les données dans un travail scolaire."
    )

    st.subheader("Ce que sont les données ERA5")
    st.markdown(
        """
**ERA5** est une *réanalyse* : un modèle de physique de l'atmosphère couplé à
l'assimilation d'observations. À chaque pas de temps, le modèle est corrigé par
les mesures disponibles (satellites, radiosondes, stations, bouées), ce qui donne
la meilleure estimation cohérente de l'état de l'atmosphère.

Conséquences à connaître :

- **La grille vaut 0,25° x 0,25°**, soit environ 25 km de côté. Ce n'est pas une
  mesure de station, c'est la moyenne du modèle sur une maille.
- **L'incertitude de position est d'environ 14 km** (une demi-maille).
- **La période commence en 1940** et se complète avec un décalage de quelques
  jours. La version provisoire (*ERA5T*) peut être modifiée 2 à 3 mois plus
  tard : les chiffres peuvent donc changer légèrement.
- **Les précipitations sont une quantité prévue, pas une observation assimilée.**
  Elles sont fiables en moyenne, mais ce sont des estimations du modèle.
        """
    )

    st.subheader("Les choix de calcul")
    st.markdown(
        """
| Choix | Ce que l'application fait | Pourquoi |
|---|---|---|
| Moyenne spatiale | Pondérée par `cos(latitude)` | Les cellules polaires sont plus petites ; sans cette pondération, l'Arctique serait surestimé |
| Point de mesure | Cellule la plus proche | Interpoler lisserait les extrêmes, ce qui est moins honnête |
| Normale | 1991-2020 (OMM) | Trente ans : la durée qui caractérise un climat |
| Anomalie | `valeur − normale` | Rend comparables deux périodes, deux lieux |
| Années | Seules les années à 12 mois | Une année à 3 mois fausserait la moyenne |
| Tendance | Moindres carrés | Droite d'ajustement ; R² n'est pas une probabilité |
| Carte | Cellules non lissées | Une interpolation crée des valeurs inexistantes |
| Impression | Couleurs séquentielles ou divergentes | Un arc-en-ciel fabrique des contours qui n'existent pas |
        """
    )

    st.divider()
    st.subheader("Jeux de données utilisés")
    st.dataframe(pd.DataFrame(catalog.summary_table()), use_container_width=True,
                 hide_index=True)

    for key, dataset in catalog.DATASETS.items():
        with st.expander(f"{dataset.label} — `{dataset.id}`"):
            st.write(dataset.summary)
            st.markdown(
                f"""
- **Fréquence** : {dataset.frequency} · **Début** : {dataset.start_year}
- **Résolution** : {dataset.resolution}
- **Licence** : {dataset.licence} · **Poids indicatif** (Europe, ~1 an) : ≈ {dataset.size_hint_mb:.0f} Mo
- **Page officielle** : {dataset.doc_url}
                """
            )
            if dataset.notes:
                st.info(dataset.notes)
            st.dataframe(
                pd.DataFrame([
                    {"Variable": v.slug, "Libellé": v.label, "Unité": v.unit,
                     "Statistiques journalières": ", ".join(v.daily_stats),
                     "Leçon rattachée": v.lesson}
                    for v in dataset.variables
                ]),
                use_container_width=True, hide_index=True,
            )

    st.divider()
    st.subheader("Citer les données dans un travail")
    st.code(config.ERA5_CITATION, language="text")
    st.caption(config.ERA5_ATTRIBUTION)
    st.markdown(
        f"""
**Exemple de mention en bas d'un graphique ou d'un exposé :**

> Données : ERA5, Copernicus Climate Change Service (C3S), ECMWF, licence
> CC BY 4.0. Traitement et figures réalisés avec C3S Climate Lab.
> Référence : {config.ERA5_CITATION.split('https')[0].strip()}
        """
    )

    st.divider()
    st.subheader("Fonds de carte et ressources")
    st.markdown(
        "Les contours et frontières proviennent du projet **Natural Earth** "
        "(domaine public). Les données climatiques proviennent exclusivement du "
        "**Copernicus Climate Change Service**."
    )
    if st.button("Télécharger les fonds de carte"):
        status = basemaps.prefetch()
        for name, state in status.items():
            st.write(f"**{basemaps.BASEMAPS[name]['label']}** : {state}")


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #

#: Onglets réservés à l'enseignant, ajoutés en bas de la navigation seulement
#: après saisie du code. Ils n'existent pas du tout pour un élève : l'accès
#: direct par URL échoue également.
TEACHER_PAGES = [
    ("Accueil", page_accueil, "🏠", "accueil"),
    ("Connexion CDS", page_connexion, "🔑", "connexion"),
    ("Méthode et données", page_methode, "📐", "methode"),
]


def build_pages() -> list:
    """Assemble la navigation : onglets élèves d'abord, enseignant en bas."""
    pages = [
        st.Page(page_activites, title="Activités", icon="🎓", url_path="activites"),
        st.Page(page_avant_apres, title="Avant / Après", icon="🔄", url_path="avant-apres"),
        st.Page(page_cartes, title="Cartes", icon="🗺️", url_path="cartes"),
        st.Page(page_graphiques, title="Graphiques", icon="📈", url_path="graphiques"),
        st.Page(page_villes, title="Villes", icon="🏙️", url_path="villes"),
    ]
    if ui.is_teacher():
        for title, func, icon, path in TEACHER_PAGES:
            pages.append(st.Page(func, title=title, icon=icon, url_path=path))
    return pages


def main() -> None:
    """Point d'entrée : styles, barre latérale commune, puis navigation."""
    ui.inject_css()
    ui.sidebar_controls()
    ui.lock_button()
    st.navigation(build_pages()).run()


if __name__ == "__main__":
    main()
