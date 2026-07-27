from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface
import threading
import time

class LidarSensor(GenericSensor):
    # Soglia sui valori grezzi di get_ir_proximity(): DA CALIBRARE in laboratorio,
    # non è una distanza in cm ma un segnale IR grezzo (più alto = più vicino).
    SAFETY_THRESHOLD = 200
    def __init__(self, connector):
        """Initialize the LiDAR sensor using the Create3's onboard IR proximity.

            Args:
                connector: Create3Connector già connesso al robot.

            Returns:
                None.

            Raises:
                ConnectionError: If Redis is unavailable during initialization.
        """
        super().__init__("ir_proximity")

        self.connector = connector

        # 2. Connessione a Redis (Condivisa e sicura grazie al Singleton)
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
 

        self.last_data = {"ostacolo": False, "valore_max": 0}
        self.frequenza_lettura = 0.05
        self._running = False
        self._thread = None

    def start(self):
        """Start the background LiDAR-reading thread.

        Returns:
            None. Calling this method while the sensor is already running has
            no effect.
        """
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] 🟢 Thread avviato in modalità REALE.")

 
    def _loop_lettura(self):
        """Continuously read proximity data and publish obstacle state.

        The loop stores the latest obstacle flag and distance in
        ``last_data`` and publishes ``ostacolo_lidar`` to Brain memory.

        Returns:
            None. The loop exits when ``_running`` becomes ``False``.
        """
        while self._running:
            try:
                ir = self.connector.get_ir_proximity()
                ostacolo, valore_max = self._valuta_ostacolo(ir)
                self.last_data = {"ostacolo": ostacolo, "valore_max": valore_max}
                self.redis_client.update_sensor_data("brain_memory", {"ostacolo_lidar": ostacolo})
            except Exception as e:
                print(f"[{self.name}] ❌ Errore nel loop: {e}")
            time.sleep(self.frequenza_lettura)

    def _valuta_ostacolo(self, ir):
        if ir is None or not hasattr(ir, "sensors"):
            return False, 0
        valore_max = max(ir.sensors)
        return valore_max > self.SAFETY_THRESHOLD, valore_max

    def stop(self):
        """Stop the background LiDAR-reading thread.

        Returns:
            None. The method waits for the worker thread to finish when it has
            been started.
        """
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] 🔴 Thread fermato.")