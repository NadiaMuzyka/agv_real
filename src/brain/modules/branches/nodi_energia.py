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
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)
        #flag per indicare che siamo sotto il 20% e dobbiamo ricaricare,
        #questo serve per evitare di rientrare in questa condizione ad ogni tick del BT
        #verrà settato a True quando la batteria scende sotto il 20% e a False quando la ricarica è completa
        self.blackboard.register_key(key="is_charging", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ControlloBatteria")
        return True

    def initialise(self):
        pass

    def update(self):
        livello_batteria = self.blackboard.battery_level
        # Se la batteria è sotto il 20% attivo "Modalità Ricarica"
        if livello_batteria < 20:
            self.blackboard.logic_controller.set_energy_mode("CHARGE_MODE")
        if livello_batteria >= 100.0:
            self.blackboard.logic_controller.set_energy_mode("NORMAL_MODE")

        # Restituisco SUCCESS se siamo in modalità ricarica, altrimenti FAILURE
        if self.blackboard.is_charging:
            if livello_batteria < 20:
                print(f"[ControlloBatteria] Batteria critica: {livello_batteria}%. Attivo modalità ricarica.")
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



