import threading
import time
import json
from modules.connection.redis_interface import RedisInterface

class SensorManager:
    BODY_KEY = "body_memory"
    BRAIN_KEY = "brain_memory"
    

    def __init__(self):
        """
        """
        self.redis_client = RedisInterface()
        
        if not self.redis_client.db:
            raise ConnectionError("[SensorManager] Impossibile connettersi a Redis.")

        self._running = False
        self._thread = None
        self.frequenza_controllo = 0.1  # 20 Hz (più veloce dei sensori per non perdere dati)
        self.last_in_node = False

    def start(self):
        """Avvia il thread di monitoraggio."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_logica, daemon=True)
            self._thread.start()
            print(f"[SensorManager] Monitoraggio avviato.")

    def _loop_logica(self):
        """Ciclo principale di elaborazione dati."""
        while self._running:
            self._elabora_dati_sensori()
            time.sleep(self.frequenza_controllo)

    def _elabora_dati_sensori(self):
        """Legge i sensori da Redis e decide se siamo su un nodo."""
        
        # 1. Usa il tuo nuovo metodo per ottenere direttamente il dizionario Python!
        self.last_in_node = self.redis_client.get_sensor_data(self.BRAIN_KEY).get(self.NODE_KEY)
        body_memory = self.redis_client.get_sensor_data(self.BODY_KEY)
        
        # Se il dizionario è vuoto (i sensori non hanno ancora scritto nulla), saltiamo
        if not body_memory:
            return

        self.redis_client.update_sensor_data(self.BRAIN_KEY, {"battery_level": 100 })
        

    def stop(self):
        """Ferma il thread."""
        self._running = False
        if self._thread:
            self._thread.join()
            print("[SensorManager] Monitoraggio fermato.")