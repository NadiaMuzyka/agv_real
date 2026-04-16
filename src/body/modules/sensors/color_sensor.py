from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface 
import threading
import time

SENSORS_KEY = "body_memory"

class ColorSensor(GenericSensor):
    def __init__(self, name):
        # Richiama il costruttore della classe base (GenericSensor)
        super().__init__(name)
        
        # 1. Connessione a CoppeliaSim (Isolata e sicura grazie al Multiton)
        self.connector = CoppeliaConnector(name=f"conn_{self.name}")
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
        
        self.frequenza_lettura = 0.05 # 20 Hz
        self._running = False
        self._thread = None
        self.last_color = [255, 255, 255] # Default bianco

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
            time.sleep(self.frequenza_lettura) 

    def read(self):
        """Legge i dati, struttura il dizionario e aggiorna Redis."""
        color_val = self.read_rgb255()
        self.last_color = color_val #Aggiorno l'ultimo colore letto, accessibile da fuori (es. PIDController)
        
        sensor_data = {self.name: color_val}

        
        # Aggiorna il Belief State su Redis
        self.redis_client.update_sensor_data(SENSORS_KEY, sensor_data)
        return color_val 

    def read_normalized(self):
        """Legge dal sensore e restituisce i valori RGB normalizzati (0.0 - 1.0)."""
        if not self.handle:
            return None, None, None

        try:
            # self.sim è ora univoco per questo thread, nessun rischio di collisione!
            res, p1, p2 = self.sim.handleVisionSensor(self.handle)
            if res >= 0 and p1 and len(p1) > 12:
                r = round(p1[10], 3)
                g = round(p1[11], 3)
                b = round(p1[12], 3)
                return r, g, b
        except Exception as e:
            print(f"[{self.name}] Errore di lettura da CoppeliaSim: {e}")
            
        return None, None, None

    def read_rgb255(self):
        """Restituisce i valori RGB in scala 0-255."""
        r, g, b = self.read_normalized()
        if r is not None:
            return int(r * 255), int(g * 255), int(b * 255)
        return None, None, None
    
    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")