import threading
import time
from modules.connection.redis_interface import RedisInterface
from modules.actuators.wheel_actuator import WheelsActuator
from modules.controllers.path_controller import PathController

class ManueverController:
    def __init__(self, redis_client: RedisInterface):
        self.redis_client = redis_client
        self.wheels = WheelsActuator()
        self.path_controller = PathController()
        
        # Lock per evitare race condition su wheel_actuator
        self._wheel_lock = threading.Lock()

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
        self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "IN_PROGRESS"})
        print(f"🚀 Esecuzione manovra: {command_type} con dati: {command_data}")
        if command_type == "MOVE_TO":
            print(f"✅ Manovra {command_type} completata.")
            
            # Chiedi al PathController quale manovra fare (LEFT, RIGHT, STRAIGHT)
            maneuver_direction = self.path_controller.get_next_step(
                command_data.get("current_position"), 
                command_data.get("next_node")
            )
            print(f"🚗 PathController ha deciso la manovra: {maneuver_direction}")
            
            time.sleep(10)  # Simula il tempo di esecuzione della manovra

    
    def set_velocity(self, v, w):
        """
        Comanda i wheel in modo thread-safe.
        Usato sia da PID che da TaskController/Maneuver.
        """
        with self._wheel_lock:
            self.wheels.move(v, w)
    
    def stop(self):
        """
        Ferma il robot immediatamente.
        Thread-safe grazie al lock.
        """
        with self._wheel_lock:
            self.wheels.move(0, 0)
        if self.redis_client:
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "NONE"})
            

