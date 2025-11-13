# Otto Mayer RAG Tools - Docker Deployment

Docker-basierte Deployment-Anleitung für die RAG-Preisverwaltungstools.

## 🚀 Quick Start

### Voraussetzungen

- Docker Engine 20.10+ oder Docker Desktop
- Docker Compose v2.0+
- Mindestens 2GB freier RAM

### 1. Repository klonen

```bash
git clone <repository-url>
cd open-mcp-tools
git checkout release/rag-tools-client
```

### 2. Pfad-Konfiguration (Optional)

**Standard:** Preislisten werden in `./resources/pricelists` erwartet.

**Eigener Pfad?** Erstellen Sie eine `.env` Datei:

```bash
# Beispiel-Datei kopieren
cp docker.env.example .env

# Pfad anpassen (z.B.)
echo "PRICELISTS_DIR=/home/kunde/meine-preislisten" > .env
```

**Mögliche Pfade:**
- `./resources/pricelists` - Relativ zum Projektverzeichnis (Standard)
- `/absolute/pfad/zu/preislisten` - Absoluter Pfad
- `~/Dokumente/preislisten` - Home-Verzeichnis

### 3. Preislisten vorbereiten

Legen Sie Ihre Excel-Preislisten in den konfigurierten Ordner:

```bash
# Standard-Pfad
mkdir -p resources/pricelists
# Kopieren Sie Ihre .xlsx Dateien hierhin

# ODER: Eigener Pfad (wenn in .env konfiguriert)
mkdir -p /ihr/eigener/pfad
```

### 4. Container starten

```bash
# Image bauen und Container starten
docker-compose up -d

# Logs anzeigen
docker-compose logs -f
```

### 5. Docker Desktop Auto-Start (EMPFOHLEN)

**Für automatischen Start nach System-Neustart:**

**Windows & Mac:**
1. Docker Desktop öffnen
2. Settings (⚙️) → General
3. ☑️ "Start Docker Desktop when you log in" aktivieren

**Vorteil:**
- Container startet automatisch beim System-Start
- 🐳 Docker-Icon in Statusleiste zeigt Status:
  - **Grün** = Docker läuft, Tools verfügbar
  - **Grau/Rot** = Docker gestoppt

✅ Konfiguriert durch `restart: unless-stopped` in docker-compose.yml

## 📦 Verfügbare Tools

Der Container stellt folgende MCP-Tools bereit:

### Import & Verwaltung
- `rag_import_pricelist` - Excel-Preislisten importieren
- `rag_list_pricelists` - Importierte Listen anzeigen
- `rag_delete_pricelist` - Preisliste löschen

### Abfragen
- `rag_lookup_ean` - Einzelne EAN nachschlagen
- `rag_bulk_lookup_ean` - Mehrere EANs gleichzeitig
- `rag_search_products` - Produkte nach Name suchen
- `rag_price_history` - Preisentwicklung anzeigen

### Vergleiche & Statistiken
- `rag_compare_basket` - Warenkorb-Preisvergleich
- `rag_supplier_stats` - Lieferanten-Statistiken

## 🔧 Konfiguration

### Environment Variables

Bearbeiten Sie `docker-compose.yml`:

```yaml
environment:
  - PYTHONUNBUFFERED=1          # Python-Ausgabe nicht puffern
  - RAG_DB_DIR=/app/resources/pricelists  # Datenbank-Verzeichnis
  # Optional: DCAP Broadcasting aktivieren
  # - DCAP_BROADCAST_ENABLED=true
  # - DCAP_RELAY_HOST=159.89.110.236
  # - DCAP_RELAY_PORT=10191
```

### Volumes

Persistente Daten werden in `./resources/pricelists` gespeichert:

```yaml
volumes:
  - ./resources/pricelists:/app/resources/pricelists
```

**Wichtig:** Die SQLite-Datenbank (`pricelist.db`) wird automatisch in diesem Verzeichnis angelegt und bleibt zwischen Container-Neustarts erhalten.

## 🛠️ Verwaltung

### Container-Befehle

```bash
# Container starten
docker-compose up -d

# Container stoppen
docker-compose down

# Logs anzeigen
docker-compose logs -f

# Container neu starten
docker-compose restart

# In Container einloggen (Debug)
docker-compose exec mcp-rag-tools /bin/bash

# Datenbank direkt prüfen
docker-compose exec mcp-rag-tools sqlite3 /app/resources/pricelists/pricelist.db
```

### Image-Updates

```bash
# Neuestes Image bauen
docker-compose build --no-cache

# Container mit neuem Image neu starten
docker-compose up -d --force-recreate
```

### Backup erstellen

```bash
# Datenbank sichern
cp resources/pricelists/pricelist.db resources/pricelists/pricelist.db.backup-$(date +%Y%m%d)

# Oder gesamten Ordner
tar -czf pricelists-backup-$(date +%Y%m%d).tar.gz resources/pricelists/
```

## 🔌 Integration mit MCP-Clients

### Cursor AI / Claude Desktop

1. **Container muss laufen:**
   ```bash
   docker-compose up -d
   ```

2. **MCP-Konfiguration** in `~/.cursor/mcp.json`:

   ```json
   {
     "mcpServers": {
       "otto-mayer-rag": {
         "type": "sse",
         "url": "http://localhost:7284/mcp"
       }
     }
   }
   ```

3. **Cursor neu starten** → Tools sind verfügbar!

### Verbindung testen

```bash
# Health-Check
curl http://localhost:7284/health

# Sollte zurückgeben: {"status":"healthy","timestamp":"..."}
```

## 📊 Ressourcen & Port

### Exponierter Port

- **Port 7284** - MCP Server (HTTP/SSE)
  - Health: `http://localhost:7284/health`
  - MCP Endpoint: `http://localhost:7284/mcp`
  - Server Info: `http://localhost:7284/`

### Ressourcen-Limits

Standard-Konfiguration in `docker-compose.yml`:

- **CPU Limit:** 2.0 Cores
- **RAM Limit:** 2GB
- **RAM Reservation:** 512MB

Bei Bedarf anpassen:

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'      # Mehr CPU
      memory: 4G       # Mehr RAM
```

## 🔍 Troubleshooting

### Container startet nicht

```bash
# Logs prüfen
docker-compose logs

# Port-Konflikte prüfen
docker-compose ps
```

### Datenbank-Probleme

```bash
# Datenbank neu initialisieren (ACHTUNG: Löscht alle Daten!)
rm resources/pricelists/pricelist.db
docker-compose restart

# Datenbank-Integrität prüfen
docker-compose exec mcp-rag-tools sqlite3 /app/resources/pricelists/pricelist.db "PRAGMA integrity_check;"
```

### Performance-Probleme beim Import

- Reduzieren Sie die Batch-Größe in der Import-Funktion
- Erhöhen Sie RAM-Limits in `docker-compose.yml`
- Prüfen Sie Disk I/O mit `docker stats`

### Berechtigungsprobleme

```bash
# Dateiberechtigungen anpassen
sudo chown -R 1000:1000 resources/pricelists/

# Oder Container mit root ausführen (nicht empfohlen)
docker-compose exec -u root mcp-rag-tools /bin/bash
```

## 🔒 Sicherheit

- Container läuft als **non-root user** (`mcpuser`, UID 1000)
- Nur notwendige Ports exponiert
- Resource limits aktiv
- Health checks konfiguriert

### Produktions-Empfehlungen

1. **Secrets Management:** Verwenden Sie Docker Secrets für sensitive Daten
2. **Network Isolation:** Nutzen Sie separate Docker Networks
3. **Read-Only Filesystem:** Bei Bedarf Root-Filesystem read-only mounten
4. **Logging:** Integrieren Sie mit zentralem Log-Management

## 📝 Wartung

### Regelmäßige Aufgaben

- **Wöchentlich:** Logs rotieren/prüfen
- **Monatlich:** Datenbank-Backup erstellen
- **Vierteljährlich:** Container-Image aktualisieren

### Monitoring

```bash
# Ressourcen-Nutzung überwachen
docker stats otto-mayer-rag-tools

# Health-Status prüfen
docker inspect --format='{{.State.Health.Status}}' otto-mayer-rag-tools
```

## 📞 Support

Bei Fragen oder Problemen:
- Logs sammeln: `docker-compose logs > debug.log`
- Issue erstellen mit Log-Datei

## 📄 Lizenz

Proprietär - Otto Mayer Client Deployment

