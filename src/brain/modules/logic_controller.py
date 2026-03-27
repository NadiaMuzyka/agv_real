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
        sensor_data = self.db.get_sensor_data(SENSORS_KEY) or {}
        #return sensor_data
        # Stampiamo cosa c'è davvero nel DB (all'inizio sarà vuoto: {})
        print(f"[LogicController] Letti dati REALI da Redis: {sensor_data}") 
        
        # GENERAZIONE DATI RANDOMICI (Per testare il Behavior Tree)
        dati_random = {
            # Genera True al 5%, False all'95%
            "person_detected": random.choices([True, False], weights=[5, 95], k=1)[0],
            # Tutti i dati sottostanti possono essere generati casualmente per il test, al momento vengono letti da redis tramite 
            #il logic controller e scritti sulla blackboard, poi lo faranno i sensori
            "battery_level": sensor_data.get("battery_level",10.0),
            "pallet_list_empty": False,
            "am_i_in_a_node": sensor_data.get("am_i_in_a_node", True),
            "next_node": sensor_data.get("next_node", None),
            "current_position": sensor_data.get("current_position", "I3"),
            "path_to_target": sensor_data.get("path_to_target", []),
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
            self.blackboard.battery_level = sensor_data.get("battery_level", 100.0)#livello batteria
            self.blackboard.person_detected = sensor_data.get("person_detected", False)#persona rilevata
            self.blackboard.pallet_list_empty = sensor_data.get("pallet_list_empty", False)#lista pallet vuota?
            self.blackboard.am_i_in_a_node = sensor_data.get("am_i_in_a_node", False)#sono in un nodo?
            self.blackboard.next_node = sensor_data.get("next_node", None)#prossimo nodo verso cui stiamo andando
            self.blackboard.current_position = sensor_data.get("current_position", "I3")#posizione attuale dell'AGV
            self.blackboard.mission_queue = sensor_data.get("mission_queue", [])#lista dei nodi dove svolgere la missione
            self.blackboard.path_to_target = sensor_data.get("path_to_target", [])#percorso completo verso il target
    
    #Metodo per trovare il percorso ottimotra due nodi
    def find_path(self, nodo_partenza: str, nodo_arrivo: str) -> bool:

        print(f"[LogicController] Trovando percorso da {nodo_partenza} a {nodo_arrivo}...")
        # percorso = lista di stringhe (nodi da attraversare), distanza = float (costo totale del percorso) 
        percorso = self.navigatore.trova_percorso_minimo(nodo_partenza, nodo_arrivo)[0]
        if percorso:
            esito_aggiornamento = self.update_mission_for_recharge(percorso)
            if esito_aggiornamento:
                print(f"[LogicController] Percorso trovato: {percorso}")
            else:
                print(f"[LogicController] Errore nell'aggiornamento della mission queue e del target.")
            return esito_aggiornamento
        else:
            print(f"[LogicController] Nessun percorso trovato da {nodo_partenza} a {nodo_arrivo}.")
            return False
        
    #Metodo per aggiornare mission queue e current target
    def update_mission_for_recharge(self, path: list)-> bool:
        """ Aggiorna la mission queue e il current target sulla blackboard. """
        if path:
            #se il prossimo nodo del vecchi percorso è lo stesso del nuovo percorso
            #che porta a stazione di ricarica, allora non cambio niente,
            if (path[1]==self.blackboard.next_node):
                self.blackboard.path_to_target = path
                self.blackboard.next_node = path[0] if path else None
            #se ti trovi in un nodo e ancora non l'hai lasciato, allora non cambio niente, 
            elif (self.blackboard.am_i_in_a_node):
                self.blackboard.path_to_target = path
                self.blackboard.next_node = path[0] if path else None
            # se invece sei fuori da un nodo e il nodo di destinazione del vecchio percorso è diverso
            # da quello del nuovo percorso, modifico il path,
            #raggiungo il nodo successivo del vecchio percorso, 
            #poi torno al vecchio nodo da cui stavo venendo e da li prendo il nuovo percorso verso la stazione di ricarica
            else:
                next_node_vecchio_percorso = self.blackboard.next_node
                nodo_attuale = self.blackboard.current_position
                path = [next_node_vecchio_percorso, nodo_attuale] + path
            return True 
        else:
            self.blackboard.next_node = None  # Nessun target se la coda è vuota
            print("[LogicController] Mission queue vuota. Nessun target da assegnare.")
            return False
        #NOTA: non cambio mission_queue, quella viene sospesa finché non ricarico la batteria
        #      non cambia current_target, quello è sempre il primo nodo della missione
        #      non cambia am_i_in_a_node, se stavi raggiungendo il prossimo nodo e ti sei fermato a metà strada, quando riparti devi continuare ad andare verso quel nodo finché non ci arrivi, poi aggiorni next_node al nodo successivo della missione (o None se era l'ultimo nodo)
    

    #Metodo che va a ricaricare l'AGV  (VA RISCRITTO APPENA COLLEGHIAMO IL BODY)
    def go_to_charge_station(self) -> str:
        comando = {
            "type": "MOVE_TO",
            "next_node":self.blackboard.next_node, # Nodo verso cui stiamo andando
            "current_position": self.blackboard.current_position, # Nodo in cui siamo attualmente
            "am_i_in_a_node": self.blackboard.am_i_in_a_node # Flag che indica se siamo in un nodo
        }
        #se sono in un nodo
        if self.blackboard.am_i_in_a_node:
            # è la stazione di ricarica? 
            if self.blackboard.current_position == "ER":
                print("[LogicController] Arrivati alla stazione di ricarica. Inizio ricarica...")
                comando = {
                    "type": "STOP"
                }
                self.db.set_command(self.db.COMMAND_CHANNEL, comando)
                return "SUCCESS"
            # mi trovo in un nodo del percorso verso la stazione di ricarica
            else:
                print(f"[LogicController] Mi trovo in un nodo del percorso verso la stazione di ricarica: {self.blackboard.next_node}. Continuo a seguire il percorso...")
                #invio il comando per partire verso il prossimo nodo del percorso
                self.db.set_command(self.db.COMMAND_CHANNEL, comando)
                #simulo la partenza
                self.db.update_sensor_data("agv_sensors", {"am_i_in_a_node": False })
                return "RUNNING"
        #se non sono in un nodo, sto seguendo il percorso verso la stazione di ricarica
        else:
            #variabile per simulare l'arrivo in un nodo (DA RIMUOVERE)
            arrivato_in_nodo = random.choices([True, False], weights=[30, 70], k=1)[0]
            if arrivato_in_nodo:
                #faccio una scrittura sul DB per simulare il body , verrà fatto dal sensore (DA RIMUOVERE)
                #aggiorno la posizione attuale su redis
                if len(self.blackboard.path_to_target)>0:
                    aggiornamenti = {
                        "current_position": self.blackboard.path_to_target[0], #aggiorno la posizione attuale al nodo appena raggiunto
                    }
                    if len(self.blackboard.path_to_target)>1:
                        #aggiorno il next_node su redis
                        aggiornamenti["next_node"] = self.blackboard.path_to_target[1] #aggiorno il next_node al nodo successivo del percorso
                    else:
                        aggiornamenti["next_node"] = None
                    #aggiorno il path_to_target su redis
                    aggiornamenti["path_to_target"] = self.blackboard.path_to_target[1:] #rimuovo il nodo appena raggiunto dal percorso verso la stazione di ricarica
                    self.db.update_sensor_data("agv_sensors", aggiornamenti) #chiamata unica per aggiornare posizione, più veloce
                #aggiorno l'arrivo a nodo su redis (singola chiamata per aggiornamento am_i_in_a_node, deve avvenire dopo le altre)
                self.db.update_sensor_data("agv_sensors", {"am_i_in_a_node": True })
            self.db.set_command(self.db.COMMAND_CHANNEL, comando)
            return "RUNNING"

    #Metodo che simula la carica della batteria (VA RISCRITTO APPENA COLLEGHIAMO IL BODY)
    def recharge_battery(self) -> str:
        step_ricarica = 5.0 # percentuale di carica aggiunta ad ogni step
        if self.blackboard.battery_level < 100.0:
            #aggiorno il livello della batteria su redis
            self.db.update_sensor_data("agv_sensors", {"battery_level": min(self.blackboard.battery_level + step_ricarica, 100.0) })
            return "RUNNING"
        else:
            return "SUCCESS"

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