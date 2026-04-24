from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface 
import threading
import time
import json
import base64
import numpy as np

SENSORS_KEY = "body_memory"

class VisionSensor(GenericSensor):
    def __init__(self, name):
        # Richiama il costruttore della classe base (GenericSensor)
        super().__init__(name)
        
        # 1. Connessione a CoppeliaSim (Isolata e sicura grazie al Multiton)
        self.connector = CoppeliaConnector(name=f"{self.name}")
        self.sim = self.connector.get_sim()
        
        # Recuperiamo l'handle dell'oggetto da CoppeliaSim
        try:
            self.handle = self.sim.getObject(self.name)
        except Exception as e:
            print(f"[{self.name}] ERRORE: Sensore non trovato in CoppeliaSim. Dettagli: {e}")
            self.handle = None

        # 2. Connessione a Redis (Condivisa e sicura grazie al Singleton)
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
        
        self.last_data = {"detected": False, "distance": 999.0}
        self.frequenza_lettura = 0.1# 10 Hz
        self._running = False
        self._thread = None

    def start(self):
        """Avvia il thread del sensore."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] Thread avviato.")

    def _loop_lettura(self):
        """Metodo privato che gira in background nel thread."""
        while self._running:
            self.read() 
    
            if self.last_data["detected"] and self.last_data["distance"] < 3.0:
                #agv.stop()
                print("ALT! Riflesso di sicurezza dal Body!")
            time.sleep(self.frequenza_lettura)

    def read(self):
        """Legge l'immagine dal sensore di visione via ZMQ e la pubblica su Redis."""
        if self.handle is None:
            print(f"[{self.name}] Errore: handle del sensore non valido.")
            return
        
        try:
            # Legge l'immagine dal sensore di visione via ZMQ Remote API
            img_buffer, resolution = self.sim.getVisionSensorImg(self.handle)
            
            if img_buffer is None:
                print(f"[{self.name}] Errore: nessun dato immagine ricevuto.")
                return
            
            # Converte il buffer in array numpy per facilità di manipolazione
            img_array = np.frombuffer(img_buffer, dtype=np.uint8).reshape(
                resolution[1], resolution[0], 3  # height, width, 3 (RGB)
            )
            
            # Capovolge l'immagine se necessario (CoppeliaSim usa convenzioni diverse)
            img_array = img_array[::-1, :, :]
            
            # Encode l'immagine in base64 per facilitare la trasmissione via Redis
            img_base64 = base64.b64encode(img_array.tobytes()).decode('utf-8')
            
            # Prepara i dati per Redis
            vision_data = {
                "image_base64": img_base64,
                "width": resolution[0],
                "height": resolution[1],
                "timestamp": time.time(),
                "channels": 3
            }
            
            # Salva su Redis
            redis_key = f"{SENSORS_KEY}:{self.name}"
            self.redis_client.db.set(redis_key, json.dumps(vision_data))
            
            
        except Exception as e:
            print(f"[{self.name}] Errore nella lettura dell'immagine: {e}")
            self.last_data["detected"] = False

    
    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")