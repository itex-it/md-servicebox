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

# Wir müssen hier kein apt-get mehr ausführen!

# Den restlichen Quellcode in das Verzeichnis kopieren
COPY . .

# Port freigeben, auf dem Uvicorn lauscht
EXPOSE 8005

# Den FastAPI Server mit Uvicorn starten
CMD ["uvicorn", "servicebox_api:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "1"]
