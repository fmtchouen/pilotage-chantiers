"""
Construction des variables (features) du modèle d'anticipation.

Pour chaque chantier et chaque semaine, on ne garde QUE ce qu'un conducteur de travaux
connaît à cette date-là : indicateurs de valeur acquise (CPI, SPI), leur évolution sur
les 4 dernières semaines, l'écart entre budget consommé et avancement, la vitesse
d'avancement, et le nombre d'heures pointées par euro dépensé.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEUIL = 0.909          # CPI ou SPI < 0,909  <=>  dépassement projeté de plus de 10 %


def resultat_final(h: pd.DataFrame, chantiers: pd.DataFrame) -> pd.DataFrame:
    """Dépassement final de coût et de délai de chaque chantier (la « vérité » à prédire)."""
    fin = h.sort_values("semaine").groupby("chantier_id").tail(1).set_index("chantier_id")
    c = chantiers.set_index("chantier_id")
    r = pd.DataFrame(index=c.index)
    r["depassement_cout"] = fin.ac_eur / c.budget_initial_eur - 1
    r["retard"] = (fin.semaine + 1) / c.duree_prevue_sem - 1
    r["derive_10pct"] = ((r.depassement_cout > 0.10) | (r.retard > 0.10)).astype(int)
    return r


def construire():
    h = pd.read_csv(DATA / "indicateurs_hebdo.csv")
    chantiers = pd.read_csv(DATA / "chantiers.csv")
    p = pd.read_csv(DATA / "pointages.csv")

    heures = p.groupby(["chantier_id", "semaine"])[["heures", "depense_eur"]].sum().reset_index()
    h = h.merge(heures, on=["chantier_id", "semaine"], how="left").fillna({"heures": 0, "depense_eur": 0})
    h = h.merge(chantiers[["chantier_id", "duree_prevue_sem"]], on="chantier_id")
    h = h.sort_values(["chantier_id", "semaine"]).reset_index(drop=True)
    g = h.groupby("chantier_id")

    h["temps_ecoule_pct"] = 100 * h.semaine / h.duree_prevue_sem
    h["spi"] = h.spi.clip(upper=2)                           # le SPI est instable les premières semaines
    h["ecart_conso_avancement"] = h.budget_consomme_pct - h.avancement_pct
    h["cpi_tendance_4s"] = h.cpi - g.cpi.shift(4)
    h["spi_tendance_4s"] = h.spi - g.spi.shift(4)
    h["vitesse_4s"] = h.avancement_pct - g.avancement_pct.shift(4)          # points d'avancement en 4 semaines
    pv_pct = 100 * h.pv_eur / h.budget_initial_eur
    h["vitesse_prevue_4s"] = pv_pct - pv_pct.groupby(h.chantier_id).shift(4)
    h["vitesse_relative"] = h.vitesse_4s / h.vitesse_prevue_4s.replace(0, np.nan)
    # heures par k€ dépensés sur 4 semaines, rapportées au niveau habituel du chantier (8 premières semaines)
    h["h_par_keur_4s"] = (g.heures.rolling(4).sum().reset_index(level=0, drop=True)
                          / (g.depense_eur.rolling(4).sum().reset_index(level=0, drop=True) / 1000))
    ref = h[h.semaine.between(1, 8)].groupby("chantier_id").h_par_keur_4s.median()
    h["ratio_heures"] = h.h_par_keur_4s / h.chantier_id.map(ref)

    # Moment où la méthode classique « constate » la dérive :
    # CPI ou SPI sous 0,909 deux semaines de suite, une fois 10 % d'avancement atteints.
    sous = ((h.cpi < SEUIL) | (h.spi < SEUIL)) & (h.avancement_pct >= 10)
    h["constat_classique"] = sous & g.cpi.shift(1).notna() & sous.groupby(h.chantier_id).shift(1, fill_value=False)

    res = resultat_final(h, chantiers)
    h = h.merge(res, left_on="chantier_id", right_index=True)
    return h, res


FEATURES = ["temps_ecoule_pct", "avancement_pct", "cpi", "spi", "ecart_conso_avancement",
            "cpi_tendance_4s", "spi_tendance_4s", "vitesse_relative", "ratio_heures"]

if __name__ == "__main__":
    h, res = construire()
    c = h[h.constat_classique].groupby("chantier_id").semaine.min()
    print(res.derive_10pct.value_counts().to_dict())
    print("Chantiers en dérive dont la méthode classique constate la dérive :",
          c.index.isin(res.index[res.derive_10pct == 1]).sum(),
          "| fausses alertes de la méthode classique :", (~c.index.isin(res.index[res.derive_10pct == 1])).sum())
    print(h[FEATURES].describe().round(2).T[["mean", "min", "max"]])
