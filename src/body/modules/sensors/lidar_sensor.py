from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface
import threading
import time

class LidarSensor(GenericSensor):
    def __init__(self, name):
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

        self.last_data = {"ostacolo": False, "distanza": 999.0}
        self.frequenza_lettura = 0.05  
        self._running = False
        self._thread = None
        self.soglia_sicurezza = 2.0  

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] 🟢 Thread avviato in modalità REALE.")

 
    def _loop_lettura(self):
        """Loop principale di lettura del lidar"""
        while self._running:
            try:
                result, distance = self.read_distanza()
                ostacolo = bool(
                    result and distance is not None and distance < self.soglia_sicurezza
                )
                self.last_data = {
                    "ostacolo": ostacolo,
                    "distanza": distance if distance is not None else 999.0,
                }
                # print( f"[{self.name}] result: {result}, distanza: {distance}, ostacolo: {ostacolo}")
                self.redis_client.update_sensor_data(
                    "brain_memory", {"ostacolo_lidar": ostacolo}
                )

            except Exception as e:
                print(f"[{self.name}] ❌ Errore nel loop: {e}")
            
            time.sleep(self.frequenza_lettura)

    def read_distanza(self):
        """Legge dal sensore e restituisce i valori RGB normalizzati (0.0 - 1.0)."""
        if not self.handle:
            return None, None

        try:
            res, dist, detectedPoint, detectedObjectHandle, detectedSurfaceNormalVector = self.sim.handleProximitySensor(self.handle)
            #print(f"[{self.name}] DEBUG - res={res}, dist={dist}, detectedObjectHandle={detectedObjectHandle}")
            if res > 0:
                return True, dist
            else:
                return False, None
        except Exception as e:
            print(f"[{self.name}] Errore di lettura da CoppeliaSim: {e}")
        
        return None, None

            
            

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] 🔴 Thread fermato.")