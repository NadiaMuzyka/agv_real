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
    Azione: Chiede al LogicController di scaricare i nuovi task.
    """
    def __init__(self):
        super(RiceviListaPallet, self).__init__(name="Ricevi Lista Pallet")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
    
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

        lc.download_mission_from_central_system()
        
        return py_trees.common.Status.SUCCESS

class GeneraPianoOttimale(py_trees.behaviour.Behaviour):
    """
    Azione: Elabora l'ordine ottimale di visita dei nodi (algoritmo di scheduling).
    """
    def __init__(self):
        super(GeneraPianoOttimale, self).__init__(name="Genera Piano Ottimale")
    
    def setup(self):
        print("Setup GeneraPianoOttimale")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS

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
    Azione: Esegue la navigazione (Line Follower / Path Planning) verso il nodo corrente.
    """
    def __init__(self):
        super(NavigaVersoNodo, self).__init__(name="Naviga Verso Nodo")
    
    def setup(self):
        print("Setup NavigaVersoNodo")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS