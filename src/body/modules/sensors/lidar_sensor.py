from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface
import threading
import time

class LidarSensor(GenericSensor):
    def __init__(self, name="Lidar"):
        super().__init__(name)
        
        # Il cruscotto che leggerà il TaskController
        self.last_data = {"ostacolo": False, "distanza": 999.0}
        
        self.frequenza_lettura = 0.05  # 20 Hz, per avere un freno reattivo
        self._running = False
        self._thread = None
        self.soglia_sicurezza = 2.0  # Regola KISS: sotto i 2 metri è allarme

        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
        
        # --- VARIABILE MOCK --- 
        # Cambiando questo numero simuleremo se la strada è libera (>2) o bloccata (<2)
        self.finta_distanza_letta = 1.5  

    def start(self):
        """Avvia il thread del sensore in background."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] 🟢 Thread avviato in modalità TEST (Dati Finti).")

    def _aggiorna_redis(self, ostacolo_rilevato):
        """Aggiorna lo stato ostacolo LIDAR su brain_memory senza sovrascrivere gli altri."""
        try:
            self.redis_client.update_sensor_data("brain_memory", {
                "ostacolo_lidar": bool(ostacolo_rilevato)
            })
        except Exception as e:
            print(f"[{self.name}] Errore scrittura Redis: {e}")


    def _loop_lettura(self):
        """Loop ad alta frequenza per aggiornare lo stato di pericolo."""
        while self._running:
            # 1. Acquisizione (Finta per ora)
            distanza_minima = self.finta_distanza_letta
            
            # 2. Aggiornamento del cruscotto interno
            self.last_data["distanza"] = distanza_minima
            self.last_data["ostacolo"] = distanza_minima < self.soglia_sicurezza
            

            # --- SCRITTURA SU REDIS ---
            #self._aggiorna_redis(self.last_data["ostacolo"])
            # --------------------------
                
            time.sleep(self.frequenza_lettura)

    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] 🔴 Thread fermato.")