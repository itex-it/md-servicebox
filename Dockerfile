# Verwenden des offiziellen Playwright-Images (beinhaltet Python 3.10 und alle System-Abhaengigkeiten für Chromium)
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Umgebungsvariablen für Python einrichten
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# Requirements in den Container kopieren
COPY requirements.txt .

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Playwright-Browser installieren
RUN playwright install chromium

# Den restlichen Quellcode in das Verzeichnis kopieren
# HINWEIS: .git_hash wird als committed Datei mitgeliefert (kein git-Befehl noetig)
# Portainer klont das Repo ggf. ohne .git-History, daher wird der Hash pre-computed committed.
COPY . .

# Hash-Datei verifizieren und ausgeben (nur Kontrollausgabe beim Build)
RUN echo "Build hash: $(cat /app/.git_hash 2>/dev/null || echo 'unknown')"

# Port freigeben, auf dem Uvicorn lauscht
EXPOSE 8005

# Den FastAPI Server mit Uvicorn starten (plus automatischer Datenbank-Migration!)
CMD ["sh", "-c", "python migrate_db.py && uvicorn servicebox_api:app --host 0.0.0.0 --port 8005 --workers 1"]
