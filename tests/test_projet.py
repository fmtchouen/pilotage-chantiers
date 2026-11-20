"""Tests du projet : qualité des données et performances minimales du modèle.
Lancer : python -m pytest -v   (ou : python tests/test_projet.py)"""
import sqlite3, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

def test_controles_qualite_a_zero():
    import os, subprocess
    # PYTHONIOENCODING : sous Windows, la sortie capturée est en cp1252 et ne sait pas
    # écrire certains caractères (≠, €) ; on force l'UTF-8 pour que le script ne plante pas.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    subprocess.run([sys.executable, str(ROOT / "src" / "charger_base.py")], check=True, capture_output=True, env=env)
    con = sqlite3.connect(ROOT / "data" / "chantiers.db")
    orphelins = con.execute("SELECT COUNT(*) FROM pointages p LEFT JOIN lots l USING (chantier_id, lot_id) WHERE l.lot_id IS NULL").fetchone()[0]
    assert orphelins == 0

def test_modele_anticipe_les_derives():
    ev = pd.read_csv(ROOT / "data" / "evaluation_modeles.csv").set_index("methode").loc["Forêt aléatoire"]
    assert ev.rappel >= 0.9                 # au moins 90 % des dérives repérées
    assert ev.fausses_alertes <= 0.10       # au plus 10 % de fausses alertes
    assert ev.avance_mediane_sem >= 4       # au moins 4 semaines d'avance (médiane)

if __name__ == "__main__":
    for t in (test_controles_qualite_a_zero, test_modele_anticipe_les_derives):
        t(); print("OK ", t.__name__)
