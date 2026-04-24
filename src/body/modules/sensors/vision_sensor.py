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
            # 1. NON SCATTIAMO PIÙ LA FOTO DA QUI. FA TUTTO IL VISION CONTAINER!
            # self.read()  <-- RIGA CANCELLATA

            # 2. Ascoltiamo solo il verdetto dell'Intelligenza Artificiale da Redis
            try:
                risposta_str = self.redis_client.db.get("brain_memory")
                if risposta_str:
                    risposta = json.loads(risposta_str)
                    self.last_data["detected"] = risposta.get("person_detected", False)
                    self.last_data["distance"] = risposta.get("person_distance", 999.0)
            except Exception as e:
                print(f"[{self.name}] Errore lettura da Redis: {e}")

            # 3. Eseguiamo il riflesso incondizionato sui motori
            if self.last_data["detected"] and self.last_data["distance"] < 3.0:
                # agv.stop()
                print(f"🛑 [{self.name}] ALT! Ostacolo a {self.last_data['distance']}m")
                
            time.sleep(self.frequenza_lettura)
    
    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")