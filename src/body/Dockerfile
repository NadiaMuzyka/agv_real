# USIAMO PYTHON 3.10
FROM python:3.10

ENV PYTHONUNBUFFERED=1
# AGGIUNGI QUESTA RIGA: permette a Python di trovare la cartella modules
ENV PYTHONPATH=/app

WORKDIR /app

# 1. Installiamo strumenti di compilazione essenziali
# Niente Git o build-essential pesante, solo le basi per il Python 3.10 full
# bluez: fornisce bluetoothctl, usato da bleak per rilevare la versione di
# BlueZ; senza non è un errore, ma bleak stampa un warning e assume 5.51+.
RUN apt-get update && apt-get install -y \
    build-essential \
    bluez \
    && rm -rf /var/lib/apt/lists/*

# 2. Aggiorniamo pip
RUN pip install --upgrade pip

# 3. Installiamo le dipendenze (NIENTE ZMQ/CBOR, le prendiamo dall'esterno)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3b. Applichiamo i fix noti a irobot_edu_sdk (bug della libreria upstream,
# vedi patch_irobot_edu_sdk.py). Viene rieseguito ad ogni build dell'immagine.
COPY patch_irobot_edu_sdk.py .
RUN python patch_irobot_edu_sdk.py

# 4. Copia il codice Body
COPY . .

CMD ["python", "-u", "main_body.py"]