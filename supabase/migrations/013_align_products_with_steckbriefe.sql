-- 013_align_products_with_steckbriefe.sql
-- Align customer products with steckbriefe PDFs.
-- Insurance personas: single product tier ("Basis").
-- Banking personas: no products listed in steckbriefe.

-- Laura Baumann (insurance) — Steckbrief: Produkt: Basis
UPDATE customers
SET products = '["Basis"]'
WHERE id = '0c4bffe9-0730-4ac0-a533-610bf1f054f4';

-- Nico Keller (insurance) — Steckbrief: Produkt: Basis
UPDATE customers
SET products = '["Basis"]'
WHERE id = '74695d5e-8bd0-4141-94d6-21b39a1e6d86';

-- Alex Meyer (banking) — Steckbrief: no products listed
UPDATE customers
SET products = '[]'
WHERE id = '572fb421-2f53-4b54-a356-52dd5e3a4f38';

-- Sarah Steiner (banking) — Steckbrief: no products listed
UPDATE customers
SET products = '[]'
WHERE id = '66afa766-dbcb-4003-9283-3e04d1930683';
