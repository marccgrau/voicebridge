-- 011_replace_seed_customers.sql
-- Replace legacy English seed customers (from 002) with the 4 experiment personas (German).

-- ============================================================================
-- Remove legacy seed customers and their interactions/sessions
-- ============================================================================

-- Detach sessions from old customers (SET NULL to avoid cascade-deleting sessions)
UPDATE sessions SET customer_id = NULL
WHERE customer_id IN (
    'c1a1a1a1-1111-1111-1111-111111111111',
    'c2b2b2b2-2222-2222-2222-222222222222',
    'c3c3c3c3-3333-3333-3333-333333333333',
    'c4d4d4d4-4444-4444-4444-444444444444',
    'c5e5e5e5-5555-5555-5555-555555555555'
);

-- Delete old interactions (cascade from customers would also work, but be explicit)
DELETE FROM customer_interactions
WHERE customer_id IN (
    'c1a1a1a1-1111-1111-1111-111111111111',
    'c2b2b2b2-2222-2222-2222-222222222222',
    'c3c3c3c3-3333-3333-3333-333333333333',
    'c4d4d4d4-4444-4444-4444-444444444444',
    'c5e5e5e5-5555-5555-5555-555555555555'
);

-- Delete old customers
DELETE FROM customers
WHERE id IN (
    'c1a1a1a1-1111-1111-1111-111111111111',
    'c2b2b2b2-2222-2222-2222-222222222222',
    'c3c3c3c3-3333-3333-3333-333333333333',
    'c4d4d4d4-4444-4444-4444-444444444444',
    'c5e5e5e5-5555-5555-5555-555555555555'
);

-- ============================================================================
-- Insert 4 experiment personas (all German)
-- UUIDs are deterministic: SHA-256(customer_code) → UUIDv4
-- ============================================================================

-- Laura Baumann (health_insurance, insurance_claim_denial_civil)
INSERT INTO customers (
    id, customer_code, name, gender, date_of_birth, email, phone,
    address_street, address_postal_code, address_city, address_country,
    customer_since, classification, products, preferred_language,
    preferred_contact_channel, notes, quick_internal_note, domain, scenario_id
) VALUES (
    '0c4bffe9-0730-4ac0-a533-610bf1f054f4',
    'INS-CH-558603',
    'Laura Baumann',
    'female',
    '1991-02-09',
    'laura.baumann@examplemail.ch',
    '+41 79 331 74 25',
    '3 Rosenweg', '4058', 'Basel', 'CH',
    '2019-04-01',
    'Standard',
    '["Grundversicherung (KVG)", "Zusatzversicherung Ambulant", "Unfallzusatz", "Rechtsschutz Gesundheit"]',
    'de',
    'email',
    'Strukturierte Kommunikation; benötigt verständliche Erklärungen und explizite Checklisten.',
    'Strukturierte Kommunikation; benötigt verständliche Erklärungen und explizite Checklisten.',
    'health_insurance',
    'insurance_claim_denial_civil'
) ON CONFLICT (id) DO NOTHING;

-- Nico Keller (health_insurance, insurance_unauth_claim_uncivil)
INSERT INTO customers (
    id, customer_code, name, gender, date_of_birth, email, phone,
    address_street, address_postal_code, address_city, address_country,
    customer_since, classification, products, preferred_language,
    preferred_contact_channel, notes, quick_internal_note, domain, scenario_id
) VALUES (
    '74695d5e-8bd0-4141-94d6-21b39a1e6d86',
    'INS-CH-992174',
    'Nico Keller',
    'male',
    '1992-07-14',
    'nico.keller@examplemail.ch',
    '+41 76 442 18 90',
    '8 Seefeldstrasse', '8008', 'Zürich', 'CH',
    '2020-01-01',
    'Standard Plus',
    '["Grundversicherung (KVG)", "Zusatzversicherung Ambulant", "Spitalzusatz Halbprivat", "Telemedizin-Modul"]',
    'de',
    'email',
    'Detailorientiert; erwartet explizite Prozessmeilensteine und schriftliche Bestätigung.',
    'Detailorientiert; erwartet explizite Prozessmeilensteine und schriftliche Bestätigung.',
    'health_insurance',
    'insurance_unauth_claim_uncivil'
) ON CONFLICT (id) DO NOTHING;

-- Alex Meyer (banking, bank_credit_denial_civil)
INSERT INTO customers (
    id, customer_code, name, gender, date_of_birth, email, phone,
    address_street, address_postal_code, address_city, address_country,
    customer_since, classification, products, preferred_language,
    preferred_contact_channel, notes, quick_internal_note, domain, scenario_id
) VALUES (
    '572fb421-2f53-4b54-a356-52dd5e3a4f38',
    'BK-CH-784291',
    'Alex Meyer',
    'male',
    '1989-03-03',
    'alex.meyer@examplemail.ch',
    '+41 79 555 41 22',
    '45 Lindenstrasse', '8001', 'Zürich', 'CH',
    '2018-09-01',
    'Affluent',
    '["Privatkonto Plus", "Debitkarte Visa", "Sparkonto", "eBanking + Mobile Banking", "Business Lite Account"]',
    'de',
    'sms',
    'Unter Zeitdruck; erwartet sofortige Schutzmassnahmen und klare Zeitangaben.',
    'Unter Zeitdruck; erwartet sofortige Schutzmassnahmen und klare Zeitangaben.',
    'banking',
    'bank_credit_denial_civil'
) ON CONFLICT (id) DO NOTHING;

-- Sarah Steiner (banking, bank_unauth_transaction_uncivil)
INSERT INTO customers (
    id, customer_code, name, gender, date_of_birth, email, phone,
    address_street, address_postal_code, address_city, address_country,
    customer_since, classification, products, preferred_language,
    preferred_contact_channel, notes, quick_internal_note, domain, scenario_id
) VALUES (
    '66afa766-dbcb-4003-9283-3e04d1930683',
    'BK-CH-441028',
    'Sarah Steiner',
    'female',
    '1985-11-21',
    'sarah.steiner@examplemail.ch',
    '+41 78 667 03 11',
    '27 Gartenweg', '8400', 'Winterthur', 'CH',
    '2016-06-15',
    'Basis Plus',
    '["Privatkonto", "Debitkarte", "Kreditkarte Classic", "Sparkonto", "eBanking"]',
    'de',
    'email',
    'Fairness-sensibel; benötigt klare Begründungen und konkrete nächste Schritte bei jeder Entscheidung.',
    'Fairness-sensibel; benötigt klare Begründungen und konkrete nächste Schritte bei jeder Entscheidung.',
    'banking',
    'bank_unauth_transaction_uncivil'
) ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- Insert interaction histories (all German)
-- ============================================================================

-- Laura Baumann interactions
INSERT INTO customer_interactions (
    customer_id, type, date, summary, outcome, agent_name, channel_detail,
    direction, topic, subtopic, sentiment, priority, owner_team, status,
    resolution_time_hours, sla_breached, follow_up_required, related_case_id, csat
) VALUES
(
    '0c4bffe9-0730-4ac0-a533-610bf1f054f4', 'portal_message', '2026-02-08T10:26:00Z',
    'Rückerstattung: Antrag #CL-88217 Einreichung und Nachverfolgung',
    'Physiotherapie-Antrag abgelehnt: Fehlende Hausarzt-Überweisung gemäss Zusatzversicherung Ambulant erforderlich. Einspruch möglich mit Überweisungsdokument und Original-Arztrechnung.',
    'AGT-721', 'inbound · claims',
    'inbound', 'Rückerstattung', 'Antrag #CL-88217 Einreichung und Nachverfolgung',
    'frustrated', 'high', 'claims', 'denied', 36, false, true, 'CASE-INS-23199', 2
),
(
    '0c4bffe9-0730-4ac0-a533-610bf1f054f4', 'phone', '2025-11-25T14:43:00Z',
    'Deckung: Deckungsprüfung Facharztkonsultation',
    'Deckungsbedingungen erläutert, einschliesslich Überweisungspflicht.',
    'AGT-289', 'inbound · general_support',
    'inbound', 'Deckung', 'Deckungsprüfung Facharztkonsultation',
    'neutral', 'medium', 'general_support', 'resolved', 1, false, false, 'CASE-INS-22610', 4
),
(
    '0c4bffe9-0730-4ac0-a533-610bf1f054f4', 'email', '2025-07-07T10:00:00Z',
    'Rückerstattung: Bearbeitungszeit Medikamenten-Rückerstattung',
    'Bearbeitungszeit für Medikamenten-Rückerstattung erläutert; Zahlung innerhalb der üblichen 10-Werktage-Frist bestätigt.',
    'AGT-207', 'inbound · billing',
    'inbound', 'Rückerstattung', 'Bearbeitungszeit Medikamenten-Rückerstattung',
    'neutral', 'low', 'billing', 'resolved', 4, false, false, 'CASE-INS-21502', 4
),
(
    '0c4bffe9-0730-4ac0-a533-610bf1f054f4', 'service_desk', '2025-04-18T13:30:00Z',
    'Policenverwaltung: Korrektur Policendokument',
    'Namensschreibweise auf Policenzertifikat korrigiert und Dokument per Post neu zugestellt.',
    'AGT-041', 'inbound · service_desk',
    'inbound', 'Policenverwaltung', 'Korrektur Policendokument',
    'neutral', 'low', 'service_desk', 'resolved', 2, false, false, 'CASE-INS-20744', 5
);

-- Nico Keller interactions
INSERT INTO customer_interactions (
    customer_id, type, date, summary, outcome, agent_name, channel_detail,
    direction, topic, subtopic, sentiment, priority, owner_team, status,
    resolution_time_hours, sla_breached, follow_up_required, related_case_id, csat
) VALUES
(
    '74695d5e-8bd0-4141-94d6-21b39a1e6d86', 'portal_message', '2026-01-16T11:07:00Z',
    'Leistungen: Klärung Physiotherapie-Leistungen',
    'Jährliche Sitzungslimiten und Überweisungsanforderungen erläutert.',
    'AGT-512', 'inbound · claims',
    'inbound', 'Leistungen', 'Klärung Physiotherapie-Leistungen',
    'neutral', 'medium', 'claims', 'resolved', 5, false, false, 'CASE-INS-22013', 5
),
(
    '74695d5e-8bd0-4141-94d6-21b39a1e6d86', 'phone', '2025-10-02T08:34:00Z',
    'Abrechnung: Rechnungscode-Anfrage',
    'Fehlerhafter Anbieterschlüssel korrigiert; Neuverarbeitung im laufenden Abrechnungszyklus.',
    'AGT-207', 'inbound · billing',
    'inbound', 'Abrechnung', 'Rechnungscode-Anfrage',
    'frustrated', 'medium', 'billing', 'resolved', 18, false, false, 'CASE-INS-21144', 4
),
(
    '74695d5e-8bd0-4141-94d6-21b39a1e6d86', 'email', '2025-06-21T15:10:00Z',
    'Rückerstattung: Rückerstattung Facharztkonsultation',
    'Rückerstattung Facharztkonsultation abgelehnt: Hausarzt-Überweisung nicht beigelegt. Zusatzversicherung Ambulant erfordert Überweisung für Facharztbesuche. Einspruch möglich mit Überweisungsschreiben und Arztbericht.',
    'AGT-721', 'inbound · claims',
    'inbound', 'Rückerstattung', 'Rückerstattung Facharztkonsultation',
    'frustrated', 'high', 'claims', 'denied', 24, false, true, 'CASE-INS-20847', 2
),
(
    '74695d5e-8bd0-4141-94d6-21b39a1e6d86', 'mobile_app_chat', '2025-03-11T09:45:00Z',
    'Deckung: Anfrage Deckungsumfang Spitalzusatz',
    'Deckungsumfang Spitalzusatz Halbprivat erläutert, einschliesslich Zimmerkategorie, Arztwahl und geografische Einschränkungen.',
    'AGT-289', 'inbound · general_support',
    'inbound', 'Deckung', 'Anfrage Deckungsumfang Spitalzusatz',
    'neutral', 'low', 'general_support', 'resolved', 3, false, false, 'CASE-INS-20112', 5
);

-- Alex Meyer interactions
INSERT INTO customer_interactions (
    customer_id, type, date, summary, outcome, agent_name, channel_detail,
    direction, topic, subtopic, sentiment, priority, owner_team, status,
    resolution_time_hours, sla_breached, follow_up_required, related_case_id, csat
) VALUES
(
    '572fb421-2f53-4b54-a356-52dd5e3a4f38', 'mobile_app_chat', '2026-01-28T09:41:00Z',
    'Kartendienstleistungen: Klärung Kartenlimite',
    'Temporäres Ausgabelimit und Nutzungsverhalten im Ausland erläutert.',
    'AGT-114', 'inbound · cards',
    'inbound', 'Kartendienstleistungen', 'Klärung Kartenlimite',
    'neutral', 'medium', 'cards', 'resolved', 3, false, false, 'CASE-BK-12091', 4
),
(
    '572fb421-2f53-4b54-a356-52dd5e3a4f38', 'branch_visit', '2025-11-09T14:22:00Z',
    'Stammdatenpflege: Adressänderung',
    'Adresse aktualisiert und Bestätigung per E-Mail gesendet.',
    'AGT-041', 'inbound · service_desk',
    'inbound', 'Stammdatenpflege', 'Adressänderung',
    'positive', 'low', 'service_desk', 'resolved', 2, false, false, 'CASE-BK-11302', 5
),
(
    '572fb421-2f53-4b54-a356-52dd5e3a4f38', 'phone', '2025-08-14T10:15:00Z',
    'Gebühren: Antrag auf Gebührenrückerstattung',
    'Rückerstattung der Jahresgebühr abgelehnt; Gebühr ist vertraglich im Privatkonto-Plus-Vertrag vorgesehen. Neubeurteilung möglich bei dokumentierter finanzieller Härte oder langjähriger Kundentreue.',
    'AGT-088', 'inbound · general_support',
    'inbound', 'Gebühren', 'Antrag auf Gebührenrückerstattung',
    'frustrated', 'high', 'general_support', 'denied', 5, false, true, 'CASE-BK-10874', 2
),
(
    '572fb421-2f53-4b54-a356-52dd5e3a4f38', 'phone', '2025-05-03T16:30:00Z',
    'Kartendienstleistungen: Reisenotiz für Kartennutzung im Ausland',
    'Reisenotiz für Südostasien-Reise erfasst. Karte für internationale Transaktionen über 3 Wochen freigeschaltet.',
    'AGT-114', 'inbound · cards',
    'inbound', 'Kartendienstleistungen', 'Reisenotiz für Kartennutzung im Ausland',
    'neutral', 'low', 'cards', 'resolved', 1, false, false, 'CASE-BK-10201', 5
);

-- Sarah Steiner interactions
INSERT INTO customer_interactions (
    customer_id, type, date, summary, outcome, agent_name, channel_detail,
    direction, topic, subtopic, sentiment, priority, owner_team, status,
    resolution_time_hours, sla_breached, follow_up_required, related_case_id, csat
) VALUES
(
    '66afa766-dbcb-4003-9283-3e04d1930683', 'mobile_app_chat', '2026-02-05T09:37:00Z',
    'Kreditlimite: Temporäre Kreditlimiten-Erhöhung',
    'Temporäre Limiten-Erhöhung abgelehnt: Aktuelle Auslastungsquote überschreitet interne Risikoschwelle. Neuantrag möglich mit aktuellem Lohnausweis und aktuellen Kontoauszügen.',
    'AGT-402', 'inbound · cards',
    'inbound', 'Kreditlimite', 'Temporäre Kreditlimiten-Erhöhung',
    'frustrated', 'high', 'cards', 'denied', 2, false, true, 'CASE-BK-13024', 2
),
(
    '66afa766-dbcb-4003-9283-3e04d1930683', 'secure_message', '2025-12-12T11:20:00Z',
    'Gebühren: Erläuterung Überziehungsgebühr',
    'Berechnung der Überziehungsgebühr erläutert; Gebühr entspricht dem publizierten Tarif. Kundin nach Aufschlüsselung zufrieden.',
    'AGT-088', 'inbound · general_support',
    'inbound', 'Gebühren', 'Erläuterung Überziehungsgebühr',
    'neutral', 'medium', 'general_support', 'resolved', 6, false, false, 'CASE-BK-12814', 3
),
(
    '66afa766-dbcb-4003-9283-3e04d1930683', 'phone', '2025-09-19T14:05:00Z',
    'Kartendienstleistungen: Kartenersatz wegen Abnutzung',
    'Ersatz-Debitkarte bestellt und an Privatadresse versandt. Zustellung innerhalb von 4 Werktagen.',
    'AGT-114', 'inbound · cards',
    'inbound', 'Kartendienstleistungen', 'Kartenersatz wegen Abnutzung',
    'neutral', 'low', 'cards', 'resolved', 1, false, false, 'CASE-BK-12301', 5
);
