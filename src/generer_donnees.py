"""
Projet : Pilotage de chantiers par la donnée et anticipation des dérives
Étape 1 — Génération d'un jeu de données simulé de 60 chantiers de bâtiment.

Le script crée 4 tables :
  - chantiers  : une ligne par chantier (type, budget, durée prévue...)
  - lots       : une ligne par lot de travaux d'un chantier (gros œuvre, électricité...)
  - planning   : avancement PRÉVU de chaque lot, semaine par semaine (la référence)
  - pointages  : ce qui s'est RÉELLEMENT passé, par lot et par semaine (dépenses, heures, avancement)

Environ 1 chantier sur 4 subit une dérive réaliste (météo, hausse des matériaux,
sous-effectif). Le modèle de l'étape 3 devra apprendre à la repérer à l'avance.
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)          # graine fixe : résultats reproductibles
SORTIE = Path(__file__).resolve().parents[1] / "data"

N_CHANTIERS = 60
TYPES = {   # type : (budget min, budget max en €, durée min, durée max en semaines)
    "Logements collectifs": (3e6, 12e6, 40, 80),
    "Bureaux":              (4e6, 15e6, 42, 76),
    "Rénovation":           (0.5e6, 3e6, 20, 45),
    "Ouvrage public":       (2e6, 10e6, 36, 70),
}
REGIONS = ["Normandie", "Île-de-France", "Hauts-de-France", "Grand Est", "Bretagne"]
CONDUCTEURS = [f"CT-{i:02d}" for i in range(1, 13)]
# lot : (part du budget, début et fin de la fenêtre en % de la durée prévue, coût horaire €)
LOTS = {
    "Terrassement / VRD":        (0.08, 0.00, 0.20, 70),
    "Gros œuvre":                (0.30, 0.05, 0.55, 55),
    "Charpente / couverture":    (0.08, 0.40, 0.65, 60),
    "Menuiseries":               (0.10, 0.50, 0.80, 50),
    "Électricité":               (0.10, 0.45, 0.90, 58),
    "Plomberie / CVC":           (0.12, 0.45, 0.90, 60),
    "Isolation / cloisons":      (0.06, 0.55, 0.85, 48),
    "Sécurité incendie":         (0.04, 0.60, 0.95, 62),
    "Finitions":                 (0.07, 0.70, 1.00, 45),
    "Aménagements extérieurs":   (0.05, 0.85, 1.00, 50),
}
DERIVES = ["aucune", "meteo", "materiaux", "sous_effectif"]

def courbe_s(x):
    """Avancement cumulé 'en S' entre 0 et 1 (démarrage lent, accélération, fin lente)."""
    x = np.clip(x, 0, 1)
    return 3 * x**2 - 2 * x**3

chantiers, lots, pointages, verite, planning = [], [], [], [], []
for c in range(1, N_CHANTIERS + 1):
    type_c = rng.choice(list(TYPES))
    bmin, bmax, dmin, dmax = TYPES[type_c]
    budget = round(rng.uniform(bmin, bmax), -3)
    duree = int(rng.integers(dmin, dmax + 1))
    debut = pd.Timestamp("2023-01-02") + pd.Timedelta(weeks=int(rng.integers(0, 80)))

    # Environ 25 % des chantiers dérivent, à partir d'une semaine aléatoire
    derive = rng.choice(DERIVES, p=[0.75, 0.09, 0.09, 0.07])
    debut_derive = rng.uniform(0.25, 0.55)            # en % de la durée prévue
    intensite = rng.uniform(0.12, 0.30)               # ampleur de la dérive

    verite.append(dict(chantier_id=c, derive_simulee=derive,
                       debut_derive_pct=round(100 * debut_derive, 1) if derive != "aucune" else None))
    chantiers.append(dict(chantier_id=c, nom=f"Chantier {c:02d}", type=type_c,
                          region=rng.choice(REGIONS), conducteur=rng.choice(CONDUCTEURS),
                          date_debut=debut.date(), duree_prevue_sem=duree, budget_initial_eur=budget))

    # Facteurs globaux de la dérive
    ralentissement = 1.0 + (intensite if derive in ("meteo", "sous_effectif") else intensite * 0.2)
    surcout = 1.0 + (intensite if derive == "materiaux" else intensite * 0.4)
    if derive == "aucune":
        ralentissement, surcout = 1.0, 1.0
    duree_reelle = int(np.ceil(duree * ralentissement)) + 1

    for lot_id, (nom_lot, (part, f0, f1, cout_h)) in enumerate(LOTS.items(), start=1):
        budget_lot = budget * part
        lots.append(dict(chantier_id=c, lot_id=lot_id, lot=nom_lot, budget_lot_eur=round(budget_lot, 2)))
        s0, s1 = f0 * duree, f1 * duree                 # fenêtre prévue du lot (semaines)
        for s in range(duree + 1):                       # planning de référence (prévu)
            planning.append(dict(chantier_id=c, lot_id=lot_id, semaine=s,
                                 avancement_prevu_pct=round(100 * courbe_s((s - s0) / max(s1 - s0, 1)), 2)))
        av_prec = 0.0
        for s in range(duree_reelle + 1):
            # Avancement réel : suit le prévu, ralenti après le début de la dérive
            t = s / duree
            if derive != "aucune" and t > debut_derive:
                frein = 1 + (ralentissement - 1) * min((t - debut_derive) / 0.2, 1)
            else:
                frein = 1.0
            reel = courbe_s((s / frein - s0) / max(s1 - s0, 1))
            reel = float(np.clip(reel + rng.normal(0, 0.01), av_prec, 1.0))
            gain = reel - av_prec
            if gain <= 0 and reel < 1e-3:
                continue                                    # lot pas encore démarré
            if gain <= 0 and reel >= 0.999:
                break                                       # lot terminé
            # Coût de la semaine : avancement réalisé × budget × surcoût éventuel × bruit
            facteur_cout = surcout if (derive != "aucune" and t > debut_derive) else 1.0
            depense = gain * budget_lot * facteur_cout * rng.normal(1.0, 0.04)
            if derive == "sous_effectif" and t > debut_derive:
                heures = depense / cout_h * rng.uniform(0.70, 0.85)   # moins d'heures pointées
            else:
                heures = depense / cout_h * rng.normal(1.0, 0.05)
            pointages.append(dict(
                chantier_id=c, lot_id=lot_id,
                semaine=s, date_semaine=(debut + pd.Timedelta(weeks=s)).date(),
                depense_eur=round(max(depense, 0), 2), heures=round(max(heures, 0), 1),
                avancement_pct=round(100 * reel, 2)))
            av_prec = reel

df_c, df_l, df_p = pd.DataFrame(chantiers), pd.DataFrame(lots), pd.DataFrame(pointages)


SORTIE.mkdir(exist_ok=True)
df_c.to_csv(SORTIE / "chantiers.csv", index=False)
df_l.to_csv(SORTIE / "lots.csv", index=False)
df_p.to_csv(SORTIE / "pointages.csv", index=False)
pd.DataFrame(planning).to_csv(SORTIE / "planning.csv", index=False)
# La "vérité" sur les dérives simulées est gardée à part : elle ne doit JAMAIS servir
# d'entrée au modèle, seulement à vérifier à la fin qu'il retrouve les bons chantiers.
pd.DataFrame(verite).to_csv(SORTIE / "verite_derives_NE_PAS_UTILISER_EN_ENTREE.csv", index=False)
print(f"{len(df_c)} chantiers | {len(df_l)} lots | {len(df_p)} lignes de pointage")
