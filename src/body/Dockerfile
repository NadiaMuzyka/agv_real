# USIAMO PYTHON 3.10
FROM python:3.10

ENV PYTHONUNBUFFERED=1
# AGGIUNGI QUESTA RIGA: permette a Python di trovare la cartella modules
ENV PYTHONPATH=/app

WORKDIR /app

# 1. Installiamo strumenti di compilazione essenziali
# Niente Git o build-essential pesante, solo le basi per il Python 3.10 full
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Aggiorniamo pip
RUN pip install --upgrade pip

# 3. Installiamo le dipendenze (NIENTE ZMQ/CBOR, le prendiamo dall'esterno)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia il codice Body
COPY . .

CMD ["python", "main_body.py"]