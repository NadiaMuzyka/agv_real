from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface 
import threading
import time

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
        self.frequenza_lettura = 0.05 # 20 Hz
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
        """Il Body legge solo il risultato finale su Redis"""
        dati_percezione = self.redis_client.get_dict("brain_memory")
        
        if dati_percezione:
            self.last_data = {
                "detected": dati_percezione.get("person_detected", False),
                "distance": dati_percezione.get("person_distance", 999.0)
            }
     



    
    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")