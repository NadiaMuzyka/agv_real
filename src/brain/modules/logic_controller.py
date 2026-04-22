# FILE: src/brain/modules/logic_controller.py
import time
import random
import py_trees
import json
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
        self.blackboard.register_key(key="previous_node", access=py_trees.common.Access.WRITE)#nodo precedente
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.WRITE)#sono in un nodo?
        self.blackboard.register_key(key="is_charging", access=py_trees.common.Access.WRITE)#sto ricaricando?
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.WRITE)#nodo target della missione in corso, None se non c'è missione in corso
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.WRITE)#sto trasportando un carico?
        self.blackboard.register_key(key="mission_finished", access=py_trees.common.Access.WRITE)#la missione è stata completata?
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
        SENSORS_KEY = "brain_memory"  # Chiave Redis dove sono salvati i dati dei sensori
        sensor_data = self.db.get_sensor_data(SENSORS_KEY) or {}
        print(f"[LogicController] Letti dati REALI da Redis: {sensor_data}") 

        #se REDIS  è vuoto all'inizio
        if not sensor_data:
            print("[LogicController] Redis vuoto, inizializzo con dati di default.")
            sensor_data = {
                "battery_level": 100.0,
                "person_detected": False,
                "pallet_list_empty": False,
                "am_i_in_a_node": True,
                "next_node": None,
                "previous_node": None,
                "current_position": "I3",
                "mission_queue": [],
                "path_to_target": [],
                "is_charging": False,
                "current_target": None,
                "is_load": False,
                "mission_finished": False
            }
            #scrittura dell'universo iniziale su Redis secondo quello che penso sia
            self.db.update_sensor_data(SENSORS_KEY, sensor_data)

        # ========================================================
        # 2. EDGE DETECTION: Sincronizzazione istantanea dello stato
        # ========================================================
        try:
            vecchio_is_load = self.blackboard.is_load
        except KeyError:
            vecchio_is_load = False

        nuovo_is_load = sensor_data.get("is_load", False)

        # TRANSIZIONE 1: Da False a True -> PRELIEVO COMPLETATO
        if vecchio_is_load == False and nuovo_is_load == True:
            print("[LogicController] ⚡ Edge Detection: Prelievo completato! Svuoto il target per calcolare la consegna.")
            sensor_data["current_target"] = None
            sensor_data["path_to_target"] = []
            sensor_data["next_node"] = None
            self.db.update_sensor_data(SENSORS_KEY, sensor_data)

        # TRANSIZIONE 2: Da True a False -> CONSEGNA COMPLETATA
        elif vecchio_is_load == True and nuovo_is_load == False:
            print("[LogicController] ⚡ Edge Detection: Consegna completata! Aggiorno la coda missioni.")
            coda = sensor_data.get("mission_queue", [])
            
            if len(coda) > 0:
                finita = coda.pop(0)
                print(f"[LogicController] Missione {finita.get('id')} completata e rimossa.")
            
            mission_over = (len(coda) == 0)
            
            sensor_data["mission_queue"] = coda
            sensor_data["current_target"] = None
            sensor_data["path_to_target"] = []
            sensor_data["next_node"] = None
            sensor_data["pallet_list_empty"] = mission_over
            sensor_data["mission_finished"] = mission_over
            
            self.db.update_sensor_data(SENSORS_KEY, sensor_data)
        # ========================================================

        print(f"[LogicController] Aggiornamento blackboard con dati REALI da Redis: {sensor_data}")
        # NOTA: se la chiave non esiste, usiamo un valore di default
        self.blackboard.battery_level = sensor_data.get("battery_level", 100.0)#livello batteria
        self.blackboard.person_detected = sensor_data.get("person_detected", False)#persona rilevata
        self.blackboard.pallet_list_empty = sensor_data.get("pallet_list_empty", False)#lista pallet vuota?
        self.blackboard.am_i_in_a_node = sensor_data.get("am_i_in_a_node", True)#sono in un nodo?
        self.blackboard.next_node = sensor_data.get("next_node", None)#prossimo nodo verso cui stiamo andando
        self.blackboard.current_position = sensor_data.get("current_position", "I3")#posizione attuale dell'AGV
        self.blackboard.previous_node = sensor_data.get("previous_node", None)#nodo precedente da cui siamo arrivati al current_position
        self.blackboard.mission_queue = sensor_data.get("mission_queue", [])#lista dei nodi dove svolgere la missione
        self.blackboard.path_to_target = sensor_data.get("path_to_target", [])#percorso completo verso il target
        self.blackboard.is_charging = sensor_data.get("is_charging", False)#sono in modalità ricarica?
        self.blackboard.current_target = sensor_data.get("current_target", None)#nodo target della missione in corso, None se non c'è missione in corso 
        self.blackboard.is_load = sensor_data.get("is_load", False)#sto trasportando un carico?
        self.blackboard.mission_finished = sensor_data.get("mission_finished", False)#la missione è stata completata?
        #self.temp è nella blackboard, ma non è persistente su Redis


    #region Metodi Nodi Sicurezza
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
    #endregion

    #region Metodi Nodi Energia
    #Metodo per settare la modalità di energia
    def set_energy_mode(self, mode: str):
        if mode == "CHARGE_MODE":
            self.db.update_sensor_data("brain_memory", {"is_charging": True})
        else:
            self.db.update_sensor_data("brain_memory", {"is_charging": False})

    #Metodo per trovare il percorso ottimo tra due nodi (per la ricarica)
    def find_path_to_recharge(self, nodo_partenza: str, nodo_arrivo: str) -> bool:

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
            self.db.update_sensor_data("brain_memory", aggiornamenti)     
            return True 
        else:
            self.db.update_sensor_data("brain_memory",{"next_node": None})
            print("[LogicController] Mission queue vuota. Nessun target da assegnare.")
            return False
        #NOTA: non cambio mission_queue, quella viene sospesa finché non ricarico la batteria
        #      non cambia current_target, quello è sempre il primo nodo della missione
        #      non cambia am_i_in_a_node, se stavi raggiungendo il prossimo nodo e ti sei fermato a metà strada, quando riparti devi continuare ad andare verso quel nodo finché non ci arrivi, poi aggiorni next_node al nodo successivo della missione (o None se era l'ultimo nodo)
    

    #Metodo che va a ricaricare l'AGV  (VA RISCRITTO APPENA COLLEGHIAMO IL BODY)
    def go_to_charge_station(self) -> str:
        return self._navigate_to_target(target_node="ER", send_stop_on_arrival=True)

    def _navigate_to_target(self, target_node: str | None, send_stop_on_arrival: bool = False) -> str:
        """
        Metodo unico di navigazione per target missione o ricarica.
        Restituisce: SUCCESS, RUNNING, FAILURE.
        """
        if target_node is None:
            print("[LogicController] Navigazione fallita: target mancante.")
            return "FAILURE"

        if self.blackboard.am_i_in_a_node and self.blackboard.current_position == target_node:
            # ========================================================
            # CONTROLLO FINE MISSIONE
            # ========================================================
            # Usiamo getattr per evitare errori se la variabile non dovesse esistere
            if getattr(self.blackboard, "mission_finished", False):
                print("\n" + "="*50)
                print("🎉 [FINE TURNO] Tutte le missioni completate!")
                print("🔋 [FINE TURNO] L'AGV è rientrato alla base. Spegnimento in corso... Addio!")
                print("="*50 + "\n")
                    
                # 1. Mandiamo il comando di morte al Body
                self.db.set_command(self.db.COMMAND_CHANNEL, {"type": "SHUTDOWN"})
                    
                # 2. Spegniamo il Brain
                import sys
                sys.exit(0)
            # ========================================================
            
            if send_stop_on_arrival:
                
                self.db.set_command(self.db.COMMAND_CHANNEL, {"type": "STOP"})
                print("[LogicController] Arrivato in ER: comando STOP inviato.")
            else:
                print(f"[LogicController] Arrivato al target {target_node}.")
            return "SUCCESS"

        next_node = self.blackboard.next_node
        if not next_node:
            print(
                f"[LogicController] Navigazione fallita: next_node non disponibile "
                f"(posizione={self.blackboard.current_position}, target={target_node})."
            )
            return "FAILURE"

        comando = {
            "type": "MOVE_TO",
            "next_node": next_node,  # Nodo verso cui stiamo andando
            "current_position": self.blackboard.current_position, # Nodo in cui siamo attualmente
            "previous_node": self.blackboard.previous_node, # Nodo da cui siamo arrivati al current_position
            "am_i_in_a_node": self.blackboard.am_i_in_a_node # Flag che indica se siamo in un nodo
        }

        if self.blackboard.am_i_in_a_node:
            print(f"[LogicController] Partenza verso nodo {next_node} (target finale: {target_node}).")
            self.db.set_command(self.db.COMMAND_CHANNEL, comando)

            return "RUNNING"

        self.db.set_command(self.db.COMMAND_CHANNEL, comando)
        print(f"[LogicController] In transito verso {next_node} (target finale: {target_node}).")
        return "RUNNING"


    #Metodo che simula la carica della batteria (VA RISCRITTO APPENA COLLEGHIAMO IL BODY)
    def recharge_battery(self) -> str:
        step_ricarica = 5.0 # percentuale di carica aggiunta ad ogni step
        if self.blackboard.battery_level < 100.0:
            nuova_batteria = min(100.0, self.blackboard.battery_level + step_ricarica)
            aggiornamenti = {
                "battery_level": nuova_batteria,
                "is_charging": True
            }
            self.db.update_sensor_data("brain_memory", aggiornamenti)
            print(f"[LogicController] Ricaricando... Livello batteria: {nuova_batteria}%")
            return "RUNNING"
        else:
            self.db.update_sensor_data("brain_memory", {"is_charging": False})
            return "SUCCESS"
    #endregion

    #region Metodi Nodi Operativi
    #Metodo per leggere le richieste e i dati dei pacchetti
    def download_mission_from_central_system(self)-> str:
        # --- FIX: Evita il loop infinito se abbiamo già finito le missioni ---
        if getattr(self.blackboard, "mission_finished", False):
            print("[LogicController] 🛑 Turno finito, rifiuto di scaricare nuove missioni.")
            return "FAILURE"
        # ------------------------------------------------------------------
        info_pack = self.read_json_file("docs/info_pack.json")
        plan = self.read_json_file("docs/plan.json", reset_after_read=True)
        if info_pack and plan:
            self.blackboard.temp["info_pack"] = info_pack
            self.blackboard.temp["plan"] = plan
            return "SUCCESS"
        else:
            return "FAILURE"
        
        #Metodo per creare un piano ottimale a partire da infopack e plan
    
    #Metodo per creare un piano ottimale a partire da infopack e plan
    def create_optimal_plan(self) -> str:

        infopack = self.blackboard.temp.get("info_pack", [])
        plan = self.blackboard.temp.get("plan", [])

        if not isinstance(infopack, list) or not isinstance(plan, list):
            print("[LogicController] Dati missione non validi (info_pack/plan).")
            return "FAILURE"
        
        merge_result = self.merge_plan_infopack(plan, infopack)

        if not merge_result:
            print("[LogicController] Nessuna attività valida trovata dopo la fusione di plan e infopack.")
            return "FAILURE"
        
        # ordiniamo la lista risultante in base alla priorità (dal più alto al più basso)
        ordered_result = sorted(merge_result, key=lambda x: x.get("priority", 0), reverse=True)
        aggiornamenti = {
            "mission_queue": ordered_result
        }

        try:
            self.db.update_sensor_data("brain_memory", aggiornamenti)
            print(f"[LogicController] Piano ottimale creato e mission queue aggiornata: {ordered_result}")
            return "SUCCESS"
        except Exception as e:
            print(f"[LogicController] Errore nell'aggiornamento della mission queue su Redis: {e}")
            return "FAILURE"
    #endregion

    #region Metodi Nodi Operativi - Prelievo e Consegna
    def esegui_prelievo(self):
        """ Metodo che simula l'esecuzione del prelievo (VA RISCRITTO APPENA COLLEGHIAMO IL BODY) """
        print("[LogicController] Esecuzione prelievo in corso...")
        self.db.set_command(self.db.COMMAND_CHANNEL, {"type": "PICKUP"})
        print("[LogicController] Comando PICKUP inviato e stato is_load aggiornato a True.")

    # Metodo che aggiorna lo stato dopo ilprelievo
    def aggiorna_stato_dopo_prelievo(self) -> bool:
        """ 
        Metodo chiamato dal BT quando il prelievo è confermato dai sensori.
        Resetta il target e il percorso per forzare il ricalcolo verso la consegna.
        """
        try:
            # Svuotiamo il target e il percorso attuale su Redis
            # Questo obbligherà il nodo 'Il Percorso È Stato Calcolato' a restituire FAILURE
            # e quindi farà scattare il nodo 'Calcola Percorso'.
            aggiornamenti = {
                "current_target": None,
                "path_to_target": [],
                "next_node": None
            }
            self.db.update_sensor_data("brain_memory", aggiornamenti)
            print("[LogicController] Stato post-prelievo sincronizzato. Target resettato per ricalcolo percorso.")
            return True
        except Exception as e:
            print(f"[LogicController] Errore critico durante l'aggiornamento post-prelievo: {e}")
            return False

    def esegui_consegna(self):
        """ Metodo che simula l'esecuzione della consegna (VA RISCRITTO APPENA COLLEGHIAMO IL BODY) """
        print("[LogicController] Esecuzione consegna in corso...")
        self.db.set_command(self.db.COMMAND_CHANNEL, {"type": "DROP"})
        print("[LogicController] Comando DROP inviato e stato is_load aggiornato a False.")

    def aggiorna_stato_dopo_consegna(self) -> bool:
        """ 
        Metodo chiamato dal BT quando la consegna è confermata dai sensori.
        Rimuove la missione completata dalla coda e resetta i target.
        """
        try:
            coda_attuale = self.blackboard.mission_queue
            
            # Rimuoviamo la missione appena completata (la prima della lista)
            if len(coda_attuale) > 0:
                missione_finita = coda_attuale.pop(0)
                print(f"[LogicController] Missione {missione_finita.get('id')} completata e rimossa dalla coda.")

            #Abbiamo finito tutte le missioni?
            mission_over = False
            if len(coda_attuale) == 0:
                print("[LogicController] 🛑 Tutte le missioni sono state completate! Magazzino svuotato.")
                mission_over = True
            
            # Salviamo la nuova coda (più corta) e resettiamo i parametri di navigazione
            aggiornamenti = {
                "mission_queue": coda_attuale,
                "current_target": None,
                "path_to_target": [],
                "next_node": None,
                "pallet_list_empty": mission_over,  # la missione è finita se la coda è vuota, quindi anche la lista dei pallet è vuota
                "mission_finished": mission_over
            }
            
            self.db.update_sensor_data("brain_memory", aggiornamenti)
            print("[LogicController] Stato post-consegna sincronizzato. In attesa della prossima missione.")
            return True
            
        except Exception as e:
            print(f"[LogicController] Errore critico durante l'aggiornamento post-consegna: {e}")
            return False
    #endregion

    #Metodo per trovare il percorso ottimo tra due nodi (generico)
    def find_path(self, nodo_partenza: str, nodo_arrivo: str) -> list|bool:
        """
            restituisce una lista di nodi da attraversare per andare da nodo_partenza
            a nodo_arrivo, o False se non esiste un percorso valido.
        """
        print(f"[LogicController] Trovando percorso da {nodo_partenza} a {nodo_arrivo}...")
        percorso = self.navigatore.trova_percorso_minimo(nodo_partenza, nodo_arrivo)[0]
        if percorso:
            print(f"[LogicController] Percorso trovato: {percorso}")
            return percorso
        else:
            print(f"[LogicController] Nessun percorso trovato da {nodo_partenza} a {nodo_arrivo}.")
            return False
    

    #Metodo per calcolare il percorso verso il target della missione in corso
    def calculate_path_to_current_target(self):
        #Gestisco il caso in cui la missione sia finita
        nodo_partenza = self.blackboard.current_position
        if getattr(self.blackboard, "mission_finished", False):
            #posizione del nodo di ricarica
            #------------------------------------
            nodo_arrivo = "ER"
            #------------------------------------
            print(f"[LogicController] Turno finito! Ritorno alla base: {nodo_arrivo}")
            esito = self.find_path(nodo_partenza, nodo_arrivo)
            if esito != False:
                aggiornamenti = {
                    "current_target": nodo_arrivo,
                    "path_to_target": esito,
                    "next_node": esito[1] if len(esito)>1 else None,
                    "previous_node": nodo_partenza
                }
                try:
                    self.db.update_sensor_data("brain_memory", aggiornamenti)
                    return "SUCCESS"
                except Exception as e:
                    print(f"[LogicController] Errore nell'aggiornamento del percorso verso il target su Redis: {e}")
                    return "FAILURE"
            else:
                print("[LogicController] Errore: percorso verso il target non trovato.")
                return "FAILURE"

        #controllo se ho un carico da trasportare a bordo,
        # se si,mi trovo in un nodo e il targhet sarà la destinazione
        # dove devo consegnare il carico
        if self.blackboard.is_load and self.blackboard.am_i_in_a_node: 
            nodo_partenza = self.blackboard.current_position
            primo_elemento_missione = self.blackboard.mission_queue[0] if len(self.blackboard.mission_queue)>0 else None

            if primo_elemento_missione is not None:
                nodo_arrivo = primo_elemento_missione.get("destination")
                if nodo_arrivo is not None:
                    esito = self.find_path(nodo_partenza, nodo_arrivo)
                    if esito != False:
                        aggiornamenti = {
                            "current_target": nodo_arrivo,
                            "path_to_target": esito,
                            "next_node": esito[1] if len(esito)>1 else None,
                            "previous_node": nodo_partenza
                        }
                        try:
                            self.db.update_sensor_data("brain_memory", aggiornamenti)
                            return "SUCCESS"
                        except Exception as e:
                            print(f"[LogicController] Errore nell'aggiornamento del percorso verso il target su Redis: {e}")
                            return "FAILURE"
                    else:
                        print("[LogicController] Errore: percorso verso il target non trovato.")
                        return "FAILURE"   
                else:
                    print("[LogicController] Errore: destinazione non trovata nella mission queue.")
                    return "FAILURE"
            else:
                print("[LogicController] Errore: mission queue vuota, nessun target da raggiungere.")
                return "FAILURE"
        # se invece non ho un carico a bordo, 
        # mi trovo in un nodo e il target sarà il nodo di pick up
        # del prossimo carico da prendere
        else:
            nodo_partenza = self.blackboard.current_position
            primo_elemento_missione = self.blackboard.mission_queue[0] if len(self.blackboard.mission_queue) > 0 else None
            if primo_elemento_missione is not None:
                nodo_arrivo = primo_elemento_missione.get("pick_up_position")
                if nodo_arrivo is not None:
                    esito = self.find_path(nodo_partenza, nodo_arrivo)
                    if esito != False:
                        aggiornamenti = {
                            "current_target": nodo_arrivo,
                            "path_to_target": esito,
                            "next_node": esito[1] if len(esito)>1 else None,
                            "previous_node": nodo_partenza
                        }
                        try:
                            self.db.update_sensor_data("brain_memory", aggiornamenti)
                            return "SUCCESS"
                        except Exception as e:
                            print(f"[LogicController] Errore nell'aggiornamento del percorso verso il target su Redis: {e}")
                            return "FAILURE"
                    else:
                        print("[LogicController] Errore: percorso verso il target non trovato.")
                        return "FAILURE"   
                else:
                    print("[LogicController] Errore: pick_up_position non trovata nella mission queue.")
                    return "FAILURE"
            else:
                print("[LogicController] Errore: mission queue vuota, nessun target da raggiungere.")
                return "FAILURE"
    
    
    #Metodo per leggere un file JSON 
    def read_json_file(self, file_path: str, reset_after_read: bool = False):
        """ Legge un file JSON e restituisce il contenuto (lista o dizionario). """
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                print(f"[LogicController] Dati letti da {file_path}: {data}")

                if reset_after_read:
                    empty_payload = [] if isinstance(data, list) else {}
                    with open(file_path, 'w') as reset_file:
                        json.dump(empty_payload, reset_file, indent=4)
                    print(f"[LogicController] File {file_path} resettato dopo la lettura.")

                return data
        except Exception as e:
            print(f"[LogicController] Errore nella lettura del file {file_path}: {e}")
            return {}


    #metodo per inviare un comando di movimento verso il prossimo nodo del percorso
    def move_towards(self, next_node: str):
        """ Invia un comando di movimento verso il prossimo nodo. """
        command = {
            "type": "MOVE_TO",
            "next_node": next_node,
            "current_position": self.blackboard.current_position,
            "previous_node": self.blackboard.previous_node,
            "am_i_in_a_node": self.blackboard.am_i_in_a_node
        }
        self.db.set_command(self.db.COMMAND_CHANNEL, command)
        print(f"[LogicController] Comando MOVE_TO inviato per nodo: {next_node}")

    #metodo per aggiornare il percorso verso il target e il prossimo nodo su Redis
    def update_path_in_redis(self, next_node: str, path_to_target: list):
        """ Sincronizza il nuovo nodo e il percorso rimanente su Redis """
        aggiornamenti = {
            "next_node": next_node,
            "path_to_target": path_to_target
        }
        self.db.update_sensor_data("brain_memory", aggiornamenti)

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

    #Metodo per raggiungere il nodo target
    def navigate_to_current_target(self) -> str:
        target = self.blackboard.current_target
        return self._navigate_to_target(target_node=target, send_stop_on_arrival=False)