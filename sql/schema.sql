-- Schéma de la base « chantiers » (SQLite)
DROP TABLE IF EXISTS pointages; DROP TABLE IF EXISTS planning; DROP TABLE IF EXISTS lots; DROP TABLE IF EXISTS chantiers;

CREATE TABLE chantiers (
  chantier_id         INTEGER PRIMARY KEY,
  nom                 TEXT NOT NULL,
  type                TEXT NOT NULL,
  region              TEXT NOT NULL,
  conducteur          TEXT NOT NULL,
  date_debut          DATE NOT NULL,
  duree_prevue_sem    INTEGER NOT NULL CHECK (duree_prevue_sem > 0),
  budget_initial_eur  REAL NOT NULL CHECK (budget_initial_eur > 0)
);

CREATE TABLE lots (
  chantier_id     INTEGER NOT NULL REFERENCES chantiers(chantier_id),
  lot_id          INTEGER NOT NULL,
  lot             TEXT NOT NULL,
  budget_lot_eur  REAL NOT NULL CHECK (budget_lot_eur >= 0),
  PRIMARY KEY (chantier_id, lot_id)
);

CREATE TABLE planning (               -- avancement PRÉVU (référence)
  chantier_id           INTEGER NOT NULL,
  lot_id                INTEGER NOT NULL,
  semaine               INTEGER NOT NULL,
  avancement_prevu_pct  REAL NOT NULL CHECK (avancement_prevu_pct BETWEEN 0 AND 100),
  PRIMARY KEY (chantier_id, lot_id, semaine),
  FOREIGN KEY (chantier_id, lot_id) REFERENCES lots(chantier_id, lot_id)
);

CREATE TABLE pointages (              -- ce qui s'est RÉELLEMENT passé
  chantier_id     INTEGER NOT NULL,
  lot_id          INTEGER NOT NULL,
  semaine         INTEGER NOT NULL,
  date_semaine    DATE NOT NULL,
  depense_eur     REAL NOT NULL CHECK (depense_eur >= 0),
  heures          REAL NOT NULL CHECK (heures >= 0),
  avancement_pct  REAL NOT NULL CHECK (avancement_pct BETWEEN 0 AND 100),
  PRIMARY KEY (chantier_id, lot_id, semaine),
  FOREIGN KEY (chantier_id, lot_id) REFERENCES lots(chantier_id, lot_id)
);
CREATE INDEX idx_pointages_ch_sem ON pointages (chantier_id, semaine);
