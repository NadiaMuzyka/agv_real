import threading
import time
from modules.connection.redis_interface import RedisInterface

class ManueverController:
    def __init__(self, redis_client: RedisInterface):
        self.redis_client = redis_client

    def execute_maneuver(self, command_type, command_data=None):
        """
        Avvia un thread per eseguire la manovra.
        Il thread è daemon, quindi termina automaticamente quando finisce.
        """
        maneuver_thread = threading.Thread(
            target=self._execute_maneuver_thread,
            args=(command_type, command_data),
            daemon=True
        )
        maneuver_thread.start()

    def _execute_maneuver_thread(self, command_type, command_data):
        """
        Esecuzione effettiva della manovra all'interno del thread.
        Termina automaticamente quando finisce.
        """
        print(f"🚀 Esecuzione manovra: {command_type} con dati: {command_data}")
        if command_type == "MOVE_TO":
            time.sleep(2)  # Simula il tempo di esecuzione della manovra
            print(f"✅ Manovra {command_type} completata.")

            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "IN_PROGRESS"})
