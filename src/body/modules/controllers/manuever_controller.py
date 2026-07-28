import threading
from modules.controllers.position_controller import PositionController


class ManueverController:
    def __init__(self, connector, redis_client):
        self.connector = connector  # Create3Connector: BLE/asyncio già gestiti dentro
        self.redis_client = redis_client
        self.position_controller = PositionController()
        self._stop_requested = threading.Event()

    def execute_maneuver(self, command_type, command_data=None):
        """Avvia la manovra in un thread daemon, come nella versione originale."""
        maneuver_thread = threading.Thread(
            target=self._execute_maneuver_thread,
            args=(command_type, command_data),
            daemon=True
        )
        maneuver_thread.start()

    def request_stop(self):
        """
        Stop non più cooperativo per fasi: navigate_to() è un comando atomico,
        non possiamo più distinguere "sto girando" da "sto avanzando" come nel
        vecchio PID a due fasi. Fermo subito, fisicamente, e basta.
        """
        self._stop_requested.set()
        try:
            self.connector.stop()
        except Exception as e:
            print(f"⚠️ [request_stop] Errore nell'arresto: {e}")

    def _execute_maneuver_thread(self, command_type, command_data):
        self._stop_requested.clear()
        print(f"🚀 Esecuzione manovra: {command_type} con dati: {command_data}")

        if command_type == "MOVE_TO":
            next_node = (command_data or {}).get("next_node")
            target = self.position_controller.get_position(next_node) if next_node else None
            if target:
                x, y = target
                print(f"🧭 [move_to] navigate_to({x}, {y})")
                try:
                    self.connector.navigate_to(x, y)
                except Exception as e:
                    print(f"⚠️ [move_to] navigate_to interrotta/fallita: {e}")
            else:
                print(f"⚠️ [move_to] Nodo sconosciuto o mancante: {next_node}")

        elif command_type == "PICKUP":
            self.connector.set_lights_on_rgb(0, 255, 0)  # verde = carico agganciato
            self.redis_client.update_sensor_data("brain_memory", {"is_load": True})

        elif command_type == "DROP":
            self.connector.set_lights_on_rgb(255, 64, 0)  # arancione = carico rilasciato
            self.redis_client.update_sensor_data("brain_memory", {"is_load": False})

        elif command_type == "SHUTDOWN":
            print("🅿️ [SHUTDOWN] Rientro al dock...")
            try:
                self.connector.dock()
            except Exception as e:
                print(f"⚠️ [SHUTDOWN] Docking interrotto/fallito: {e}")

        self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})
        print(f"🧠 [ManeuverController] Manovra completata")

    def stop(self):
        """Usato anche da TaskController.stop() in fase di shutdown."""
        self.connector.stop()