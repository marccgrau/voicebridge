-- Fix street address format to Swiss convention: "Strassenname Hausnummer"
-- DB had "Hausnummer Strassenname" (e.g. "3 Rosenweg" → "Rosenweg 3")

UPDATE customers SET address = jsonb_set(address, '{street}', '"Rosenweg 3"')
WHERE name = 'Laura Baumann' AND address->>'street' = '3 Rosenweg';

UPDATE customers SET address = jsonb_set(address, '{street}', '"Seefeldstrasse 8"')
WHERE name = 'Nico Keller' AND address->>'street' = '8 Seefeldstrasse';

UPDATE customers SET address = jsonb_set(address, '{street}', '"Lindenstrasse 45"')
WHERE name = 'Alex Meyer' AND address->>'street' = '45 Lindenstrasse';

UPDATE customers SET address = jsonb_set(address, '{street}', '"Gartenweg 27"')
WHERE name = 'Sarah Steiner' AND address->>'street' = '27 Gartenweg';
