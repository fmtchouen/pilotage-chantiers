"""
Étape 1 (suite) — Chargement des CSV dans une base SQLite, contrôles de qualité
et création de la vue d'indicateurs (valeur acquise : CPI, SPI).
"""
import sqlite3
import pandas as pd
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DATA, SQL = RACINE / "data", RACINE / "sql"
BASE = DATA / "chantiers.db"

con = sqlite3.connect(BASE)
con.executescript((SQL / "schema.sql").read_text(encoding="utf-8"))
for table in ["chantiers", "lots", "planning", "pointages"]:
    pd.read_csv(DATA / f"{table}.csv").to_sql(table, con, if_exists="append", index=False)

# Contrôles de qualité : chaque requête doit renvoyer 0
CONTROLES = {
    "pointages sans lot correspondant":
        "SELECT COUNT(*) FROM pointages p LEFT JOIN lots l USING (chantier_id, lot_id) WHERE l.lot_id IS NULL",
    "budgets des lots ≠ budget du chantier (écart > 1 €)":
        "SELECT COUNT(*) FROM (SELECT c.chantier_id FROM chantiers c JOIN lots l USING (chantier_id) "
        "GROUP BY c.chantier_id HAVING ABS(SUM(l.budget_lot_eur) - c.budget_initial_eur) > 1)",
    "avancement réel qui recule d'une semaine à l'autre":
        "SELECT COUNT(*) FROM (SELECT avancement_pct - LAG(avancement_pct) OVER "
        "(PARTITION BY chantier_id, lot_id ORDER BY semaine) AS d FROM pointages) WHERE d < -0.001",
    "valeurs manquantes":
        "SELECT COUNT(*) FROM pointages WHERE depense_eur IS NULL OR heures IS NULL OR avancement_pct IS NULL",
}
print("Contrôles de qualité :")
for nom, requete in CONTROLES.items():
    n = con.execute(requete).fetchone()[0]
    print(f"  {'OK ' if n == 0 else 'KO '} {nom} : {n}")

con.executescript((SQL / "indicateurs.sql").read_text(encoding="utf-8"))
ind = pd.read_sql("SELECT * FROM v_indicateurs_hebdo", con)
ind.to_csv(DATA / "indicateurs_hebdo.csv", index=False)
print(f"\nVue v_indicateurs_hebdo : {len(ind)} lignes (une par chantier et par semaine)")
con.close()
