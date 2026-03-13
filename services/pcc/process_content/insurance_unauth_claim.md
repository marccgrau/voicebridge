---
process_key: insurance_unauth_claim
name: Unbekannte Rechnung Arztpraxis
domain: health_insurance
intents:
  - unbekannte Rechnung
  - Rechnung von Praxis nie besucht
  - Rechnung Arztpraxis nie gewesen
  - falsche Rechnung Versicherung
  - Fehlzuordnung Rechnung
---

# Unbekannte Rechnung Arztpraxis

Dieser Prozess wird verwendet, wenn ein Kunde eine Rechnung einer Praxis erhält, bei der er nie war.

## Step 1: Begrüssung & Anliegenaufnahme

Anliegen aufnehmen, Verständnis zeigen, strukturiert führen.

## Step 2: Berechtigung & Identitätsprüfung

Identität nach Standard prüfen.

## Step 3: Rechnungsdetails erfassen

Praxis, Datum, Betrag, Leistungsbeschreibung und Status notieren.

## Step 4: Plausibilitätscheck

Kennt der Kunde die Praxis? Nähe zum Wohnort? War er dort? Medizinischer Sachverhalt plausibel?

## Step 5: Einordnung und Sofortmassnahme

Starke Hinweise auf Fehlzuordnung oder Missbrauch. Rechnung als bestritten führen. Zahlungsstopp/Prüfvermerk setzen.

## Step 6: Abklärungsfragen

Zahlungspflicht klären (bis Klärung: keine). Wer kontaktiert die Praxis (Versicherung). Weitere Rechnungen prüfen.

## Step 7: Kasse kontaktiert Praxis

Versicherung fordert Klärung/Korrektur/Storno und Belege an.

## Step 8: Folgefragen beantworten

Ursache erklären (Verwechslung/Fehlzuordnung/Missbrauch möglich). Zeitrahmen setzen ohne fixe Zusage.

## Step 9: Abschluss

Zusammenfassen: Zahlungsstopp + Abklärung mit Praxis + Rückmeldung. Erwartung setzen und freundlich beenden.
