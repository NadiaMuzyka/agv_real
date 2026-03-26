# FILE: src/brain/modules/logic_controller.py
import time
import random
import py_trees
from modules.redis_interface import RedisInterface 
from modules.navigatore_grafo import NavigatoreGrafo

class LogicController:
    """ Traduce l'intento del BT in comandi di alto livello e li pubblica su Redis. """
    
    # Costruttore di classe
    def __init__(self, redis_interface: RedisInterface):
        self.db = redis_interface
        self.blackboard = py_trees.blackboard.Client(name="LogicController")
        # Registriamo le chiavi che il logic controller dovrà leggere e scrivere sulla blackboard
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="person_detected", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="pallet_list_empty", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="emergency_state", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="line_error", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.WRITE)
        self.navigatore = NavigatoreGrafo() 

    # Metodo che legge i dati percepiti ed elaborati dai sensori da Redis
    def read_sensors_data_from_redis(self) -> dict:
        """ Legge i dati dei sensori da Redis e li restituisce come dizionario. """
        SENSORS_KEY = "agv_sensors"
        sensor_data = self.db.get_sensor_data(SENSORS_KEY)
        #return sensor_data
        # Stampiamo cosa c'è davvero nel DB (all'inizio sarà vuoto: {})
        print(f"[LogicController] Letti dati REALI da Redis: {sensor_data}") 
        
        # GENERAZIONE DATI RANDOMICI (Per testare il Behavior Tree)
        dati_random = {
            # Genera True al 5%, False all'95%
            "person_detected": random.choices([True, False], weights=[5, 95], k=1)[0],
            # Tutti i dati sottostanti possono essere generati casualmente per il test
            "battery_level": 100.0,
            "pallet_list_empty": False,
            "emergency_state": False,
            "line_error": 0.0,
            "current_target": None,
            "current_position": "ER",
            "mission_queue": []
        }
        if dati_random["person_detected"]:
            print("[LogicController] SIMULAZIONE: Persona rilevata (dati random).")
        else:
            print("[LogicController] SIMULAZIONE: Nessuna persona rilevata (dati random).")
        return dati_random # Restituiamo al main_brain i dati falsati per la simulazione
    
    # Metodo che aggiorna la blackboard con i dati dei sensori
    def update_blackboard_from_sensors(self, sensor_data: dict):
        """ Aggiorna la blackboard con i dati provenienti dai sensori. """
        if sensor_data:
            # NOTA: se la chiave non esiste, usiamo un valore di default
            self.blackboard.battery_level = sensor_data.get("battery_level", 100.0)
            self.blackboard.person_detected = sensor_data.get("person_detected", False)
            self.blackboard.pallet_list_empty = sensor_data.get("pallet_list_empty", False)
            self.blackboard.emergency_state = sensor_data.get("emergency_state", False)
            self.blackboard.line_error = sensor_data.get("line_error", 0.0)
            self.blackboard.current_target = sensor_data.get("current_target", None)
            self.blackboard.current_position = sensor_data.get("current_position", "I3")
            self.blackboard.mission_queue = sensor_data.get("mission_queue", [])
    
    #Metodo per trovare il percorso ottimotra due nodi
    def find_path(self, nodo_partenza: str, nodo_arrivo: str) -> bool:

        print(f"[LogicController] Trovando percorso da {nodo_partenza} a {nodo_arrivo}...")
        # percorso = lista di stringhe (nodi da attraversare), distanza = float (costo totale del percorso) 
        percorso = self.navigatore.trova_percorso_minimo(nodo_partenza, nodo_arrivo)[0]
        if percorso:
            esito_aggiornamento = self.update_mission_queue_e_target(percorso[1:], nodo_arrivo)
            if esito_aggiornamento:
                print(f"[LogicController] Percorso trovato: {percorso}")
            else:
                print(f"[LogicController] Errore nell'aggiornamento della mission queue e del target.")
            return esito_aggiornamento
        else:
            print(f"[LogicController] Nessun percorso trovato da {nodo_partenza} a {nodo_arrivo}.")
            return False
        
    #Metodo per aggiornare mission queue e current target
    def update_mission_queue_e_target(self, mission_queue: list, current_target):
        """ Aggiorna la mission queue e il current target sulla blackboard. """
        if mission_queue:
            self.blackboard.mission_queue = mission_queue
            self.blackboard.current_target = current_target
            return True 
        else:
            self.blackboard.current_target = None  # Nessun target se la coda è vuota
            print("[LogicController] Mission queue vuota. Nessun target da assegnare.")
            return False
    
    
    #Metodo per stoppare l'AGV  
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

    #------------------------------------------------------------------------