"""
Export des données pour Power BI, en modèle en étoile :
  * dim_chantier       : une ligne par chantier (type, région, conducteur, budget, durée)
  * dim_lot            : une ligne par lot (gros œuvre, électricité…) et son budget
  * fait_pointages     : dépenses, heures et avancement par lot et par semaine
  * fait_indicateurs   : PV, EV, AC, CPI, SPI et score de risque par chantier et par semaine
Le guide docs/Guide_Power_BI.docx explique comment construire le tableau de bord.
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from features import construire, ROOT

def main():
    out = ROOT / "data" / "powerbi"; out.mkdir(exist_ok=True)
    h, res = construire()
    s = pd.read_csv(ROOT / "data" / "scores_risque.csv")
    c = pd.read_csv(ROOT / "data" / "chantiers.csv").merge(res.reset_index(), on="chantier_id")
    c.round(4).to_csv(out / "dim_chantier.csv", index=False, encoding="utf-8-sig")
    pd.read_csv(ROOT / "data" / "lots.csv").to_csv(out / "dim_lot.csv", index=False, encoding="utf-8-sig")
    pd.read_csv(ROOT / "data" / "pointages.csv").to_csv(out / "fait_pointages.csv", index=False, encoding="utf-8-sig")
    f = h[["chantier_id", "semaine", "pv_eur", "ev_eur", "ac_eur", "avancement_pct", "budget_consomme_pct", "cpi", "spi"]] \
        .merge(s[["chantier_id", "semaine", "score_risque_validation"]], on=["chantier_id", "semaine"], how="left") \
        .rename(columns={"score_risque_validation": "score_risque"})
    f.to_csv(out / "fait_indicateurs.csv", index=False, encoding="utf-8-sig")
    print("Export Power BI :", sorted(p.name for p in out.glob("*.csv")))

if __name__ == "__main__":
    main()
