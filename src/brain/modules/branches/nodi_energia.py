import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 2. NODI DI GESTIONE ENERGIA
# =============================================================================

class ControlloBatteria(py_trees.behaviour.Behaviour):
    """
    Verifica il livello della batteria.
    Restituisce SUCCESS se la batteria è CRITICA (< 20%), attivando la sequenza di ricarica.
    """
    def __init__(self):
        super(ControlloBatteria, self).__init__(name="Controllo Batteria < 20%")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ControlloBatteria")
        return True

    def initialise(self):
        pass

    def update(self):
        # Controlla se il livello della batteria è inferiore al 20%
        if self.blackboard.battery_level < 20.0:
            print(f"[ControlloBatteria] Batteria critica: {self.blackboard.battery_level:.2f}%")
            return Status.SUCCESS
        else:
                return Status.FAILURE

class CalcolaPercorsoRicarica(py_trees.behaviour.Behaviour):
    """
    Calcola il percorso ottimale verso la stazione di ricarica più vicina.
    """
    def __init__(self, nodo_ricarica="ER"):
        super(CalcolaPercorsoRicarica, self).__init__(name="Calcola Percorso Ricarica")
        self.nodo_ricarica = nodo_ricarica

        # Blackboard per leggere la posizione attuale e scrivere il percorso da seguire
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup CalcolaPercorsoRicarica")
        return True

    def initialise(self):
        pass

    def update(self):
        LogicController = self.blackboard.logic_controller
        # Legge la posizione attuale dalla blackboard
        try:
            nodo_partenza = self.blackboard.current_position
        except KeyError:
            print("[CalcolaPercorsoRicarica] Errore: Posizione 'current_position' non trovata sulla blackboard.")
            return Status.FAILURE
        # Se stavo già andando a ricaricare non devo ricalcolare il percorso
        if self.blackboard.path_to_target and self.blackboard.path_to_target[-1] == self.nodo_ricarica:
            print("[CalcolaPercorsoRicarica] Già in missione verso la stazione di ricarica, non ricalcolo il percorso.")
            return Status.SUCCESS
        else:
            esito = LogicController.find_path(nodo_partenza, self.nodo_ricarica)
            match esito:
                case True:
                    return Status.SUCCESS
                case False:
                    return Status.FAILURE

class VaiAStazioneRicarica(py_trees.behaviour.Behaviour):
    """
    Gestisce la navigazione fisica verso la stazione di ricarica.
    """
    def __init__(self):
        super(VaiAStazioneRicarica, self).__init__(name="Vai A Stazione Ricarica")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup VaiAStazioneRicarica")
        return True

    def initialise(self):
        pass

    def update(self):
        LogicController = self.blackboard.logic_controller
        esito = LogicController.go_to_charge_station()
        match esito:
            case "SUCCESS":
                return Status.SUCCESS
            case "FAILURE":
                return Status.FAILURE
            case "RUNNING":
                return Status.RUNNING
            

class RicaricaBatteria(py_trees.behaviour.Behaviour):
    """
    Gestisce il processo di ricarica (attesa fino al 100%).
    """
    def __init__(self):
        super(RicaricaBatteria, self).__init__(name="Ricarica Batteria")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup RicaricaBatteria")
        return True

    def initialise(self):
        print("[RicaricaBatteria] Inizio ricarica... Attesa fino al 100%")

    def update(self):
        try:
            logic_controller = self.blackboard.logic_controller
        except KeyError:
            print("[RicaricaBatteria] Errore: 'logic_controller' non trovato sulla blackboard.")
            return Status.FAILURE
        
        esito = logic_controller.recharge_battery()

        match esito:
            case "SUCCESS":
                print(f"[RicaricaBatteria] Ricarica completata: {self.blackboard.battery_level}%.")
                return Status.SUCCESS
            case "RUNNING":
                print(f"[RicaricaBatteria] In ricarica... livello attuale: {self.blackboard.battery_level}%")
                return Status.RUNNING
            case "FAILURE":
                print("[RicaricaBatteria] Errore durante la ricarica.")
                return Status.FAILURE



class RicaricaBatteria(py_trees.behaviour.Behaviour):
    """
    Gestisce il processo di ricarica incrementando il livello della batteria
    fino al raggiungimento del 100%.
    """
    def __init__(self, step_ricarica=25.0):
        super(RicaricaBatteria, self).__init__(name="Ricarica Batteria")
        self.step_ricarica = step_ricarica # Quanta batteria recupera per ogni "tick"
        
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        # Legge E SCRIVE il livello della batteria per ricaricarla
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.WRITE)
    
    def setup(self):
        print("Setup RicaricaBatteria")
        return True

    def initialise(self):
        print(f"[{self.name}] Inizio ricarica della batteria...")

    def update(self):
        try:
            # Controlla il livello attuale
            if self.blackboard.battery_level < 100.0:
                # Incrementa la batteria
                self.blackboard.battery_level += self.step_ricarica
                
                # Assicuriamoci che non superi il 100%
                if self.blackboard.battery_level >= 100.0:
                    self.blackboard.battery_level = 100.0
                    print(f"[{self.name}] Ricarica completata: 100%.")
                    return Status.SUCCESS
                else:
                    print(f"[{self.name}] In ricarica... livello attuale: {self.blackboard.battery_level}%")
                    return Status.RUNNING
            else:
                return Status.SUCCESS
        except KeyError:
            print(f"[{self.name}] Errore: 'battery_level' non trovato.")
            return Status.FAILURE