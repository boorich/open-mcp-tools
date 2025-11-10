# Preislisten-Management System
## MCP Tools für effizientes Preisvergleich und Lieferantenmanagement

---

## 🎯 Übersicht

Das Preislisten-Management System ermöglicht es, Excel-Preislisten von verschiedenen Lieferanten zu importieren und intelligent auszuwerten. Alle Daten werden in einer zentralen Datenbank gespeichert, die schnelle Preisvergleiche und Analysen ermöglicht.

### Hauptvorteile

✅ **Automatischer Import** - Excel-Dateien werden automatisch geparst, Spalten erkannt  
✅ **Mehrere Lieferanten** - Zentrale Verwaltung aller Lieferanten in einer Datenbank  
✅ **Preisstaffeln** - Automatische Berechnung von Gewerbe-, Industrie- und Topkundenpreisen  
✅ **Schnelle Suche** - EAN-Suche über alle Lieferanten in Sekunden  
✅ **Intelligenter Vergleich** - Warenkorbvergleich zeigt günstigsten Lieferanten  

---

## 🚀 Verfügbare Tools

### 1. **rag_import_pricelist** - Preisliste importieren

Importiert eine Excel-Preisliste in die Datenbank.

**Parameter:**
- `filePath`: Pfad zur Excel-Datei (z.B. `/pfad/zu/Metabo.xlsx`)
- `supplierName`: Name des Lieferanten (z.B. `"Metabo"`, `"HAZET"`)
- `version`: Optional - Versionsnummer der Preisliste
- `columnMapping`: Optional - Manuelle Spalten-Zuordnung (falls Automatik fehlschlägt)
- `headerRow`: Optional - Zeile mit Spaltenüberschriften (wird automatisch erkannt)

**Beispiel:**
```json
{
  "filePath": "/Users/martin/Preislisten/HAZET.xlsx",
  "supplierName": "HAZET"
}
```

**Ausgabe:**
- Anzahl importierter Produkte
- Anzahl importierter Preise
- Verwendete Spalten-Zuordnung
- Fehler (falls vorhanden)

**Performance:** ~5.000 Artikel in 2-5 Sekunden

---

### 2. **rag_lookup_ean** - Einzelne EAN suchen

Sucht eine EAN über alle Lieferanten und zeigt alle verfügbaren Preise sortiert nach Preis.

**Parameter:**
- `ean`: EAN-Code (z.B. `"4000896000241"`)
- `supplierFilter`: Optional - Nur bestimmten Lieferanten anzeigen

**Ausgabe:**
- Produktname
- Alle Preise von allen Lieferanten
- EK-Preis, Rabatt, Gewerbepreis, Industriepreis, Topkundenpreis
- Importdatum der Preisliste

**Beispiel-Ergebnis:**
```
EAN: 4000896000241
Produkt: KAROSSERIE-WERKZEUG-SORTIMENT

HAZET:
  EK-Preis: 3.133,00 €
  Gewerbepreis: 4.386,20 €
  Industriepreis: 4.072,90 €
  Topkundenpreis: 3.759,60 €
```

---

### 3. **rag_bulk_lookup_ean** - Mehrere EANs suchen

Sucht mehrere EANs gleichzeitig (bis zu 100 Stück).

**Parameter:**
- `eans`: Liste von EAN-Codes (z.B. `["4000896000241", "4007430083005"]`)
- `supplierFilter`: Optional - Nur bestimmten Lieferanten

**Ausgabe:**
- Für jede EAN: Gefunden/Nicht gefunden
- Alle verfügbaren Preise
- Zusammenfassung: X von Y gefunden

**Use Case:** Schnellcheck einer Einkaufsliste

---

### 4. **rag_search_products** - Produktsuche nach Name

Sucht Produkte anhand des Namens (wenn EAN unbekannt).

**Parameter:**
- `searchTerm`: Suchbegriff (z.B. `"Bohrmaschine"`, `"Akkuschrauber"`)
- `limit`: Maximale Anzahl Ergebnisse (Standard: 50)
- `supplierFilter`: Optional - Nur bestimmten Lieferanten

**Ausgabe:**
- Gefundene Produkte mit EAN und Name
- Günstigster Preis und Lieferant
- Alle Lieferanten, die den Artikel führen

**Beispiel:**
```
Suchbegriff: "Bohrmaschine"
Gefunden: 5 Produkte

1. B 32/3 Bohrmaschine
   EAN: 4007430172204
   Günstigster Preis: 189,50 € (Metabo)

2. BE 500/10 Bohrmaschine
   EAN: 4007430262011
   Günstigster Preis: 215,80 € (Metabo)
...
```

---

### 5. **rag_price_history** - Preisentwicklung

Zeigt die Preisentwicklung eines Produkts über alle Importe hinweg.

**Parameter:**
- `ean`: EAN-Code
- `supplierFilter`: Optional - Nur bestimmten Lieferanten

**Ausgabe:**
- Chronologische Liste aller Preise
- Preisänderung in Prozent
- Erste und letzte Import-Daten

**Use Case:** "Hat Metabo den Preis erhöht?"

---

### 6. **rag_compare_basket** - Warenkorbvergleich

Vergleicht die Gesamtkosten eines Warenkorbs über alle Lieferanten.

**Parameter:**
- `items`: Liste von Artikeln mit EAN und Menge (z.B. `[{"ean": "4000896000241", "quantity": 2}]`)
- `priceTier`: Preisstaffel (`"ek"`, `"gewerbepreis"`, `"industriepreis"`, `"topkundenpreis"`)

**Ausgabe:**
- Gesamtkosten pro Lieferant
- Beste Option (niedrigste Kosten, meiste Artikel verfügbar)
- Fehlende Artikel pro Lieferant
- Einzelpreise je Artikel

**Use Case:** "Wo bestelle ich 50 Artikel am günstigsten?"

**Beispiel:**
```
Warenkorb: 2x Artikel A, 1x Artikel B

HAZET:
  Verfügbar: 1 von 2 Artikeln
  Gesamtpreis: 8.772,40 €
  Fehlt: Artikel B

Metabo:
  Verfügbar: 1 von 2 Artikeln
  Gesamtpreis: 28.350.561,40 €
  Fehlt: Artikel A

✓ Beste Option: HAZET (8.772,40 €)
```

---

### 7. **rag_supplier_stats** - Lieferanten-Statistiken

Zeigt Übersicht aller Lieferanten mit Statistiken.

**Parameter:**
- `supplierName`: Optional - Nur bestimmten Lieferanten anzeigen

**Ausgabe:**
- Anzahl Produkte pro Lieferant
- Anzahl Preislisten (Importe)
- Letzter Import
- Durchschnittlicher/Min/Max EK-Preis

**Use Case:** Dashboard, Reporting

---

### 8. **rag_list_pricelists** - Alle Preislisten anzeigen

Listet alle importierten Preislisten mit Details.

**Parameter:**
- `supplierFilter`: Optional - Nur bestimmten Lieferanten

**Ausgabe:**
- Pricelist-ID
- Lieferant
- Importdatum
- Anzahl Produkte/Preise
- Dateipfad

**Use Case:** Überblick behalten, alte Importe identifizieren

---

### 9. **rag_delete_pricelist** - Preisliste löschen

Löscht eine importierte Preisliste (z.B. fehlerhafte/alte Importe).

**Parameter:**
- `pricelistId`: ID der zu löschenden Preisliste (aus `rag_list_pricelists`)

**Ausgabe:**
- Erfolg/Fehler
- Anzahl gelöschter Preise
- Details der gelöschten Liste

**Wichtig:** Produkte bleiben erhalten, nur die Preise werden gelöscht.

---

## 📊 Datenbank-Schema

Die Daten werden in einer SQLite-Datenbank gespeichert:

```
pricelist.db
├── suppliers (Lieferanten)
├── pricelists (Import-Historie)
├── products (Produkte mit EAN)
├── prices (Preise pro Lieferant & Import)
└── supplier_column_mappings (Gespeicherte Spalten-Zuordnungen)
```

**Speicherort:** `resources/pricelists/pricelist.db`

---

## 💡 Typische Workflows

### Workflow 1: Neue Preisliste importieren
1. `rag_import_pricelist` - Excel-Datei importieren
2. `rag_list_pricelists` - Import verifizieren
3. `rag_supplier_stats` - Statistiken prüfen

### Workflow 2: Artikel suchen
1. **Mit EAN:** `rag_lookup_ean` - Direkte Suche
2. **Ohne EAN:** `rag_search_products` - Nach Name suchen → EAN finden

### Workflow 3: Einkaufsliste vergleichen
1. `rag_bulk_lookup_ean` - Alle EANs prüfen (Verfügbarkeit)
2. `rag_compare_basket` - Gesamtkosten vergleichen
3. Entscheidung: Bei wem bestellen?

### Workflow 4: Preise überwachen
1. `rag_price_history` - Preisentwicklung prüfen
2. Bei Preisänderung → Entscheidung treffen

---

## ⚡ Performance

- **Import:** 5.000 Artikel in 2-5 Sekunden
- **EAN-Suche:** < 1 Sekunde
- **Bulk-Lookup (100 EANs):** 1-2 Sekunden
- **Warenkorbvergleich:** 2-3 Sekunden

---

## 🔧 Technische Details

**Excel-Parser:**
- Automatische Spaltenerkennung (EAN, Preis, Rabatt, Name)
- Automatische Header-Erkennung
- Unterstützt verschiedene Excel-Formate
- Optimiert für große Dateien (100.000+ Zeilen)

**Preisstaffeln:**
- Gewerbepreis: EK × 1,4
- Industriepreis: EK × 1,3
- Topkundenpreis: EK × 1,2

**Datenbank:**
- SQLite (keine Installation nötig)
- Normalisiertes Schema (keine Duplikate)
- Optimierte Indizes für schnelle Suche
- Vollständige Historie aller Importe

---

## 📝 Bekannte Besonderheiten

- **Duplikate:** Bei mehrfachem Import derselben Datei werden neue Preise angelegt (Historie)
- **Fehlende EANs:** Produkte ohne gültige EAN (8/13/14 Ziffern) werden übersprungen
- **Spalten-Mapping:** Wird pro Lieferant gespeichert und wiederverwendet
- **Produkt-Namen:** Werden bei Re-Import aktualisiert (falls vorhanden)

---

## 🆘 Troubleshooting

**Problem:** Import dauert sehr lange  
**Lösung:** Excel-Datei prüfen, eventuell viele leere Zeilen am Ende entfernen

**Problem:** Spalten nicht erkannt  
**Lösung:** Manuelle `columnMapping` angeben mit korrekten Spaltennummern

**Problem:** EAN nicht gefunden  
**Lösung:** 
1. Mit `rag_search_products` nach Name suchen
2. Prüfen ob Lieferant importiert wurde (`rag_list_pricelists`)
3. EAN-Format prüfen (muss 8/13/14 Ziffern haben)

**Problem:** Falsche Preise bei Metabo  
**Lösung:** Alte Preisliste löschen (`rag_delete_pricelist`) und neu importieren

---

## 📞 Support

Bei Fragen oder Problemen:
1. `rag_supplier_stats` - Überblick verschaffen
2. `rag_list_pricelists` - Imports prüfen
3. Logs im Terminal prüfen
4. Datenbankzustand mit SQLite-Tool prüfen (`resources/pricelists/pricelist.db`)

---

**Stand:** 10. November 2025  
**Version:** 1.0  
**Importierte Lieferanten:** HAZET (5.897 Artikel), Metabo (4.563 Artikel)

