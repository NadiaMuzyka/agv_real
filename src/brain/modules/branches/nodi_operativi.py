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
    Condizione: Verifica se l'AGV è fisicamente arrivato su un nodo di prelievo (PICKUP).
    """
    def __init__(self):
        super(ENodoDiPrelievo, self).__init__(name="E' Nodo di Prelievo?")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup ENodoDiPrelievo")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            target = self.blackboard.current_target
            pos_attuale = self.blackboard.current_position
        except KeyError:
            return py_trees.common.Status.FAILURE

        if target is None:
            return py_trees.common.Status.FAILURE

        print(f"[ENodoDiPrelievo] Valuto il target: {target['id']} (Azione: {target.get('tipo_azione')})")
        
        if target.get("tipo_azione") == "PICKUP":
            if pos_attuale == target["id"]:
                print(f"[ENodoDiPrelievo] ✅ CONFERMATO: Siamo fisicamente sul nodo di prelievo {target['id']}.")
                return py_trees.common.Status.SUCCESS
            else:
                return py_trees.common.Status.FAILURE
        else:
            return py_trees.common.Status.FAILURE 


class EseguiPrelievo(py_trees.behaviour.Behaviour):
    """
    Azione: Invia il comando di PICKUP al Body e attende il feedback dai sensori.
    """
    def __init__(self, name="Esegui Prelievo"):
        super().__init__(name)
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.WRITE)
        self.fase = "INNESCO"

    def setup(self):
        return True

    def initialise(self):
        self.fase = "INNESCO"

    def update(self):
        lc = self.blackboard.logic_controller
        target = self.blackboard.current_target
        
        if target is None:
            return py_trees.common.Status.FAILURE

        if self.fase == "INNESCO":
            print(f"[{self.name}] Invio comando al Body: Sollevare carico per missione {target['id']}...")

            comando = {"type": "PICKUP"}
            lc.db.set_command(lc.db.COMMAND_CHANNEL, comando)
            
            self.fase = "ATTESA"
            return py_trees.common.Status.RUNNING
            
        elif self.fase == "ATTESA":
            sensori = lc.db.get_sensor_data("agv_sensors")
            stato_carico = sensori.get("carico_sollevato", False)
            
            if stato_carico == True:
                print(f"[{self.name}] ✅ Il Body conferma: Prelievo completato meccanicamente!")
                
                self.blackboard.current_target = None
                
                return py_trees.common.Status.SUCCESS
            else:
                return py_trees.common.Status.RUNNING

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
    Azione: Invia il comando di DROP al Body e attende il feedback.
    """
    def __init__(self, name="Esegui Consegna"):
        super().__init__(name)
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        
        # Permesso in SCRITTURA per svuotare le mani del robot a missione finita
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.fase = "INNESCO"

    def setup(self):
        print("Setup EseguiConsegna")
        return True

    def initialise(self):
        self.fase = "INNESCO"

    def update(self):
        lc = self.blackboard.logic_controller
        target = self.blackboard.current_target
        pos_attuale = self.blackboard.current_position 
        
        if target is None:
            return py_trees.common.Status.FAILURE

        if self.fase == "INNESCO":
            print(f"[{self.name}] Invio comando al Body: Consegna sul nodo {pos_attuale} per target {target['id']}")
            
            comando = {"type": "DROP"}
            lc.db.set_command(lc.db.COMMAND_CHANNEL, comando)
            
            self.fase = "ATTESA"
            return py_trees.common.Status.RUNNING
            
        elif self.fase == "ATTESA":
            sensori = lc.db.get_sensor_data("agv_sensors")
            
            stato_carico = sensori.get("carico_sollevato", True) 
            
            if stato_carico == False:
                print(f"[{self.name}] ✅ Il Body conferma: Consegna completata fisicamente!")
                
                # Svuotiamo le mani (missione completata)
                self.blackboard.current_target = None
                return py_trees.common.Status.SUCCESS
            else:
                return py_trees.common.Status.RUNNING