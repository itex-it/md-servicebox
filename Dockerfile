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

# (Optional falls Playwright-Browser nachgeladen werden muss, aber das Image hat sie meist schon)
RUN playwright install chromium

# Git installieren (fuer Commit-Hash beim Build-Schritt)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Den restlichen Quellcode in das Verzeichnis kopieren (inkl. .git fuer den Commit-Hash)
COPY . .

# Git-Commit-Hash direkt beim Build extrahieren und in Datei speichern
# Portainer klont das Repo, daher ist .git im Build-Context verfuegbar
RUN git -C /app rev-parse --short HEAD > /app/.git_hash 2>/dev/null || echo "unknown" > /app/.git_hash && \
    echo "Build hash: $(cat /app/.git_hash)"

# Port freigeben, auf dem Uvicorn lauscht
EXPOSE 8005

# Den FastAPI Server mit Uvicorn starten (plus automatischer Datenbank-Migration!)
CMD ["sh", "-c", "python migrate_db.py && uvicorn servicebox_api:app --host 0.0.0.0 --port 8005 --workers 1"]
