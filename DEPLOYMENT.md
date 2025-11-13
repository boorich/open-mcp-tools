## 🚀 Installation (EMPFOHLEN)

### Schritt 1: Repository klonen

```bash
git clone <repository-url>
cd open-mcp-tools
git checkout release/rag-tools-client
```

### Schritt 2: Docker Container starten

```bash
# Image bauen und Container starten (dauert beim ersten Mal ~30 Sekunden)
docker-compose up -d

# Logs prüfen
docker-compose logs -f
```

**Fertig!** Container läuft auf `http://localhost:7284`

### Schritt 2a: Docker Desktop Auto-Start konfigurieren (WICHTIG!)

**Windows & Mac:** Damit die RAG-Tools nach System-Neustart automatisch verfügbar sind:

1. Docker Desktop öffnen
2. **Settings** (⚙️) → **General**
3. ☑️ **"Start Docker Desktop when you log in"** aktivieren
4. Optional: ☑️ **"Start Docker Desktop when you sign in to your computer"**

**Statusleiste:**
- 🐳 Docker-Icon in der Taskbar/Menüleiste zeigt Status
- **Grün** = Docker läuft, RAG-Tools verfügbar
- **Grau/Rot** = Docker gestoppt, Tools nicht verfügbar

✅ Container startet automatisch mit Docker Desktop!

### Schritt 3: Cursor konfigurieren

In `~/.cursor/mcp.json` (oder `.cursor/mcp.json` im Projekt):

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

Cursor neu starten → Tools sind verfügbar!

### Schritt 4: Erste Preisliste importieren

1. Excel-Datei ablegen: `resources/pricelists/IHRE_LISTE.xlsx`
2. In Cursor: "Importiere die Preisliste IHRE_LISTE.xlsx"

**System läuft!** ✅

---

**Beim Kunden:**
- [ ] Git installiert
- [ ] Docker Desktop installiert und gestartet
- [ ] **Docker Desktop Auto-Start aktiviert** (Settings → General)
- [ ] Cursor installiert
- [ ] Repository geklont
- [ ] `docker-compose up -d` ausgeführt
- [ ] Container läuft (Check: `http://localhost:7284/health`)
- [ ] 🐳 **Docker-Icon in Statusleiste ist grün**
- [ ] Cursor MCP-Config angepasst
- [ ] Cursor neu gestartet
- [ ] Erste Test-Preisliste importiert

**Zeit-Aufwand:** ~10-15 Minuten (inkl. Downloads)

---

## 🆘 Troubleshooting

### "Container startet nicht"
→ Port 7284 bereits belegt? Kunde soll prüfen:
```bash
docker-compose logs
lsof -i :7284  # Linux/Mac
netstat -ano | findstr :7284  # Windows
```

### "Excel-Import funktioniert nicht"
→ Dateien nicht im richtigen Verzeichnis (siehe README-DOCKER.md)

