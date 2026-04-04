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


    def setup(self):
        print("Setup NavigaVersoNodo")
        return True

    def initialise(self):
        """ Eseguito UNA SOLA VOLTA all'inizio della navigazione. """
        print("[NavigaVersoNodo] Inizializzazione navigazione...")
        try:
            lc = self.blackboard.logic_controller
            posizione_attuale = self.blackboard.current_position
            destinazione_finale = self.blackboard.current_target["id"]
        except KeyError:
            return
        
        lc.find_path(posizione_attuale, destinazione_finale)


    def update(self):
        """ Eseguito CONTINUAMENTE finché restituisce RUNNING. """
        try:
            posizione_attuale = self.blackboard.current_position
            prossimo_nodo = self.blackboard.next_node
            percorso_rimanente = self.blackboard.path_to_target
            lc = self.blackboard.logic_controller
        except KeyError:
            return py_trees.common.Status.FAILURE

        if posizione_attuale == prossimo_nodo:
            
            # SE ci sono ancora nodi nel percorso_rimanente:
            if len(percorso_rimanente) > 0:
                prossimo_nodo = percorso_rimanente.pop(0)
                self.blackboard.next_node = prossimo_nodo
                self.blackboard.path_to_target = percorso_rimanente
                lc.update_path_in_redis(prossimo_nodo, percorso_rimanente)
                print(f"[NavigaVersoNodo] Prossimo nodo: {prossimo_nodo}. Nodi rimanenti: {len(percorso_rimanente)}")
                return py_trees.common.Status.RUNNING
                pass
                
            # ALTRIMENTI (percorso finito, siamo arrivati a destinazione!):
            else:
                print(f"[NavigaVersoNodo] Arrivati a destinazione: {posizione_attuale}")
                return py_trees.common.Status.SUCCESS
                pass

        if posizione_attuale != prossimo_nodo:
            print(f"[NavigaVersoNodo] In viaggio... Posizione attuale: {posizione_attuale}, Prossimo nodo: {prossimo_nodo}")
            lc.move_towards(prossimo_nodo)
            return py_trees.common.Status.RUNNING
        pass