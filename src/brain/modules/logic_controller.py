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
        self.blackboard.register_key(key="next_node", access=py_trees.common.Access.WRITE)#prossimo nodo verso cui staimo andando
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.WRITE)#percorso completo verso il target
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.WRITE)#lista dei nodi dove svolgere la missione
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.WRITE)#posizione attuale dell'AGV
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.WRITE)#sono in un nodo?
        self.blackboard.register_key(key="is_charging", access=py_trees.common.Access.WRITE)#sto ricaricando?
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.WRITE)#nodo target della missione in corso, None se non c'è missione in corso
        self.blackboard.register_key(key="temp", access=py_trees.common.Access.WRITE)#variabile temporanea per salvare dati vari, non persistente su Redis
        self.navigatore = NavigatoreGrafo() 

        self.blackboard.temp = dict() 
        self.blackboard.mission_queue = []
        self.blackboard.current_target = None

    # Metodo che legge i dati percepiti ed elaborati dai sensori da Redis
    def update_blackboard_reading_from_redis(self):
        """ 
            Legge i dati dei sensori da Redis e aggiorna la blackboard. 
        """
        SENSORS_KEY = "agv_sensors"
        sensor_data = self.db.get_sensor_data(SENSORS_KEY) or {}
        print(f"[LogicController] Letti dati REALI da Redis: {sensor_data}") 
        
        
        print(f"[LogicController] Aggiornamento blackboard con dati REALI da Redis: {sensor_data}")
        # Aggiorna la blackboard con i dati random (o reali se presenti)
        # NOTA: se la chiave non esiste, usiamo un valore di default
        self.blackboard.battery_level = sensor_data.get("battery_level", 10.0)#livello batteria
        self.blackboard.person_detected = sensor_data.get("person_detected", random.choices([True, False], weights=[5, 95], k=1)[0])#persona rilevata
        self.blackboard.pallet_list_empty = sensor_data.get("pallet_list_empty", False)#lista pallet vuota?
        self.blackboard.am_i_in_a_node = sensor_data.get("am_i_in_a_node", True)#sono in un nodo?
        self.blackboard.next_node = sensor_data.get("next_node", None)#prossimo nodo verso cui stiamo andando
        self.blackboard.current_position = sensor_data.get("current_position", "I3")#posizione attuale dell'AGV
        self.blackboard.path_to_target = sensor_data.get("path_to_target", [])#percorso completo verso il target
        self.blackboard.is_charging = sensor_data.get("is_charging", False)#sono in modalità ricarica?

        #self.temp è nella blackboard, ma non è persistente su Redis

    #Metodo per settare la modalità di energia
    def set_energy_mode(self, mode: str):
        if mode == "CHARGE_MODE":
            self.db.update_sensor_data("agv_sensors", {"is_charging": True})
        else:
            self.db.update_sensor_data("agv_sensors", {"is_charging": False})

    #Metodo per trovare il percorso ottimo tra due nodi
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
        aggiornamenti ={}
        if path:

            nuovo_next_node = path[1] if len(path)>1 else None 
            #se il prossimo nodo del vecchi percorso è lo stesso del nuovo percorso
            #che porta a stazione di ricarica, allora non cambio niente,
            if (nuovo_next_node==self.blackboard.next_node):
                aggiornamenti["path_to_target"] = path
                aggiornamenti["next_node"] = path[0] if path else None
            #se ti trovi in un nodo e ancora non l'hai lasciato, allora non cambio niente, 
            elif (self.blackboard.am_i_in_a_node):
                aggiornamenti["path_to_target"] = path
                aggiornamenti["next_node"] = path[0] if path else None
            # se invece sei fuori da un nodo e il nodo di destinazione del vecchio percorso è diverso
            # da quello del nuovo percorso, modifico il path,
            #raggiungo il nodo successivo del vecchio percorso, 
            #poi torno al vecchio nodo da cui stavo venendo e da li prendo il nuovo percorso verso la stazione di ricarica
            else:
                next_node_vecchio_percorso = self.blackboard.next_node
                nodo_attuale = self.blackboard.current_position
                aggiornamenti["path_to_target"] = [next_node_vecchio_percorso, nodo_attuale] + path
            self.db.update_sensor_data("agv_sensors", aggiornamenti)     
            return True 
        else:
            self.db.update_sensor_data("agv_sensors",{"next_node": None})
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

    #Metodo per leggere un file JSON 
    def read_json_file(self, file_path: str)-> dict:
        """ Legge un file JSON e restituisce il contenuto come dizionario. """
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                print(f"[LogicController] Dati letti da {file_path}: {data}")
                return data
        except Exception as e:
            print(f"[LogicController] Errore nella lettura del file {file_path}: {e}")
            return {}

    #Metodo per leggere le richieste e i dati dei pacchetti
    def download_mission_from_central_system(self)-> str:
        info_pack = self.read_json_file("docs/info_pack.json")
        plan = self.read_json_file("docs/plan.json")
        if info_pack and plan:
            self.blackboard.temp["info_pack"] = info_pack
            self.blackboard.temp["plan"] = plan
            return "SUCCESS"
        else:
            return "FAILURE"

    def move_towards(self, next_node: str):
        """ Invia un comando di movimento verso il prossimo nodo. """
        command = {
            "type": "MOVE_TO",
            "next_node": next_node,
            "current_position": self.blackboard.current_position,
            "am_i_in_a_node": self.blackboard.am_i_in_a_node
        }
        self.db.set_command(self.db.COMMAND_CHANNEL, command)
        print(f"[LogicController] Comando MOVE_TO inviato per nodo: {next_node}")

    def update_path_in_redis(self, next_node: str, path_to_target: list):
        """ Sincronizza il nuovo nodo e il percorso rimanente su Redis """
        aggiornamenti = {
            "next_node": next_node,
            "path_to_target": path_to_target
        }
        self.db.update_sensor_data("agv_sensors", aggiornamenti)

    def calcola_distanza_stimata(self, nodo_partenza: str, nodo_arrivo: str) -> float:
        """
        Calcola la lunghezza del percorso minimo tra due nodi SENZA modificare lo stato.
        Uso esclusivo per algoritmi di ottimizzazione e scheduling (Read-Only).
        """
        if nodo_partenza == nodo_arrivo:
            return 0.0
            
        try:
            percorso, distanza = self.navigatore.trova_percorso_minimo(nodo_partenza, nodo_arrivo)
            
            if percorso is None:
                return 99999.0 # Nessuna rotta trovata, diamo una penalità massima
                
            distanza = float(len(percorso))
            
            return distanza
            
        except Exception as e:
            print(f"[LogicController] Errore nel calcolo distanza stimata: {e}")
            return 99999.0


    # Metodo ausiliario per unire le informazioni del piano e dell'infopack (esempio di elaborazione dati)
    def merge_plan_infopack(self, plan: dict, infopack: list) -> list:
        """ 
            Esempio di metodo che unisce le informazioni del piano e dell'infopack per creare un piano ottimale. 
            In questo esempio, ordiniamo le attività in base alla priorità indicata nell'infopack.
        """
        # Creiamo un dizionario che mappa gli ID delle attività del piano alle loro informazioni nell'infopack
        destinazione_per_id = {item['type']: item for item in infopack}
        result = []
        for item in plan:
            id_item = item.get("id")
            if id_item in destinazione_per_id:
                info_item = destinazione_per_id[id_item]
                result.append({
                    "id": id_item,
                    "pick_up_position":info_item.get("pick_up_position"), 
                    "destination": item.get("destination"),
                    "priority": info_item.get("priority", 0)
                })
        return result

    #metodo per creare un piano ottimale a partire da infopack e plan
    def create_optimal_plan(self, mission_queue: list) -> list:
        infopack = self.blackboard.temp.get("info_pack", {})
        plan = self.blackboard.temp.get("plan", {})
        merge_result = self.merge_plan_infopack(plan, infopack)
        # ordiniamo la lista risultante in base alla priorità (dal più alto al più basso)
        ordered_result = sorted(merge_result, key=lambda x: x['priority'], reverse=True)
        aggiornamenti = {
            "mission_queue": ordered_result,
            "pallet_list_empty": False,
            "current_target": ordered_result[0]['destination'] if len(ordered_result)>0 else None}
        self.db.update_sensor_data("agv_sensors", aggiornamenti)









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