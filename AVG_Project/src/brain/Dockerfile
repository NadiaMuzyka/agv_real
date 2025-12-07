# USIAMO PYTHON 3.10
FROM python:3.10

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 1. Installiamo strumenti di compilazione (per YOLO/OpenCV) e librerie grafiche
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Aggiorniamo pip
RUN pip install --upgrade pip

# 3. Installiamo le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia il codice Brain
COPY . .

CMD ["python", "main_brain.py"]