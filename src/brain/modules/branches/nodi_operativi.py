import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 4. NODI OPERATIVI (RITIRO E CONSEGNA)
# =============================================================================


class ENodoDiPrelievo(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se l'AGV è fisicamente arrivato su un nodo di prelievo (PICKUP).
    """
    def __init__(self):
        super(ENodoDiPrelievo, self).__init__(name="E' Nodo di Prelievo?")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup ENodoDiPrelievo")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            target = self.blackboard.current_target
            pos_attuale = self.blackboard.current_position
            am_i_in_a_node = self.blackboard.am_i_in_a_node
            is_load = self.blackboard.is_load
        except KeyError:
            return py_trees.common.Status.FAILURE

        if target is None:
            return py_trees.common.Status.FAILURE

        #print(f"[ENodoDiPrelievo] Valuto il target: {target['id']} (Azione: {target.get('tipo_azione')})")
        
        if is_load:
            return py_trees.common.Status.FAILURE
        
        #NOTA: se qui lavoriamo con current_target,invece di mission_queue[pick_up_position]
        #poi dobbiamo aggiornare current_target 
        if pos_attuale == target and am_i_in_a_node:
            #print(f"[ENodoDiPrelievo] ✅ CONFERMATO: Siamo fisicamente sul nodo di prelievo {target.get('id')}.")
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE


class EseguiPrelievo(py_trees.behaviour.Behaviour):
    """
    Azione: Invia il comando di PICKUP al Body e attende il feedback dai sensori.
    """
    def __init__(self):
        super(EseguiPrelievo, self).__init__(name="Esegui Prelievo")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        
        # Registriamo le chiavi in lettura
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)

    def setup(self):
        print(f"Setup {self.name}")
        return True

    def initialise(self):
        """ Eseguito UNA SOLA VOLTA quando il nodo parte. Invio del comando. """
        try:
            lc = self.blackboard.logic_controller
            print(f"[{self.name}] 📦 Invio comando di PICKUP ai motori...")
            
            lc.esegui_prelievo()  # Metodo che imposta il comando di PICKUP sul DB, da cui il Mock Body leggerà
            
        except KeyError:
            print(f"[{self.name}] ERRORE: Logic Controller non trovato sulla Blackboard!")
            pass # Non possiamo restituire FAILURE qui, lo farà l'update al prossimo tick

    def update(self):
        """ Eseguito CONTINUAMENTE finché restituisce RUNNING. Lettura sensori. """
        try:
            is_load = self.blackboard.is_load # In questo caso, il feedback che ci interessa è se il carico è stato sollevato, non tanto lo stato delle forche
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        # 1. Se le forche non sono ancora alzate, stiamo in silenzio e aspettiamo
        if not is_load:
            return py_trees.common.Status.RUNNING
        
        else:
            esito = self.blackboard.logic_controller.aggiorna_stato_dopo_prelievo()  # Metodo che aggiorna lo stato interno del Logic Controller dopo il prelievo, se necessario 
            if esito:
                print(f"[{self.name}] ✅ Feedback ricevuto: Forche alzate con successo, carico a bordo!")
                return py_trees.common.Status.SUCCESS
            else:
                print(f"[{self.name}] ❌ Feedback ricevuto: C'è stato un problema durante il prelievo. Verificare i sensori e lo stato del carico.")
                return py_trees.common.Status.FAILURE
            


class ENodoDiConsegna(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se il nodo attuale è un punto di consegna (Delivery).
    """
    def __init__(self):
        super(ENodoDiConsegna, self).__init__(name="È Nodo di Consegna")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ENodoDiConsegna")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            target = self.blackboard.current_target
            pos_attuale = self.blackboard.current_position
            am_i_in_a_node = self.blackboard.am_i_in_a_node
            is_load = self.blackboard.is_load
        except KeyError:
            return py_trees.common.Status.FAILURE

        if target is None:
            return py_trees.common.Status.FAILURE

        #print(f"[ENodoDiConsegna] Valuto il target: {target['id']} (Azione: {target.get('tipo_azione')})")
        
        if not is_load:
            return py_trees.common.Status.FAILURE
        
        if pos_attuale == target and am_i_in_a_node:
            #print(f"[ENodoDiConsegna] ✅ CONFERMATO: Siamo fisicamente sul nodo di consegna {target.get('id')}.")
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE


class EseguiConsegna(py_trees.behaviour.Behaviour):
    """
    Azione: Invia il comando di DROP al Body e attende il feedback dai sensori.
    """
    def __init__(self):
        super(EseguiConsegna, self).__init__(name="Esegui Consegna")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)

    def setup(self):
        print(f"Setup {self.name}")
        return True

    def initialise(self):
        """ Eseguito UNA SOLA VOLTA quando il nodo parte. Invio del comando. """
        try:
            lc = self.blackboard.logic_controller
            print(f"[{self.name}] 📦 Invio comando di DROP ai motori...")
            
            lc.esegui_consegna()  # Metodo che imposta il comando di DROP sul DB, da cui il Mock Body leggerà
            
        except KeyError:
            print(f"[{self.name}] ERRORE: Logic Controller non trovato sulla Blackboard!")
            pass 

    def update(self):
        """ Eseguito CONTINUAMENTE finché restituisce RUNNING. Lettura sensori. """
        try:
            is_load = self.blackboard.is_load
        except KeyError:
            return py_trees.common.Status.FAILURE
         
        if is_load:
            return py_trees.common.Status.RUNNING
            
        # La conferma avviene quando forche_abbassate diventa True, segnalando che il carico è stato rilasciato.
        print(f"[{self.name}] ✅ Feedback ricevuto: Forche abbassate con successo, carico rilasciato!")
        return py_trees.common.Status.SUCCESS