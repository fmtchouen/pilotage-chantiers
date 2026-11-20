"""
Étape 3 — Modèle d'anticipation des dérives.

Question : à une semaine donnée, ce chantier va-t-il finir avec un dépassement de plus de
10 % de son budget ou de son délai ?

Méthode
- Une ligne par chantier et par semaine (à partir de 10 % d'avancement), avec uniquement
  les informations connues à cette date (voir features.py).
- Validation croisée PAR CHANTIER (GroupKFold, 5 plis) : un chantier n'est jamais à la fois
  dans l'entraînement et dans le test, sinon le modèle « reconnaîtrait » le chantier.
- Règle d'alerte : probabilité de dérive >= 80 % deux semaines de suite. Le seuil a été choisi
  en comparant 0,5 à 0,9 sur les prédictions de validation croisée : le résultat est donc
  légèrement optimiste, à confirmer sur de nouveaux chantiers.
- Comparaison avec la méthode classique (CPI ou SPI < 0,909 deux semaines de suite).

Mesures, par chantier
- rappel : part des chantiers en dérive qui reçoivent une alerte ;
- fausses alertes : part des chantiers sains qui reçoivent une alerte ;
- avance : nombre de semaines entre l'alerte du modèle et le constat de la méthode classique.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent))
from features import construire, FEATURES, ROOT

SEUIL_ALERTE = 0.8   # choisi en comparant plusieurs seuils (0,5 à 0,9) en validation croisée


def predictions_hors_echantillon(df, modele):
    """Probabilité de dérive pour chaque ligne, prédite par un modèle qui n'a jamais vu ce chantier."""
    proba = pd.Series(np.nan, index=df.index)
    for train, test in GroupKFold(n_splits=5).split(df, df.derive_10pct, df.chantier_id):
        m = modele()
        m.fit(df.iloc[train][FEATURES], df.iloc[train].derive_10pct)
        proba.iloc[test] = m.predict_proba(df.iloc[test][FEATURES])[:, 1]
    return proba


def premiere_alerte(df, colonne_alerte):
    """Première semaine où l'alerte est vraie deux semaines de suite."""
    a = df[colonne_alerte]
    deux = a & a.groupby(df.chantier_id).shift(1, fill_value=False)
    return df[deux].groupby("chantier_id").semaine.min()


def evaluer(df, res, alerte, constat):
    derive = res.index[res.derive_10pct == 1]
    sain = res.index[res.derive_10pct == 0]
    avance = (constat.reindex(derive) - alerte.reindex(derive)).dropna()
    return {
        "rappel": alerte.index.isin(derive).sum() / len(derive),
        "fausses_alertes": alerte.index.isin(sain).sum() / len(sain),
        "avance_mediane_sem": float(avance.median()) if len(avance) else np.nan,
        "part_avance_4s_ou_plus": float((avance >= 4).mean()) if len(avance) else np.nan,
        "n_derive": len(derive), "n_sain": len(sain),
    }


def main():
    h, res = construire()
    df = h[(h.avancement_pct >= 10) & h[FEATURES].notna().all(axis=1)].copy()
    constat = premiere_alerte(h.assign(c=h.constat_classique), "c")

    modeles = {
        "Régression logistique": lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
        "Forêt aléatoire": lambda: RandomForestClassifier(n_estimators=300, min_samples_leaf=5, class_weight="balanced", random_state=0),
    }
    lignes = [dict(methode="Méthode classique (CPI/SPI < 0,909)", **evaluer(h, res, constat, constat))]
    probas = {}
    for nom, m in modeles.items():
        df[nom] = predictions_hors_echantillon(df, m)
        probas[nom] = df[nom]
        alerte = premiere_alerte(df.assign(a=df[nom] >= SEUIL_ALERTE), "a")
        lignes.append(dict(methode=nom, **evaluer(df, res, alerte, constat)))
    tab = pd.DataFrame(lignes).set_index("methode")
    print(tab.round(2).to_string())

    # Modèle retenu : entraîné sur tous les chantiers, pour le tableau de bord
    meilleur = "Forêt aléatoire"   # meilleur compromis rappel / fausses alertes
    final = modeles[meilleur]().fit(df[FEATURES], df.derive_10pct)
    out = h[["chantier_id", "semaine"]].copy()
    ok = h[FEATURES].notna().all(axis=1) & (h.avancement_pct >= 10)
    out["score_risque"] = np.nan
    out.loc[ok, "score_risque"] = final.predict_proba(h.loc[ok, FEATURES])[:, 1].round(3)
    # score hors échantillon (honnête) pour l'évaluation affichée
    out["score_risque_validation"] = df[meilleur].reindex(out.index).round(3)
    out.to_csv(ROOT / "data" / "scores_risque.csv", index=False)
    tab.to_csv(ROOT / "data" / "evaluation_modeles.csv")
    if hasattr(final, "feature_importances_"):
        imp = pd.Series(final.feature_importances_, FEATURES).sort_values(ascending=False)
    else:
        imp = pd.Series(np.abs(final[-1].coef_[0]), FEATURES).sort_values(ascending=False)
    print("\nModèle retenu :", meilleur)
    print("Variables les plus utiles :", imp.round(3).head(5).to_dict())
    return tab, meilleur


if __name__ == "__main__":
    main()
