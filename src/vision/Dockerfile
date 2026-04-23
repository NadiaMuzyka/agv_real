# Partiamo da un'immagine Python leggera (slim) per ottimizzare lo spazio
FROM python:3.10-slim

# Installiamo le dipendenze di sistema necessarie per far girare OpenCV in ambiente Linux
# Questo passaggio è fondamentale per evitare errori di librerie mancanti (.so)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Impostiamo la directory di lavoro all'interno del container
WORKDIR /app

# Copiamo il file dei requisiti ed eseguiamo l'installazione
# Copiarlo prima del resto del codice permette di velocizzare le build successive
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamo l'intero codice del progetto nella cartella di lavoro
COPY . .

# Comando per avviare il microservizio di visione
CMD ["python", "person_detector.py"]