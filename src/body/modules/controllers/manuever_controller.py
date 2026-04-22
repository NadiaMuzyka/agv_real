import threading
import time
from modules.connection.redis_interface import RedisInterface
from modules.actuators.wheel_actuator import WheelsActuator
from modules.controllers.path_controller import PathController

class ManueverController:
    # Costanti dei sensori
    LEFT_SENSOR_NAME = "/Robot/leftColorSensor"
    CENTER_SENSOR_NAME = "/Robot/centralColorSensor"
    RIGHT_SENSOR_NAME = "/Robot/rightColorSensor"
    BLACK_TARGET = [22, 22, 22]
    
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
            
            # Chiedi al PathController quale manovra fare (LEFT, RIGHT, STRAIGHT)
            maneuver_direction = self.path_controller.get_next_step(
                command_data.get("current_position"), 
                command_data.get("next_node")
            )
            print(f"🚗 PathController ha deciso la manovra: {maneuver_direction}")

            if maneuver_direction == "STRAIGHT":
                self.set_velocity(0.07, 0)
                time.sleep(1)
                self.stop()
                print(f"✅ Manovra STRAIGHT completata.")
                
            elif maneuver_direction == "LEFT":
                self._execute_left_turn()
                print(f"✅ Manovra LEFT completata.")
                
            elif maneuver_direction == "RIGHT":
                self._execute_right_turn()
                print(f"✅ Manovra RIGHT completata.")
            
            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})

    
    def _execute_left_turn(self):
        """
        Esegue una svolta a sinistra finché il sensore sinistro vede nero
        e il sensore destro non vede nero.
        """
        print("🔄 Inizio svolta SINISTRA...")
        self.set_velocity(0.03, 0.1)  # Ruota a sinistra (w positivo)
        
        while True:
            body_memory = self.redis_client.get_sensor_data("body_memory")
            
            left_sensor = body_memory.get(self.LEFT_SENSOR_NAME)
            right_sensor = body_memory.get(self.RIGHT_SENSOR_NAME)
            
            # Condizione: sensore sinistro vede nero AND sensore destro NON vede nero
            left_sees_black = left_sensor == self.BLACK_TARGET
            right_not_black = right_sensor != self.BLACK_TARGET
            
            if left_sees_black and right_not_black:
                print("✓ Sensore sinistro allineato, fine svolta SINISTRA")
                break
            
            time.sleep(0.05)  # Controlla ogni 50ms
        
        self.stop()

    def _execute_right_turn(self):
        """
        Esegue una svolta a destra finché il sensore destro vede nero
        e il sensore sinistro non vede nero.
        """
        print("🔄 Inizio svolta DESTRA...")
        self.set_velocity(0.03, -0.1)  # Ruota a destra (w negativo)
        
        while True:
            body_memory = self.redis_client.get_sensor_data("body_memory")
            
            left_sensor = body_memory.get(self.LEFT_SENSOR_NAME)
            right_sensor = body_memory.get(self.RIGHT_SENSOR_NAME)
            
            # Condizione: sensore destro vede nero AND sensore sinistro NON vede nero
            right_sees_black = right_sensor == self.BLACK_TARGET
            left_not_black = left_sensor != self.BLACK_TARGET
            
            if right_sees_black and left_not_black:
                print("✓ Sensore destro allineato, fine svolta DESTRA")
                break
            
            time.sleep(0.05)  # Controlla ogni 50ms
        
        self.stop()

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
            

