import threading
import time
import json
from modules.connection.redis_interface import RedisInterface

class SensorManager:
    BODY_KEY = "body_memory"
    BRAIN_KEY = "brain_memory"
    NODE_KEY = "am_i_in_a_node"
    
    # Valore target per il nero (come richiesto)
    BLACK_TARGET = [22, 22, 22]

    def __init__(self, sensor_names):
        """
        :param sensor_names: Lista dei nomi dei 3 sensori da monitorare (es. ['s1', 's2', 's3'])
        """
        self.sensor_names = sensor_names
        self.redis_client = RedisInterface()
        
        if not self.redis_client.db:
            raise ConnectionError("[SensorManager] Impossibile connettersi a Redis.")

        self._running = False
        self._thread = None
        self.frequenza_controllo = 0.05  # 20 Hz (più veloce dei sensori per non perdere dati)

    def start(self):
        """Avvia il thread di monitoraggio."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_logica, daemon=True)
            self._thread.start()
            print(f"[SensorManager] Monitoraggio avviato su: {self.sensor_names}")

    def _loop_logica(self):
        """Ciclo principale di elaborazione dati."""
        while self._running:
            self._elabora_dati_sensori()
            time.sleep(self.frequenza_controllo)

    def _elabora_dati_sensori(self):
        """Legge i sensori da Redis e decide se siamo su un nodo."""
        
        # 1. Usa il tuo nuovo metodo per ottenere direttamente il dizionario Python!
        body_memory = self.redis_client.get_sensor_data(self.BODY_KEY)
        
        # Se il dizionario è vuoto (i sensori non hanno ancora scritto nulla), saltiamo
        if not body_memory:
            return

        # 2. Controlla se tutti e tre i sensori rilevano il nero
        detect_count = 0
        for name in self.sensor_names:
            # .get(name) restituisce None se il sensore non ha ancora scritto la sua chiave
            sensor_info = body_memory.get(name)
            
            if sensor_info and sensor_info == self.BLACK_TARGET:
                detect_count += 1

        # 3. Logica finale: tutti e tre devono aver visto il target
        is_in_node = (detect_count == len(self.sensor_names))

        # 4. Scrive il risultato nello spazio "brain_memory"
        self.redis_client.update_sensor_data(self.BRAIN_KEY, {self.NODE_KEY: is_in_node})

    def stop(self):
        """Ferma il thread."""
        self._running = False
        if self._thread:
            self._thread.join()
            print("[SensorManager] Monitoraggio fermato.")