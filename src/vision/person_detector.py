import cv2
import time
import signal
import socket
import threading
import numpy as np
from ultralytics import YOLO
from coppeliasim_zmqremoteapi_client import RemoteAPIClient
import redis
import json
import os

class PersonDetectorTestNode:
    FOCALE_SIMULATA = 989.1  # Calcolata per 720x720 con FOV 40°
    LARGHEZZA_SPALLE = 0.5 

    def __init__(self, sensor_name="/Robot/visionSensor"):
        print("[TEST DIRETTO] 🔌 Connessione diretta a CoppeliaSim in corso...")
        
        # Connessione con retry e timeout tramite thread
        max_retries = 30
        delay = 1
        connection_timeout = 5
        connected = False

        indirizzo_redis = os.getenv("REDIS_HOST", "host.docker.internal")
        self.r = redis.Redis(host=indirizzo_redis, port=6379, db=0, decode_responses=True)
        self.chiave_scrittura = "brain_memory"
        
        for attempt in range(max_retries):
            print(f"[TEST DIRETTO] Tentativo {attempt + 1}/{max_retries} - Connessione a host.docker.internal:23000...")
            
            # Prova prima con un test TCP sulla porta
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(connection_timeout)
                result = sock.connect_ex(('host.docker.internal', 23000))
                sock.close()
                if result == 0:
                    print(f"[TEST DIRETTO] ✅ Porta 23000 raggiungibile. Connessione a CoppeliaSim...")
                    try:
                        self.client = RemoteAPIClient(host='host.docker.internal')
                        self.sim = self.client.getObject('sim')
                        self.cam_handle = self.sim.getObject(sensor_name)
                        print(f"[TEST DIRETTO] ✅ Telecamera '{sensor_name}' agganciata con successo!")
                        connected = True
                        break
                    except Exception as e:
                        print(f"[TEST DIRETTO] Errore con RemoteAPIClient: {type(e).__name__}: {e}")
                else:
                    print(f"[TEST DIRETTO] Porta 23000 non raggiungibile (timeout o rifiuto connessione)")
            except Exception as e:
                print(f"[TEST DIRETTO] Errore nel test TCP: {e}")
            
            if attempt < max_retries - 1:
                print(f"[TEST DIRETTO] In attesa {delay}s prima del prossimo tentativo...")
                time.sleep(delay)
                delay = min(delay * 1.5, 10)
        
        if not connected:
            print(f"[TEST DIRETTO] ❌ ERRORE CRITICO: Impossibile connettersi a CoppeliaSim dopo {max_retries} tentativi.")
            exit(1)

        print("[TEST DIRETTO] 🧠 Caricamento modello YOLOv8n in corso...")
        self.model = YOLO("yolov8n.pt")
        
        self.is_running = True
        signal.signal(signal.SIGINT, self._gestisci_spegnimento)
        signal.signal(signal.SIGTERM, self._gestisci_spegnimento)

    def _gestisci_spegnimento(self, signum, frame):
        self.is_running = False

    def run(self):
        print("[TEST DIRETTO] 👁️ Inizio cattura fotogrammi diretta...")
        
        try:
            while self.is_running:
                # 1. Lettura diretta (senza passare da Redis)
                img_raw, res = self.sim.getVisionSensorImg(self.cam_handle)
                
                if not img_raw:
                    print("[TEST DIRETTO] ⚠️ Immagine vuota dal simulatore.")
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
                    # --- INIZIO DEBUG VISIVO SU FILE ---
                    # Chiediamo a YOLO di disegnare i riquadri colorati sull'immagine
                    annotated_frame = r.plot()
                    # Salviamo l'immagine processata fisicamente dentro il container
                    cv2.imwrite("vista_yolo.jpg", annotated_frame)
                    # --- FINE DEBUG VISIVO ---

                    for box in r.boxes:
                        if int(box.cls[0]) == 0 and float(box.conf[0]) > 0.25:
                            x1, _, x2, _ = box.xyxy[0]
                            w_pixel = float(x2 - x1)
                            dist = (self.LARGHEZZA_SPALLE * self.FOCALE_SIMULATA) / w_pixel
                            trovata = True
                            print(f"[TEST DIRETTO - YOLO] 🎯 PERSONA RILEVATA! Distanza: {dist:.2f}m")
                            break

                if not trovata:
                    print(f"[TEST DIRETTO - YOLO] 🙈 Nessuna persona rilevata nel frame corrente.")
                
                time.sleep(0.1) # Rallentiamo per poter leggere il terminale

                # --- SCRITTURA SU REDIS ---
                memoria = {
                    "person_detected": trovata,
                    "person_distance": round(dist, 2) if trovata else 999.0
                }
                self.r.set(self.chiave_scrittura, json.dumps(memoria))
                # --------------------------

        finally:
            print("[TEST DIRETTO] Nodo spento.")

if __name__ == "__main__":
    nodo = PersonDetectorTestNode(sensor_name="/Robot/visionSensor")
    nodo.run()