-- Indicateurs hebdomadaires par chantier : méthode de la VALEUR ACQUISE
--   PV (valeur planifiée) = Σ budget du lot × avancement PRÉVU     → ce qu'on aurait dû avoir réalisé
--   EV (valeur acquise)   = Σ budget du lot × avancement RÉEL      → ce qu'on a réellement réalisé
--   AC (coût réel)        = Σ dépenses cumulées                     → ce que ça a coûté
--   CPI = EV / AC  (< 1 : on dépense plus que prévu pour ce qu'on réalise)
--   SPI = EV / PV  (< 1 : on est en retard sur le planning)
DROP VIEW IF EXISTS v_indicateurs_hebdo;
CREATE VIEW v_indicateurs_hebdo AS
WITH RECURSIVE sem(chantier_id, semaine, fin) AS (
  SELECT chantier_id, 0, (SELECT MAX(semaine) FROM pointages p WHERE p.chantier_id = c.chantier_id) FROM chantiers c
  UNION ALL SELECT chantier_id, semaine + 1, fin FROM sem WHERE semaine < fin
),
grille AS (                          -- chaque lot de chaque chantier, chaque semaine
  SELECT s.chantier_id, s.semaine, l.lot_id, l.budget_lot_eur FROM sem s JOIN lots l USING (chantier_id)
),
calc AS (
  SELECT g.chantier_id, g.semaine, g.budget_lot_eur,
    COALESCE((SELECT avancement_prevu_pct FROM planning pl WHERE pl.chantier_id = g.chantier_id AND pl.lot_id = g.lot_id
              AND pl.semaine <= g.semaine ORDER BY pl.semaine DESC LIMIT 1), 0)                      AS prevu,
    COALESCE((SELECT avancement_pct FROM pointages p WHERE p.chantier_id = g.chantier_id AND p.lot_id = g.lot_id
              AND p.semaine <= g.semaine ORDER BY p.semaine DESC LIMIT 1), 0)                         AS reel,
    COALESCE((SELECT SUM(depense_eur) FROM pointages p WHERE p.chantier_id = g.chantier_id AND p.lot_id = g.lot_id
              AND p.semaine <= g.semaine), 0)                                                          AS ac
  FROM grille g
)
SELECT c.chantier_id, c.nom, c.type, c.region, c.conducteur, k.semaine,
       c.budget_initial_eur,
       ROUND(SUM(k.budget_lot_eur * k.prevu / 100), 0) AS pv_eur,
       ROUND(SUM(k.budget_lot_eur * k.reel  / 100), 0) AS ev_eur,
       ROUND(SUM(k.ac), 0)                             AS ac_eur,
       ROUND(100 * SUM(k.ac) / c.budget_initial_eur, 1)                         AS budget_consomme_pct,
       ROUND(100 * SUM(k.budget_lot_eur * k.reel / 100) / c.budget_initial_eur, 1) AS avancement_pct,
       ROUND(SUM(k.budget_lot_eur * k.reel / 100) / NULLIF(SUM(k.ac), 0), 3)    AS cpi,
       ROUND(SUM(k.budget_lot_eur * k.reel / 100) / NULLIF(SUM(k.budget_lot_eur * k.prevu / 100), 0), 3) AS spi
FROM calc k JOIN chantiers c USING (chantier_id)
GROUP BY c.chantier_id, k.semaine;
