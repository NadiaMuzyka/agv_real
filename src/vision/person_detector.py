import cv2
import time
import signal
import socket
import numpy as np
from ultralytics import YOLO
from coppeliasim_zmqremoteapi_client import RemoteAPIClient
import redis
import json
import os

class PersonDetector:
    def __init__(self, sensor_name="/Robot/visionSensor"):
        print("[PERSON DETECTOR] 🔌 Connessione diretta a CoppeliaSim in corso...")
        
        # Connessione con retry e timeout
        max_retries = 30
        delay = 1
        connection_timeout = 5
        connected = False

        indirizzo_redis = os.getenv("REDIS_HOST", "host.docker.internal")
        self.r = redis.Redis(host=indirizzo_redis, port=6379, db=0, decode_responses=True)
        self.chiave_scrittura = "brain_memory"
        
        for attempt in range(max_retries):
            print(f"[PERSON DETECTOR] Tentativo {attempt + 1}/{max_retries} - Connessione a host.docker.internal:23000...")
            
            # Prova prima con un test TCP sulla porta
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(connection_timeout)
                result = sock.connect_ex(('host.docker.internal', 23000))
                sock.close()
                if result == 0:
                    print(f"[PERSON DETECTOR] ✅ Porta 23000 raggiungibile. Connessione a CoppeliaSim...")
                    try:
                        self.client = RemoteAPIClient(host='host.docker.internal')
                        self.sim = self.client.getObject('sim')
                        self.cam_handle = self.sim.getObject(sensor_name)
                        print(f"[PERSON DETECTOR] ✅ Telecamera '{sensor_name}' agganciata con successo!")
                        connected = True
                        break
                    except Exception as e:
                        print(f"[PERSON DETECTOR] Errore con RemoteAPIClient: {type(e).__name__}: {e}")
                else:
                    print(f"[PERSON DETECTOR] Porta 23000 non raggiungibile (timeout o rifiuto connessione)")
            except Exception as e:
                print(f"[PERSON DETECTOR] Errore nel test TCP: {e}")
            
            if attempt < max_retries - 1:
                print(f"[PERSON DETECTOR] In attesa {delay}s prima del prossimo tentativo...")
                time.sleep(delay)
                delay = min(delay * 1.5, 10)
        
        if not connected:
            print(f"[PERSON DETECTOR] ❌ ERRORE CRITICO: Impossibile connettersi a CoppeliaSim dopo {max_retries} tentativi.")
            exit(1)

        print("[PERSON DETECTOR] 🧠 Caricamento modello YOLOv8n in corso...")
        self.model = YOLO("yolov8n.pt")
        
        self.is_running = True
        signal.signal(signal.SIGINT, self._gestisci_spegnimento)
        signal.signal(signal.SIGTERM, self._gestisci_spegnimento)

    def _gestisci_spegnimento(self, signum, frame):
        self.is_running = False

    def _update_brain_memory(self, partial_data):
        """Aggiorna solo i campi passati, preservando il resto di brain_memory."""
        try:
            existing_data_str = self.r.get(self.chiave_scrittura)
            if existing_data_str:
                try:
                    current_data = json.loads(existing_data_str)
                    if not isinstance(current_data, dict):
                        current_data = {}
                except json.JSONDecodeError:
                    current_data = {}
            else:
                current_data = {}

            current_data.update(partial_data)
            self.r.set(self.chiave_scrittura, json.dumps(current_data))
        except Exception as e:
            print(f"[PERSON DETECTOR] Errore aggiornamento Redis: {e}")

    def run(self):
        print("[PERSON DETECTOR] 👁️ Inizio cattura fotogrammi diretta...")
        
        try:
            while self.is_running:
                # 1. Lettura diretta
                img_raw, res = self.sim.getVisionSensorImg(self.cam_handle)
                
                if not img_raw:
                    print("[PERSON DETECTOR] ⚠️ Immagine vuota dal simulatore.")
                    time.sleep(0.1)
                    continue

                # 2. Conversione pura
                frame = np.frombuffer(img_raw, dtype=np.uint8).reshape(res[1], res[0], 3)
                frame = cv2.flip(frame, 0)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # 3. Analisi YOLO
                risultati = self.model(frame, stream=True, verbose=False)
                trovata = False

                for r in risultati:

                    for box in r.boxes:
                        if int(box.cls[0]) == 0 and float(box.conf[0]) > 0.25:
                            trovata = True
                            print(f"[PERSON DETECTOR - YOLO] 🎯 PERSONA RILEVATA!")
                            break

                if not trovata:
                    print(f"[PERSON DETECTOR - YOLO] 🙈 Nessuna persona rilevata nel frame corrente.")
                
                time.sleep(0.1) # Rallentiamo per poter leggere il terminale

                # --- SCRITTURA SU REDIS ---
                self._update_brain_memory({
                    "person_detected": trovata
                })
                # --------------------------

        finally:
            print("[PERSON DETECTOR] Nodo spento.")

if __name__ == "__main__":
    nodo = PersonDetector(sensor_name="/Robot/visionSensor")
    nodo.run()