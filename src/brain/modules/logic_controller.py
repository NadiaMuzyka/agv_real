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
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.WRITE) #livello batteria
        self.blackboard.register_key(key="person_detected", access=py_trees.common.Access.WRITE)#persona rilevata
        self.blackboard.register_key(key="pallet_list_empty", access=py_trees.common.Access.WRITE)#lista pallet vuota?
        self.blackboard.register_key(key="emergency_state", access=py_trees.common.Access.WRITE)#stato di emergenza?
        self.blackboard.register_key(key="line_error", access=py_trees.common.Access.WRITE)#errore di linea?
        self.blackboard.register_key(key="next_node", access=py_trees.common.Access.WRITE)#prossimo nodo verso cui staimo andando
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.WRITE)#percorso completo verso il target
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.WRITE)#lista dei nodi dove svolgere la missione
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.WRITE)#posizione attuale dell'AGV
        
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
            "battery_level": 10.0,
            "pallet_list_empty": False,
            "emergency_state": False,
            "line_error": 0.0,
            "next_node": self.blackboard.next_node if hasattr(self.blackboard, 'next_node') else None,
            "current_position": self.blackboard.current_position if hasattr(self.blackboard, 'current_position') else "I3",
            "path_to_target": self.blackboard.path_to_target if hasattr(self.blackboard, 'path_to_target') else [],
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
            self.blackboard.next_node = sensor_data.get("next_node", None)
            self.blackboard.current_position = sensor_data.get("current_position", "I3")
            self.blackboard.mission_queue = sensor_data.get("mission_queue", [])
            self.blackboard.path_to_target = sensor_data.get("path_to_target", [])
    
    #Metodo per trovare il percorso ottimotra due nodi
    def find_path(self, nodo_partenza: str, nodo_arrivo: str) -> bool:

        print(f"[LogicController] Trovando percorso da {nodo_partenza} a {nodo_arrivo}...")
        # percorso = lista di stringhe (nodi da attraversare), distanza = float (costo totale del percorso) 
        percorso = self.navigatore.trova_percorso_minimo(nodo_partenza, nodo_arrivo)[0]
        if percorso:
            esito_aggiornamento = self.update_mission_for_recharge(percorso[1:], nodo_arrivo)
            if esito_aggiornamento:
                print(f"[LogicController] Percorso trovato: {percorso}")
            else:
                print(f"[LogicController] Errore nell'aggiornamento della mission queue e del target.")
            return esito_aggiornamento
        else:
            print(f"[LogicController] Nessun percorso trovato da {nodo_partenza} a {nodo_arrivo}.")
            return False
        
    #Metodo per aggiornare mission queue e current target
    def update_mission_for_recharge(self, path: list, next_node: str):
        """ Aggiorna la mission queue e il current target sulla blackboard. """
        if path:
            self.blackboard.path_to_target = path
            self.blackboard.next_node = next_node
            return True 
        else:
            self.blackboard.next_node = None  # Nessun target se la coda è vuota
            print("[LogicController] Mission queue vuota. Nessun target da assegnare.")
            return False
        #NOTA: non cambio mission_queue, quella viene sospesa finché non ricarico la batteria
    

    #Metodo che va a ricaricare l'AGV  (VA RISCRITTO APPENA COLLEGHIAMO IL BODY)
    def go_to_charge_station(self) -> str:
        comando = {
            "type": "MOVE_TO",
            
        # Abbiamo il prossimo nodo?
        if self.blackboard.next_node:
            #L'abbiamo gia raggiunto?
            if self.blackboard.current_position == self.blackboard.next_node:
                #E' il nodo di ricarica?
                if self.blackboard.current_position == "ER":
                    print("[LogicController] Stazione di ricarica raggiunta!")
                    return "SUCCESS"
                else:
                    #abbiamo raggiunto un nodo intermedio
                    # Simuliamo che il sensore di posizione rilevi l'arrivo al nodo intermedio
                    print(f"[LogicController] Nodo intermedio {self.blackboard.next_node} raggiunto, proseguo verso la stazione di ricarica.")
                    self.blackboard.current_position = self.blackboard.next_node  
                    self.blackboard.next_node = self.blackboard.path_to_target.pop(0) if self.blackboard.path_to_target else None
                    #aggiorno il path_to_target rimuovendo il nodo appena raggiunto (LO FARANNO I SENSORI)
                    self.blackboard.path_to_target = self.blackboard.path_to_target[1:] if len(self.blackboard.path_to_target) > 1 else []
                    return "RUNNING"
            else:
                # Non siamo ancora arrivati al prossimo nodo
                # non mando nessun comando, l'attuatore continua a seguire il comando precedente
                return "RUNNING"






       


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