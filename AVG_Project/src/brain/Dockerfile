# USIAMO PYTHON 3.10
FROM python:3.10

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 1. Installiamo strumenti di compilazione (per OpenCV/YOLO) e librerie grafiche
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Aggiorniamo pip
RUN pip install --upgrade pip

# 3. Installiamo le dipendenze Python
# NOTA: Usiamo --extra-index-url per trovare la versione PyTorch CPU, più piccola e stabile.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# 4. Copia il codice Brain
COPY . .

CMD ["python", "main_brain.py"]