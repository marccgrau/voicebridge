---
process_key: insurance_claim_denial
name: Rechnung nicht übernommen – Deckung fehlt
domain: health_insurance
intents:
  - Rechnung nicht übernommen
  - Deckungslücke
  - Physiotherapie nicht gedeckt
  - warum wurde meine Rechnung abgelehnt
  - Leistung nicht versichert
---

# Rechnung nicht übernommen – Deckung fehlt

Dieser Prozess wird verwendet, wenn eine eingereichte Rechnung nicht übernommen wird, weil die Leistung in der aktuellen Deckung nicht enthalten ist.

## Step 1: Begrüssung & Anliegenaufnahme

Anliegen aufnehmen und Verständnis zeigen.

## Step 2: Berechtigung & Identitätsprüfung

Identität nach Standard prüfen.

## Step 3: Rechnungsdetails klären

Leistung, Betrag, Datum, Leistungserbringer und Status erfassen. Ablehnungsgrund einordnen (Deckungslücke vs. fehlende Unterlagen).

## Step 4: Ablehnungsgrund bestätigen

Erklären, dass es sich um eine Deckungslücke handelt, nicht um fehlende Unterlagen.

## Step 5: Deckung erklären

Aktuelle Versicherung deckt die Leistung nicht. Kosten gehen zu Lasten des Kunden (Selbstzahlung).

## Step 6: Einwand auffangen

Prämien-Einwand sachlich erklären. Produktabhängige Leistungsabgrenzung, kein Einzelfallentscheid. Optionen anbieten.

## Step 7: Optionen anbieten

Option A: Alternative Versicherung/Produkt (Zusatzdeckung). Option B: Interne Rückfrage nach gedeckten Alternativen.

## Step 8: Abschluss

Next Step festhalten und Erwartung setzen. Zusammenfassen und freundlich verabschieden.
