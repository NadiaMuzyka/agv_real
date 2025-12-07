# Usa Python leggero
FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Non servono dipendenze di sistema pesanti qui

# Copia e installa i requisiti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main_body.py"]