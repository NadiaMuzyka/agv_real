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
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile contattare il Fleet Manager per scaricare la lista pallet.")
            return py_trees.common.Status.FAILURE
        else:
            print(f"[{self.name}] Lista pallet scaricata con successo: {esito}")
            return py_trees.common.Status.SUCCESS
        

        # # Anti-Tick Fantasma: aspettiamo che l'AGV sia "sveglio" e connesso a Redis
        # sensori = lc.db.get_sensor_data("brain_memory")
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
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def update(self):

        lc = self.blackboard.logic_controller
        esito = lc.create_optimal_plan()
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile generare un piano ottimale.")
            return py_trees.common.Status.FAILURE
        else:            
            print(f"[{self.name}] Piano ottimale generato con successo: {esito}")
            return py_trees.common.Status.SUCCESS

        # coda = self.blackboard.mission_queue
        # posizione_attuale = self.blackboard.current_position
        # lc = self.blackboard.logic_controller
        
        # if len(coda) <= 1:
        #     # Se c'è un solo task (o zero), non c'è nulla da ottimizzare
        #     return py_trees.common.Status.SUCCESS

        # # PESI DELL'ALGORITMO (da tarare empiricamente nel tuo simulatore)
        # PESO_DISTANZA = 1.0  
        # PESO_INVECCHIAMENTO = 0.5 # Quanto valore diamo all'attesa?

        # for task in coda:
        #     # 1. Calcola Distanza Reale (o stimata) dal robot al punto di PICKUP
        #     nodo_pickup = task['id'] 
        #     distanza = lc.calcola_distanza_stimata(posizione_attuale, nodo_pickup)
            
        #     # 2. Calcola Invecchiamento (se il server ti passa un timestamp di creazione)
        #     # time_in_queue = time.time() - task['timestamp_creazione']
        #     # Per ora, se non hai il timestamp, possiamo usare l'indice originale nella coda: 
        #     # i task arrivati prima hanno un indice più basso (maggiore priorità temporale).
        #     invecchiamento = task.get('tempo_attesa', 0) # Assumiamo che il server ce lo dia, o lo calcoliamo
            
        #     # 3. CALCOLO DELLO SCORE (Più è basso, meglio è)
        #     # La distanza penalizza (aumenta lo score), l'attesa premia (abbassa lo score)
        #     task['score_ottimizzazione'] = (distanza * PESO_DISTANZA) - (invecchiamento * PESO_INVECCHIAMENTO)

        # # 4. RIORDINA LA CODA IN BASE ALLO SCORE (Dal minore al maggiore)
        # coda_ordinata = sorted(coda, key=lambda x: x['score_ottimizzazione'])
        
        # # Scrivi la nuova coda ottimizzata sulla Blackboard
        # self.blackboard.mission_queue = coda_ordinata
        
        # print(f"[GeneraPianoOttimale] Coda riordinata online! Prossimo target: {coda_ordinata[0]['id']}")
        
        # return py_trees.common.Status.SUCCESS

class NavigaVersoTarget(py_trees.behaviour.Behaviour):
    def __init__(self):
        super(NavigaVersoTarget, self).__init__(name="Naviga Verso Target")
        print("Inizializzo nodo NavigaVersoTarget")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup NavigaVersoTarget")
        return True

    def initialise(self):
        pass

    def update(self):
        esito = self.blackboard.logic_controller.navigate_to_current_target()
        if esito == "SUCCESS":
            return py_trees.common.Status.SUCCESS
        elif esito == "RUNNING":
            return py_trees.common.Status.RUNNING
        else:
                return py_trees.common.Status.FAILURE
        
class IlPercorsoEStatoCalcolato(py_trees.behaviour.Behaviour):
    def __init__(self):
        print("Inizializzo nodo IlPercorsoEStatoCalcolato")
        super(IlPercorsoEStatoCalcolato, self).__init__(name="Il Percorso È Stato Calcolato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        
    def setup(self):
        print("Setup IlPercorsoEStatoCalcolato")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            percorso = self.blackboard.path_to_target
            target_attuale = self.blackboard.current_target
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        # Controlliamo che esista un percorso valido verso il target attuale
        if target_attuale is not None and isinstance(percorso, list) and len(percorso) > 0:
            print(f"[{self.name}] Il percorso verso il target {target_attuale} è stato calcolato.")
            return py_trees.common.Status.SUCCESS
        
        #Se non c'è un percorso significa che o c'è stato un errore
        #oppure sono arrivato al targhet ho effettuato un pickup/dropoff 
        #e ora devo decidere il prossimo target da raggiungere
        return py_trees.common.Status.FAILURE
    

class CalcolaPercorso(py_trees.behaviour.Behaviour):
    def __init__(self):
        print("Inizializzo nodo CalcolaPercorso")
        super(CalcolaPercorso, self).__init__(name="Calcola Percorso")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup CalcolaPercorso")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            lc = self.blackboard.logic_controller
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        esito = lc.calculate_path_to_current_target()
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile calcolare il percorso verso il target.")
            return py_trees.common.Status.FAILURE
        else:
            print(f"[{self.name}] Percorso calcolato con successo: {esito}")
            return py_trees.common.Status.SUCCESS