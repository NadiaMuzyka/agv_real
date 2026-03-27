import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 4. NODI OPERATIVI (RITIRO E CONSEGNA)
# =============================================================================

# esempio dizionario di current_target
# {"id": "E1", "tipo_azione": "PICKUP"}

class ENodoDiPrelievo(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se il nodo attuale è un punto di ritiro (Pickup).
    """
    def __init__(self):
        super(ENodoDiPrelievo, self).__init__(name="È Nodo di Prelievo")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ENodoDiPrelievo")
        return True

    def initialise(self):
        pass

    def update(self):
        if self.blackboard.current_target is None:
            # Se non abbiamo un target attuale, non possiamo determinare se siamo su un nodo di prelievo
            return Status.FAILURE
            
        if self.blackboard.current_target.get("tipo_azione") == "PICKUP":
            print(f"[ENodoDiPrelievo] Sto sul nodo {self.blackboard.current_target.get('id')} che è un punto di prelievo.")
            return Status.SUCCESS
            
        return Status.FAILURE
        

class EseguiPrelievo(py_trees.behaviour.Behaviour):
    """
    Azione: Attiva gli attuatori (es. muletto) per prelevare il pallet.
    """
    def __init__(self, name):
        super().__init__(name)
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.lc = self.blackboard.logic_controller  

    def initialise(self):
        self.fase = "INNESCO"
        self.inizio_timer = 0

    def update(self):
        target = self.blackboard.current_target
        
        if self.fase == "INNESCO":
            print(f"Avvio prelievo sul nodo {target['id']}")
            
            # self.lc.invia_comando_sollevatore()
            
            self.inizio_timer = time.time()
            self.fase = "ATTESA"

            return Status.RUNNING
            
        elif self.fase == "ATTESA":
            # Per ora simuliamo che l'azione ci metta 3 secondi
            if (time.time() - self.inizio_timer) < 3.0:
                return Status.RUNNING
            else:
                print("Prelievo completato meccanicamente!")
                
                # diciamo al logic controller che abbiamo prelevato il pallet (per aggiornare la blackboard)
                # NOTA: questa è una semplificazione, in realtà dovremmo leggere un feedback dai sensori per capire se il prelievo è avvenuto con successo
                # self.lc.blackboard.current_target = {"id": target["id"], "tipo_azione": "PICKUP", "pallet_prelevato": True}
                # self.lc.updateTarget()

                return Status.SUCCESS


class ENodoDiConsegna(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se il nodo attuale è un punto di consegna (Delivery).
    """
    def __init__(self):
        super(ENodoDiConsegna, self).__init__(name="È Nodo di Consegna")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ENodoDiConsegna")
        return True

    def initialise(self):
        pass

    def update(self):
        if self.blackboard.current_target is None:
            # Se non abbiamo un target attuale, non possiamo determinare se siamo su un nodo di consegna
            return Status.FAILURE
            
        if self.blackboard.current_target.get("tipo_azione") == "DELIVERY":
            print(f"[ENodoDiConsegna] Sto sul nodo {self.blackboard.current_target.get('id')} che è un punto di consegna.")
            return Status.SUCCESS
            
        return Status.FAILURE


class EseguiConsegna(py_trees.behaviour.Behaviour):
    """
    Azione: Attiva gli attuatori per depositare il pallet.
    """
    def __init__(self, name):
        super().__init__(name)
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="last_operation", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.lc = self.blackboard.logic_controller
    
    def setup(self):
        print("Setup EseguiConsegna")
        return True

    def initialise(self):
        self.fase = "INNESCO"
        self.inizio_timer = 0
        pass

    def update(self):
        target = self.blackboard.current_target
        position = self.blackboard.current_position
        
        if position is None or target is None:
            return Status.FAILURE
        
        if self.fase == "INNESCO":
            print(f"Avvio consegna sul nodo {position['id']} per target {target['id']}")
            
            # self.lc.invia_comando_sollevatore()  # Simula il comando di deposito
            
            self.inizio_timer = time.time()
            self.fase = "ATTESA"
            return Status.RUNNING
            
        if self.fase == "ATTESA":
            # Simuliamo che l'azione ci metta 3 secondi
            if (time.time() - self.inizio_timer) < 3.0:
                return Status.RUNNING
            else:
                print("Consegna completata meccanicamente!")
                
                # diciamo al logic controller che abbiamo consegnato il pallet (per aggiornare la blackboard)
                # NOTA: questa è una semplificazione, in realtà dovremmo leggere un feedback dai sensori per capire se la consegna è avvenuta con successo
                # self.lc.blackboard.current_target = {"id": target["id"], "tipo_azione": "DELIVERY", "pallet_consegnato": True}
                # self.lc.updateTarget()

                return Status.SUCCESS
            
        return Status.FAILURE