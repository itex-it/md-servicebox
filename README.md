# ServiceBox Integration API (v1.1.0)

Ein automatisierter, hoch skalierbarer "Headless" Web-Scraper zur automatischen Extraktion von Revisionsdaten, Garantiezeiten und Service-Handbüchern (Wartungsplänen) aus dem ServiceBox-Portal (Peugeot, Citroen, DS, Opel).

## Funktionen (v1.1.0)
- **Multi-Brand Routing**: Automatische Erkennung der Fahrgestellnummer (WMI) und Weiterleitung an den korrekten Scraper (aktuell: ServiceBox/Stellantis).
- **Paperless-ngx**: PDFs werden nicht lokal gespeichert, sondern nahtlos in dein bestehendes Paperless-Archiv gepusht. Die API "proxied" die PDFs von Paperless bei späteren Downloads.
- **Warteschlange (Redis & SQL)**: Parallele Ausführung. Nutzer triggern Jobs über eine Frontend-API, der Arbeiter ackert diese per echter Push-Queue in Redis im Hintergrund ab (`BLPOP`). Fällt Redis aus, springt der Worker lautlos auf SQL-basiertes Polling zurück.
- **Backend-Abstraktion (SQLAlchemy)**: Egal ob 100 Autos oder 50.000 Autos im Jahr: Die gesamte Speicherarchitektur läuft über ORM-Modelle. In `config.json` kannst du zwischen SQLite, PostgreSQL oder MySQL wählen.
- **Ressourcen-Blocker**: Zur Steigerung der Geschwindigkeit (Faktor 2x) und maximaler Stabilität blockiert der interne Scraper-Browser jegliche Werbenetzwerke, Videos, Google Analytics und Bilder per Netzwerk-Intercept.
- **Cockpit-Dashboard**: Vollständige Live-GUI (`index.html`) zur Überwachung der Warteschlangen, Einsicht in die Historie (Garantie, LCDV, Rückrufe) und Anzeige von Fehlerprotokollen.
- **Proxy-Support**: Trage deine (rotierenden) Proxy-Server in die Konfiguration ein, um IP-Sperren des ServiceBox-Portals zu umgehen.

---

## Installation & Setup

### Voraussetzungen
1. **Python 3.10+** (64-Bit empfohlen)
2. **PostgreSQL / MySQL** oder lokales **SQLite**

### 1. Anwendung installieren
```cmd
git clone <repository_url> servicebox_api
cd servicebox_api
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Konfiguration (`config.json`)
Benenne eine eventuell existierende `config.example.json` in `config.json` um oder lege sie neu an.
Hier ein Beispiel:
```json
{
    "user_id": "DEINE_SERVICEBOX_ID",
    "password": "DEIN_PASSWORT",
    "login_url": "https://servicebox.peugeot.com/",
    "headless": true,
    "log_level": "INFO",
    "output_dir": "downloads",
    "timeout_seconds": 30000,
    "short_timeout_seconds": 5000,
    "auth_token": "SECRET_TOKEN_123",
    "db_connection": "sqlite:///servicebox_history.db",
    "redis_url": "redis://localhost:6379/0",
    "paperless_enabled": true,
    "paperless_url": "http://paperless.itex.at",
    "paperless_token": "849735f8c2f685acdf6feec8bc9c2a58a9566afe",
    "proxy": {
        "server": "",
        "username": "",
        "password": ""
    }
}
```

### 3. Starten
Klicke in Windows idealerweise auf die beiliegende `start_api.bat` oder starte den Server händisch:
```cmd
.venv\Scripts\uvicorn servicebox_api:app --host 0.0.0.0 --port 8005 --reload
```

Das GUI-Panel (Cockpit) erreichst du anschließend im Browser deiner Wahl unter:
`http://localhost:8005/static/dashboard.html`

---

## Datenbank Management (`db_manager.py`)
Um die riesigen gesammelten Datensätze für die Zukunft sicher zu verwalten, gibt es ein eigens geschriebenes Kommandozeilenwerkzeug. Öffne dein Terminal im Ordner und nutze `db_manager.py`.

### 1. Daten Exportieren (Sichern / Backup)
Exportiert den kompletten aktuellen Zustand aus deiner konfigurierten Datenbank in eine rohe `.json`-Datei.
```bash
python db_manager.py export --file backup_2026.json
```

### 2. Daten Importieren / Überführen (Migration)
Möchtest du z. B. von SQLite nach PostgreSQL wechseln?
Ändere in deiner `config.json` den `db_connection` String auf deinen neuen Server (`postgresql://...`) und führe danach den Import aus. Die Daten werden 1:1 in die neuen PostgreSQL-Tabellen geschrieben.
```bash
python db_manager.py import --file backup_2026.json
```

### 3. Daten Löschen (Bereinigung)
Löscht gezielt nur bestimmte Partitionen oder leert die komplette Infrastruktur (Tabellenstruktur bleibt erhalten).
```bash
# Löscht nur die hängengelassene Warteschlange und laufenden Jobs:
python db_manager.py clear --target queue

# Löscht nur die Wartungspläne:
python db_manager.py clear --target maintenance

# Löscht die komplette Historie (Fahrzeugdaten etc.):
python db_manager.py clear --target history

# Alles unwiderruflich leeren:
python db_manager.py clear --target all
```
