import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 3. NODI DI GESTIONE MISSIONE
# =============================================================================

class ListaPalletVuota(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se la lista dei pallet da processare è vuota.
    Restituisce SUCCESS se non ci sono più lavori da fare.
    """
    def __init__(self):
        super(ListaPalletVuota, self).__init__(name="Lista Pallet Vuota")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="pallet_list_empty", access=py_trees.common.Access.READ) 
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ListaPalletVuota")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            magazzino_vuoto = self.blackboard.pallet_list_empty
            coda_locale = self.blackboard.mission_queue
            target_attuale = self.blackboard.current_target
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        if magazzino_vuoto and not coda_locale and target_attuale is None:
            print("[ListaPalletVuota] Missione globale conclusa. Rientro alla base.")
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE

class PianoNonGenerato(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se manca un piano di navigazione per i pallet attuali.
    Restituisce SUCCESS se bisogna generare un nuovo piano.
    """
    def __init__(self):
        super(PianoNonGenerato, self).__init__(name="Piano Non Generato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)

    
    def setup(self):
        print("Setup PianoNonGenerato")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            target_attuale = self.blackboard.current_target
            coda_locale = self.blackboard.mission_queue
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        if target_attuale is None and len(coda_locale) == 0:
            print("[PianoNonGenerato] Nuova missione da pianificare.")
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE
        
class RiceviListaPallet(py_trees.behaviour.Behaviour):
    """
    Azione: Contatta il Fleet Manager tramite API REST per scaricare i nuovi task.
    Se non ci sono task o il server è irraggiungibile, mette l'albero in attesa (IDLE).
    """
    def __init__(self):
        super(RiceviListaPallet, self).__init__(name="Ricevi Lista Pallet")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        
        #il mio gemini pensa che Matteo sia Simone, questa cosa mi fa ridere e non lo correggerò.
        #scusami "Simone" (non so come gli sia venuto)
        # Registriamo in SCRITTURA perché questo nodo popolerà la coda
        
        # TODO per l'incontro di domani: Inserire qui l'IP reale di Simone
        #self.api_url = "http://HOST_DI_SIMONE:PORTA/api/get_mission/agv_1"

    def setup(self):
        print("Setup RiceviListaPallet")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            lc = self.blackboard.logic_controller
        except KeyError:
            return py_trees.common.Status.FAILURE

        esito = lc.download_mission_from_central_system()
        if esito is "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile contattare il Fleet Manager per scaricare la lista pallet.")
            return py_trees.common.Status.FAILURE
        else:
            print(f"[{self.name}] Lista pallet scaricata con successo: {esito}")
            return py_trees.common.Status.SUCCESS
        

        # # Anti-Tick Fantasma: aspettiamo che l'AGV sia "sveglio" e connesso a Redis
        # sensori = lc.db.get_sensor_data("agv_sensors")
        # if not sensori:
        #     return py_trees.common.Status.RUNNING

        # print(f"[{self.name}] Contatto il Fleet Manager...")
        
        # try:
        #     # =========================================================
        #     # CODICE PER DOMANI (Scommentare quando Simone è pronto)
        #     # risposta = requests.get(self.api_url, timeout=2.0)
        #     # if risposta.status_code == 200:
        #     #     missioni_scaricate = risposta.json()
        #     # else:
        #     #     raise Exception(f"Errore HTTP {risposta.status_code}")
        #     # =========================================================
            
        #     # --- MOCK PER OGGI ---
        #     # Stiamo fingendo che 'requests' abbia restituito questo JSON
        #     missioni_scaricate = 
        #     # ---------------------

        #     # SCENARIO 1: Il server ha mandato del lavoro
        #     if len(missioni_scaricate) > 0:
        #         print(f"[{self.name}] Ricevuti {len(missioni_scaricate)} task dal server.")
        #         self.blackboard.mission_queue = missioni_scaricate
        #         return py_trees.common.Status.SUCCESS
            
        #     # SCENARIO 2: Il server dice "Nessun lavoro" (Lista vuota)
        #     else:
        #         print(f"[{self.name}] Coda server vuota. Robot in attesa (IDLE).")
        #         lc.execute_stop() # Assicuriamoci che i motori siano fermi!
        #         return py_trees.common.Status.RUNNING

        # # SCENARIO 3: Errore di Rete (Server spento, cavo staccato, URL sbagliato)
        # except Exception as e:
        #     print(f"[{self.name}] ERRORE DI RETE (Server irraggiungibile): {e}")
        #     lc.execute_stop()
        #     # Restando in RUNNING, l'AGV non crasha ma riprova pacificamente al prossimo tick
        #     return py_trees.common.Status.RUNNING
        

class GeneraPianoOttimale(py_trees.behaviour.Behaviour):
    """
    Azione: Elabora l'ordine ottimale delle missioni (task scheduling) con algortmo Greedy (per zio Daniele) bilanciato.
    """
    def __init__(self):
        super(GeneraPianoOttimale, self).__init__(name="Genera Piano Ottimale")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="temp", access=py_trees.common.Access.WRITE) # Variabile temporanea per salvare dati vari, non persistente su Redis

    def update(self):
        coda = self.blackboard.mission_queue
        posizione_attuale = self.blackboard.current_position
        lc = self.blackboard.logic_controller
        
        if len(coda) <= 1:
            # Se c'è un solo task (o zero), non c'è nulla da ottimizzare
            return py_trees.common.Status.SUCCESS

        # PESI DELL'ALGORITMO (da tarare empiricamente nel tuo simulatore)
        PESO_DISTANZA = 1.0  
        PESO_INVECCHIAMENTO = 0.5 # Quanto valore diamo all'attesa?

        for task in coda:
            # 1. Calcola Distanza Reale (o stimata) dal robot al punto di PICKUP
            nodo_pickup = task['id'] 
            distanza = lc.calcola_distanza_stimata(posizione_attuale, nodo_pickup)
            
            # 2. Calcola Invecchiamento (se il server ti passa un timestamp di creazione)
            # time_in_queue = time.time() - task['timestamp_creazione']
            # Per ora, se non hai il timestamp, possiamo usare l'indice originale nella coda: 
            # i task arrivati prima hanno un indice più basso (maggiore priorità temporale).
            invecchiamento = task.get('tempo_attesa', 0) # Assumiamo che il server ce lo dia, o lo calcoliamo
            
            # 3. CALCOLO DELLO SCORE (Più è basso, meglio è)
            # La distanza penalizza (aumenta lo score), l'attesa premia (abbassa lo score)
            task['score_ottimizzazione'] = (distanza * PESO_DISTANZA) - (invecchiamento * PESO_INVECCHIAMENTO)

        # 4. RIORDINA LA CODA IN BASE ALLO SCORE (Dal minore al maggiore)
        coda_ordinata = sorted(coda, key=lambda x: x['score_ottimizzazione'])
        
        # Scrivi la nuova coda ottimizzata sulla Blackboard
        self.blackboard.mission_queue = coda_ordinata
        
        print(f"[GeneraPianoOttimale] Coda riordinata online! Prossimo target: {coda_ordinata[0]['id']}")
        
        return py_trees.common.Status.SUCCESS

class EstraiProssimoNodo(py_trees.behaviour.Behaviour):
    """
    Azione: Estrae il prossimo nodo target dalla lista pianificata.
    """
    def __init__(self):
        super(EstraiProssimoNodo, self).__init__(name="Estrai Prossimo Nodo")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.WRITE)

    def setup(self):
        print("Setup EstraiProssimoNodo")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            coda = self.blackboard.mission_queue
            target_attuale = self.blackboard.current_target
        except KeyError:
            return py_trees.common.Status.FAILURE

        if target_attuale is None and len(coda) > 0:
            
            prossimo_target = coda.pop(0)
            
            self.blackboard.current_target = prossimo_target
            
            self.blackboard.mission_queue = coda
            
            print(f"[EstraiProssimoNodo] Estratto nuovo target: {prossimo_target}. Rimasti in coda: {len(coda)}")
            
            return py_trees.common.Status.SUCCESS

        if target_attuale is not None:
             return py_trees.common.Status.SUCCESS

        return py_trees.common.Status.FAILURE

class NavigaVersoNodo(py_trees.behaviour.Behaviour):
    """
    Azione: Calcola il percorso ed esegue la navigazione verso il target attuale.
    """
    def __init__(self):
        super(NavigaVersoNodo, self).__init__(name="Naviga Verso Nodo")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="next_node", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="next_node", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.READ)


    def setup(self):
        print("Setup NavigaVersoNodo")
        return True

    def initialise(self):
        """ Eseguito UNA SOLA VOLTA all'inizio della navigazione. """
        print("[NavigaVersoNodo] Inizializzazione navigazione...")
        try:
            lc = self.blackboard.logic_controller
            posizione_attuale = self.blackboard.current_position
            
            # SALVAVITA: Controlliamo che il target esista davvero prima di estrarre l'ID
            target = self.blackboard.current_target
            if target is None:
                print("[NavigaVersoNodo] ERRORE: Nessun target definito durante l'inizializzazione!")
                return
                
            destinazione_finale = target["id"]
            lc.find_path(posizione_attuale, destinazione_finale)
            
        except KeyError:
            return


    def update(self):
        """ Eseguito CONTINUAMENTE finché restituisce RUNNING. """
        
        # 1. LETTURA DATI FRESCHI DALLA BLACKBOARD
        try:
            posizione_attuale = self.blackboard.current_position
            prossimo_nodo = self.blackboard.next_node
            percorso_rimanente = self.blackboard.path_to_target
            lc = self.blackboard.logic_controller
            am_i_in_a_node = self.blackboard.am_i_in_a_node
            target = self.blackboard.current_target 
        except KeyError:
            return py_trees.common.Status.FAILURE

        # Sicurezza: se non c'è una missione attiva, il nodo fallisce
        if target is None:
            return py_trees.common.Status.FAILURE

        # 2. SE IL ROBOT E' FERMO IN UN NODO (am_i_in_a_node == True)
        if am_i_in_a_node:
            
            # CASO A: VITTORIA! Siamo al traguardo finale.
            if posizione_attuale == target["id"]:
                print(f"[{self.name}] 📍 Arrivati a destinazione finale: {posizione_attuale}")
                
                comando_stop = {
                    "type": "STOP", 
                    "current_position": posizione_attuale
                }
                lc.db.set_command(lc.db.COMMAND_CHANNEL, comando_stop)
                
                return py_trees.common.Status.SUCCESS
                
            # CASO B: NODO INTERMEDIO. Aggiorniamo la mappa se siamo arrivati al prossimo_nodo
            if posizione_attuale == prossimo_nodo and len(percorso_rimanente) > 0:
                nuovo_prossimo_nodo = percorso_rimanente.pop(0)
                
                # Aggiorniamo Blackboard
                self.blackboard.next_node = nuovo_prossimo_nodo
                self.blackboard.path_to_target = percorso_rimanente
                
                # Aggiorniamo Redis
                lc.update_path_in_redis(nuovo_prossimo_nodo, percorso_rimanente)
                
                print(f"[{self.name}] Raggiunto snodo: {posizione_attuale}. Calcolo rotta verso {nuovo_prossimo_nodo}...")
                
            # CASO C: PARTENZA. 
            # Ci arriviamo sia se abbiamo estratto un nuovo nodo (Caso B), sia se siamo appena partiti.
            print(f"[{self.name}] Invio comando: Partenza da {posizione_attuale} verso {self.blackboard.next_node}...")
            
            comando_move = {
                "type": "MOVE_TO",
                "next_node": self.blackboard.next_node,
                "current_position": posizione_attuale
            }
            lc.db.set_command(lc.db.COMMAND_CHANNEL, comando_move)
            
            return py_trees.common.Status.RUNNING

        # 3. SE IL ROBOT E' IN VIAGGIO (am_i_in_a_node == False)
        # Il BT non fa assolutamente nulla. Sta in silenzio e aspetta che i sensori confermino l'arrivo.
        return py_trees.common.Status.RUNNING