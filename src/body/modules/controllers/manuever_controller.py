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

    def execute_maneuver(self, command_type, command_data=None, retro = False, pid = None):
        """
        Avvia un thread per eseguire la manovra.
        Il thread è daemon, quindi termina automaticamente quando finisce.
        """
        maneuver_thread = threading.Thread(
            target=self._execute_maneuver_thread,
            args=(command_type, command_data, retro, pid),
            daemon=True
        )
        maneuver_thread.start()

    def _execute_maneuver_thread(self, command_type, command_data, retro, pid = None):
        """
        Esecuzione effettiva della manovra all'interno del thread.
        Termina automaticamente quando finisce.
        """
        self.pid = pid  # Store pid as instance attribute
        self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "IN_PROGRESS"})
        print(f"🚀 Esecuzione manovra: {command_type} con dati: {command_data}")
        if command_type == "MOVE_TO":

            # Chiedi al PathController quale manovra fare (LEFT, RIGHT, STRAIGHT)
            maneuver_direction = self.path_controller.get_next_step2(
                command_data.get("current_position"),
                command_data.get("next_node"),
                command_data.get("previous_node")
            )
            print(f"🚗 PathController ha deciso la manovra: {maneuver_direction}")


            if maneuver_direction == "STRAIGHT":
                self.set_velocity_for(0.05, 0, 2)
                self.stop()
                print(f"✅ Manovra STRAIGHT completata.")

            elif (maneuver_direction == "LEFT" and not retro) or (maneuver_direction == "RIGHT" and retro):
                self._execute_left_turn(reversed=retro)
                print(f"✅ Manovra di svolta a sinistra completata.")

            elif (maneuver_direction == "RIGHT" and not retro) or (maneuver_direction == "LEFT" and retro):
                self._execute_right_turn(reversed=retro)
                print(f"✅ Manovra di svolta a destra completata.")


            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})

        elif command_type == "DROP":

            self.execute_drop()
            print(f"✅ Manovra DROP completata.")

            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})



    def _execute_left_turn(self, reversed = False, pid = None):
        """
        Esegue una svolta a sinistra finché il sensore sinistro vede nero
        e il sensore destro non vede nero.
        """
        print("🔄 Inizio svolta SINISTRA...")
        direction = 1 if not reversed else -1

        self.set_velocity_for(0.0, 0.2, 7)  # Ruota a sinistra (w positivo)

        self.set_velocity_for(0.0, 0.0, 0.5)  # Ferma il robot dopo la svolta

        self.set_velocity_for(0.03*direction, 0.0, 2)  # Avanza leggermente per riagganciare il pid

    def _execute_right_turn(self, reversed = False, pid = None):
        """
        Esegue una svolta a destra finché il sensore destro vede nero
        e il sensore sinistro non vede nero.
        """
        print("🔄 Inizio svolta DESTRA...")
        direction = 1 if not reversed else -1
        self.set_velocity_for(0.0, -0.2, 7)  # Ruota a destra (w negativo)

        self.set_velocity_for(0.0, 0.0, 0.5)  # Ferma il robot dopo la svolta

        self.set_velocity_for(0.03*direction, 0.0, 2)  # Avanza leggermente per riagganciare il pid


    def execute_drop(self):
        """
        Esegue la manovra di DROP.
        Per ora è un placeholder che simula il drop con una pausa.
        """
        print("🔄 Esecuzione manovra DROP...")
        self.set_velocity(0, 0)  # Ferma il robot durante il drop
        time.sleep(2)  # Simula il tempo necessario per il drop
        self.stop()

    def set_velocity(self, v, w):
        """
        Comanda i wheel in modo thread-safe.
        Usato sia da PID che da TaskController/Maneuver.
        """

        with self._wheel_lock:
            self.wheels.move(v, w)

    def set_velocity_for(self, v, w, duration):
        """
        Comanda i wheel in modo thread-safe.
        Usato sia da PID che da TaskController/Maneuver.
        """
        with self._wheel_lock:
            self.wheels.move_for(v, w, duration)


    def stop(self):
        """
        Ferma il robot immediatamente.
        Thread-safe grazie al lock.
        """
        with self._wheel_lock:
            self.wheels.move(0, 0)
        if self.redis_client:
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "NONE"})


