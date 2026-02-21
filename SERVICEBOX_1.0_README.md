# ServiceBox Extraktor - Version 1.0

## Versionsbeschreibung (Release 1.0)
Diese Version markiert den produktionsreifen Stand ("ServiceBox 1.0") des Tools zur automatisierten Abfrage und PDF-Extraktion aus dem Hersteller-Portal "ServiceBox". 

### Kernfunktionen (Features):
1. **Automatisierter PDF-Download**: 
   - Lädt zuverlässig den offiziellen Wartungsplan als PDF herunter.
2. **Daten-Extraktion**:
   - Liest Fahrzeugdaten, Rückrufaktionen (inkl. offener Codes) und Garantiedaten vollautomatisch aus dem Dashboard aus.
3. **Cockpit (Web-Dashboard)**:
   - Moderne Live-Übersicht: `http://localhost:8005/dashboard`.
   - Zeigt Live-Statistiken, Job-Status (Pending, Processing, Failed, Completed), Live-Logs sowie die Extraktions-Historie an.
   - Integriertes Ampel-System (LEDs) für Garantie- und Rückrufstatus.
4. **Hintergrund-Queue (JobManager)**:
   - Abfragen können priorisiert und im Hintergrund verarbeitet werden, ohne dass das System bei vielen Anfragen blockiert.
   - Integrierte "Self-Healing"-Mechanismen und "Panic Mode" bei Netzwerkproblemen oder IP-Sperren.
5. **REST-API**:
   - Möglichkeit zur nahtlosen Integration in Drittsysteme (z.B. CRM/ERP) via HTTP (`/api/maintenance-plan`).

---

## Installationsanleitung für einen neuen Rechner

Dieses Paket enthält alles, was benötigt wird, um die ServiceBox 1.0 auf einem Windows-Rechner zu betreiben.

### Systemvoraussetzungen
- Einen PC/Server mit **Windows 10** oder **Windows 11 / Server 2019+**.
- **Python 3.8 oder neuer** muss installiert sein.
  > Bei der Python-Installation unbedingt das Häkchen bei **"Add Python to PATH"** setzen!
- Eine bestehende Internetverbindung.

### Schritt-für-Schritt Installation

1. **Entpacken**: 
   Entpacken Sie die `.zip`-Datei am Zielrechner (z.B. nach `C:\ServiceBox`).
2. **Installation starten**: 
   Öffnen Sie den Ordner und machen Sie einen **Doppelklick auf `install.bat`**.
   - Das Skript erstellt automatisch eine isolierte Umgebung (`.venv`).
   - Es lädt alle notwendigen Pakete (`requirements.txt`) herunter.
   - Es installiert den für die Automatisierung benötigten Chromium-Browser (`playwright`).
3. **Zugangsdaten eintragen**:
   Öffnen Sie die Datei `config.json` mit einem Texteditor (z.B. Notepad) und überprüfen/ändern Sie die ServiceBox-Zugangsdaten (`user_id`, `password`) sowie den `auth_token` für das Dashboard/API. 
4. **Server starten**:
   Machen Sie einen **Doppelklick auf `start_api.bat`**. 
   - Ein Konsolen-Fenster öffnet sich, der Server läuft nun im Hintergrund. Das Fenster bitte geöffnet lassen!
5. **Dashboard öffnen**:
   Öffnen Sie Ihren Browser und rufen Sie `http://localhost:8005/` auf. Loggen Sie sich mit dem in der config hinterlegten `auth_token` ein.

### Enthaltene Pakete (Dependencies)
Die Software installiert bei Ausführung der `install.bat` vollautomatisch folgende Python-Bibliotheken:
- `fastapi` & `uvicorn` (Für den High-Performance Webserver)
- `playwright` (Für die Browser-Automatisierung)
- `beautifulsoup4` (Für das Auslesen der HTML-Strukturen)
- `pydantic` (Für die Daten-Validierung)
