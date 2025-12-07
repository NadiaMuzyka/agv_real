# Usa Python leggero
FROM python:3.9-slim

# Variabili d'ambiente per vedere i log subito
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Installa librerie di sistema per OpenCV (necessarie per YOLO/Visione)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copia e installa i requisiti Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice (anche se il volume lo sovrascrive, è buona pratica per il deploy)
COPY . .

# Il comando CMD è definito nel docker-compose, ma lo mettiamo qui come default
CMD ["python", "main_brain.py"]