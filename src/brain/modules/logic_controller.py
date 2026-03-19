# FILE: src/brain/modules/logic_controller.py
import time
from modules.redis_interface import RedisInterface 

class LogicController:
    """ Traduce l'intento del BT in comandi di alto livello e li pubblica su Redis. """
    
    # Costruttore di classe
    def __init__(self, redis_interface: RedisInterface):
        self.db = redis_interface

    # Metodo che legge i dati percepiti ed elaborati dai sensori da Redis
    def read_sensors_data_from_redis(self) -> dict:
        """ Legge i dati dei sensori da Redis e li restituisce come dizionario. """
        SENSORS_KEY = "agv_sensors"
        sensor_data = self.db.get_sensor_data(SENSORS_KEY)
        return sensor_data
    
    # Metodo che aggiorna la blackboard con i dati dei sensori
    def update_blackboard_from_sensors(self, sensor_data: dict, blackboard_client):
        """ Aggiorna la blackboard con i dati provenienti dai sensori. """
        if sensor_data:
            # NOTA: se la chiave non esiste, usiamo un valore di default
            blackboard_client.battery_level = sensor_data.get("battery_level", 100.0)
            blackboard_client.person_detected = sensor_data.get("person_detected", False)
            blackboard_client.pallet_list_empty = sensor_data.get("pallet_list_empty", False)
            blackboard_client.emergency_state = sensor_data.get("emergency_state", False)
            blackboard_client.line_error = sensor_data.get("line_error", 0.0)
            blackboard_client.current_target = sensor_data.get("current_target", None)
            blackboard_client.mission_queue = sensor_data.get("mission_queue", [])
    
    
    # METODI DI ESEMPIO
    #------------------------------------------------------------------------
    def execute_line_follow(self, line_error: float):
        """ Invia l'errore di linea al Body, delegando il controllo PID al basso livello. """
        # Pubblica un comando di tipo "LINE_FOLLOW" con l'errore
        command = {
            "type": "LINE_FOLLOW",
            "error": line_error,
            "target_speed": 0.5 # Velocità desiderata
        }
        self.db.set_command(self.db.COMMAND_CHANNEL, command)
      
    #Funzione per stoppare l'AGV  
    def execute_stop(self):
        """ Invia il comando di stop. """
        command = {
            "type": "STOP",
            "v": 0.0, 
            "w": 0.0
        }
        self.db.set_command(self.db.COMMAND_CHANNEL, command)
        print("[LogicController] Comando STOP inviato.")
        return True
    #------------------------------------------------------------------------