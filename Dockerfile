# Verwenden eines offiziellen Python-Images als Basis
FROM python:3.10-slim

# Umgebungsvariablen für Python einrichten (kein Puffer, keine Bytecode-Dateien)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# Erforderliche Systempakete für Playwright und dessen Abhängigkeiten installieren
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgconf-2-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libnss3-dev \
    libxss-dev \
    fonts-liberation \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Requirements in den Container kopieren
COPY requirements.txt .

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Browser (Chromium) und dessen OS-Abhängigkeiten installieren
RUN playwright install chromium
RUN playwright install-deps chromium

# Den restlichen Quellcode in das Verzeichnis kopieren
COPY . .

# Port freigeben, auf dem Uvicorn lauscht
EXPOSE 8005

# Den FastAPI Server mit Uvicorn starten
CMD ["uvicorn", "servicebox_api:app", "--host", "0.0.0.0", "--port", "8005", "--workers", "1"]
