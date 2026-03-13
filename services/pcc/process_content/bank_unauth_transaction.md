---
process_key: bank_unauth_transaction
name: Nicht autorisierte Transaktion (TWINT)
domain: banking
intents:
  - TWINT Zahlung nicht angekommen
  - Empfänger hat Geld nicht erhalten
  - bestrittene TWINT Transaktion
  - Geld weg TWINT
  - TWINT Reklamation
---

# Nicht autorisierte Transaktion (TWINT)

Dieser Prozess wird verwendet, wenn ein Kunde eine TWINT-Transaktion meldet, bei der der Empfänger das Geld nicht erhalten hat.

## Step 1: Begrüssung & Anliegenaufnahme

Anliegen spiegeln, beruhigen, strukturiert führen.

## Step 2: Berechtigung & Identitätsprüfung

Nur Kontoinhaber. Identität nach Standard prüfen.

## Step 3: Transaktionsdetails klären

Kanal (TWINT), Betrag, Empfänger, Zeitpunkt erfassen. Prüfen ob definitiv abgebucht und innerhalb 50 Tage.

## Step 4: Einordnung der Transaktion

Bestrittene Transaktion vs. Schadenfall (Missbrauch) einordnen.

## Step 5: Kontaktversuche klären

Bisherige Kontaktversuche erfragen. Mindestens 2 Kontaktversuche (App + SMS) vorgesehen.

## Step 6: Nachweise und Screenshots

Screenshots bestätigen. Zeitpunkt des letzten Kontakts erfragen.

## Step 7: 2-Tage-Regel und Empfängerbestätigung

Mindestens 2 Tage seit letzter Kontaktaufnahme. Schriftliche Empfängerbestätigung einholen.

## Step 8: Restliche Angaben erfassen

Genaues Datum, Uhrzeit, Betrag und Empfängername bestätigen.

## Step 9: Gebührenhinweis

Bei Irrtum des Kunden: Bearbeitungsgebühr CHF 60 möglich. Sachlich kommunizieren.

## Step 10: Abschluss

Zusammenfassen: Einordnung + Sofortmassnahmen + nächste Schritte + fehlende Unterlagen. Erwartung setzen und freundlich beenden.
