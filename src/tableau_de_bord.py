"""
Étape 2 — Tableau de bord (page web autonome : dashboard/index.html).

Trois vues :
  * Portefeuille : chiffres clés et tableau des 60 chantiers ;
  * Chantier     : courbes prévu / réalisé / dépensé, CPI et SPI, score de risque ;
  * Alertes      : chantiers signalés par le modèle, avec l'avance prise sur la méthode classique.

Les alertes affichées utilisent les scores de validation croisée (le modèle n'avait jamais vu
le chantier), pour montrer des performances honnêtes.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from features import construire, ROOT
from modele_anticipation import SEUIL_ALERTE, premiere_alerte

def main():
    h, res = construire()
    s = pd.read_csv(ROOT / "data" / "scores_risque.csv")
    h = h.merge(s, on=["chantier_id", "semaine"], how="left")
    ch = pd.read_csv(ROOT / "data" / "chantiers.csv").set_index("chantier_id")

    alerte = premiere_alerte(h.assign(a=h.score_risque_validation >= SEUIL_ALERTE), "a")
    constat = premiere_alerte(h.assign(c=h.constat_classique), "c")

    chantiers = []
    for cid, g in h.groupby("chantier_id"):
        g = g.sort_values("semaine")
        info = ch.loc[cid]
        a = alerte.get(cid); c = constat.get(cid)
        row_a = g[g.semaine == a].iloc[0] if a is not None else None
        cause = None
        if row_a is not None:
            cause = "coût" if (row_a.cpi or 1) < (row_a.spi or 1) else "délai"
        chantiers.append(dict(
            id=int(cid), nom=info.nom, type=info.type, region=info.region, conducteur=info.conducteur,
            budget=float(info.budget_initial_eur), duree=int(info.duree_prevue_sem),
            depassement=round(float(res.loc[cid, "depassement_cout"]) * 100, 1),
            retard=round(float(res.loc[cid, "retard"]) * 100, 1),
            derive=int(res.loc[cid, "derive_10pct"]),
            alerte=None if a is None else int(a), constat=None if c is None else int(c),
            avance=None if (a is None or c is None) else int(c - a), cause=cause,
            sem=g.semaine.astype(int).tolist(),
            pv=(g.pv_eur / 1000).round(0).tolist(), ev=(g.ev_eur / 1000).round(0).tolist(),
            ac=(g.ac_eur / 1000).round(0).tolist(),
            cpi=g.cpi.round(3).where(g.cpi.notna(), None).tolist(),
            spi=g.spi.round(3).where(g.spi.notna() & (g.semaine >= 4), None).tolist(),
            score=g.score_risque_validation.where(g.score_risque_validation.notna(), None).tolist(),
            avancement=g.avancement_pct.round(1).tolist(),
        ))
    ev = pd.read_csv(ROOT / "data" / "evaluation_modeles.csv").set_index("methode").loc["Forêt aléatoire"]
    resume = dict(n=len(chantiers), n_derive=int(res.derive_10pct.sum()),
                  detectes=int(sum(1 for c in chantiers if c["derive"] and c["alerte"] is not None)),
                  fausses=int(sum(1 for c in chantiers if not c["derive"] and c["alerte"] is not None)),
                  avance_mediane=float(ev.avance_mediane_sem),
                  part4=round(float(ev.part_avance_4s_ou_plus) * 100),
                  budget_total=round(float(ch.budget_initial_eur.sum()) / 1e6, 1), seuil=SEUIL_ALERTE)
    data = json.dumps(dict(resume=resume, chantiers=chantiers), ensure_ascii=False, default=lambda o: None)
    data = data.replace("NaN", "null")
    html = (ROOT / "src" / "gabarit_tableau_de_bord.html").read_text(encoding="utf-8").replace("__DATA__", data)
    out = ROOT / "dashboard" / "index.html"
    out.write_text(html, encoding="utf-8")
    print("Tableau de bord écrit :", out, f"({len(html)//1024} Ko)")

if __name__ == "__main__":
    main()
